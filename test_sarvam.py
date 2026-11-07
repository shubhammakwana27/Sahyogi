"""Sarvam integration uses a real CrewAI agent and SDK with an in-memory HTTP transport."""
from contextlib import contextmanager
import importlib.util
import json
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from agent import read_reply
from reader_errors import safe_error_summary
from store import Store

MARATHI = "आम्ही कुठे जायचे? कोणती कागदपत्रे लागतील?"
PAYLOAD = {"category":"DOCUMENTS_ROUTE","summary":"Caregiver asks about the collection location and documents.",
           "clinical_concern":False,"uncertain":False}
ENV = {"SAHYOGI_READER":"crewai","SAHYOGI_PROVIDER":"sarvam",
       "SARVAM_API_KEY":"synthetic-sarvam-key","SARVAM_MODEL":"sarvam-105b",
       "OPENAI_API_KEY":"synthetic-unused-openai-key","GEMINI_API_KEY":"synthetic-unused-gemini-key"}


class SarvamRoutingTests(unittest.TestCase):
    def test_sarvam_key_and_model_reach_adapter(self):
        adapter=Mock(return_value=PAYLOAD)
        with patch.dict(os.environ,ENV),patch.dict("sys.modules",{"crewai_reader":SimpleNamespace(run_reader=adapter)}):
            result=read_reply(MARATHI)
        adapter.assert_called_once_with(MARATHI,model="sarvam-105b",api_key="synthetic-sarvam-key",provider="sarvam")
        self.assertEqual(result.category,"DOCUMENTS_ROUTE")
        self.assertEqual(result.engine,"crewai")

    def test_missing_or_placeholder_sarvam_key_does_not_use_another_provider(self):
        for key in ["","YOUR_SARVAM_API_KEY"]:
            adapter=Mock()
            with self.subTest(key=key),patch.dict(os.environ,{**ENV,"SARVAM_API_KEY":key}),patch.dict("sys.modules",{"crewai_reader":SimpleNamespace(run_reader=adapter)}):
                result=read_reply(MARATHI)
            adapter.assert_not_called()
            self.assertEqual(result.engine,"unavailable")
            self.assertTrue(result.uncertain)

    def test_sarvam_error_codes_have_correct_safe_actions(self):
        for status,code,expected in [(403,"invalid_api_key_error","AUTH"),
             (402,"insufficient_quota_error","CREDITS"),(429,"seat_budget_exhausted_error","SPEND_LIMIT"),
             (503,"rate_limit_exceeded_error","RATE_LIMIT"),(429,"model_rate_limit_exceeded_error","RATE_LIMIT")]:
            with self.subTest(code=code):
                error=RuntimeError("sensitive-response-or-key")
                error.status_code=status
                error.body={"error":{"code":code,"message":"sensitive-response-or-key"}}
                summary=safe_error_summary(error)
                self.assertIn(f"[{expected}]",summary)
                self.assertNotIn("sensitive-response-or-key",summary)


HAS_CREWAI=importlib.util.find_spec("crewai") is not None


