"""Sentora error hierarchy.

All application errors derive from SentoraError. Domain-specific errors
derive from their respective domain base class. The global exception handler
in middleware/error_handler.py converts these to consistent JSON responses.
"""

from __future__ import annotations


class SentoraError(Exception):
    """Base class for all application errors.

    Attributes:
        status_code: HTTP status code for the response.
        error_code: Machine-readable error code (e.g. "SYNC_ALREADY_RUNNING").
        message: Human-readable description of the error.
        detail: Optional extra context (included in response body).
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: dict | None = None) -> None:
        """Initialise with a human-readable message and optional detail dict."""
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


# ── Sync domain ──────────────────────────────────────────────────────────────


class SyncError(SentoraError):
    """Base class for sync domain errors."""

    status_code = 500
    error_code = "SYNC_ERROR"


class SyncAlreadyRunningError(SyncError):
    """Raised when a sync is triggered while one is already running."""

    status_code = 409
    error_code = "SYNC_ALREADY_RUNNING"


class SyncNotFoundError(SyncError):
    """Raised when a requested sync run does not exist."""

    status_code = 404
    error_code = "SYNC_NOT_FOUND"


class S1ApiError(SyncError):
    """Raised when the SentinelOne API returns an unexpected error."""

    status_code = 502
    error_code = "S1_API_ERROR"


class S1RateLimitError(S1ApiError):
    """Raised specifically when the SentinelOne API rate limit is hit."""

    status_code = 429
    error_code = "S1_RATE_LIMIT"


# ── Fingerprint domain ────────────────────────────────────────────────────────


class FingerprintError(SentoraError):
    """Base class for fingerprint domain errors."""

    status_code = 500
    error_code = "FINGERPRINT_ERROR"


class FingerprintNotFoundError(FingerprintError):
    """Raised when a fingerprint for the requested group does not exist."""

    status_code = 404
    error_code = "FINGERPRINT_NOT_FOUND"


class FingerprintAlreadyExistsError(FingerprintError):
    """Raised when creating a fingerprint for a group that already has one."""

    status_code = 409
    error_code = "FINGERPRINT_ALREADY_EXISTS"


class MarkerNotFoundError(FingerprintError):
    """Raised when a marker ID does not exist in the fingerprint."""

    status_code = 404
    error_code = "MARKER_NOT_FOUND"


class SuggestionNotFoundError(FingerprintError):
    """Raised when a suggestion ID does not exist."""

    status_code = 404
    error_code = "SUGGESTION_NOT_FOUND"


# ── Classification domain ─────────────────────────────────────────────────────


class ClassificationError(SentoraError):
    """Base class for classification domain errors."""

    status_code = 500
    error_code = "CLASSIFICATION_ERROR"


class ClassificationNotFoundError(ClassificationError):
    """Raised when no classification result exists for the requested agent."""

    status_code = 404
    error_code = "CLASSIFICATION_NOT_FOUND"


# ── Taxonomy domain ───────────────────────────────────────────────────────────


class TaxonomyError(SentoraError):
    """Base class for taxonomy domain errors."""

    status_code = 500
    error_code = "TAXONOMY_ERROR"


class SoftwareEntryNotFoundError(TaxonomyError):
    """Raised when a software taxonomy entry does not exist."""

    status_code = 404
    error_code = "TAXONOMY_ENTRY_NOT_FOUND"


class SoftwareEntryAlreadyExistsError(TaxonomyError):
    """Raised when creating a software entry that already exists."""

    status_code = 409
    error_code = "TAXONOMY_ENTRY_ALREADY_EXISTS"


# ── Config domain ─────────────────────────────────────────────────────────────


class ConfigError(SentoraError):
    """Base class for configuration errors."""

    status_code = 500
    error_code = "CONFIG_ERROR"


# ── Tags domain ───────────────────────────────────────────────────────────────


class TagError(SentoraError):
    """Base class for tag domain errors."""

    status_code = 500
    error_code = "TAG_ERROR"


class TagRuleNotFoundError(TagError):
    """Raised when a tag rule does not exist."""

    status_code = 404
    error_code = "TAG_RULE_NOT_FOUND"


class TagRuleAlreadyExistsError(TagError):
    """Raised when creating a tag rule with a tag_name that already exists."""

    status_code = 409
    error_code = "TAG_RULE_ALREADY_EXISTS"


class TagPatternNotFoundError(TagError):
    """Raised when a pattern ID does not exist in the tag rule."""

    status_code = 404
    error_code = "TAG_PATTERN_NOT_FOUND"


# ── Webhooks domain ─────────────────────────────────────────────────────────


class WebhookError(SentoraError):
    """Base class for webhook domain errors."""

    status_code = 500
    error_code = "WEBHOOK_ERROR"


class WebhookNotFoundError(WebhookError):
    """Raised when a webhook does not exist."""

    status_code = 404
    error_code = "WEBHOOK_NOT_FOUND"


# ── Library domain ───────────────────────────────────────────────────────────


class LibraryError(SentoraError):
    """Base class for library domain errors."""

    status_code = 500
    error_code = "LIBRARY_ERROR"


class LibraryEntryNotFoundError(LibraryError):
    """Raised when a library entry does not exist."""

    status_code = 404
    error_code = "LIBRARY_ENTRY_NOT_FOUND"


class SubscriptionConflictError(LibraryError):
    """Raised when a subscription already exists."""

    status_code = 409
    error_code = "SUBSCRIPTION_CONFLICT"


class IngestionError(LibraryError):
    """Raised when an ingestion run fails."""

    status_code = 500
    error_code = "INGESTION_ERROR"


# ── Compliance domain ────────────────────────────────────────────────────────


class ComplianceError(SentoraError):
    """Base class for compliance domain errors."""

    status_code = 500
    error_code = "COMPLIANCE_ERROR"


class FrameworkNotFoundError(ComplianceError):
    """Raised when a requested framework does not exist."""

    status_code = 404
    error_code = "FRAMEWORK_NOT_FOUND"


class ControlNotFoundError(ComplianceError):
    """Raised when a requested control does not exist."""

    status_code = 404
    error_code = "CONTROL_NOT_FOUND"


class CustomControlAlreadyExistsError(ComplianceError):
    """Raised when creating a custom control with an ID that already exists."""

    status_code = 409
    error_code = "CUSTOM_CONTROL_ALREADY_EXISTS"


class ComplianceRunInProgressError(ComplianceError):
    """Raised when a compliance run is triggered while one is already active."""

    status_code = 409
    error_code = "COMPLIANCE_RUN_IN_PROGRESS"


class InvalidCheckTypeError(ComplianceError):
    """Raised when a control references a check type that does not exist."""

    status_code = 400
    error_code = "INVALID_CHECK_TYPE"


# ── Enforcement domain ───────────────────────────────────────────────────


class EnforcementError(SentoraError):
    """Base class for enforcement domain errors."""

    status_code = 500
    error_code = "ENFORCEMENT_ERROR"


class EnforcementRuleNotFoundError(EnforcementError):
    """Raised when a requested enforcement rule does not exist."""

    status_code = 404
    error_code = "ENFORCEMENT_RULE_NOT_FOUND"


class InvalidTaxonomyCategoryError(EnforcementError):
    """Raised when a rule references a taxonomy category that does not exist."""

    status_code = 400
    error_code = "INVALID_TAXONOMY_CATEGORY"


# ── Audit chain domain ─────────────────────────────────────────────────────


class AuditChainError(SentoraError):
    """Base class for audit hash-chain errors."""

    status_code = 500
    error_code = "AUDIT_CHAIN_ERROR"


class ChainNotInitializedError(AuditChainError):
    """Raised when chain operations are attempted before genesis."""

    status_code = 409
    error_code = "CHAIN_NOT_INITIALIZED"


class ChainIntegrityError(AuditChainError):
    """Raised when a chain integrity violation is detected during write."""

    status_code = 500
    error_code = "CHAIN_INTEGRITY_ERROR"


class EpochNotFoundError(AuditChainError):
    """Raised when a requested epoch does not exist."""

    status_code = 404
    error_code = "EPOCH_NOT_FOUND"


class EpochNotCompleteError(AuditChainError):
    """Raised when attempting to export an incomplete epoch."""

    status_code = 409
    error_code = "EPOCH_NOT_COMPLETE"


# ── API Keys domain ─────────────────────────────────────────────────────────


class APIKeyError(SentoraError):
    """Base class for API key domain errors."""

    status_code = 400
    error_code = "API_KEY_ERROR"


class APIKeyNotFoundError(APIKeyError):
    """Raised when a requested API key does not exist."""

    status_code = 404
    error_code = "API_KEY_NOT_FOUND"


class APIKeyScopeError(APIKeyError):
    """Raised when an API key scope is invalid."""

    status_code = 400
    error_code = "API_KEY_INVALID_SCOPE"
