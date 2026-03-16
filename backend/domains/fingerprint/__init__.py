"""Fingerprint domain.

A *fingerprint* is a named collection of glob-pattern markers associated with
a SentinelOne agent group. Each marker has a weight (0.1–2.0) used to compute
a weighted coverage score when classifying agents against their group's expected
software profile.

Sub-modules
-----------
entities    — Pydantic domain entities (FingerprintMarker, Fingerprint, FingerprintSuggestion)
dto         — Request/response DTOs (API contract layer)
repository  — Async MongoDB operations (no business logic)
matcher     — TF-IDF suggestion computation and glob/weight scoring logic
service     — Business logic; converts DTOs ↔ entities; raises domain errors
router      — FastAPI routers (fingerprint_router, suggestions_router)
"""
