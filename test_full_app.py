"""Practice cases, guided steps, local setup, search, exports and backups."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from agent import demo_read
from app import DemoServer, help_page, home
from http_test_client import coordinator_browser
from backup_records import backup_database
from examples import EXAMPLES, next_step
from start_app import main as launch, prepare_runtime
from store import RuleError, Store


class GuidedAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/"cases.db";self.store=Store(self.path)
        self.id=self.store.create_practice("directions",uuid4().hex)
    def tearDown(self):self.tmp.cleanup()
    def case(self):return self.store.detail(self.id)
    def act(self,action,data):self.store.act(self.id,action,data,self.case()["version"],uuid4().hex,"Coordinator")

    def test_each_practice_case_starts_without_calling_ai_or_approving_a_reply(self):
        for key in EXAMPLES:
            key_token=uuid4().hex
            one=self.store.create_practice(key,key_token);two=self.store.create_practice(key,key_token)
            self.assertEqual(one,two)
            case=self.store.detail(one)
            self.assertEqual(case["practice_example"],key)
            self.assertEqual(case["workflow"],"WAITING_REPLY")
            self.assertFalse(case["messages"])
            self.assertEqual(case["access"],"NOT_CONFIRMED")
        with self.assertRaises(RuleError):self.store.create_practice("unknown",uuid4().hex)

    def test_guidance_follows_reader_approval_review_and_handover(self):
        self.assertEqual(next_step(self.case())[2],"read-reply")
        self.store.add_reply(self.id,EXAMPLES["directions"]["message"],self.case()["version"],uuid4().hex,demo_read)
        self.assertIn("Approve",next_step(self.case())[0])
        self.act("approve",{"message_id":self.case()["messages"][0]["id"],"note":"Check directions."})
        self.assertEqual(next_step(self.case())[2],"caregiver-update")
        self.store.add_reply(self.id,"The patient has pain.",self.case()["version"],uuid4().hex,demo_read)
        self.assertEqual(next_step(self.case())[2],"care-review")
        self.act("handover",{"person":"Rahul","due_at":self.case()["due_at"],"note":"Review needs another owner."})
        self.assertEqual(next_step(self.case())[2],"care-review")
        self.store.act(self.id,"clear_review",{"note":"Practice care team review completed."},self.case()["version"],uuid4().hex,"Care team")
        self.assertEqual(next_step(self.case())[2],"handover")
        self.act("withdraw",{})
        self.assertEqual(next_step(self.case())[0],"Contact is stopped")

    def test_search_filters_and_help_escape_inputs(self):
        page=home(self.store,"csrf",search="does-not-match")
        self.assertIn("No matching cases",page)
        self.assertIn("PRACTICE-DIRECTIONS",home(self.store,"csrf",search="Anita"))
        self.assertIn("No matching cases",home(self.store,"csrf",view="completed"))
        self.assertIn("&lt;script&gt;",home(self.store,"csrf",search="<script>"))
        self.assertNotIn('value="<script>"',home(self.store,"csrf",search="<script>"))
        help_html=help_page("csrf")
        self.assertEqual(help_html.count('action="/practice"'),10)
        for item in EXAMPLES.values():self.assertIn(item["title"],help_html)

    def test_reschedule_preserves_owner_and_review_and_checks_future_time(self):
        self.store.add_reply(self.id,"The patient has pain.",self.case()["version"],uuid4().hex,demo_read)
        future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        self.act("reschedule",{"due_at":future,"note":"Care team follow-up time recorded."})
        self.assertEqual(self.case()["owner"],"Anita")
        self.assertTrue(self.case()["review_required"])
        self.assertEqual(self.case()["workflow"],"HUMAN_REVIEW")
        with self.assertRaises(RuleError):self.act("reschedule",{"due_at":"2020-01-01T00:00:00+00:00","note":"Old time"})
        self.act("withdraw",{})
        with self.assertRaises(RuleError):self.act("reschedule",{"due_at":future,"note":"Not allowed"})

    def test_backup_is_complete_does_not_overwrite_and_restores_practice_metadata(self):
        target=Path(self.tmp.name)/"backup.db"
        backup_database(self.path,target)
        self.assertEqual(Store(target).detail(self.id),self.case())
        with self.assertRaises(ValueError):backup_database(self.path,target)
        with self.assertRaises(ValueError):backup_database(self.path,self.path)
        missing=Path(self.tmp.name)/"missing.db"
        with self.assertRaises(ValueError):backup_database(missing)
        self.assertFalse(missing.exists())


class LauncherTests(unittest.TestCase):
    def test_demo_needs_no_key_or_package_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse((Path(tmp)/".venv").exists())
            self.assertTrue(prepare_runtime(Path(tmp),False))
            self.assertFalse((Path(tmp)/".venv").exists())
        with patch("start_app.prepare_runtime",return_value="test-python"),patch("start_app.subprocess.call",return_value=0) as child,redirect_stdout(io.StringIO()):
            self.assertEqual(launch(["--mode","demo"]),0)
        self.assertEqual(child.call_args.kwargs["env"]["SAHYOGI_READER"],"demo")

    def test_real_provider_key_is_hidden_and_only_passed_to_child(self):
        output=io.StringIO()
        with patch.dict(os.environ,{"SARVAM_API_KEY":"","SARVAM_MODEL":"sarvam-105b"}),patch("start_app.getpass.getpass",return_value="synthetic-private-key"),patch("start_app.prepare_runtime",return_value="test-python"),patch("start_app.subprocess.call",return_value=0) as child,redirect_stdout(output):
            self.assertEqual(launch(["--mode","sarvam"]),0)
            self.assertEqual(os.environ["SARVAM_API_KEY"],"")
        self.assertEqual(child.call_args.kwargs["env"]["SARVAM_API_KEY"],"synthetic-private-key")
        self.assertEqual(child.call_args.kwargs["env"]["SAHYOGI_PROVIDER"],"sarvam")
        self.assertNotIn("synthetic-private-key",output.getvalue())


class FullAppHttpTests(unittest.TestCase):
    def test_practice_help_and_export_use_http_without_a_paid_request(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{"SAHYOGI_READER":"demo","SARVAM_API_KEY":"synthetic-hidden-key"}):
            server=DemoServer(("127.0.0.1",0),Store(Path(tmp)/"http.db"))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            browser=coordinator_browser(server)
            def request(method,path,data=None):
                return browser.request(method,path,data)
            try:
                self.assertEqual(request("GET","/help")[0],200)
                self.assertEqual(request("GET","/practice")[0],404)
                data={"csrf":server.csrf,"token":uuid4().hex,"example_id":"directions"}
                status,headers,_=request("POST","/practice",data);self.assertEqual(status,303)
                page=request("GET",headers["Location"])[2]
                self.assertIn("What to do next",page)
                self.assertIn(EXAMPLES["directions"]["message"],page)
                self.assertIn("Practice example",page)
                case_id=server.store.list_cases()[0]["id"]
                status,headers,body=request("GET","/export?id="+case_id)
                self.assertEqual(status,200)
                self.assertIn("attachment",headers["Content-Disposition"])
                self.assertEqual(json.loads(body)["practice_example"],"directions")
                self.assertNotIn("synthetic-hidden-key",body)
                self.assertEqual(request("POST","/practice",{**data,"token":uuid4().hex,"example_id":"invalid"})[0],400)
                self.assertEqual(len(server.store.list_cases()),1)
            finally:server.shutdown();server.server_close();thread.join()


if __name__=="__main__":unittest.main()
