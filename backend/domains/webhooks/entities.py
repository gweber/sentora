"""Webhooks domain entities.

Webhook registrations define HTTP callback endpoints that receive POST
notifications when specific application events occur (e.g. sync completion,
classification anomalies). Payloads are signed with HMAC-SHA256 so receivers
can verify authenticity.

MongoDB storage notes
---------------------
- Webhooks are stored in the ``webhooks`` collection, one document per webhook.
- ``name`` is informational; ``url`` + ``events`` define the delivery target.
- ``secret`` is used for HMAC-SHA256 payload signing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Supported event names that webhooks can subscribe to.
VALID_EVENTS: set[str] = {
    # Sync
    "sync.completed",
    "sync.failed",
    # Classification
    "classification.completed",
    "classification.anomaly_detected",
    # Enforcement
    "enforcement.check.completed",
    "enforcement.violation.new",
    "enforcement.violation.resolved",
    # Compliance
    "compliance.check.completed",
    "compliance.violation.new",
    "compliance.violation.resolved",
    "compliance.score.degraded",
    # Audit chain
    "audit.chain.integrity_failure",
}


@dataclass
class Webhook:
    """A registered webhook endpoint.

    Attributes:
        id: Unique identifier (string ObjectId).
        name: Human-readable label.
        url: Target URL that receives POST requests.
        events: List of event names this webhook subscribes to.
        secret: HMAC-SHA256 signing secret for payload verification.
        enabled: Whether the webhook is active.
        created_at: ISO-8601 creation timestamp.
        last_triggered_at: ISO-8601 timestamp of last successful delivery.
        failure_count: Consecutive delivery failures; webhook is auto-disabled
            after 10 consecutive failures.
    """

    id: str = ""
    name: str = ""
    url: str = ""
    events: list[str] = field(default_factory=list)
    secret: str = ""
    enabled: bool = True
    created_at: str = ""
    last_triggered_at: str | None = None
    failure_count: int = 0
    last_error: str | None = None
