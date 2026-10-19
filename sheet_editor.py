"""Workbook-style cable editor. The component buffers every cable in one form."""
from pathlib import Path
import streamlit as st
from wirelog import (normalize, FIELDS, STRUCTURES, IDENTIFIERS, CONNECTORS,
                     TERMINATIONS, CONTACTS, STATES, CHECKS)
from palette import PALETTE

HERE = Path(__file__).parent
_sheet = st.components.v2.component(
    "cable_work_sheet", html='<div class="wire-sheet"></div>',
    css=(HERE / "sheet_editor.css").read_text(encoding="utf-8"),
    js=(HERE / "sheet_editor.js").read_text(encoding="utf-8"))


def sheet_editor(rows, key):
    initial = [normalize(row) for row in rows]
    buffered = st.session_state.get(key, {}).get("rows", initial)
    result = _sheet(data={"rows": buffered, "fields": FIELDS, "palette": PALETTE,
        "structures": STRUCTURES, "identifiers": IDENTIFIERS, "connectors": CONNECTORS,
        "terminations": TERMINATIONS, "contacts": CONTACTS, "states": STATES, "checks": CHECKS},
        key=key, default={"rows": initial}, on_rows_change=lambda: None)
    return [normalize(row) for row in result.get("rows", initial)]
