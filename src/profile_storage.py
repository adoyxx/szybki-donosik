from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import extra_streamlit_components as stx
import streamlit as st

_COOKIE_EMAIL = "konfident_email"
_COOKIE_NAME = "konfident_name"
_EXPIRES = datetime.now() + timedelta(days=365)


@dataclass
class Profile:
    email: str = ""
    full_name: str = ""


def _cookie_manager() -> stx.CookieManager:
    # CookieManager is itself a widget; instantiate once per rerun via session_state.
    if "_cookie_mgr" not in st.session_state:
        st.session_state._cookie_mgr = stx.CookieManager(key="konfident_cookies")
    return st.session_state._cookie_mgr


def load_profile() -> Profile:
    cm = _cookie_manager()
    cookies = cm.get_all() or {}
    return Profile(
        email=cookies.get(_COOKIE_EMAIL, "") or "",
        full_name=cookies.get(_COOKIE_NAME, "") or "",
    )


def save_profile(profile: Profile) -> None:
    cm = _cookie_manager()
    cm.set(_COOKIE_EMAIL, profile.email, expires_at=_EXPIRES, key="set_email")
    cm.set(_COOKIE_NAME, profile.full_name, expires_at=_EXPIRES, key="set_name")
