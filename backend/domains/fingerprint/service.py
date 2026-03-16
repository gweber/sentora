"""Fingerprint service — business logic for the fingerprint domain."""

from __future__ import annotations

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from domains.fingerprint import matcher, repository
from domains.fingerprint.dto import (
    FingerprintExportItem,
    FingerprintExportMarker,
    FingerprintImportResponse,
    FingerprintMarkerResponse,
    FingerprintResponse,
    FingerprintSuggestionResponse,
    MarkerCreateRequest,
    MarkerReorderRequest,
    MarkerUpdateRequest,
)
from domains.fingerprint.entities import Fingerprint, FingerprintMarker
from domains.fingerprint.entities import FingerprintSuggestion as FingerprintSuggestionEntity
from errors import (
    FingerprintAlreadyExistsError,
    FingerprintNotFoundError,
    MarkerNotFoundError,
    SuggestionNotFoundError,
)
from utils.dt import utc_now


def _marker_to_response(m: FingerprintMarker) -> FingerprintMarkerResponse:
    return FingerprintMarkerResponse(
        id=m.id,
        pattern=m.pattern,
        display_name=m.display_name,
        category=m.category,
        weight=m.weight,
        source=m.source,
        confidence=m.confidence,
        added_at=m.added_at.isoformat(),
        added_by=m.added_by,
    )


def _fingerprint_to_response(fp: Fingerprint) -> FingerprintResponse:
    return FingerprintResponse(
        id=fp.id,
        group_id=fp.group_id,
        group_name=fp.group_name,
        site_name=fp.site_name,
        account_name=fp.account_name,
        markers=[_marker_to_response(m) for m in fp.markers],
        created_at=fp.created_at.isoformat(),
        updated_at=fp.updated_at.isoformat(),
        created_by=fp.created_by,
    )


# ── Fingerprint operations ────────────────────────────────────────────────────


