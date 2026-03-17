"""EOL product matching engine.

Two-layer matching strategy:
1. CPE-based matching (high confidence) — static mapping table
2. Name-based fuzzy matching (lower confidence, opt-in)

Fuzzy matches are NEVER auto-included in compliance results.  They must
be confirmed by the MSP before being treated as reliable.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.eol.entities import EOLCycle, EOLMatch
from domains.sources.collections import INSTALLED_APPS

# ---------------------------------------------------------------------------
# Layer 1: Static CPE vendor:product → endoflife.date product slug mapping
# ---------------------------------------------------------------------------

CPE_TO_EOL_MAP: dict[str, str] = {
    # Browsers
    "google:chrome": "chrome",
    "mozilla:firefox": "firefox",
    "mozilla:firefox_esr": "firefox",
    "microsoft:edge": "microsoft-edge",
    "apple:safari": "safari",
    "opera:opera_browser": "opera",
    # Operating Systems
    "microsoft:windows_10": "windows",
    "microsoft:windows_11": "windows",
    "microsoft:windows_server_2016": "windows-server",
    "microsoft:windows_server_2019": "windows-server",
    "microsoft:windows_server_2022": "windows-server",
    "apple:macos": "macos",
    "canonical:ubuntu_linux": "ubuntu",
    "redhat:enterprise_linux": "rhel",
    "centos:centos": "centos",
    "debian:debian_linux": "debian",
    "fedoraproject:fedora": "fedora",
    "suse:linux_enterprise_server": "sles",
    # Office & Productivity
    "microsoft:office": "office",
    "microsoft:365_apps": "office",
    "microsoft:outlook": "office",
    "microsoft:word": "office",
    "microsoft:excel": "office",
    "microsoft:powerpoint": "office",
    "libreoffice:libreoffice": "libreoffice",
    # Runtimes & Languages
    "python_software_foundation:python": "python",
    "oracle:java_se": "oracle-jdk",
    "oracle:jre": "oracle-jdk",
    "oracle:openjdk": "openjdk",
    "nodejs:node.js": "nodejs",
    "php:php": "php",
    "ruby-lang:ruby": "ruby",
    "golang:go": "go",
    "rust-lang:rust": "rust",
    "microsoft:.net": "dotnet",
    "microsoft:.net_framework": "dotnetfx",
    "microsoft:.net_core": "dotnet",
    # Databases
    "mysql:mysql": "mysql",
    "postgresql:postgresql": "postgresql",
    "mongodb:mongodb": "mongodb",
    "microsoft:sql_server": "mssqlserver",
    "oracle:database_server": "oracle-database",
    "mariadb:mariadb": "mariadb",
    "redis:redis": "redis",
    # Adobe
    "adobe:acrobat_reader": "adobe-acrobat",
    "adobe:acrobat": "adobe-acrobat",
    "adobe:acrobat_reader_dc": "adobe-acrobat",
    "adobe:creative_cloud": "adobe-creative-cloud",
    "adobe:photoshop": "photoshop",
    # Virtualization & Containers
    "docker:docker": "docker-engine",
    "vmware:esxi": "esxi",
    "vmware:vcenter_server": "vcenter",
    "hashicorp:terraform": "terraform",
    "kubernetes:kubernetes": "kubernetes",
    # Networking & Security
    "cisco:ios": "cisco-ios",
    "fortinet:fortios": "fortios",
    "paloaltonetworks:pan-os": "pan-os",
    "openssh:openssh": "openssh",
    "openssl:openssl": "openssl",
    # Development Tools
    "microsoft:visual_studio_code": "visual-studio-code",
    "microsoft:visual_studio": "visual-studio",
    "jetbrains:intellij_idea": "intellij-idea",
    "git:git": "git",
    # Communication
    "zoom:zoom": "zoom",
    "microsoft:teams": "microsoft-teams",
    "slack:slack": "slack",
    # Other common software
    "7-zip:7-zip": "7-zip",
    "videolan:vlc_media_player": "vlc",
    "wireshark:wireshark": "wireshark",
    "filezilla:filezilla_client": "filezilla",
    "notepad-plus-plus:notepad\\+\\+": "notepad-plus-plus",
    "apple:iphone_os": "ios",
    "google:android": "android",
    "elastic:elasticsearch": "elasticsearch",
    "elastic:kibana": "kibana",
    "grafana:grafana": "grafana",
    "apache:http_server": "apache",
    "nginx:nginx": "nginx",
    "torvalds:linux_kernel": "linux",
}


def cpe_to_eol_product(cpe_vendor: str, cpe_product: str) -> str | None:
    """Look up the endoflife.date product slug from CPE vendor:product.

    Args:
        cpe_vendor: CPE vendor string (e.g. ``google``).
        cpe_product: CPE product string (e.g. ``chrome``).

    Returns:
        The endoflife.date product slug, or ``None`` if no mapping exists.
    """
    key = f"{cpe_vendor.lower()}:{cpe_product.lower()}"
    return CPE_TO_EOL_MAP.get(key)


# ---------------------------------------------------------------------------
# Version extraction — maps app version strings to EOL cycle identifiers
# ---------------------------------------------------------------------------

# Regex for extracting version components
_VERSION_RE = re.compile(r"(\d+(?:\.\d+)*)")


def extract_cycle_match(
    version_string: str,
    cycles: list[EOLCycle],
) -> EOLCycle | None:
    """Match an app version string to the best EOL release cycle.

    Strategy:
    1. Extract numeric version components from the version string
    2. Try matching against each cycle identifier (longest prefix match)
    3. Return the best matching cycle or ``None``

    Args:
        version_string: The application's version string (e.g. ``3.8.19``).
        cycles: Available release cycles for the product.

    Returns:
        The best matching ``EOLCycle``, or ``None`` if no match.
    """
    if not version_string or not cycles:
        return None

    m = _VERSION_RE.search(version_string)
    if not m:
        return None

    version_parts = m.group(1)

    # Build a map of cycle identifiers for quick lookup
    cycle_map: dict[str, EOLCycle] = {c.cycle: c for c in cycles}

    # Try progressively shorter prefixes of the version string
    # e.g. for "3.8.19" try "3.8.19", "3.8", "3"
    parts = version_parts.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in cycle_map:
            return cycle_map[prefix]

    # Some products use year-based cycles (e.g. "2021")
    # Try matching just the first component against 4-digit year patterns
    if len(parts) >= 1 and len(parts[0]) == 4 and parts[0] in cycle_map:
        return cycle_map[parts[0]]

    return None


# ---------------------------------------------------------------------------
# Fuzzy matching — name-based fallback
# ---------------------------------------------------------------------------

# Common noise words to strip from app names for fuzzy matching
_NOISE_WORDS = frozenset(
    {
        "the",
        "for",
        "and",
        "with",
        "pro",
        "professional",
        "enterprise",
        "standard",
        "edition",
        "version",
        "update",
        "x64",
        "x86",
        "64-bit",
        "32-bit",
        "amd64",
        "arm64",
        "portable",
        "installer",
        "setup",
        # Vendor names too common to be discriminative in fuzzy matching
        "microsoft",
        "google",
        "apple",
        "adobe",
        "oracle",
        "ibm",
        "dell",
        "hp",
        "intel",
        "nvidia",
        "vmware",
        "cisco",
        "red",
        "hat",
    }
)


def _normalize_for_fuzzy(name: str) -> str:
    """Normalize an app name for fuzzy matching.

    Strips version numbers, noise words, and normalizes whitespace.

    Args:
        name: Raw application name.

    Returns:
        Normalized name string suitable for fuzzy comparison.
    """
    # Remove version-like patterns
    cleaned = re.sub(r"\d+(\.\d+)+", "", name)
    # Remove parenthetical content
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    # Lowercase and split into tokens
    tokens = cleaned.lower().split()
    # Filter noise words and short tokens
    tokens = [t for t in tokens if t not in _NOISE_WORDS and len(t) > 1]
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Layer 0: Direct name → EOL product mapping (highest confidence)
# ---------------------------------------------------------------------------

# Maps (normalized_app_name_prefix, publisher_hint) → eol_product_id.
# These are curated from real-world Sentora fleet data.  The normalized
# name is lowercase, version-stripped.  Publisher is optional — used to
# disambiguate when the name alone is ambiguous.
NAME_TO_EOL_MAP: dict[str, str] = {
    # Only non-obvious mappings where the app name doesn't start with the
    # endoflife.date product slug.  Identity mappings (e.g. "redis" → "redis")
    # are auto-derived by _direct_name_match from the EOL product list.
    #
    # Browsers (vendor-prefixed names)
    "google chrome": "chrome",
    "microsoft edge": "microsoft-edge",
    "mozilla firefox": "firefox",
    "mozilla firefox esr": "firefox",
    # Runtimes (alternate names)
    "python launcher": "python",
    "node.js": "nodejs",
    "go programming language": "go",
    # Microsoft products (brand ≠ slug)
    "microsoft 365": "office",
    "microsoft office": "office",
    "microsoft visual studio code": "visual-studio-code",
    "microsoft visual studio": "visual-studio",
    "microsoft .net": "dotnet",
    "microsoft .net framework": "dotnetfx",
    "microsoft .net runtime": "dotnet",
    "microsoft asp.net": "dotnet",
    "microsoft windows desktop runtime": "dotnet",
    "microsoft teams": "microsoft-teams",
    "microsoft sql server": "mssqlserver",
    # Adobe (vendor-prefixed)
    "adobe acrobat": "adobe-acrobat",
    "adobe acrobat reader": "adobe-acrobat",
    "adobe creative cloud": "adobe-creative-cloud",
    # Java (multiple distributions)
    "java": "oracle-jdk",
    "oracle java": "oracle-jdk",
    "amazon corretto": "amazon-corretto",
    "eclipse temurin": "eclipse-temurin",
    # Non-obvious slugs
    "docker": "docker-engine",
    "ansible": "ansible-core",
    "vlc media player": "vlc",
    "notepad++": "notepad-plus-plus",
    "vmware tools": "vmware-tools",
    "vmware workstation": "vmware-workstation",
}


def _direct_name_match(
    normalized_name: str,
    eol_products: dict[str, Any],
    user_mappings: dict[str, str] | None = None,
) -> str | None:
    """Match a normalized app name against curated + user mappings.

    User mappings take priority over the built-in ``NAME_TO_EOL_MAP``.
    Tries exact match first, then prefix match (for versioned names like
    ``"python 3.12.3"`` matching the ``"python"`` key).

    Args:
        normalized_name: Lowercase normalized app name.
        eol_products: Available EOL products (for existence check).
        user_mappings: User-configured overrides from the database.

    Returns:
        The EOL product ID, or ``None``.
    """
    # Merge: user mappings override built-in
    merged = dict(NAME_TO_EOL_MAP)
    if user_mappings:
        merged.update(user_mappings)

    # Exact match
    if normalized_name in merged:
        pid = merged[normalized_name]
        if pid in eol_products:
            return pid

    # Prefix match via explicit mappings — try longest prefix first
    # e.g. "microsoft 365 apps for enterprise - en-us" starts with "microsoft 365"
    best: str | None = None
    best_len = 0
    for key, pid in merged.items():
        if len(key) > best_len and normalized_name.startswith(key) and pid in eol_products:
            best = pid
            best_len = len(key)

    if best:
        return best

    # Auto-derive: if the app name starts with an EOL product slug, use it
    # directly.  Covers identity cases ("apache" → "apache", "redis" → "redis")
    # without needing explicit mapping entries.  Only slugs ≥ 4 chars to
    # avoid false positives from short slugs like "go", "qt", "r".
    for slug in eol_products:
        if (
            len(slug) >= 4
            and len(slug) > best_len
            and (
                normalized_name == slug
                or normalized_name.startswith(slug + " ")
                or normalized_name.startswith(slug + "-")
            )
        ):
            best = slug
            best_len = len(slug)

    return best


def fuzzy_match_product(
    app_name: str,
    eol_products: dict[str, str],
) -> tuple[str, float] | None:
    """Attempt to fuzzy-match an app name to an endoflife.date product.

    Uses normalized token overlap scoring.  Results below 0.4 confidence
    are discarded.  Short product slugs (<=3 chars) require exact token
    match to avoid false positives.

    Args:
        app_name: The application's display name.
        eol_products: Mapping of product_id → product display name.

    Returns:
        Tuple of (product_id, confidence) or ``None`` if no reasonable match.
    """
    normalized_app = _normalize_for_fuzzy(app_name)
    if not normalized_app:
        return None

    app_tokens = set(normalized_app.split())
    if not app_tokens:
        return None

    best_match: str | None = None
    best_score = 0.0

    for product_id, product_name in eol_products.items():
        # Direct slug match — require minimum slug length to avoid
        # false positives from short slugs like "go", "r", "qt"
        slug_clean = product_id.replace("-", " ").replace("_", " ").lower()
        if len(slug_clean) <= 3:
            # Short slug: require exact token match
            if slug_clean in app_tokens:
                score = 0.65
                if score > best_score:
                    best_score = score
                    best_match = product_id
            continue

        if slug_clean in normalized_app or normalized_app in slug_clean:
            score = 0.7
            if score > best_score:
                best_score = score
                best_match = product_id
            continue

        # Token overlap
        product_tokens = set(_normalize_for_fuzzy(product_name).split())
        if not product_tokens:
            continue

        overlap = app_tokens & product_tokens
        if not overlap:
            continue

        # Jaccard-like score weighted toward the product name
        score = len(overlap) / max(len(product_tokens), 1)
        score = min(score, 0.65)  # Cap fuzzy matches below CPE confidence

        if score > best_score:
            best_score = score
            best_match = product_id

    if best_match and best_score >= 0.4:
        return best_match, best_score

    return None


def compute_eol_match(
    *,
    eol_product_id: str,
    version_string: str,
    cycles: list[EOLCycle],
    match_source: str,
    match_confidence: float,
    reference_date: date | None = None,
) -> EOLMatch | None:
    """Compute a full EOL match for an app against a product's cycles.

    Extracts the version, finds the matching cycle, and computes the
    EOL/security-only status relative to the reference date.

    Args:
        eol_product_id: The endoflife.date product slug.
        version_string: The app's version string.
        cycles: The product's release cycles.
        match_source: How the match was made (``cpe``, ``fuzzy``, ``manual``).
        match_confidence: Confidence score.
        reference_date: Date to compare EOL dates against (default: today).

    Returns:
        An ``EOLMatch`` if a cycle was matched, or ``None``.
    """
    cycle = extract_cycle_match(version_string, cycles)
    if cycle is None:
        return None

    today = reference_date or date.today()

    is_eol = bool(cycle.eol_date and cycle.eol_date < today)
    is_security_only = bool(
        cycle.support_end
        and cycle.support_end < today
        and (not cycle.eol_date or cycle.eol_date >= today)
    )

    return EOLMatch(
        eol_product_id=eol_product_id,
        matched_cycle=cycle.cycle,
        match_source=match_source,  # type: ignore[arg-type]
        match_confidence=match_confidence,
        is_eol=is_eol,
        eol_date=cycle.eol_date,
        is_security_only=is_security_only,
        support_end=cycle.support_end,
    )


async def run_eol_matching(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    eol_products: dict[str, list[EOLCycle]],
    *,
    delta_only: bool = False,
    changed_app_names: list[str] | None = None,
) -> int:
    """Run EOL matching for apps in the database.

    For each app summary, attempts CPE-based matching first (via library
    entry upstream_id), then fuzzy matching as fallback.  Persists the
    ``eol_match`` field on each app summary document.

    Args:
        db: Motor database handle.
        eol_products: Product ID → list of cycles mapping.
        delta_only: If True, only match apps in ``changed_app_names``.
        changed_app_names: Specific app names to re-match (for post-sync delta).

    Returns:
        Number of apps matched.
    """
    query: dict[str, Any] = {}
    if delta_only and changed_app_names:
        query = {"normalized_name": {"$in": changed_app_names}}

    # Load user-configured name mappings (override built-in NAME_TO_EOL_MAP)
    from domains.eol.repository import get_all_name_mappings_dict

    user_mappings = await get_all_name_mappings_dict(db)

    # Load product name map for fuzzy matching
    product_names: dict[str, str] = {}
    async for doc in db["eol_products"].find({}, {"product_id": 1, "name": 1}):
        product_names[doc["product_id"]] = doc.get("name", doc["product_id"])

    # Load CPE data from library entries for CPE-based matching.
    # Library entries from nist_cpe store upstream_id as "vendor:product"
    # (the dedup key), not full CPE URIs.
    cpe_map: dict[str, tuple[str, str]] = {}  # pattern → (cpe_vendor, cpe_product)
    async for entry in db["library_entries"].find(
        {"source": "nist_cpe"},
        {"upstream_id": 1, "markers": 1},
    ):
        upstream_id = entry.get("upstream_id", "")
        # upstream_id is "vendor:product" (e.g. "google:chrome")
        if ":" not in upstream_id:
            continue
        vendor, _, product = upstream_id.partition(":")
        if not vendor or not product:
            continue
        for marker in entry.get("markers", []):
            pattern = marker.get("pattern", "").lower().strip("*")
            if pattern and len(pattern) > 2:
                cpe_map[pattern] = (vendor, product)

    matched = 0
    cursor = db["app_summaries"].find(query, {"normalized_name": 1, "display_name": 1})

    async for doc in cursor:
        nname = doc["normalized_name"]
        display_name = doc.get("display_name", nname)

        # The eol_match on app_summaries stores only the product mapping
        # (which endoflife.date product this app maps to).  Version-level
        # EOL determination happens at query time in the compliance check
        # and in the app detail endpoint — NOT here.
        eol_match_doc: dict[str, Any] | None = None

        # Layer 0: Direct name mapping (highest confidence, curated + user)
        direct_pid = _direct_name_match(nname, eol_products, user_mappings)
        if direct_pid:
            eol_match_doc = {
                "eol_product_id": direct_pid,
                "match_source": "cpe",
                "match_confidence": 0.95,
            }

        # Layer 1: CPE library pattern matching (if no direct match)
        if eol_match_doc is None:
            for pattern, (vendor, product) in cpe_map.items():
                if pattern in nname or nname in pattern:
                    eol_product_id = cpe_to_eol_product(vendor, product)
                    if eol_product_id and eol_product_id in eol_products:
                        eol_match_doc = {
                            "eol_product_id": eol_product_id,
                            "match_source": "cpe",
                            "match_confidence": 0.9,
                        }
                        break

        # Layer 2: Fuzzy matching (lowest confidence, needs review)
        if eol_match_doc is None:
            fuzzy_result = fuzzy_match_product(display_name, product_names)
            if fuzzy_result:
                product_id, confidence = fuzzy_result
                if product_id in eol_products:
                    eol_match_doc = {
                        "eol_product_id": product_id,
                        "match_source": "fuzzy",
                        "match_confidence": confidence,
                    }

        # Persist match (or clear stale match)
        update: dict[str, Any] = (
            {"$set": {"eol_match": eol_match_doc}}
            if eol_match_doc
            else {"$unset": {"eol_match": ""}}
        )
        await db["app_summaries"].update_one(
            {"normalized_name": nname},
            update,
        )
        if eol_match_doc:
            matched += 1

    logger.info("EOL matching complete: {} apps matched", matched)
    return matched


async def _get_app_version(db: AsyncIOMotorDatabase, normalized_name: str) -> str | None:  # type: ignore[type-arg]
    """Get the most common version for an app from installed apps.

    Args:
        db: Motor database handle.
        normalized_name: The normalized application name.

    Returns:
        The most common version string, or ``None``.
    """
    pipeline: list[dict[str, Any]] = [
        {"$match": {"normalized_name": normalized_name}},
        {"$group": {"_id": "$version", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 1},
    ]
    async for doc in db[INSTALLED_APPS].aggregate(pipeline):
        return doc["_id"]
    return None


def _match_to_doc(match: EOLMatch) -> dict[str, Any]:
    """Convert an EOLMatch entity to a MongoDB-storable dict.

    Args:
        match: The EOL match entity.

    Returns:
        Dictionary suitable for MongoDB storage.
    """
    return {
        "eol_product_id": match.eol_product_id,
        "matched_cycle": match.matched_cycle,
        "match_source": match.match_source,
        "match_confidence": match.match_confidence,
        "is_eol": match.is_eol,
        "eol_date": match.eol_date.isoformat() if match.eol_date else None,
        "is_security_only": match.is_security_only,
        "support_end": match.support_end.isoformat() if match.support_end else None,
    }
