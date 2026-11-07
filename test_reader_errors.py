"""Regression tests for safe diagnostics. No live API requests."""
from contextlib import redirect_stdout
import io
import os
import unittest
from unittest.mock import patch

from agent import Reading, read_reply
from check_reader import main
from reader_errors import ReaderOutputError, ReaderConfigurationError, classify_error, safe_error_summary
from care_agents import CareResult,demo_care
from agent_settings import api_timeout_seconds


class ProviderError(Exception):
    def __init__(self, status, code=None):
        super().__init__("sensitive-provider-text fake-secret-and-message")
        self.status_code = status
        self.code = code


class DiagnosticTests(unittest.TestCase):
    def test_statuses_and_billing_codes_have_distinct_actions(self):
        for status, code, expected in [(401,None,"AUTH"),(403,None,"ACCESS"),
            (404,None,"MODEL"),(429,None,"RATE_LIMIT"),(429,"insufficient_quota","CREDITS"),
            (429,"credit_balance_exhausted","CREDITS"),(429,"project_spend_limit_exceeded","SPEND_LIMIT"),
            (400,None,"REQUEST"),(422,None,"REQUEST"),(408,None,"TIMEOUT"),(503,None,"SERVICE")]:
            with self.subTest(status=status, code=code):
                error = ProviderError(status, code)
                self.assertEqual(classify_error(error), expected)
                summary = safe_error_summary(error)
                self.assertIn(f"[{expected}]", summary)
                self.assertNotIn("fake-secret", summary)
                self.assertNotIn("sensitive-provider", summary)

    def test_wrapped_sdk_error_is_preserved(self):
        wrapper = ConnectionError("private")
        wrapper.__cause__ = ProviderError(401)
        self.assertEqual(classify_error(wrapper), "AUTH")
        wrapper.__cause__.__context__ = wrapper
        self.assertEqual(classify_error(wrapper), "AUTH")

    def test_nested_body_code_wins_over_generic_429(self):
        error = ProviderError(429)
        error.body = {"error": {"code": "credit_balance_exhausted", "message": "secret"}}
        self.assertEqual(classify_error(error), "CREDITS")

    def test_local_failures_are_safe(self):
        for error, expected in [(TimeoutError(),"TIMEOUT"),(ImportError(),"DEPENDENCY"),
            (ReaderOutputError(),"OUTPUT"),(ConnectionError(),"CONNECTION"),(ValueError("secret"),"UNKNOWN")]:
            self.assertEqual(classify_error(error), expected)
            self.assertNotIn("secret", safe_error_summary(error))

    def test_placeholders_are_not_sent_to_provider(self):
        with patch.dict(os.environ, {"SAHYOGI_READER":"crewai", "OPENAI_API_KEY":"YOUR_API_KEY", "OPENAI_MODEL":"gpt-6.1-sol"}):
            result = read_reply("Which documents?")
        self.assertEqual(result.engine,"unavailable")
        self.assertIn("[CONFIG]",result.summary)

    def test_default_check_never_calls_reader_or_reveals_key(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"OPENAI_API_KEY":"private-test-key", "OPENAI_MODEL":"private-model"}), patch("check_reader.read_reply") as reader, redirect_stdout(output):
            self.assertEqual(main([]),0)
        reader.assert_not_called()
        self.assertNotIn("private-test-key",output.getvalue())
        self.assertNotIn("private-model",output.getvalue())

    def test_test_flag_forces_real_mode_and_restores_it(self):
        output = io.StringIO()
        def fake(text):
            print("sensitive-framework-output")
            self.assertEqual(os.environ["SAHYOGI_READER"],"crewai")
            return Reading("DOCUMENTS_ROUTE","Synthetic summary",engine="crewai")
        with patch.dict(os.environ, {"SAHYOGI_READER":"demo"}), patch("check_reader.read_reply",side_effect=fake), redirect_stdout(output):
            self.assertEqual(main(["--test"]),0)
            self.assertEqual(os.environ["SAHYOGI_READER"],"demo")
        self.assertNotIn("sensitive-framework-output",output.getvalue())

    def test_empty_crewai_result_is_output_failure_without_guessing_other_values(self):
        empty=ValueError('Invalid response from LLM call - None or empty.')
        wrapper=RuntimeError('private wrapper');wrapper.__cause__=empty
        self.assertEqual(classify_error(wrapper),'OUTPUT')
        self.assertEqual(classify_error(ValueError('other private failure')),'UNKNOWN')
        self.assertNotIn('private',safe_error_summary(wrapper,component='barrier'))

    def test_component_names_do_not_call_every_failure_reader(self):
        for component,label in [('reader','Reader'),('barrier','Barrier Assistant'),('followup','Follow-up Agent')]:
            summary=safe_error_summary(TimeoutError('private'),component=component)
            self.assertIn(label,summary);self.assertIn('[TIMEOUT]',summary);self.assertNotIn('private',summary)
        self.assertNotIn('private',safe_error_summary(TimeoutError(),component='private'))

    def test_bounded_timeout_defaults_and_invalid_values(self):
        with patch.dict(os.environ,{'SAHYOGI_API_TIMEOUT_SECONDS':''}):
            self.assertEqual(api_timeout_seconds('sarvam'),60)
            self.assertEqual(api_timeout_seconds('openai'),20)
            self.assertEqual(api_timeout_seconds('gemini'),20)
        for raw in ['10','90','120']:
            with patch.dict(os.environ,{'SAHYOGI_API_TIMEOUT_SECONDS':raw}):
                self.assertEqual(api_timeout_seconds('sarvam'),int(raw))
        for raw in ['0','9','121','60.5','private-invalid-value']:
            with patch.dict(os.environ,{'SAHYOGI_API_TIMEOUT_SECONDS':raw}):
                with self.assertRaises(ReaderConfigurationError) as ctx:api_timeout_seconds('sarvam')
                self.assertIn('[CONFIG]',safe_error_summary(ctx.exception))
                if raw.startswith('private'):self.assertNotIn(raw,safe_error_summary(ctx.exception))

    def test_agent_selection_without_test_makes_no_api_call(self):
        with patch('check_reader.read_reply') as reader,patch('check_reader.run_care_agent') as care,redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--agent','all']),0)
        reader.assert_not_called();care.assert_not_called()

    def test_barrier_diagnostic_uses_fixed_sample_and_no_reader_call_or_database(self):
        output=io.StringIO()
        def fake(kind,payload):
            self.assertEqual(kind,'barrier');self.assertEqual(os.environ['SAHYOGI_READER'],'crewai')
            self.assertEqual(payload['messages'],['Which documents do we need for palliative care?'])
            self.assertNotIn('request_id',payload)
            print('private framework output')
            return CareResult('crewai',demo_care(kind,payload))
        with patch.dict(os.environ,{'SAHYOGI_READER':'demo'}),patch('check_reader.read_reply') as reader,patch('check_reader.run_care_agent',side_effect=fake) as care,patch('sqlite3.connect',side_effect=AssertionError('No database in diagnostics')),redirect_stdout(output):
            self.assertEqual(main(['--test','--agent','barrier']),0)
            self.assertEqual(os.environ['SAHYOGI_READER'],'demo')
        reader.assert_not_called();care.assert_called_once()
        self.assertIn('Barrier Assistant',output.getvalue());self.assertIn('DOCUMENTS',output.getvalue())
        self.assertNotIn('private framework',output.getvalue())

    def test_followup_diagnostic_does_not_claim_real_staff_approval(self):
        result=CareResult('crewai',demo_care('followup',{'confirmed_barrier':{'code':'DOCUMENTS'}}))
        output=io.StringIO()
        with patch('check_reader.run_care_agent',return_value=result) as care,redirect_stdout(output):
            self.assertEqual(main(['--test','--agent','followup']),0)
        self.assertEqual(care.call_args.args[1]['medicine_status'],'NOT_CHECKED')
        self.assertIn('Clinical team approval is still required',output.getvalue())

    def test_all_diagnostic_reports_stage_failure_and_restores_mode(self):
        def fake(kind,payload):
            if kind=='barrier':raise TimeoutError('private provider detail')
            return CareResult('crewai',demo_care(kind,payload))
        output=io.StringIO()
        with patch.dict(os.environ,{'SAHYOGI_READER':'demo'}),patch('check_reader.read_reply',return_value=Reading('DOCUMENTS_ROUTE','Synthetic',engine='crewai')),patch('check_reader.run_care_agent',side_effect=fake),redirect_stdout(output):
            self.assertEqual(main(['--test','--agent','all']),2)
            self.assertEqual(os.environ['SAHYOGI_READER'],'demo')
        self.assertIn('[TIMEOUT] Barrier Assistant',output.getvalue())
        self.assertIn('Agent: Follow-up Agent',output.getvalue());self.assertNotIn('private provider',output.getvalue())

    def test_prompted_key_is_hidden_and_environment_is_restored(self):
        output=io.StringIO()
        def fake(kind,payload):
            self.assertEqual(os.environ['SAHYOGI_PROVIDER'],'sarvam')
            self.assertEqual(os.environ['SARVAM_API_KEY'],'private-prompted-key')
            self.assertEqual(os.environ['SARVAM_MODEL'],'sarvam-105b')
            return CareResult('crewai',demo_care(kind,payload))
        with patch.dict(os.environ,{'SAHYOGI_PROVIDER':'openai','SARVAM_API_KEY':'old-private-key','SARVAM_MODEL':''}),patch('check_reader.getpass.getpass',return_value='private-prompted-key'),patch('check_reader.run_care_agent',side_effect=fake),redirect_stdout(output):
            self.assertEqual(main(['--test','--agent','barrier','--provider','sarvam','--prompt-key']),0)
            self.assertEqual(os.environ['SAHYOGI_PROVIDER'],'openai')
            self.assertEqual(os.environ['SARVAM_API_KEY'],'old-private-key')
            self.assertEqual(os.environ['SARVAM_MODEL'],'')
        self.assertNotIn('private-prompted-key',output.getvalue());self.assertNotIn('old-private-key',output.getvalue())


if __name__ == "__main__":
    unittest.main()
