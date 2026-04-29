from __future__ import annotations

"""Streamlit interface placeholder for business-facing contract review workflows."""

from typing import Any


def create_app() -> Any:
    """Create and return Streamlit app object.

    This is a stub for future business UI implementation.
    """
    try:
        import streamlit as st
    except Exception as exc:
        raise RuntimeError("streamlit is required to run ContractHub UI") from exc

    st.set_page_config(page_title="ContractHub", layout="wide")
    st.title("ContractHub")
    st.info(
        "UI module scaffold is in place. Implement contract editing workflows here."
    )
    return st
