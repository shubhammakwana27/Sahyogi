"""Streamlit host for the original SAHYOGI screens and permission checks.

The HTML/CSS comes unchanged from the original application. The component only
transports navigation and form submissions to its existing HTTP routes.
"""
import base64
import os
from pathlib import Path
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components

from streamlit_bridge import Backend, PortalSession, local_path

ROOT = Path(__file__).resolve().parent
ENV_KEYS = (
    "SAHYOGI_DB", "SAHYOGI_PROVIDER", "SAHYOGI_READER",
    "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
    "SARVAM_API_KEY", "SARVAM_MODEL", "GEMINI_API_KEY", "GEMINI_MODEL",
)


def configured_secrets():
    try:
        return st.secrets.to_dict()
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return {}


@st.cache_resource(show_spinner=False)
def get_backend(database):
    return Backend(database)


def bootstrap(backend, config):
    """Only the server owner can set the first coordinator through secrets."""
    if backend.server.accounts.has_users():
        return True
    setup = config.get("sahyogi", {})
    if not setup.get("bootstrap_username") or not setup.get("bootstrap_password"):
        st.info("First start: the app owner must create the coordinator account.")
        st.code("python manage_users.py setup", language="text")
        st.caption("On Streamlit Community Cloud, add the [sahyogi] coordinator settings from secrets.example.toml in Advanced settings → Secrets.")
        return False
    if setup["bootstrap_password"] in {"YOUR_NEW_PASSWORD", "CHANGE_THIS_FIRST", "YOUR_PASSWORD"}:
        st.error("Replace the example coordinator password in Secrets with your own password before deploying.")
        return False
    try:
        backend.server.accounts.create_user(
            str(setup["bootstrap_username"]),
            str(setup.get("bootstrap_display_name", "Coordinator")),
            "coordinator", str(setup["bootstrap_password"]), bootstrap=True,
        )
    except (ValueError, PermissionError):
        st.error("Check the coordinator settings. Use a valid username and a password of 4 to 18 characters.")
        return False
    return True


def event_is_current(event, revision, seen):
    return (isinstance(event, dict) and isinstance(event.get("id"), str)
            and event.get("id") != seen and event.get("revision") == revision)


def perform(session, backend, event):
    """Use the same CSRF, version, role and approval checks as the local app."""
    method = str(event.get("method", "GET")).upper()
    if method not in {"GET", "POST"}:
        raise ValueError("Choose a page in this app.")
    path = local_path(event.get("path", "/"))
    data = event.get("data", {})
    if not isinstance(data, dict) or any(not isinstance(v, str) for v in data.values()):
        raise ValueError("Reload the page and try again.")
    response = (session.page(backend, path) if method == "GET"
                else session.request(backend, method, path, data))
    if response.status in {301, 302, 303, 307, 308}:
        return session.page(backend, response.headers.get("Location", "/"))
    return response


def main():
    st.set_page_config(page_title="SAHYOGI", page_icon="🏥", layout="wide", initial_sidebar_state="collapsed")
    config = configured_secrets()
    for name in ENV_KEYS:
        if name in config and not os.getenv(name):
            os.environ[name] = str(config[name])
    database = os.getenv("SAHYOGI_DB", str(ROOT / "data" / "sahyogi.db"))
    backend = get_backend(database)
    if not bootstrap(backend, config):
        return

    # Hide only the Streamlit shell; keep the original HTML and CSS untouched.
    st.markdown("""<style>
      [data-testid="stHeader"], [data-testid="stToolbar"],
      [data-testid="stSidebar"], [data-testid="stStatusWidget"], footer {display:none!important}
      .stMainBlockContainer {max-width:none!important;padding:0!important}
      [data-testid="stVerticalBlock"] {gap:0!important}
      [data-testid="stAppViewContainer"] {padding:0!important}
      iframe {display:block;border:0}
    </style>""", unsafe_allow_html=True)
    if "portal_session" not in st.session_state:
        st.session_state.portal_session = PortalSession()
        st.session_state.portal_revision = uuid4().hex
        st.session_state.portal_seen = None
        st.session_state.portal_path = "/login"
        st.session_state.portal_page = None
        st.session_state.portal_download = None
    session = st.session_state.portal_session
    if st.session_state.portal_page is None:
        st.session_state.portal_page = session.page(backend, st.session_state.portal_path)
    page = st.session_state.portal_page
    component = components.declare_component("sahyogi_original_screens", path=str(ROOT / "streamlit_frontend"))
    event = component(
        html=page.text, revision=st.session_state.portal_revision,
        download=st.session_state.portal_download, key="sahyogi_portal", default=None,
    )
    if event_is_current(event, st.session_state.portal_revision, st.session_state.portal_seen):
        st.session_state.portal_seen = event["id"]
        try:
            response = perform(session, backend, event)
        except (ValueError, OSError):
            st.error("The request could not finish. Refresh and check the saved record before trying again.")
            return
        if "text/html" in response.headers.get("Content-Type", ""):
            st.session_state.portal_page = response
            st.session_state.portal_path = response.path
            st.session_state.portal_download = None
        else:
            st.session_state.portal_download = {
                "id": uuid4().hex,
                "content": base64.b64encode(response.body).decode("ascii"),
                "type": response.headers.get("Content-Type", "application/octet-stream"),
                "filename": "sahyogi-case-record.json",
            }
        # New revision rejects repeats and forms left open before navigation.
        st.session_state.portal_revision = uuid4().hex
        st.rerun()


if __name__ == "__main__":
    main()
