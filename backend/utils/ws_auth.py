"""WebSocket authentication utility.

Extracts JWT tokens from the ``Sec-WebSocket-Protocol`` header instead of
query parameters, preventing token leakage in server logs, browser history,
and reverse-proxy access logs.

The frontend sends the token as a subprotocol value prefixed with ``bearer.``.
"""

from __future__ import annotations

from fastapi import WebSocket

from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from domains.auth.service import verify_token


async def authenticate_websocket(
    websocket: WebSocket,
    *,
    allowed_roles: set[UserRole] | None = None,
) -> TokenPayload | None:
    """Authenticate a WebSocket connection via the subprotocol header.

    The client sends the JWT as a subprotocol value: ``bearer.<token>``.
    On success the connection is accepted with the matching subprotocol so
    the browser considers it negotiated.

    Args:
        websocket: The incoming WebSocket connection.
        allowed_roles: If provided, the user must have one of these roles.
            ``super_admin`` is always permitted regardless.

    Returns:
        The decoded ``TokenPayload`` on success, or ``None`` if the
        connection was rejected (and already closed with an error code).
    """
    # Extract token from Sec-WebSocket-Protocol header
    # Format: "bearer.<jwt_token>"
    token: str | None = None
    subprotocol: str | None = None
    for proto in websocket.headers.get("sec-websocket-protocol", "").split(","):
        proto = proto.strip()
        if proto.startswith("bearer."):
            token = proto[len("bearer.") :]
            subprotocol = proto
            break

    # Fall back to query parameter for backwards compatibility during rollout
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return None

    try:
        payload = verify_token(token)
    except ValueError:
        await websocket.close(code=4001, reason="Invalid authentication token")
        return None

    # Role check
    if allowed_roles is not None and (  # noqa: SIM102
        payload.role != UserRole.super_admin.value
        and payload.role not in {r.value for r in allowed_roles}
    ):
        await websocket.close(code=4003, reason="Insufficient permissions")
        return None

    # Accept with the matching subprotocol so the browser negotiation succeeds
    await websocket.accept(subprotocol=subprotocol)
    return payload
