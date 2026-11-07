"""Checked facts, clinical team-approved messages and honest manual contact outcomes."""
from datetime import datetime, timedelta, timezone
import http.client
from html.parser import HTMLParser
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from agent import demo_read
from app import DemoServer, case_page
from http_test_client import coordinator_browser
from caregiver_contact import contact_progress, draft_message
from store import RuleError, Store, now


def token():
    return uuid4().hex


class ContactTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=self.tmp.name+"/cases.db"
        self.store=Store(self.path)
        self.id=self.create()
        self.store.add_reply(self.id,"Where should we go? Which documents are needed?",self.case()["version"],token(),demo_read)
        self.act("approve",{"message_id":self.case()["messages"][0]["id"],"note":"Coordinator will check details."})

    def tearDown(self):
        self.tmp.cleanup()

    def create(self):
        return self.store.create({"patient_ref":"P-CONTACT","plan_ref":token(),"target":"Collection",
            "owner":"Anita","due_at":(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),
            "plan_approved":"yes","consent":"yes"},token())

    def case(self):
        return self.store.detail(self.id)

    def act(self,action,data,role="Coordinator"):
        self.store.act(self.id,action,data,self.case()["version"],token(),role)

    def facts(self,**changes):
        return {"location":"Sample hospital, collection counter 2","documents":"Approved prescription and sample reference",
            "source":"Sample authorised service","checked_by":"Anita","checked_at":now(),"language":"en",
            "facts_checked":"yes",**changes}

    def save_facts(self,**changes):
        self.act("check_details",self.facts(**changes))
        return self.case()["collection_checks"][-1]

    def approve_message(self):
        self.act("approve_update",{"check_id":self.case()["collection_checks"][-1]["id"],
            "approved_by":"Rahul","message_checked":"yes","body":"Untrusted replacement must be ignored"})
        return self.case()["caregiver_updates"][-1]

    def contact(self,outcome="INFORMED",**changes):
        return {"update_id":self.case()["caregiver_updates"][-1]["id"],"channel":"WHATSAPP",
            "outcome":outcome,"contacted_by":"Anita","contacted_at":now(),
            "note":"Sample caregiver acknowledged the checked details.","contact_permitted":"yes",
            "receipt_confirmed":"yes",**changes}

    def ready(self):
        self.save_facts()
        return self.approve_message()

    def test_details_and_approval_do_not_claim_contact_or_confirm_access(self):
        facts=self.save_facts()
        self.assertIn("needs approval",contact_progress(self.case()))
        update=self.approve_message()
        self.assertEqual(update["body"],draft_message(facts))
        self.assertNotIn("Untrusted replacement",update["body"])
        self.assertIn("contact not yet recorded",contact_progress(self.case()))
        self.assertEqual(self.case()["access"],"NOT_CONFIRMED")
        self.assertEqual(self.case()["workflow"],"COORDINATOR_CHECKING")

    def test_approval_is_required_before_recording_contact(self):
        self.save_facts()
        with self.assertRaises(RuleError):
            self.act("record_contact",{"update_id":"not-approved"})
        with self.assertRaises(RuleError):
            self.act("approve_update",{"check_id":self.case()["collection_checks"][-1]["id"],"approved_by":"Anita"})
        self.assertFalse(self.case()["caregiver_contacts"])

    def test_sent_is_not_informed_and_acknowledgement_is_explicit(self):
        self.ready()
        self.act("record_contact",self.contact("SENT",receipt_confirmed="",note="Message sent outside app; no acknowledgement yet."))
        self.assertIn("awaiting acknowledgement",contact_progress(self.case()))
        with self.assertRaises(RuleError):
            self.act("record_contact",self.contact(receipt_confirmed=""))
        self.act("record_contact",self.contact())
        self.assertIn("Caregiver informed",contact_progress(self.case()))
        self.assertEqual(self.case()["access"],"NOT_CONFIRMED")
        # An additional failed attempt does not erase the acknowledgement already recorded.
        self.act("record_contact",self.contact("NOT_REACHED"))
        self.assertIn("Caregiver informed",contact_progress(self.case()))

    def test_phone_outcomes_and_agreed_contact_route_are_checked(self):
        self.ready()
        with self.assertRaises(RuleError):self.act("record_contact",self.contact("SENT",channel="PHONE"))
        with self.assertRaises(RuleError):self.act("record_contact",self.contact(contact_permitted=""))
        self.act("record_contact",self.contact("NOT_REACHED",channel="PHONE",receipt_confirmed=""))
        self.assertIn("not reached",contact_progress(self.case()))

    def test_revision_requires_new_approval_and_keeps_old_snapshot(self):
        old=self.ready()
        self.act("record_contact",self.contact())
        self.save_facts(location="Revised sample collection location")
        self.assertIn("needs approval",contact_progress(self.case()))
        with self.assertRaises(RuleError):
            self.act("record_contact",self.contact(update_id=old["id"]))
        self.assertEqual(self.case()["caregiver_updates"][0]["body"],old["body"])
        self.assertEqual(len(self.case()["caregiver_contacts"]),1)
        new=self.approve_message()
        self.assertIn("Revised sample collection location",new["body"])
        self.assertNotIn("Caregiver informed",contact_progress(self.case()))

    def test_stale_check_and_cross_case_update_are_rejected(self):
        old=self.save_facts()
        self.save_facts(location="New sample place")
        with self.assertRaises(RuleError):
            self.act("approve_update",{"check_id":old["id"],"approved_by":"Anita","message_checked":"yes"})
        self.approve_message()
        with self.assertRaises(RuleError):
            self.act("record_contact",self.contact(update_id="another-case-update"))

    def test_invalid_checks_and_future_or_preapproval_times_are_rejected(self):
        for change in [{"facts_checked":""},{"language":"unknown"},{"location":""},
                       {"checked_at":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}]:
            with self.subTest(change=change),self.assertRaises(RuleError):
                self.act("check_details",self.facts(**change))
        self.ready()
        for stamp in [(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                      (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()]:
            with self.subTest(stamp=stamp),self.assertRaises(RuleError):
                self.act("record_contact",self.contact(contacted_at=stamp))

    def assert_all_new_actions_blocked(self):
        actions=[("check_details",self.facts()),("approve_update",{"check_id":self.case()["collection_checks"][-1]["id"],"approved_by":"Anita","message_checked":"yes"}),
                 ("record_contact",self.contact())]
        before=self.case()
        for action,data in actions:
            with self.subTest(action=action),self.assertRaises(RuleError):self.act(action,data)
        after=self.case()
        self.assertEqual(before["version"],after["version"])
        self.assertEqual(before["events"],after["events"])

    def test_review_and_withdrawal_block_new_routine_actions(self):
        self.ready()
        self.store.add_reply(self.id,"The patient has pain.",self.case()["version"],token(),demo_read)
        self.assert_all_new_actions_blocked()
        self.act("withdraw",{})
        self.assert_all_new_actions_blocked()
        self.assertEqual(self.case()["workflow"],"STOPPED")

    def test_pending_handover_blocks_contact_until_accepted(self):
        self.ready()
        self.act("handover",{"person":"Rahul","note":"Shift ending.","due_at":self.case()["due_at"]})
        self.assert_all_new_actions_blocked()
        self.act("accept_handover",{"person":"Rahul"})
        self.act("record_contact",self.contact(contacted_by="Rahul"))
        self.assertEqual(self.case()["owner"],"Rahul")

    def test_initial_staff_approval_and_simulated_role_are_enforced(self):
        old_id=self.id
        self.id=self.create()
        with self.assertRaises(RuleError):self.act("check_details",self.facts())
        self.id=old_id
        with self.assertRaises(RuleError):self.act("check_details",self.facts(),"Verifier")

    def test_request_retry_does_not_duplicate_checked_details(self):
        key,version,data=token(),self.case()["version"],self.facts()
        for _ in range(2):self.store.act(self.id,"check_details",data,version,key,"Coordinator")
        self.assertEqual(len(self.case()["collection_checks"]),1)
        with self.assertRaises(RuleError):
            self.store.act(self.id,"check_details",self.facts(location="Different"),self.case()["version"],key,"Coordinator")
        self.approve_message()
        key,version,data=token(),self.case()["version"],self.contact()
        for _ in range(2):self.store.act(self.id,"record_contact",data,version,key,"Coordinator")
        self.assertEqual(len(self.case()["caregiver_contacts"]),1)

    def test_saved_contact_survives_restart_and_only_proof_completes_access(self):
        self.ready()
        self.act("record_contact",self.contact())
        self.store=Store(self.path)
        self.assertEqual(len(self.case()["caregiver_contacts"]),1)
        self.act("add_evidence",{"source":"Sample hospital","reference":"RECORD-CONTACT","target_match":"yes","full_supply":"yes"})
        self.act("verify",{"evidence_id":self.case()["evidence"][-1]["id"],"decision":"accept","authority_checked":"yes","note":"Sample proof checked."},"Verifier")
        self.assertEqual(self.case()["access"],"CONFIRMED")
        self.assert_all_new_actions_blocked()
        self.assertIn("Caregiver informed",contact_progress(self.case()))

    def test_old_database_upgrade_preserves_cases_and_history(self):
        self.act("add_evidence",{"source":"Demo hospital","reference":"PRE-UPGRADE-PROOF","target_match":"yes","full_supply":"yes"})
        before=self.case()
        with self.store.connection(write=True) as db:
            for table in ["caregiver_contacts","caregiver_updates","collection_checks"]:db.execute("DROP TABLE "+table)
        self.store=Store(self.path)
        after=self.case()
        self.assertEqual(before,after)
        self.save_facts()
        self.assertEqual(len(Store(self.path).detail(self.id)["collection_checks"]),1)

    def test_marathi_template_uses_only_checked_text_and_html_is_escaped(self):
        facts=self.save_facts(language="mr",location="नमुना रुग्णालय </textarea><script>alert(1)</script>",documents="नमुना कागदपत्रे")
        self.approve_message()
        self.assertIn("कुठे जायचे:",draft_message(facts))
        page=case_page(self.store,"test-csrf",self.id)
        self.assertIn("&lt;/textarea&gt;&lt;script&gt;",page)
        self.assertNotIn("<script>alert(1)</script>",page)


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__();self.forms=[];self.current=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=="form":
            if self.current is not None:raise AssertionError("Nested form")
            self.current={"action":attrs.get("action"),"hidden":{}}
        elif tag=="input" and self.current is not None and attrs.get("type")=="hidden":
            self.current["hidden"][attrs["name"]]=attrs.get("value","")
    def handle_endtag(self,tag):
        if tag=="form":self.forms.append(self.current);self.current=None


class ContactHttpTests(unittest.TestCase):
    def test_complete_form_flow_with_real_hidden_fields(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{"SAHYOGI_READER":"demo"}):
            store=Store(tmp+"/http.db")
            server=DemoServer(("127.0.0.1",0),store)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            browser=coordinator_browser(server)
            def request(method,path,data=None):
                return browser.request(method,path,data)
            try:
                case_id=store.create({"patient_ref":"P-HTTP-CONTACT","plan_ref":"PLAN-HTTP-CONTACT","target":"Collection",
                    "owner":"Anita","due_at":(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),"plan_approved":"yes","consent":"yes"},token(),principal=browser.user_id)
                path="/case?id="+case_id
                def submit(action,payload):
                    status,_,html=request("GET",path);self.assertEqual(status,200)
                    parser=FormParser();parser.feed(html)
                    forms=[f for f in parser.forms if (f["hidden"].get("action")==action if action!="reply" else f["action"]=="/reply")]
                    self.assertEqual(len(forms),1,(action,html))
                    selected=forms[0]
                    status,_,body=request("POST",selected["action"],{**selected["hidden"],**payload})
                    self.assertEqual(status,303,body)
                submit("reply",{"text":"Where should we go? Which documents are needed?"})
                submit("approve",{"note":"Coordinator will check details."})
                local=datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime("%Y-%m-%dT%H:%M")
                submit("check_details",{"location":"Sample location","documents":"Sample documents","source":"Sample authorised service",
                    "checked_by":"Anita","checked_at":local,"language":"en","facts_checked":"yes"})
                submit("approve_update",{"approved_by":"Anita","message_checked":"yes"})
                self.assertIn("contact not yet recorded",request("GET",path)[2])
                local=datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime("%Y-%m-%dT%H:%M")
                submit("record_contact",{"channel":"PHONE","outcome":"INFORMED","contacted_by":"Anita","contacted_at":local,
                    "note":"Sample call: caregiver heard the checked details.","contact_permitted":"yes","receipt_confirmed":"yes"})
                page=request("GET",path)[2]
                self.assertIn("Caregiver informed according to clinical team record",page)
                self.assertIn("Access: Not Confirmed",page)
                self.assertEqual(len(store.detail(case_id)["caregiver_contacts"]),1)
                self.assertIn("This app sends no message",page)
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__=="__main__":unittest.main()
