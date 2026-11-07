"""Tests for the Streamlit transport; all account data here is synthetic."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4
from html.parser import HTMLParser

from streamlit_bridge import Backend, PortalSession, local_path
from streamlit_app import event_is_current, perform


class Fields(HTMLParser):
    def __init__(self):
        super().__init__(); self.inputs = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("type") == "hidden":
            self.inputs[attrs["name"]] = attrs.get("value", "")


class StreamlitHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.backend = Backend(Path(self.tmp.name) / "test.db")
        self.accounts = self.backend.server.accounts
        self.admin = self.accounts.create_user("anita", "Anita", "coordinator", "Practice123!", bootstrap=True)
        self.family = self.accounts.create_user("family", "Practice caregiver", "caregiver", "Practice123!", creator=self.admin)
        self.accounts.change_password(self.family, "Practice123!", "Changed123!")
        self.session = PortalSession()

    def tearDown(self):
        self.backend.close(); self.tmp.cleanup()

    def event(self, method, path, data=None):
        return {"id": uuid4().hex, "method": method, "path": path, "data": data or {}}

    def login(self, session, name="anita", password="Practice123!"):
        page = session.page(self.backend, "/login")
        fields = Fields(); fields.feed(page.text)
        return perform(session, self.backend, self.event("POST", "/login", {
            **fields.inputs, "username": name, "password": password,
        }))

    def test_original_page_and_css_are_unchanged(self):
        from ui_components import THEME_CSS
        page = self.session.page(self.backend, "/login")
        self.assertIn(THEME_CSS, page.text)
        self.assertIn('action="/login"', page.text)
        self.assertNotIn("streamlit", page.text.lower())
        self.assertIn("Patient or caregiver sign in", page.text)

    def test_sessions_do_not_share_login(self):
        self.login(self.session)
        self.assertEqual(self.session.page(self.backend, "/accounts").status, 200)
        other = PortalSession()
        self.assertIn('action="/login"', other.page(self.backend, "/accounts").text)
        self.assertNotIn(self.session.cookie, repr(self.session))

    def test_family_cannot_open_administration(self):
        self.login(self.session, "family", "Changed123!")
        self.assertIn(self.session.page(self.backend, "/accounts").status, {403, 404})
        self.assertIn(self.session.page(self.backend, "/api-settings").status, {403, 404})

    def test_original_csrf_is_required(self):
        self.session.page(self.backend, "/login")
        page = perform(self.session, self.backend, self.event("POST", "/login", {
            "csrf": "invalid", "username": "anita", "password": "Practice123!",
        }))
        self.assertEqual(page.status, 403)

    def test_stale_or_repeated_component_events_are_ignored(self):
        event = {"id": "one", "revision": "current"}
        self.assertTrue(event_is_current(event, "current", None))
        self.assertFalse(event_is_current(event, "current", "one"))
        self.assertFalse(event_is_current(event, "new", None))
        self.assertFalse(event_is_current(None, "new", None))

    def test_transport_does_not_allow_external_routes(self):
        for path in ["https://example.org/", "//example.org/", "/bad\r\nHost: other", "/\\other"]:
            with self.assertRaises(ValueError): local_path(path)
        self.assertEqual(local_path("/request?id=sample&view=checks"), "/request?id=sample&view=checks")

    def test_password_change_is_still_required_for_new_accounts(self):
        self.accounts.create_user("newfamily", "New caregiver", "caregiver", "Practice123!", creator=self.admin)
        page = self.login(self.session, "newfamily")
        self.assertEqual(page.path, "/password")
        self.assertIn("Save new password", page.text)

    def test_bootstrap_is_owner_controlled(self):
        import streamlit_app
        self.assertTrue(streamlit_app.bootstrap(self.backend, {}))
        with self.assertRaises(ValueError):
            self.accounts.create_user("another", "Another", "coordinator", "Practice123!", bootstrap=True)


if __name__ == "__main__": unittest.main()
