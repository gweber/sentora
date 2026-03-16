"""Integration tests for webhook event dispatch across all domains.

Verifies that compliance, enforcement, and audit chain modules fire
the correct webhook events with consistent payload schemas.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.webhooks.entities import VALID_EVENTS


class TestValidEventsRegistry:
    """Tests for the VALID_EVENTS registry."""

    def test_all_expected_events_registered(self) -> None:
        """All event types are present in the registry."""
        expected = {
            "sync.completed",
            "sync.failed",
            "classification.completed",
            "classification.anomaly_detected",
            "enforcement.check.completed",
            "enforcement.violation.new",
            "enforcement.violation.resolved",
            "compliance.check.completed",
            "compliance.violation.new",
            "compliance.violation.resolved",
            "compliance.score.degraded",
            "audit.chain.integrity_failure",
        }
        assert expected == VALID_EVENTS

    def test_frontend_events_subset_of_backend(self) -> None:
        """Frontend WEBHOOK_EVENTS is a subset of backend VALID_EVENTS.

        Reads the frontend constant via JSON-like parsing to ensure
        the two lists stay in sync.
        """
        from pathlib import Path

        frontend_types = (
            Path(__file__).parent.parent.parent.parent
            / "frontend"
            / "src"
            / "types"
            / "webhooks.ts"
        )
        if not frontend_types.exists():
            pytest.skip("Frontend types file not found")

        content = frontend_types.read_text()
        # Extract event strings from the TypeScript constant
        import re

        events = re.findall(r"'([a-z._]+)'", content)
        frontend_events = set(events)
        assert frontend_events.issubset(VALID_EVENTS), (
            f"Frontend has events not in backend: {frontend_events - VALID_EVENTS}"
        )
        assert frontend_events == VALID_EVENTS, (
            f"Frontend is missing events: {VALID_EVENTS - frontend_events}"
        )


class TestEnforcementWebhookEvents:
    """Tests for enforcement domain webhook dispatch."""

    @pytest.mark.asyncio
    async def test_check_completed_fires_webhook(self, test_db: AsyncIOMotorDatabase) -> None:
        """enforcement.check.completed webhook fires after check run."""
        with patch(
            "domains.webhooks.service.dispatch_event",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            from domains.enforcement.service import trigger_check

            await trigger_check(test_db, actor="testadmin")

            # Find the check.completed call
            completed_calls = [
                c for c in mock_dispatch.call_args_list if c[0][1] == "enforcement.check.completed"
            ]
            assert len(completed_calls) == 1

            payload = completed_calls[0][0][2]
            assert "run_id" in payload
            assert "rules_checked" in payload
            assert "rules_passed" in payload
            assert "rules_failed" in payload
            assert "total_violations" in payload
            assert payload["source"] == "enforcement"

    @pytest.mark.asyncio
    async def test_violation_payloads_include_source(self, test_db: AsyncIOMotorDatabase) -> None:
        """Enforcement violation webhook payloads include source field."""
        # This test validates the payload schema structure
        from domains.enforcement.service import _dispatch_violation_webhook

        with patch(
            "domains.webhooks.service.dispatch_event",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            # Create minimal mock results
            from dataclasses import dataclass, field

            @dataclass
            class MockViolation:
                agent_id: str = "a1"
                agent_hostname: str = "host1"

            @dataclass
            class MockResult:
                rule_id: str = "rule1"
                rule_name: str = "Test Rule"
                severity: str = "high"
                violations: list = field(default_factory=lambda: [MockViolation()])

            await _dispatch_violation_webhook(
                test_db,
                [MockResult()],  # type: ignore[list-item]
                {"rule1:a1"},
                "new",
            )

            assert mock_dispatch.called
            payload = mock_dispatch.call_args[0][2]
            assert payload["source"] == "enforcement"
            assert payload["rule_name"] == "Test Rule"
            assert payload["severity"] == "high"


class TestComplianceWebhookEvents:
    """Tests for compliance domain webhook dispatch."""

    @pytest.mark.asyncio
    async def test_check_completed_fires_webhook(self, test_db: AsyncIOMotorDatabase) -> None:
        """compliance.check.completed webhook fires after check run."""
        with patch(
            "domains.webhooks.service.dispatch_event",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            from domains.compliance.commands import trigger_compliance_run

            await trigger_compliance_run(test_db, actor="testadmin")

            completed_calls = [
                c for c in mock_dispatch.call_args_list if c[0][1] == "compliance.check.completed"
            ]
            assert len(completed_calls) == 1

            payload = completed_calls[0][0][2]
            assert "controls_evaluated" in payload
            assert "controls_passed" in payload
            assert "controls_failed" in payload
            assert "controls_warning" in payload
            assert "new_violations" in payload
            assert "resolved_violations" in payload
            assert payload["source"] == "compliance"

    @pytest.mark.asyncio
    async def test_webhook_dispatch_does_not_block_run(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Webhook failures do not block compliance run completion."""
        with patch(
            "domains.webhooks.service.dispatch_event",
            side_effect=Exception("webhook delivery failed"),
        ):
            from domains.compliance.commands import trigger_compliance_run

            # Should complete without raising
            run_id, results, duration_ms = await trigger_compliance_run(test_db, actor="testadmin")
            assert run_id is not None


class TestAuditChainWebhookEvents:
    """Tests for audit chain integrity failure webhook."""

    @pytest.mark.asyncio
    async def test_integrity_failure_fires_webhook(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """audit.chain.integrity_failure fires on chain break detection."""
        from audit.chain.commands import append_chained_entry, initialize_chain

        await initialize_chain(test_db)
        for i in range(3):
            await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )

        # Tamper with an entry
        await test_db["audit_log"].update_one(
            {"sequence": 2},
            {"$set": {"summary": "TAMPERED"}},
        )

        with patch(
            "domains.webhooks.service.dispatch_event",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            from audit.chain.queries import verify_chain

            result = await verify_chain(test_db)
            assert result.status.value == "broken"

            integrity_calls = [
                c
                for c in mock_dispatch.call_args_list
                if c[0][1] == "audit.chain.integrity_failure"
            ]
            assert len(integrity_calls) == 1

            payload = integrity_calls[0][0][2]
            assert payload["broken_at_sequence"] == 2
            assert payload["reason"] == "hash_mismatch"
            assert payload["source"] == "audit"

    @pytest.mark.asyncio
    async def test_valid_chain_does_not_fire_webhook(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Valid chain verification does not fire integrity_failure webhook."""
        from audit.chain.commands import append_chained_entry, initialize_chain

        await initialize_chain(test_db)
        for i in range(3):
            await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )

        with patch(
            "domains.webhooks.service.dispatch_event",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            from audit.chain.queries import verify_chain

            result = await verify_chain(test_db)
            assert result.status.value == "valid"

            integrity_calls = [
                c
                for c in mock_dispatch.call_args_list
                if c[0][1] == "audit.chain.integrity_failure"
            ]
            assert len(integrity_calls) == 0


class TestPayloadConsistency:
    """Tests that all webhook payloads follow the consistent schema."""

    def test_all_events_follow_naming_convention(self) -> None:
        """All event names follow domain.action.detail pattern."""
        for event in VALID_EVENTS:
            parts = event.split(".")
            assert len(parts) >= 2, f"Event '{event}' must have at least 2 dot-separated parts"
            assert all(p.islower() or p.replace("_", "").islower() for p in parts), (
                f"Event '{event}' must use lowercase with dots"
            )
