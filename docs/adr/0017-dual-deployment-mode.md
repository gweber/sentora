# ADR-0017: Dual Deployment Mode (On-Prem / SaaS)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-03-15 |
| **Deciders** | Engineering |

## Context

Sentora was originally designed as a single-tenant, on-premises tool. Enterprise
adoption requires both a hosted SaaS offering (multi-tenant, platform operator manages
tenants) and a self-hosted on-premises option (single-tenant, local admin has full
control).

Without a deployment mode distinction, the role model becomes confusing: on-prem users
would need to understand `super_admin` even though there are no tenants to manage, and
SaaS operators would need to explain why `admin` can't access platform-level features.

## Decision

Introduce a `DEPLOYMENT_MODE` configuration variable with two values:

- **`onprem`** (default) — Single-tenant. `admin` is the highest role. Library source
  management is accessible to `admin`. Tenant management UI is hidden. Multi-tenancy
  is disabled regardless of `MULTI_TENANCY_ENABLED`.

- **`saas`** — Multi-tenant. `super_admin` manages the platform (tenants, library
  sources, cross-tenant config). Each tenant has its own `admin`/`analyst`/`viewer`
  users. Database-per-tenant isolation.

### Key design decisions

1. **Single codebase, runtime switch.** No code forks — the same Docker image serves
   both modes. The mode is read from config at startup and exposed via a public
   `/api/v1/deployment-info` endpoint so the frontend can adapt.

2. **`require_platform_role()` dependency.** A new auth middleware dependency resolves
   to `admin` in on-prem or `super_admin` in SaaS. Used for library ingestion and
   other platform-level operations. Avoids scattering `if is_onprem` checks across
   routers.

3. **First user auto-promotion.** The first registered user gets `admin` in on-prem
   mode and `super_admin` in SaaS mode. This eliminates the need for a separate
   bootstrap step.

4. **Frontend adapts via composable.** `useDeployment()` fetches deployment info once
   from the public endpoint. Components use `isOnprem` / `isSaas` computed refs to
   conditionally show/hide tenant management, library sources access, and the platform
   guide tab.

## Consequences

### Positive

- On-prem users get a clean, single-tenant experience without SaaS concepts.
- SaaS operators have a clear separation between platform and tenant operations.
- No code duplication — all features exist in both modes, just gated differently.
- Backward compatible — default is `onprem`, matching existing behavior.

### Negative

- Some conditional logic in auth middleware and frontend components.
- Documentation must cover both modes (role tables, quickstart, guides).
- Testing surface increases — both modes need coverage.

## Alternatives Considered

1. **Separate builds/packages.** Rejected — increases maintenance, Docker image count,
   and deployment complexity.

2. **Always multi-tenant.** Rejected — adds unnecessary complexity for single-instance
   deployments (tenant headers, master DB, super_admin role) with no benefit.

3. **Feature flags per capability.** Rejected — too granular. Deployment mode is a
   single switch that controls a coherent set of behaviors.
