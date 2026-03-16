"""Unit tests for source runner checkpoint security (AUDIT-013).

Verifies that sensitive configuration keys (api_key, secret, etc.) are
stripped from checkpoint documents before persisting to MongoDB.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from domains.library.source_runner import SourceRunner


@pytest.fixture
def runner() -> SourceRunner:
    """Create a SourceRunner with a mocked adapter and broadcast."""
    adapter = MagicMock()
    adapter.get_resume_state.return_value = {"page": 5}
    return SourceRunner("nist_cpe", adapter, broadcast=None)


class TestCheckpointSensitiveKeys:
    """_save_progress_checkpoint must strip sensitive keys from config."""

    @pytest.mark.asyncio
    async def test_api_key_stripped_from_checkpoint(self, runner: SourceRunner) -> None:
        """api_key must not appear in the persisted checkpoint config."""
        saved_data: dict = {}

        async def capture_checkpoint(data: dict) -> None:
            saved_data.update(data)

        runner.save_checkpoint = capture_checkpoint  # type: ignore[assignment]
        runner._run_id = "run-1"

        run = MagicMock()
        run.id = "ingestion-run-1"
        run.entries_created = 10
        run.entries_updated = 5
        run.entries_skipped = 0
        run.errors = []

        config = {"api_key": "nvd-secret-key-123", "batch_size": 100}
        await runner._save_progress_checkpoint(run, 50, config, "running")

        assert "api_key" not in saved_data["config"]
        assert saved_data["config"]["batch_size"] == 100

    @pytest.mark.asyncio
    async def test_multiple_sensitive_keys_stripped(self, runner: SourceRunner) -> None:
        """All sensitive keys (api_key, secret, token, password) are stripped."""
        saved_data: dict = {}

        async def capture_checkpoint(data: dict) -> None:
            saved_data.update(data)

        runner.save_checkpoint = capture_checkpoint  # type: ignore[assignment]
        runner._run_id = "run-2"

        run = MagicMock()
        run.id = "ingestion-run-2"
        run.entries_created = 0
        run.entries_updated = 0
        run.entries_skipped = 0
        run.errors = []

        config = {
            "api_key": "secret",
            "secret": "also-secret",
            "token": "bearer-xxx",
            "password": "p@ss",
            "batch_size": 50,
            "source_url": "https://example.com",
        }
        await runner._save_progress_checkpoint(run, 10, config, "running")

        checkpoint_config = saved_data["config"]
        assert "api_key" not in checkpoint_config
        assert "secret" not in checkpoint_config
        assert "token" not in checkpoint_config
        assert "password" not in checkpoint_config
        assert checkpoint_config["batch_size"] == 50
        assert checkpoint_config["source_url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_non_sensitive_config_preserved(self, runner: SourceRunner) -> None:
        """Non-sensitive config keys are preserved in the checkpoint."""
        saved_data: dict = {}

        async def capture_checkpoint(data: dict) -> None:
            saved_data.update(data)

        runner.save_checkpoint = capture_checkpoint  # type: ignore[assignment]
        runner._run_id = "run-3"

        run = MagicMock()
        run.id = "ingestion-run-3"
        run.entries_created = 0
        run.entries_updated = 0
        run.entries_skipped = 0
        run.errors = []

        config = {"batch_size": 200, "timeout": 30}
        await runner._save_progress_checkpoint(run, 0, config, "running")

        assert saved_data["config"] == {"batch_size": 200, "timeout": 30}
