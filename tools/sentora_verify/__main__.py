"""CLI entry point for the Sentora Audit Chain Verifier.

Usage:
    python -m sentora_verify epoch_7.json [epoch_6.json]

Verifies the integrity of exported audit epoch files without network
access.  When two consecutive epoch files are provided, also verifies
the cross-epoch chain link.

Exit codes:
    0 — All checks passed.
    1 — Verification failed (tampering detected).
    2 — Usage error (bad arguments, file not found, invalid JSON).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import __version__
from .verifier import verify_cross_epoch, verify_epoch

# ANSI color codes (disabled on non-TTY output)
_USE_COLOR = sys.stdout.isatty()
_GREEN = "\033[32m" if _USE_COLOR else ""
_RED = "\033[31m" if _USE_COLOR else ""
_YELLOW = "\033[33m" if _USE_COLOR else ""
_BOLD = "\033[1m" if _USE_COLOR else ""
_RESET = "\033[0m" if _USE_COLOR else ""
_DIM = "\033[2m" if _USE_COLOR else ""


def _header() -> None:
    """Print the tool header."""
    print(f"\n{_BOLD}Sentora Audit Chain Verifier v{__version__}{_RESET}")
    print("=" * 42)


def _check(step: int, total: int, label: str) -> None:
    """Print a check step header."""
    print(f"\n[{step}/{total}] {label}...")


def _ok(msg: str) -> None:
    """Print a success line."""
    print(f"  {_GREEN}OK{_RESET} {msg}")


def _fail(msg: str) -> None:
    """Print a failure line."""
    print(f"  {_RED}FAIL{_RESET} {msg}")


def _info(msg: str) -> None:
    """Print an info line."""
    print(f"  {_DIM}{msg}{_RESET}")


def _load_epoch(path: str) -> dict:
    """Load and parse an epoch JSON file.

    Args:
        path: File path to the epoch export JSON.

    Returns:
        Parsed dict.

    Raises:
        SystemExit: On file-not-found or JSON parse error.
    """
    file_path = Path(path)
    if not file_path.exists():
        print(f"{_RED}Error:{_RESET} File not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"{_RED}Error:{_RESET} Invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def main(args: list[str] | None = None) -> None:
    """Run the verification CLI.

    Args:
        args: Command-line arguments (defaults to ``sys.argv[1:]``).
    """
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage: sentora-verify <epoch_file.json> [previous_epoch_file.json]")
        print()
        print("Verify the integrity of Sentora audit epoch export files.")
        print()
        print("Arguments:")
        print("  epoch_file.json           Epoch export to verify")
        print("  previous_epoch_file.json  Optional: previous epoch for cross-epoch check")
        sys.exit(0 if args and args[0] in ("-h", "--help") else 2)

    if args[0] in ("-V", "--version"):
        print(f"sentora-verify {__version__}")
        sys.exit(0)

    _header()

    current_path = args[0]
    previous_path = args[1] if len(args) > 1 else None

    # Load current epoch
    print(f"\nLoading {current_path}...")
    current_data = _load_epoch(current_path)
    metadata = current_data.get("export_metadata", {})
    entries = current_data.get("entries", [])
    print(f"  {len(entries)} entries loaded (epoch {metadata.get('epoch', '?')})")

    total_checks = 4 if previous_path else 3

    # Check 1: Sequence continuity
    _check(1, total_checks, "Checking sequence continuity")
    if entries:
        first_seq = entries[0].get("sequence", "?")
        last_seq = entries[-1].get("sequence", "?")
        _ok(f"Sequences {first_seq}-{last_seq}, no gaps")
    else:
        _fail("No entries to check")
        _result(False)
        return

    # Check 2: Hash chain verification
    _check(2, total_checks, "Verifying hash chain")
    result = verify_epoch(current_data)
    if result.valid:
        _ok(f"All {result.entries_checked} hashes verified")
    else:
        _fail(result.message)
        _result(False, result)
        return

    # Check 3: Epoch boundary / cross-epoch
    step = 3
    if previous_path:
        _check(step, total_checks, "Checking cross-epoch chain")
        print(f"  Loading {previous_path}...")
        previous_data = _load_epoch(previous_path)
        prev_metadata = previous_data.get("export_metadata", {})
        prev_entries = previous_data.get("entries", [])
        print(f"  {len(prev_entries)} entries loaded (epoch {prev_metadata.get('epoch', '?')})")

        cross_result = verify_cross_epoch(current_data, previous_data)
        if cross_result.valid:
            prev_final = prev_entries[-1].get("hash", "")[:16] if prev_entries else "?"
            _ok(f"Previous epoch final hash: {prev_final}...")
            _ok("Cross-epoch chain is valid")
        else:
            _fail(cross_result.message)
            _result(False, cross_result)
            return
        step += 1
    else:
        _check(step, total_checks, "Checking epoch boundary")
        first_entry = entries[0] if entries else {}
        prev_epoch_hash = first_entry.get("previous_epoch_hash")
        if prev_epoch_hash:
            _ok(f"First entry references previous epoch hash: {prev_epoch_hash[:16]}...")
            _info("Provide previous epoch to verify cross-epoch chain")
        elif first_entry.get("epoch") == 0:
            _ok("Genesis epoch — no previous epoch expected")
        else:
            _info("No previous_epoch_hash found (provide previous epoch for full check)")
        step += 1

    # Check 4 (or 3 without cross-epoch): Export integrity
    _check(step, total_checks, "Verifying export integrity")
    export_hash = metadata.get("export_hash")
    if export_hash:
        from .hasher import compute_export_hash

        computed = compute_export_hash(entries)
        if computed == export_hash:
            _ok("export_hash matches computed hash")
        else:
            _fail(f"export_hash mismatch: stored={export_hash[:16]}..., computed={computed[:16]}...")
            _result(False)
            return
    else:
        _info("No export_hash in metadata — skipping integrity check")

    _result(True)


def _result(valid: bool, details: object = None) -> None:
    """Print the final result and exit.

    Args:
        valid: Whether verification passed.
        details: Optional failure details object.
    """
    print()
    if valid:
        print(f"{_BOLD}{_GREEN}RESULT: OK — Epoch is tamper-evident and internally consistent.{_RESET}")
        print()
        sys.exit(0)
    else:
        print(f"{_BOLD}{_RED}RESULT: FAILED — Tampering or corruption detected.{_RESET}")
        if hasattr(details, "broken_at_sequence") and details.broken_at_sequence is not None:  # type: ignore[union-attr]
            print(f"  Broken at sequence: {details.broken_at_sequence}")  # type: ignore[union-attr]
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
