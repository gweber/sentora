"""CSV cell sanitization to prevent spreadsheet formula injection.

Spreadsheet applications (Excel, Google Sheets) interpret cells starting
with ``=``, ``+``, ``-``, or ``@`` as formulas.  This module provides a
utility to prefix such values so they are treated as plain text.
"""

from __future__ import annotations

#: Characters that trigger formula interpretation in spreadsheets.
_FORMULA_PREFIXES = frozenset({"=", "+", "-", "@"})


def sanitize_csv_cell(value: object) -> str:
    """Sanitize a value for safe inclusion in a CSV cell.

    Prefixes the string representation with a tab character if it starts
    with a formula-triggering character, preventing spreadsheet injection
    (also known as CSV injection or DDE injection).

    Args:
        value: The cell value to sanitize.

    Returns:
        A string safe for CSV export.
    """
    s = str(value)
    if s and s[0] in _FORMULA_PREFIXES:
        return "\t" + s
    return s