async def _resolve_group_meta(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> tuple[str, str, str]:
    """Return (group_name, site_name, account_name) from s1_groups + s1_sites."""
    group_doc = await db["s1_groups"].find_one(
        {"s1_group_id": group_id}, {"name": 1, "site_id": 1, "site_name": 1}
    )
    if not group_doc:
        return "", "", ""
    group_name = str(group_doc.get("name") or "")
    site_name = str(group_doc.get("site_name") or "")
    site_id = group_doc.get("site_id", "")
    account_name = ""
    if site_id:
        site_doc = await db["s1_sites"].find_one({"s1_site_id": site_id}, {"account_name": 1})
        if site_doc:
            account_name = str(site_doc.get("account_name") or "")
    return group_name, site_name, account_name


async def get_fingerprint(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> FingerprintResponse:
    fp = await repository.get_by_group_id(db, group_id)
    if fp is None:
        raise FingerprintNotFoundError(f"No fingerprint found for group '{group_id}'")
    # Backfill hierarchy names for fingerprints created before this fix
    if not fp.group_name:
        fp.group_name, fp.site_name, fp.account_name = await _resolve_group_meta(db, group_id)
        if fp.group_name:
            await db["fingerprints"].update_one(
                {"group_id": group_id},
                {
                    "$set": {
                        "group_name": fp.group_name,
                        "site_name": fp.site_name,
                        "account_name": fp.account_name,
                    }
                },
            )
    return _fingerprint_to_response(fp)


async def create_fingerprint(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> FingerprintResponse:
    existing = await repository.get_by_group_id(db, group_id)
    if existing is not None:
        raise FingerprintAlreadyExistsError(f"A fingerprint already exists for group '{group_id}'")

    group_name, site_name, account_name = await _resolve_group_meta(db, group_id)
    now = utc_now()
    fp = Fingerprint(
        group_id=group_id,
        group_name=group_name,
        site_name=site_name,
        account_name=account_name,
        markers=[],
        created_at=now,
        updated_at=now,
    )
    created = await repository.create(db, fp)
    await audit(
        db,
        domain="fingerprint",
        action="fingerprint.created",
        actor="user",
        summary=f"Fingerprint created for group {group_id}",
        details={"group_id": group_id},
    )
    return _fingerprint_to_response(created)


async def list_fingerprints(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    skip: int = 0,
    limit: int = 200,
) -> list[FingerprintResponse]:
    fingerprints = await repository.list_all(db, skip=skip, limit=limit)
    return [_fingerprint_to_response(fp) for fp in fingerprints]


async def add_marker(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    req: MarkerCreateRequest,
) -> FingerprintMarkerResponse:
    fp = await repository.get_by_group_id(db, group_id)
    if fp is None:
        raise FingerprintNotFoundError(f"No fingerprint found for group '{group_id}'")

    now = utc_now()
    marker = FingerprintMarker(
        pattern=req.pattern,
        display_name=req.display_name,
        category=req.category,
        weight=req.weight,
        source=req.source,
        confidence=1.0,
        added_at=now,
        added_by="user",
    )
    await repository.add_marker(db, group_id, marker)
    await audit(
        db,
        domain="fingerprint",
        action="fingerprint.marker.added",
        actor="user",
        summary=f"Marker '{req.pattern}' added to group {group_id}",
        details={"group_id": group_id, "pattern": req.pattern, "weight": req.weight},
    )
    return _marker_to_response(marker)


async def update_marker(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    marker_id: str,
    req: MarkerUpdateRequest,
) -> FingerprintMarkerResponse:
    fp = await repository.get_by_group_id(db, group_id)
    if fp is None:
        raise FingerprintNotFoundError(f"No fingerprint found for group '{group_id}'")

    existing_marker = next((m for m in fp.markers if m.id == marker_id), None)
    if existing_marker is None:
        raise MarkerNotFoundError(
            f"Marker '{marker_id}' not found in fingerprint for group '{group_id}'"
        )

    updates: dict[str, object] = {k: v for k, v in req.model_dump().items() if v is not None}

    if updates:
        modified = await repository.update_marker(db, group_id, marker_id, updates)
        if not modified:
            raise MarkerNotFoundError(
                f"Marker '{marker_id}' could not be updated in group '{group_id}'"
            )
        await audit(
            db,
            domain="fingerprint",
            action="fingerprint.marker.updated",
            actor="user",
            summary=f"Marker {marker_id} updated in group {group_id}",
            details={"group_id": group_id, "marker_id": marker_id, "updates": updates},
        )

    fp_updated = await repository.get_by_group_id(db, group_id)
    if fp_updated is None:
        raise FingerprintNotFoundError(f"No fingerprint found for group '{group_id}' after update")

    updated_marker = next((m for m in fp_updated.markers if m.id == marker_id), None)
    if updated_marker is None:
        raise MarkerNotFoundError(
            f"Marker '{marker_id}' not found after update in group '{group_id}'"
        )
    return _marker_to_response(updated_marker)


async def delete_marker(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    marker_id: str,
) -> None:
    fp = await repository.get_by_group_id(db, group_id)
    if fp is None:
        raise FingerprintNotFoundError(f"No fingerprint found for group '{group_id}'")

    marker_exists = any(m.id == marker_id for m in fp.markers)
    if not marker_exists:
        raise MarkerNotFoundError(
            f"Marker '{marker_id}' not found in fingerprint for group '{group_id}'"
        )

    await repository.remove_marker(db, group_id, marker_id)
    await audit(
        db,
        domain="fingerprint",
        action="fingerprint.marker.deleted",
        actor="user",
        summary=f"Marker {marker_id} deleted from group {group_id}",
        details={"group_id": group_id, "marker_id": marker_id},
    )


async def reorder_markers(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    req: MarkerReorderRequest,
) -> None:
    fp = await repository.get_by_group_id(db, group_id)
    if fp is None:
        raise FingerprintNotFoundError(f"No fingerprint found for group '{group_id}'")

    await repository.reorder_markers(db, group_id, req.marker_ids)


# ── Import / Export operations ─────────────────────────────────────────────────


async def export_all_fingerprints(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[FingerprintExportItem]:
    """Export all fingerprints as a portable list of export items.

    Args:
        db: Motor database (injected).

    Returns:
        List of FingerprintExportItem DTOs containing group_id and markers.
    """
    fingerprints = await repository.list_all(db, skip=0, limit=10000)
    items: list[FingerprintExportItem] = []
    for fp in fingerprints:
        markers = [
            FingerprintExportMarker(
                pattern=m.pattern,
                display_name=m.display_name,
                category=m.category,
                weight=m.weight,
                source=m.source,
                confidence=m.confidence,
            )
            for m in fp.markers
        ]
        items.append(FingerprintExportItem(group_id=fp.group_id, markers=markers))
    return items


async def import_fingerprints(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    items: list[FingerprintExportItem],
    strategy: str = "merge",
) -> FingerprintImportResponse:
    """Import fingerprints from a list of export items.

    Args:
        db: Motor database (injected).
        items: List of FingerprintExportItem DTOs to import.
        strategy: Import strategy — ``"merge"`` (default) adds new markers and
            updates weights for existing ones; ``"replace"`` replaces all markers.

    Returns:
        FingerprintImportResponse with imported/skipped counts and errors.
    """
    imported = 0
    skipped = 0
    errors: list[str] = []

    for item in items:
        # Verify that the group exists in the database
        group_doc = await db["s1_groups"].find_one({"s1_group_id": item.group_id}, {"_id": 1})
        if group_doc is None:
            logger.warning("Import skipped: group_id '{}' not found in database", item.group_id)
            skipped += 1
            continue

        try:
            fp = await repository.get_by_group_id(db, item.group_id)

            if fp is None:
                # Create a new fingerprint with the imported markers
                group_name, site_name, account_name = await _resolve_group_meta(db, item.group_id)
                now = utc_now()
                new_markers = [
                    FingerprintMarker(
                        pattern=m.pattern,
                        display_name=m.display_name,
                        category=m.category,
                        weight=m.weight,
                        source=m.source,
                        confidence=m.confidence,
                        added_at=now,
                        added_by="import",
                    )
                    for m in item.markers
                ]
                new_fp = Fingerprint(
                    group_id=item.group_id,
                    group_name=group_name,
                    site_name=site_name,
                    account_name=account_name,
                    markers=new_markers,
                    created_at=now,
                    updated_at=now,
                    created_by="import",
                )
                await repository.create(db, new_fp)
                imported += 1
                continue

            if strategy == "replace":
                # Replace all markers with the imported ones
                now = utc_now()
                new_markers = [
                    FingerprintMarker(
                        pattern=m.pattern,
                        display_name=m.display_name,
                        category=m.category,
                        weight=m.weight,
                        source=m.source,
                        confidence=m.confidence,
                        added_at=now,
                        added_by="import",
                    )
                    for m in item.markers
                ]
                marker_docs = [repository._marker_to_doc(m) for m in new_markers]
                await db[repository.COLLECTION].update_one(
                    {"group_id": item.group_id},
                    {"$set": {"markers": marker_docs, "updated_at": now}},
                )
                imported += 1
            else:
                # Merge strategy: add new markers, update weights for existing
                existing_patterns = {m.pattern: m for m in fp.markers}
                now = utc_now()
                changed = False

                for m in item.markers:
                    if m.pattern in existing_patterns:
                        # Update weight if the pattern already exists
                        existing = existing_patterns[m.pattern]
                        if existing.weight != m.weight:
                            await repository.update_marker(
                                db, item.group_id, existing.id, {"weight": m.weight}
                            )
                            changed = True
                    else:
                        # Add new marker
                        new_marker = FingerprintMarker(
                            pattern=m.pattern,
                            display_name=m.display_name,
                            category=m.category,
                            weight=m.weight,
                            source=m.source,
                            confidence=m.confidence,
                            added_at=now,
                            added_by="import",
                        )
                        await repository.add_marker(db, item.group_id, new_marker)
                        changed = True

                if changed:
                    await repository.update_updated_at(db, item.group_id)
                imported += 1

        except Exception as exc:
            error_msg = f"Error importing group_id '{item.group_id}': {exc}"
            logger.error(error_msg)
            errors.append(error_msg)

    await audit(
        db,
        domain="fingerprint",
        action="fingerprint.imported",
        actor="user",
        summary=f"Fingerprint import: {imported} imported, {skipped} skipped, {len(errors)} errors",
        details={"imported": imported, "skipped": skipped, "strategy": strategy, "errors": errors},
    )

    return FingerprintImportResponse(imported=imported, skipped=skipped, errors=errors)


# ── Suggestion operations ─────────────────────────────────────────────────────


async def get_suggestions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> list[FingerprintSuggestionResponse]:
    suggestions = await repository.get_suggestions(db, group_id)
    return [_suggestion_to_response(s) for s in suggestions]


async def compute_suggestions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> list[FingerprintSuggestionResponse]:
    new_suggestions = await matcher.compute_suggestions(db, group_id)
    await repository.save_suggestions(db, group_id, new_suggestions)
    return [_suggestion_to_response(s) for s in new_suggestions]


async def accept_suggestion(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    suggestion_id: str,
) -> None:
    fp = await repository.get_by_group_id(db, group_id)
    if fp is None:
        raise FingerprintNotFoundError(f"No fingerprint found for group '{group_id}'")

    suggestion = await repository.get_suggestion_by_id(db, group_id, suggestion_id)
    if suggestion is None:
        raise SuggestionNotFoundError(
            f"Suggestion '{suggestion_id}' not found for group '{group_id}'"
        )

    await repository.update_suggestion_status(db, group_id, suggestion_id, "accepted")

    now = utc_now()
    marker = FingerprintMarker(
        pattern=suggestion.normalized_name,
        display_name=suggestion.display_name,
        category="name_pattern",
        weight=1.0,
        source="statistical",
        confidence=min(1.0, suggestion.score / 20.0),  # score is lift; 20× → 100% confidence
        added_at=now,
        added_by="system",
    )
    await repository.add_marker(db, group_id, marker)
    await audit(
        db,
        domain="fingerprint",
        action="suggestion.accepted",
        actor="user",
        summary=f"Suggestion '{suggestion.display_name}' accepted for group {group_id}",
        details={
            "group_id": group_id,
            "suggestion_id": suggestion_id,
            "pattern": suggestion.normalized_name,
            "score": suggestion.score,
        },
    )


async def reject_suggestion(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    suggestion_id: str,
) -> None:
    suggestion = await repository.get_suggestion_by_id(db, group_id, suggestion_id)
    if suggestion is None:
        raise SuggestionNotFoundError(
            f"Suggestion '{suggestion_id}' not found for group '{group_id}'"
        )

    await repository.update_suggestion_status(db, group_id, suggestion_id, "rejected")
    await audit(
        db,
        domain="fingerprint",
        action="suggestion.rejected",
        actor="user",
        summary=f"Suggestion '{suggestion.display_name}' rejected for group {group_id}",
        details={"group_id": group_id, "suggestion_id": suggestion_id},
    )


# ── Private converters ────────────────────────────────────────────────────────


def _suggestion_to_response(
    s: FingerprintSuggestionEntity,
) -> FingerprintSuggestionResponse:
    return FingerprintSuggestionResponse(
        id=s.id,
        group_id=s.group_id,
        normalized_name=s.normalized_name,
        display_name=s.display_name,
        score=s.score,
        group_coverage=s.group_coverage,
        outside_coverage=s.outside_coverage,
        agent_count_in_group=s.agent_count_in_group,
        agent_count_outside=s.agent_count_outside,
        status=s.status,
        computed_at=s.computed_at.isoformat(),
    )
