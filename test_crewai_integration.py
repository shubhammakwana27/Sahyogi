"""Real CrewAI execution, with an offline fake LLM. No provider key or calls.

Install requirements.txt to run these tests. They skip in dependency-free mode.
"""
import importlib.util
import json
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from agent import read_reply
from store import Store

HAS_CREWAI = importlib.util.find_spec("crewai") is not None
if HAS_CREWAI:
    # Import our module first so telemetry is disabled before CrewAI loads.
    from crewai_reader import ReplyOutput, build_reader_crew, create_reader_llm
    from crewai import BaseLLM

    class OfflineLLM(BaseLLM):
        def __init__(self, category="DOCUMENTS_ROUTE", clinical=False):
            super().__init__(model="offline-test")
            self.calls = 0
            self.category = category
            self.clinical = clinical

        def call(self, messages, tools=None, callbacks=None, available_functions=None, **kwargs):
            self.calls += 1
            data = {"category": self.category, "summary": "Synthetic clinical team summary.",
                    "clinical_concern": self.clinical, "uncertain": False}
            return "Final Answer: " + json.dumps(data)

        def supports_function_calling(self):
            return False

        def supports_stop_words(self):
            return False

        def get_context_window_size(self):
            return 8192


@unittest.skipUnless(HAS_CREWAI, "Install requirements.txt to run real CrewAI integration tests")
class CrewAIIntegrationTests(unittest.TestCase):
    def test_real_crew_and_native_provider_with_simulated_sdk_response(self):
        from crewai_reader import run_reader
        payload = {"category": "DOCUMENTS_ROUTE", "summary": "Synthetic document question.",
                   "clinical_concern": False, "uncertain": False}
        response = SimpleNamespace(output_text=json.dumps(payload), output=[], usage=None,
                                   id="resp_synthetic", status="completed")
        with patch("crewai.llms.providers.openai.completion.OpenAI") as client, patch("crewai.llms.providers.openai.completion.AsyncOpenAI"):
            client.return_value.responses.create.return_value = response
            result = run_reader("Synthetic document question.", model="test-model", api_key="test-key")
            request = client.return_value.responses.create.call_args.kwargs
        self.assertEqual(result, payload)
        self.assertFalse(request["store"])
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertNotIn("tools", request)

    def test_real_provider_configuration_without_sending_request(self):
        # Avoid constructing HTTP transports; CI may use an optional SOCKS proxy.
        with patch("crewai.llms.providers.openai.completion.OpenAI"), patch("crewai.llms.providers.openai.completion.AsyncOpenAI"):
            llm = create_reader_llm("openai/test-model", "fake-test-key")
        self.assertEqual(llm.model, "test-model")
        self.assertEqual(llm.api, "responses")
        self.assertFalse(llm.store)
        self.assertFalse(llm.auto_chain)
        self.assertEqual(llm.timeout, 20)
        self.assertEqual(llm.max_retries, 0)
        self.assertIs(llm.response_format, ReplyOutput)

    def test_exactly_one_agent_and_one_task_with_no_action_tools(self):
        crew = build_reader_crew(OfflineLLM())
        self.assertEqual(len(crew.agents), 1)
        self.assertEqual(len(crew.tasks), 1)
        self.assertIs(crew.tasks[0].agent, crew.agents[0])
        self.assertEqual(crew.agents[0].tools, [])
        self.assertFalse(crew.agents[0].allow_delegation)
        self.assertFalse(crew.planning)
        self.assertFalse(crew.memory)
        self.assertFalse(crew.tracing)

    def test_real_crew_executes_and_returns_structured_output(self):
        llm = OfflineLLM()
        result = build_reader_crew(llm).kickoff(inputs={"reply": "Synthetic document question."})
        self.assertIsInstance(result.pydantic, ReplyOutput)
        self.assertEqual(result.pydantic.category, "DOCUMENTS_ROUTE")
        self.assertGreater(llm.calls, 0)

    def test_public_reader_runs_real_crew_and_existing_staff_gate(self):
        env = {"SAHYOGI_READER": "crewai", "OPENAI_API_KEY": "fake-test-key", "OPENAI_MODEL": "test-model"}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env):
            store = Store(tmp + "/cases.db")
            case_id = store.create({"patient_ref": "P-014", "plan_ref": "CREW-DEMO",
                "target": "Collection", "owner": "Coordinator A", "plan_approved": "yes",
                "consent": "yes", "due_at": "2030-01-01T10:00:00+05:30"}, uuid4().hex)
            with patch("crewai_reader.LLM", return_value=OfflineLLM()):
                store.add_reply(case_id, "Synthetic document question.", 1, uuid4().hex)
            case = store.detail(case_id)
            self.assertEqual(case["messages"][0]["reading"]["engine"], "crewai")
            self.assertEqual(case["workflow"], "AWAITING_APPROVAL")
            self.assertEqual(case["access"], "NOT_CONFIRMED")
            store.act(case_id, "approve", {"message_id": case["messages"][0]["id"],
                "note": "Clinical team checked the next step."}, case["version"], uuid4().hex, "Coordinator")
            self.assertEqual(store.detail(case_id)["access"], "NOT_CONFIRMED")

    def test_clinical_crew_output_still_requires_care_team(self):
        with patch.dict(os.environ, {"SAHYOGI_READER": "crewai", "OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}):
            with patch("crewai_reader.LLM", return_value=OfflineLLM("CLINICAL", True)):
                result = read_reply("Synthetic medical question.")
        self.assertEqual(result.engine, "crewai")
        self.assertEqual(result.category, "CLINICAL")
        self.assertTrue(result.clinical_concern)


if __name__ == "__main__":
    unittest.main()
