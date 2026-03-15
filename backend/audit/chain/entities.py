"""Domain entities for the audit hash-chain subsystem.

Pure data structures with no framework dependencies.  These represent
the domain model — not the MongoDB documents or API DTOs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ChainStatus(str, Enum):
    """Verification result status."""

    VALID = "valid"
    BROKEN = "broken"
    GAP_DETECTED = "gap_detected"


class BrokenReason(str, Enum):
    """Reason a chain verification failed."""

    HASH_MISMATCH = "hash_mismatch"
    SEQUENCE_GAP = "sequence_gap"
    MISSING_ENTRY = "missing_entry"


@dataclass(frozen=True, slots=True)
class ChainedAuditEntry:
    """A single audit log entry with hash-chain fields.

    Attributes:
        sequence: Monotonically increasing, per-tenant, gapless counter.
        epoch: Epoch number this entry belongs to.
        timestamp: UTC datetime of the event.
        domain: Functional area (e.g. ``"sync"``, ``"auth"``).
        action: Specific event (e.g. ``"auth.login"``).
        actor: Who initiated the action.
        status: Outcome — ``"success"``, ``"failure"``, or ``"info"``.
        summary: Human-readable one-line description.
        details: Optional structured metadata.
        tenant_id: Tenant identifier (``None`` in on-prem mode).
        previous_hash: Hash of the preceding entry (``None`` for genesis).
        hash: SHA-256 hash of this entry.
        is_epoch_start: True if this is the first entry of a new epoch.
        is_epoch_end: True if this is the last entry of an epoch.
        previous_epoch_hash: Final hash of the preceding epoch (only
            set when ``is_epoch_start`` is True).
    """

    sequence: int
    epoch: int
    timestamp: datetime
    domain: str
    action: str
    actor: str
    status: str
    summary: str
    details: dict[str, Any]
    tenant_id: str | None
    previous_hash: str | None
    hash: str
    is_epoch_start: bool = False
    is_epoch_end: bool = False
    previous_epoch_hash: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Result of a chain verification run.

    Attributes:
        status: Overall verification status.
        verified_entries: Number of entries verified.
        first_sequence: Lowest sequence number verified.
        last_sequence: Highest sequence number verified.
        epochs_verified: Number of complete epochs verified.
        broken_at_sequence: Sequence number where the break was found.
        broken_reason: Why verification failed.
        verification_time_ms: Wall-clock time in milliseconds.
    """

    status: ChainStatus
    verified_entries: int
    first_sequence: int
    last_sequence: int
    epochs_verified: int
    broken_at_sequence: int | None = None
    broken_reason: BrokenReason | None = None
    verification_time_ms: int = 0


@dataclass(frozen=True, slots=True)
class ChainStatusInfo:
    """Current state of the audit hash-chain for a tenant.

    Attributes:
        total_entries: Total chained entries in the audit log.
        current_epoch: Current epoch number.
        current_sequence: Highest sequence number.
        genesis_hash: Hash of the genesis entry.
        latest_hash: Hash of the most recent entry.
        chain_valid: Result of the last verification (``None`` if never run).
        last_verified_at: Timestamp of the last verification run.
    """

    total_entries: int
    current_epoch: int
    current_sequence: int
    genesis_hash: str
    latest_hash: str
    chain_valid: bool | None = None
    last_verified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class EpochSummary:
    """Summary of a single completed epoch.

    Attributes:
        epoch: Epoch number.
        first_sequence: First sequence in the epoch.
        last_sequence: Last sequence in the epoch.
        entry_count: Number of entries in the epoch.
        first_timestamp: Timestamp of the first entry.
        last_timestamp: Timestamp of the last entry.
        epoch_final_hash: Hash of the last entry in the epoch.
        previous_epoch_hash: Hash linking to the previous epoch.
        exported: Whether this epoch has been exported.
    """

    epoch: int
    first_sequence: int
    last_sequence: int
    entry_count: int
    first_timestamp: datetime
    last_timestamp: datetime
    epoch_final_hash: str
    previous_epoch_hash: str | None
    exported: bool = False


@dataclass(frozen=True, slots=True)
class EpochExport:
    """A full epoch export ready for serialisation.

    Attributes:
        metadata: Export metadata dict.
        entries: Ordered list of audit entry dicts.
    """

    metadata: dict[str, Any]
    entries: list[dict[str, Any]]
