"""Request/response DTOs for the audit chain API.

Pydantic models used exclusively at the API boundary. Domain logic
operates on entities from ``entities.py``, not these DTOs.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ── Request DTOs ────────────────────────────────────────────────────────────


class VerifyChainRequest(BaseModel):
    """Request body for POST /audit/chain/verify."""

    epoch: int | None = Field(
        default=None,
        description="Epoch number to verify.  ``null`` verifies the entire chain.",
    )


# ── Response DTOs ───────────────────────────────────────────────────────────


class VerifyChainResponse(BaseModel):
    """Response from POST /audit/chain/verify."""

    status: str = Field(description="'valid', 'broken', or 'gap_detected'")
    verified_entries: int
    first_sequence: int
    last_sequence: int
    epochs_verified: int
    broken_at_sequence: int | None = None
    broken_reason: str | None = None
    verification_time_ms: int = 0


class ChainStatusResponse(BaseModel):
    """Response from GET /audit/chain/status."""

    total_entries: int
    current_epoch: int
    current_sequence: int
    genesis_hash: str
    latest_hash: str
    chain_valid: bool | None = None
    last_verified_at: datetime | None = None


class EpochSummaryResponse(BaseModel):
    """Single epoch in the epoch list response."""

    epoch: int
    first_sequence: int
    last_sequence: int
    entry_count: int
    first_timestamp: datetime
    last_timestamp: datetime
    epoch_final_hash: str
    previous_epoch_hash: str | None = None
    exported: bool = False


class EpochListResponse(BaseModel):
    """Response from GET /audit/chain/epochs."""

    epochs: list[EpochSummaryResponse]
    total: int
