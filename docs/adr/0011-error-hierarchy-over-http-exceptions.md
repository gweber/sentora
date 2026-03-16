# ADR-0011: Error Hierarchy over HTTP Exceptions

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

FastAPI's built-in `HTTPException` conflates HTTP transport concerns with domain logic concerns. Raising `HTTPException(status_code=422, detail="fingerprint not found")` inside a classification service means the domain layer must know about HTTP status codes — coupling it to the delivery mechanism. This makes domain logic harder to unit-test (tests must import and inspect HTTP response shapes) and harder to reuse across different delivery mechanisms (e.g., a CLI entrypoint or a background task). Sentora has four bounded contexts (sync, fingerprint, classification, taxonomy), each with distinct failure modes that should be expressed as first-class domain concepts.

## Decision

Sentora defines a typed error hierarchy rooted at `SentoraError`. Each bounded context has its own subclass: `SyncError` (S1 API failures, rate limits, timeout), `FingerprintError` (invalid patterns, missing fingerprint), `ClassificationError` (incomplete input data, recomputation failure), and `TaxonomyError` (duplicate category, invalid entry). Domain and service code raises these domain errors exclusively. A FastAPI exception handler registered at application startup maps each error type to the appropriate HTTP status code and a structured JSON response body containing `error_code` (machine-readable string), `message` (human-readable), and `context` (optional dict of relevant identifiers).

## Consequences

### Positive
- Domain and service layer code is testable without an HTTP client — tests assert on raised exception types and messages, not on HTTP response objects.
- All API error responses share a consistent JSON shape, simplifying Vue 3 error handling (single `useErrorHandler` composable).
- `error_code` strings are stable across API versions, allowing the frontend to branch on domain condition rather than HTTP status code alone.
- Adding a new error type requires only a new subclass and a single mapping entry in the global handler — no changes to existing routes.
- Sync and classification background tasks can raise domain errors that are logged with structured context without needing to construct fake HTTP responses.

### Negative
- Developers must learn the error hierarchy and resist the temptation to raise `HTTPException` directly in route handlers.
- Mapping errors to HTTP status codes in the global handler requires a deliberate decision for each error type (e.g., should `FingerprintError` for a missing ID be 404 or 422?).
- Tracebacks in logs now involve the domain error class rather than `HTTPException`, which may surprise developers familiar with standard FastAPI projects.

### Risks
- If `HTTPException` is raised anywhere in the codebase (e.g., in third-party middleware or FastAPI's own request validation), it bypasses the global handler and produces a different response shape. The global handler must also register a fallback for `HTTPException` to normalize the format.
- Over time, the error hierarchy may grow unwieldy if every edge case gets its own subclass. A convention for when to subclass versus reuse an existing type with a different `error_code` string must be documented.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| Raise `HTTPException` everywhere | Couples domain logic to HTTP; domain tests must use a test client; error codes are HTTP status integers, not machine-readable strings |
| Return error dicts from service functions (no exceptions) | Caller must check return type on every call; eliminates Python's exception propagation mechanics; verbose and error-prone |
| Generic `AppError` with a status_code field | Domain errors carry HTTP status codes, which is the coupling we are trying to eliminate |
| Problem Details (RFC 7807) | Correct standard for HTTP APIs; can be adopted as the JSON response schema without changing the domain error hierarchy — deferred to a future version |
