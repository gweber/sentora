"""Unit tests for S1 client helpers.

Covers the pure functions in ``domains/sync/s1_client.py`` that can be tested
without any network or database access.

Tested:
- ``make_app_cursor`` — constructs a valid base64-encoded S1 cursor JSON
- ``_s1_dt`` — normalises ISO-8601 strings to the format S1 accepts
- ``S1ApiError`` — stores status code; URL appears in message when provided
- ``S1RateLimitError`` — is a subclass of ``S1ApiError``
"""

from __future__ import annotations

import base64
import json

from domains.sync.s1_client import S1ApiError, S1RateLimitError, _s1_dt, make_app_cursor


class TestMakeAppCursor:
    """Tests for ``make_app_cursor``."""

    def test_returns_string(self) -> None:
        """Return value is a plain string (base64 bytes decoded to str)."""
        result = make_app_cursor(123)
        assert isinstance(result, str)

    def test_is_valid_base64(self) -> None:
        """Return value is valid base64."""
        result = make_app_cursor(456)
        decoded = base64.b64decode(result)  # must not raise
        assert len(decoded) > 0

    def test_decoded_is_valid_json(self) -> None:
        """Decoded base64 is valid JSON."""
        result = make_app_cursor(789)
        raw = base64.b64decode(result)
        payload = json.loads(raw)  # must not raise
        assert isinstance(payload, dict)

    def test_id_column_field(self) -> None:
        """Cursor JSON contains the expected ``id_column`` key."""
        raw = base64.b64decode(make_app_cursor(1000))
        payload = json.loads(raw)
        assert payload["id_column"] == "ApplicationView.id"

    def test_id_value_matches_argument(self) -> None:
        """``id_value`` in cursor JSON equals the after_id passed in."""
        after_id = 1_793_529_234_171_457_161
        raw = base64.b64decode(make_app_cursor(after_id))
        payload = json.loads(raw)
        assert payload["id_value"] == after_id

    def test_sort_by_column_matches(self) -> None:
        """``sort_by_column`` equals ``id_column`` (same field, same direction)."""
        raw = base64.b64decode(make_app_cursor(42))
        payload = json.loads(raw)
        assert payload["sort_by_column"] == payload["id_column"]

    def test_sort_order_is_asc(self) -> None:
        """Both sort orders are ascending so the sweep moves forward."""
        raw = base64.b64decode(make_app_cursor(1))
        payload = json.loads(raw)
        assert payload["id_sort_order"] == "asc"
        assert payload["sort_order"] == "asc"

    def test_different_ids_produce_different_cursors(self) -> None:
        """Each after_id produces a distinct cursor value."""
        c1 = make_app_cursor(100)
        c2 = make_app_cursor(200)
        assert c1 != c2

    def test_zero_id(self) -> None:
        """ID of zero is valid (start of the dataset)."""
        raw = base64.b64decode(make_app_cursor(0))
        payload = json.loads(raw)
        assert payload["id_value"] == 0


class TestS1Dt:
    """Tests for ``_s1_dt``."""

    def test_strips_microseconds(self) -> None:
        """Microseconds are removed from the output."""
        result = _s1_dt("2024-06-15T12:34:56.789012+00:00")
        assert "." not in result

    def test_uses_z_suffix(self) -> None:
        """Output ends with ``Z``, not ``+00:00``."""
        result = _s1_dt("2024-01-01T00:00:00+00:00")
        assert result.endswith("Z")
        assert "+00:00" not in result

    def test_format_is_yyyy_mm_dd_t_hh_mm_ss_z(self) -> None:
        """Output matches the exact format ``YYYY-MM-DDTHH:MM:SSZ``."""
        result = _s1_dt("2024-06-15T08:30:00+00:00")
        assert result == "2024-06-15T08:30:00Z"

    def test_converts_non_utc_timezone(self) -> None:
        """Non-UTC offsets are converted to UTC before formatting."""
        # 2024-06-15T10:00:00+02:00 == 2024-06-15T08:00:00Z
        result = _s1_dt("2024-06-15T10:00:00+02:00")
        assert result == "2024-06-15T08:00:00Z"

    def test_no_microseconds_in_already_clean_input(self) -> None:
        """Input without microseconds passes through cleanly."""
        result = _s1_dt("2024-03-01T15:00:00+00:00")
        assert result == "2024-03-01T15:00:00Z"


class TestS1ApiError:
    """Tests for ``S1ApiError``."""

    def test_stores_status_code(self) -> None:
        """``status`` attribute reflects the HTTP status code."""
        err = S1ApiError(status=403, body="Forbidden")
        assert err.status == 403

    def test_message_contains_status(self) -> None:
        """String representation includes the status code."""
        err = S1ApiError(status=500, body="Internal Server Error")
        assert "500" in str(err)

    def test_message_contains_body(self) -> None:
        """String representation includes (part of) the response body."""
        err = S1ApiError(status=400, body="Bad Request detail")
        assert "Bad Request detail" in str(err)

    def test_body_truncated_at_200_chars(self) -> None:
        """Bodies longer than 200 characters are truncated in the message."""
        long_body = "x" * 300
        err = S1ApiError(status=500, body=long_body)
        # The message must not contain the full 300-char body
        assert long_body not in str(err)
        assert "x" * 200 in str(err)

    def test_url_included_when_provided(self) -> None:
        """URL appears in the error message when passed."""
        err = S1ApiError(
            status=404, body="Not found", url="https://s1.example.com/web/api/v2.1/agents"
        )
        assert "https://s1.example.com/web/api/v2.1/agents" in str(err)

    def test_url_omitted_when_empty(self) -> None:
        """No URL bracket in message when url is the default empty string."""
        err = S1ApiError(status=404, body="Not found")
        assert "[" not in str(err)

    def test_is_exception(self) -> None:
        """``S1ApiError`` is a proper ``Exception`` subclass."""
        assert issubclass(S1ApiError, Exception)


class TestS1RateLimitError:
    """Tests for ``S1RateLimitError``."""

    def test_is_subclass_of_s1_api_error(self) -> None:
        """``S1RateLimitError`` inherits from ``S1ApiError``."""
        assert issubclass(S1RateLimitError, S1ApiError)

    def test_stores_status_code(self) -> None:
        """``status`` attribute reflects 429."""
        err = S1RateLimitError(status=429, body="Too Many Requests")
        assert err.status == 429

    def test_can_be_caught_as_s1_api_error(self) -> None:
        """A rate-limit error can be caught with the parent exception type."""
        err: Exception = S1RateLimitError(status=429, body="Too Many Requests")
        assert isinstance(err, S1ApiError)

    def test_url_in_message(self) -> None:
        """URL is included in the message when provided."""
        err = S1RateLimitError(
            status=429, body="Too Many Requests", url="https://s1.example.com/apps"
        )
        assert "https://s1.example.com/apps" in str(err)
