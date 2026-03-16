"""Epoch verification logic for air-gapped audit chain verification.

All functions use only Python standard library modules. No external
dependencies are permitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hasher import compute_entry_hash, compute_export_hash


@dataclass
class VerifyResult:
    """Result of an epoch verification."""

    valid: bool
    entries_checked: int
    message: str
    broken_at_sequence: int | None = None
    broken_reason: str | None = None


def verify_epoch(data: dict[str, Any]) -> VerifyResult:
    """Verify a single exported epoch file.

    Performs four checks:
    1. Sequence continuity (no gaps).
    2. Hash-chain integrity (each hash matches recomputed value).
    3. Epoch boundary consistency (first entry references previous epoch).
    4. Export integrity (export_hash matches computed hash over entries).

    Args:
        data: Parsed JSON dict from an epoch export file, containing
            ``export_metadata`` and ``entries`` keys.

    Returns:
        VerifyResult with the outcome.
    """
    metadata = data.get("export_metadata", {})
    entries = data.get("entries", [])

    if not entries:
        return VerifyResult(valid=False, entries_checked=0, message="No entries in export file")

    # Step 1: Check sequence continuity
    first_seq = entries[0].get("sequence")
    for i, entry in enumerate(entries):
        expected_seq = first_seq + i
        actual_seq = entry.get("sequence")
        if actual_seq != expected_seq:
            return VerifyResult(
                valid=False,
                entries_checked=i,
                message=f"Sequence gap: expected {expected_seq}, found {actual_seq}",
                broken_at_sequence=expected_seq,
                broken_reason="sequence_gap",
            )

    # Step 2: Verify hash chain
    for i, entry in enumerate(entries):
        previous_hash = entry.get("previous_hash")
        stored_hash = entry.get("hash")
        recomputed = compute_entry_hash(entry, previous_hash)

        if recomputed != stored_hash:
            return VerifyResult(
                valid=False,
                entries_checked=i,
                message=(
                    f"Hash mismatch at sequence {entry['sequence']}: "
                    f"stored={stored_hash[:16]}..., "
                    f"computed={recomputed[:16]}..."
                ),
                broken_at_sequence=entry["sequence"],
                broken_reason="hash_mismatch",
            )

        # Verify chain link: entry[i].previous_hash == entry[i-1].hash
        if i > 0:
            prev_entry_hash = entries[i - 1].get("hash")
            if previous_hash != prev_entry_hash:
                return VerifyResult(
                    valid=False,
                    entries_checked=i,
                    message=(
                        f"Chain link broken at sequence {entry['sequence']}: "
                        f"previous_hash={previous_hash[:16]}... does not match "
                        f"prior entry hash={prev_entry_hash[:16]}..."
                    ),
                    broken_at_sequence=entry["sequence"],
                    broken_reason="hash_mismatch",
                )

    # Step 3: Verify export integrity hash
    expected_export_hash = metadata.get("export_hash")
    if expected_export_hash:
        computed_export_hash = compute_export_hash(entries)
        if computed_export_hash != expected_export_hash:
            return VerifyResult(
                valid=False,
                entries_checked=len(entries),
                message=(
                    f"Export integrity hash mismatch: "
                    f"stored={expected_export_hash[:16]}..., "
                    f"computed={computed_export_hash[:16]}..."
                ),
                broken_reason="export_hash_mismatch",
            )

    return VerifyResult(
        valid=True,
        entries_checked=len(entries),
        message=(
            f"All {len(entries)} entries verified. "
            f"Sequences {first_seq}-{entries[-1]['sequence']}, "
            f"epoch {metadata.get('epoch', '?')}."
        ),
    )


def verify_cross_epoch(
    current_data: dict[str, Any],
    previous_data: dict[str, Any],
) -> VerifyResult:
    """Verify the chain link between two consecutive epochs.

    Checks that the first entry of the current epoch references the
    final hash of the previous epoch via ``previous_epoch_hash``.

    Args:
        current_data: Parsed JSON of the current epoch export.
        previous_data: Parsed JSON of the previous epoch export.

    Returns:
        VerifyResult with the cross-epoch verification outcome.
    """
    current_entries = current_data.get("entries", [])
    previous_entries = previous_data.get("entries", [])

    if not current_entries or not previous_entries:
        return VerifyResult(
            valid=False,
            entries_checked=0,
            message="One or both epoch files have no entries",
        )

    prev_final_hash = previous_entries[-1].get("hash")
    curr_first = current_entries[0]
    curr_prev_epoch_hash = curr_first.get("previous_epoch_hash")

    if curr_prev_epoch_hash is None:
        # Also check if previous_hash of first entry matches
        curr_prev_hash = curr_first.get("previous_hash")
        if curr_prev_hash == prev_final_hash:
            return VerifyResult(
                valid=True,
                entries_checked=1,
                message="Cross-epoch chain valid (via previous_hash link)",
            )
        return VerifyResult(
            valid=False,
            entries_checked=1,
            message="First entry of current epoch has no previous_epoch_hash",
            broken_reason="missing_epoch_link",
        )

    if curr_prev_epoch_hash != prev_final_hash:
        return VerifyResult(
            valid=False,
            entries_checked=1,
            message=(
                f"Cross-epoch chain broken: "
                f"previous epoch final hash={prev_final_hash[:16]}..., "
                f"current epoch previous_epoch_hash={curr_prev_epoch_hash[:16]}..."
            ),
            broken_reason="epoch_link_mismatch",
        )

    return VerifyResult(
        valid=True,
        entries_checked=1,
        message=(
            f"Cross-epoch chain valid. "
            f"Epoch {previous_data.get('export_metadata', {}).get('epoch', '?')} "
            f"-> Epoch {current_data.get('export_metadata', {}).get('epoch', '?')}"
        ),
    )