@unittest.skipUnless(HAS_CREWAI,"Install requirements.txt for Sarvam integration tests")
class SarvamIntegrationTests(unittest.TestCase):
    @contextmanager
    def transport(self,payload=PAYLOAD,status=200,error=None,content=None,finish_reason='stop'):
        import httpx
        from openai import OpenAI
        requests=[]
        clients=[]
        def handler(request):
            requests.append(request)
            if status!=200:return httpx.Response(status,json=error)
            return httpx.Response(200,json={"id":"synthetic_sarvam_response","object":"chat.completion", "created":1,
                "model":"sarvam-105b","choices":[{"index":0,"finish_reason":finish_reason,"message":{
                    "role":"assistant","content":json.dumps(payload,ensure_ascii=False) if content is None else content}}],
                "usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}})
        def client_factory(**kwargs):
            client=OpenAI(**kwargs,http_client=httpx.Client(transport=httpx.MockTransport(handler)))
            clients.append(client)
            return client
        with patch("crewai.llms.providers.openai.completion.OpenAI",side_effect=client_factory) as constructor,patch("crewai.llms.providers.openai.completion.AsyncOpenAI"):
            try:yield requests,constructor
            finally:
                for client in clients:client.close()

    def test_real_crew_marathi_request_uses_sarvam_host_header_and_strict_schema(self):
        from crewai_reader import run_reader
        with patch.dict(os.environ,{"OPENAI_BASE_URL":"https://unused.invalid/v1"}),self.transport() as (requests,constructor):
            result=run_reader(MARATHI,model="sarvam/sarvam-105b",api_key="synthetic-sarvam-key",provider="sarvam")
        self.assertEqual(result,PAYLOAD)
        self.assertGreater(len(requests),0)
        for request in requests:
            self.assertEqual(request.url.host,"api.sarvam.ai")
            self.assertEqual(request.url.path,"/v2/chat/completions")
            self.assertEqual(request.headers["api-subscription-key"],"synthetic-sarvam-key")
            body=json.loads(request.content)
            self.assertEqual(body["model"],"sarvam-105b")
            self.assertEqual(body['reasoning_effort'],'none')
            self.assertEqual(body['max_tokens'],4096)
            self.assertNotIn("store",body)
            self.assertFalse(body.get("tools"))
            self.assertIn(MARATHI,json.dumps(body,ensure_ascii=False))
            fmt=body["response_format"]
            self.assertEqual(fmt["type"],"json_schema")
            self.assertTrue(fmt["json_schema"]["strict"])
            self.assertFalse(fmt["json_schema"]["schema"]["additionalProperties"])
        self.assertEqual(constructor.call_args.kwargs["base_url"],"https://api.sarvam.ai/v2")
        self.assertEqual(constructor.call_args.kwargs["timeout"],60)
        self.assertEqual(constructor.call_args.kwargs["max_retries"],0)

    def test_configured_wait_reaches_native_sdk_and_crew_budget(self):
        from crewai_reader import create_reader_llm,build_reader_crew
        with patch.dict(os.environ,{'SAHYOGI_API_TIMEOUT_SECONDS':'90'}),self.transport() as (_,constructor):
            llm=create_reader_llm('sarvam-105b','synthetic-key',provider='sarvam')
            crew=build_reader_crew(llm)
        self.assertEqual(constructor.call_args.kwargs['timeout'],90)
        self.assertEqual(crew.agents[0].max_execution_time,105)

    def test_empty_length_limited_barrier_is_output_failure_and_keeps_staff_review(self):
        from care_agents import run_care_agent
        with patch.dict(os.environ,ENV),self.transport(content='',finish_reason='length') as (requests,_):
            result=run_care_agent('barrier',{'reader_category':'DOCUMENTS_ROUTE','messages':['Which documents do we need for palliative care?']})
        self.assertEqual(result.engine,'unavailable');self.assertIsNone(result.output)
        self.assertIn('[OUTPUT] Barrier Assistant',result.error)
        self.assertIn('Clinical team review is required',result.error)
        self.assertTrue(requests);self.assertTrue(all(r.url.host=='api.sarvam.ai' for r in requests))

    def test_httpx_subclass_failures_have_safe_categories(self):
        import httpx
        from reader_errors import classify_error
        for error,code in [(httpx.ReadTimeout('private'), 'TIMEOUT'),
                           (httpx.ConnectTimeout('private'),'TIMEOUT'),
                           (httpx.ReadError('private'),'CONNECTION'),
                           (httpx.RemoteProtocolError('private'),'CONNECTION')]:
            self.assertEqual(classify_error(error),code)
            self.assertNotIn('private',safe_error_summary(error,component='barrier'))

    def test_sarvam_suggestion_preserves_staff_approval_and_unconfirmed_access(self):
        with patch.dict(os.environ,ENV),self.transport(),tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp+"/cases.db")
            case_id=store.create({"patient_ref":"P-SARVAM","plan_ref":"PLAN-SARVAM",
                "target":"Collection","owner":"Anita","plan_approved":"yes","consent":"yes",
                "due_at":"2030-01-01T10:00:00+05:30"},uuid4().hex)
            store.add_reply(case_id,MARATHI,1,uuid4().hex)
            case=store.detail(case_id)
            self.assertEqual(case["workflow"],"AWAITING_APPROVAL")
            self.assertEqual(case["access"],"NOT_CONFIRMED")
            self.assertEqual(case["messages"][0]["body"],MARATHI)
            store.act(case_id,"approve",{"message_id":case["messages"][0]["id"],"note":"Clinical team checked route."},case["version"],uuid4().hex,"Coordinator")
            self.assertEqual(store.detail(case_id)["access"],"NOT_CONFIRMED")

    def test_real_sdk_credit_error_stays_in_review_without_fallback(self):
        with patch.dict(os.environ,ENV),self.transport(status=402,error={"error":{"code":"insufficient_quota_error","message":"synthetic private body"}}) as (requests,_):
            result=read_reply(MARATHI)
        self.assertEqual(result.engine,"unavailable")
        self.assertIn("[CREDITS]",result.summary)
        self.assertTrue(requests)
        self.assertTrue(all(r.url.host=="api.sarvam.ai" for r in requests))
        self.assertNotIn("synthetic private body",result.summary)

    def test_medical_message_still_overrides_routine_provider_output(self):
        with patch.dict(os.environ,ENV),self.transport():
            result=read_reply("The patient has pain. Which documents?")
        self.assertEqual(result.category,"CLINICAL")
        self.assertTrue(result.clinical_concern)

    def test_invalid_structured_output_cannot_enter_routine_work(self):
        with patch.dict(os.environ,ENV),self.transport(payload={"category":"CONFIRMED"}):
            result=read_reply(MARATHI)
        self.assertEqual(result.category,"UNCLEAR")
        self.assertTrue(result.uncertain)


if __name__=="__main__":
    unittest.main()
