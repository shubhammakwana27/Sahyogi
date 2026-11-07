"""Gemini routing and native CrewAI integration with a mocked Google SDK only."""
import importlib.util
import json
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from agent import read_reply
from store import Store

PAYLOAD = {"category": "DOCUMENTS_ROUTE", "summary": "Caregiver asks about the route and documents.",
           "clinical_concern": False, "uncertain": False}
ENV = {"SAHYOGI_READER": "crewai", "SAHYOGI_PROVIDER": "gemini",
       "GEMINI_API_KEY": "synthetic-gemini-key", "GEMINI_MODEL": "gemini-3.8-flash",
       "OPENAI_API_KEY": "", "OPENAI_MODEL": ""}
MARATHI = "आम्ही कुठे जायचे? कोणती कागदपत्रे लागतील?"


class GeminiRoutingTests(unittest.TestCase):
    def test_gemini_uses_its_own_key_and_model(self):
        adapter=Mock(return_value=PAYLOAD)
        with patch.dict(os.environ,ENV), patch.dict("sys.modules",{"crewai_reader":SimpleNamespace(run_reader=adapter)}):
            result=read_reply(MARATHI)
        self.assertEqual(result.engine,"crewai")
        self.assertEqual(result.category,"DOCUMENTS_ROUTE")
        adapter.assert_called_once_with(MARATHI,model="gemini-3.8-flash",api_key="synthetic-gemini-key",provider="gemini")

    def test_missing_gemini_key_does_not_fall_back_to_openai(self):
        env={**ENV,"GEMINI_API_KEY":"","OPENAI_API_KEY":"another-synthetic-key"}
        adapter=Mock()
        with patch.dict(os.environ,env), patch.dict("sys.modules",{"crewai_reader":SimpleNamespace(run_reader=adapter)}):
            result=read_reply(MARATHI)
        adapter.assert_not_called()
        self.assertEqual(result.engine,"unavailable")
        self.assertIn("GEMINI_API_KEY",result.summary)

    def test_invalid_provider_and_gemini_placeholder_fail_closed(self):
        for changes in [{"SAHYOGI_PROVIDER":"unsupported"},{"GEMINI_API_KEY":"YOUR_GEMINI_API_KEY"}]:
            with self.subTest(changes=changes), patch.dict(os.environ,{**ENV,**changes}):
                result=read_reply(MARATHI)
            self.assertIn("[CONFIG]",result.summary)
            self.assertTrue(result.uncertain)

    def test_openai_default_is_preserved_with_gemini_key_present(self):
        env={**ENV,"SAHYOGI_PROVIDER":"openai","OPENAI_API_KEY":"synthetic-openai-key","OPENAI_MODEL":"test-model"}
        adapter=Mock(return_value=PAYLOAD)
        with patch.dict(os.environ,env), patch.dict("sys.modules",{"crewai_reader":SimpleNamespace(run_reader=adapter)}):
            read_reply(MARATHI)
        adapter.assert_called_once_with(MARATHI,model="test-model",api_key="synthetic-openai-key")


try:
    HAS_GEMINI = importlib.util.find_spec("crewai") is not None and importlib.util.find_spec("google.genai") is not None
except ModuleNotFoundError:
    HAS_GEMINI = False


@unittest.skipUnless(HAS_GEMINI,"Install requirements.txt for native Gemini integration tests")
class GeminiIntegrationTests(unittest.TestCase):
    def response(self,payload):
        from google.genai import types
        return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
            role="model",parts=[types.Part(text=json.dumps(payload))]),finish_reason="STOP")])

    def test_native_gemini_config_has_no_openai_parameters(self):
        from crewai_reader import create_reader_llm, ReplyOutput
        from google.genai import types
        with patch("crewai.llms.providers.gemini.completion.genai.Client") as client:
            llm=create_reader_llm("gemini/gemini-3.8-flash","synthetic-key",provider="gemini")
        self.assertEqual(llm.model,"gemini-3.8-flash")
        self.assertFalse(llm.use_vertexai)
        self.assertIs(llm.response_format,ReplyOutput)
        self.assertEqual(client.call_args.kwargs["api_key"],"synthetic-key")
        self.assertFalse(client.call_args.kwargs["vertexai"])
        options=types.HttpOptions(**client.call_args.kwargs["http_options"])
        self.assertEqual(options.timeout,20000)
        self.assertEqual(options.retry_options.attempts,1)
        self.assertNotIn("store",client.call_args.kwargs)

    def test_real_crew_runs_marathi_through_native_google_provider(self):
        from crewai_reader import run_reader
        with patch("crewai.llms.providers.gemini.completion.genai.Client") as client:
            client.return_value.models.generate_content.return_value=self.response(PAYLOAD)
            result=run_reader(MARATHI,model="gemini-3.8-flash",api_key="synthetic-key",provider="gemini")
            request=client.return_value.models.generate_content.call_args.kwargs
        self.assertEqual(result,PAYLOAD)
        self.assertEqual(request["model"],"gemini-3.8-flash")
        self.assertEqual(request["config"].response_mime_type,"application/json")
        self.assertEqual(request["config"].response_json_schema["properties"]["category"]["enum"],
                         ["DOCUMENTS_ROUTE","TRAVEL","AVAILABILITY_REPORTED","RECEIPT_REPORTED","CLINICAL","UNCLEAR","MEDICINE_APPROVAL","COST","CARE_SUPPORT","SUPPLY_CONTINUITY","FOLLOWUP_FAILURE","OUT_OF_SCOPE"])
        self.assertFalse(request["config"].thinking_config.include_thoughts)
        self.assertFalse(request["config"].tools)

    def test_gemini_success_still_requires_staff_approval(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,ENV),patch("crewai.llms.providers.gemini.completion.genai.Client") as client:
            client.return_value.models.generate_content.return_value=self.response(PAYLOAD)
            store=Store(tmp+"/sample.db")
            case_id=store.create({"patient_ref":"P-GEMINI","plan_ref":"PLAN-GEMINI",
                "target":"Collection","owner":"Anita","plan_approved":"yes","consent":"yes",
                "due_at":"2030-01-01T10:00:00+05:30"},uuid4().hex)
            store.add_reply(case_id,MARATHI,1,uuid4().hex)
            case=store.detail(case_id)
            self.assertEqual(case["workflow"],"AWAITING_APPROVAL")
            self.assertEqual(case["access"],"NOT_CONFIRMED")
            self.assertEqual(case["messages"][0]["body"],MARATHI)
            self.assertEqual(case["messages"][0]["reading"]["engine"],"crewai")
            store.act(case_id,"approve",{"message_id":case["messages"][0]["id"],"note":"Clinical team checked the next step."},case["version"],uuid4().hex,"Coordinator")
            self.assertEqual(store.detail(case_id)["access"],"NOT_CONFIRMED")

    def test_google_sdk_quota_errors_are_safely_classified(self):
        from google.genai.errors import ClientError
        from reader_errors import safe_error_summary
        error=ClientError(429,{"error":{"code":429,"message":"synthetic private payload","status":"RESOURCE_EXHAUSTED"}})
        self.assertIn("[RATE_LIMIT]",safe_error_summary(error))
        self.assertNotIn("synthetic private payload",safe_error_summary(error))

    def test_cross_provider_model_prefix_is_rejected(self):
        from crewai_reader import create_reader_llm
        with self.assertRaises(ValueError):
            create_reader_llm("openai/test-model","synthetic-key",provider="gemini")


if __name__=="__main__":
    unittest.main()
