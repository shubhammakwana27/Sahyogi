"""Memory-only key replacement, authenticated forms and failed-message recovery."""
from concurrent.futures import ThreadPoolExecutor
import io
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from threading import Event,Thread
import unittest
from unittest.mock import patch
from uuid import uuid4

from access_control import AccessDenied
from agent import Reading,read_reply,demo_read
from agent_settings import api_timeout_seconds
from app import DemoServer
from care_agents import run_care_agent,demo_care
from http_test_client import Browser,Forms,TEST_PASSWORD,NEW_PASSWORD
from runtime_settings import RuntimeSettings,current_settings,settings_context
from store import Store,RuleError

KEY='synthetic-replacement-key'
ENV={'SAHYOGI_READER':'demo','SAHYOGI_PROVIDER':'sarvam','SARVAM_API_KEY':'synthetic-startup-key',
     'SARVAM_MODEL':'sarvam-105b','SAHYOGI_API_TIMEOUT_SECONDS':''}


def fields(version=0,**kw):
    return {'settings_version':str(version),'provider':'sarvam','model':'sarvam-105b',
            'mode':'crewai','api_key':KEY,'timeout_seconds':'60',**kw}


class RuntimeSettingsTests(unittest.TestCase):
    def setUp(self):self.env=patch.dict(os.environ,ENV);self.env.start();self.runtime=RuntimeSettings()
    def tearDown(self):self.env.stop()

    def test_public_values_and_repr_never_include_the_key(self):
        self.runtime.apply(fields())
        self.assertNotIn(KEY,json.dumps(self.runtime.public()))
        self.assertNotIn(KEY,repr(self.runtime.snapshot()))
        self.assertEqual(os.environ['SARVAM_API_KEY'],ENV['SARVAM_API_KEY'])
        self.assertEqual(self.runtime.snapshot().api_key,KEY)

    def test_blank_keeps_same_provider_key_but_not_on_provider_switch(self):
        self.runtime.apply(fields());self.runtime.apply(fields(1,api_key='',timeout_seconds='90'))
        self.assertEqual(self.runtime.snapshot().api_key,KEY)
        with self.assertRaises(ValueError):self.runtime.apply(fields(2,provider='openai',model='test-model',api_key=''))
        self.assertEqual(self.runtime.snapshot().provider,'sarvam')

    def test_stale_and_invalid_updates_leave_active_settings_intact(self):
        self.runtime.apply(fields());before=self.runtime.snapshot()
        for changes in [{'settings_version':'0'},{'provider':'untrusted'},{'api_key':'bad\nheader'},
                        {'timeout_seconds':'999'},{'model':'<script>'},{'model':'gemini/test'},
                        {'mode':'unsupported'},{'api_key':'YOUR_API_KEY'}]:
            with self.assertRaises(ValueError):self.runtime.apply(fields(1,**changes))
            self.assertEqual(self.runtime.snapshot(),before)

    def test_forget_removes_override_without_resurrecting_startup_key(self):
        self.runtime.apply(fields());self.runtime.forget(1)
        self.assertEqual(self.runtime.snapshot().api_key,'');self.assertFalse(self.runtime.public()['key_set'])
        self.assertEqual(RuntimeSettings().snapshot().api_key,ENV['SARVAM_API_KEY'])

    def test_server_instances_and_request_snapshots_are_isolated(self):
        other=RuntimeSettings();other.apply(fields(api_key='other-synthetic-key'))
        self.runtime.apply(fields());snapshot=self.runtime.snapshot()
        def worker(config):
            with settings_context(config):return current_settings().api_key,api_timeout_seconds()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(worker,[snapshot,other.snapshot()])),[(KEY,60),('other-synthetic-key',60)])
        with settings_context(snapshot):
            self.runtime.apply(fields(1,api_key='rotated-synthetic-key',timeout_seconds='90'))
            self.assertEqual(current_settings().api_key,KEY)
        self.assertEqual(self.runtime.snapshot().api_key,'rotated-synthetic-key')
        self.assertEqual(current_settings().api_key,ENV['SARVAM_API_KEY'])

    def test_new_key_reaches_all_three_roles_and_legacy_assistant(self):
        self.runtime.apply(fields())
        payload={'category':'DOCUMENTS_ROUTE','summary':'Document question','clinical_concern':False,'uncertain':False}
        with settings_context(self.runtime.snapshot()),patch('crewai_reader.run_reader',return_value=payload) as reader,patch('crewai_assistants.run_care_crew',side_effect=lambda kind,p,**kw:demo_care(kind,p)) as care,patch('crewai_assistants.run_crew_assistant',return_value={'summary':'Safe','checks':['Check source'],'missing_items':[]}) as legacy:
            self.assertEqual(read_reply('Which documents do we need for palliative care?').engine,'crewai')
            self.assertEqual(run_care_agent('barrier',{'reader_category':'DOCUMENTS_ROUTE'}).engine,'crewai')
            self.assertEqual(run_care_agent('followup',{'confirmed_barrier':{'code':'DOCUMENTS'}}).engine,'crewai')
            from assistants import run_assistant
            self.assertEqual(run_assistant('barrier',{}).engine,'crewai')
        for call in [reader.call_args,*care.call_args_list,legacy.call_args]:
            self.assertEqual(call.kwargs['api_key'],KEY);self.assertEqual(call.kwargs['provider'],'sarvam')
        self.assertEqual(os.environ['SARVAM_API_KEY'],ENV['SARVAM_API_KEY'])

    def test_connection_test_uses_only_fixed_input_and_deduplicates(self):
        self.runtime.apply(fields());token=uuid4().hex
        def fake(text):
            self.assertEqual(text,'Which documents do we need for palliative care?')
            self.assertEqual(current_settings().api_key,KEY)
            return Reading('DOCUMENTS_ROUTE',KEY,engine='crewai')
        with patch('sqlite3.connect',side_effect=AssertionError('No patient database')):
            self.runtime.test(1,token,reader=fake)
            self.runtime.test(1,token,reader=lambda _:self.fail('Duplicate API call'))
        self.assertIn('succeeded',self.runtime.public()['last_test']);self.assertNotIn(KEY,str(self.runtime.public()))

    def test_connection_failure_never_echoes_provider_body_or_key(self):
        self.runtime.apply(fields())
        self.runtime.test(1,uuid4().hex,reader=lambda _:Reading('UNCLEAR','[AUTH] '+KEY,uncertain=True,engine='unavailable'))
        self.assertIn('[AUTH]',self.runtime.public()['last_test']);self.assertNotIn(KEY,self.runtime.public()['last_test'])
        def broken(_):raise RuntimeError(KEY)
        self.runtime.test(1,uuid4().hex,reader=broken)
        self.assertIn('[UNKNOWN]',self.runtime.public()['last_test']);self.assertNotIn(KEY,self.runtime.public()['last_test'])

    def test_running_test_cannot_certify_a_replacement_key(self):
        self.runtime.apply(fields());started=Event();finish=Event()
        def slow(_):started.set();self.assertTrue(finish.wait(5));return Reading('DOCUMENTS_ROUTE','Safe',engine='crewai')
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(self.runtime.test,1,uuid4().hex,slow)
            self.assertTrue(started.wait(5))
            self.runtime.apply(fields(1,api_key='another-synthetic-key'))
            finish.set();pending.result(5)
        self.assertNotIn('succeeded',self.runtime.public()['last_test'])


class ApiSettingsHttpTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,ENV);self.env.start()
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'app.db'
        self.server=DemoServer(('127.0.0.1',0),Store(self.path));self.accounts=self.server.accounts
        self.admin=self.accounts.create_user('c123','Anita','coordinator',TEST_PASSWORD,bootstrap=True)
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.browser=Browser(self.server).login('c123',TEST_PASSWORD)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup();self.env.stop()
    def user(self,name,role):
        uid=self.accounts.create_user(name,name,role,TEST_PASSWORD,creator=self.admin)
        self.accounts.change_password(uid,TEST_PASSWORD,NEW_PASSWORD)
        return uid,Browser(self.server).login(name,NEW_PASSWORD)
    def apply(self,**kw):return self.browser.post('/api-settings/apply',{**fields(self.server.api_settings.public()['revision']),**kw})

    def test_initial_admin_can_apply_test_and_remove_key_with_blank_password_field(self):
        status,_,page=self.browser.request('GET','/api-settings');self.assertEqual(status,200)
        self.assertIn('name="api_key"',page);self.assertNotIn(ENV['SARVAM_API_KEY'],page)
        self.assertIn('href="/api-settings"',self.browser.request('GET','/')[2])
        self.assertEqual(self.apply()[0],303)
        page=self.browser.request('GET','/api-settings')[2]
        self.assertIn('A key is set',page);self.assertNotIn(KEY,page)
        with patch('agent.read_reply',return_value=Reading('DOCUMENTS_ROUTE','Safe',engine='crewai')) as reader:
            self.assertEqual(self.browser.post('/api-settings/test',{'settings_version':'1','token':uuid4().hex})[0],303)
        reader.assert_called_once();self.assertIn('succeeded',self.browser.request('GET','/api-settings')[2])
        self.assertEqual(self.browser.post('/api-settings/forget',{'settings_version':'1'})[0],303)
        self.assertIn('No active key',self.browser.request('GET','/api-settings')[2])

    def test_nonadmin_roles_cannot_read_change_test_or_remove_key(self):
        for role in ['caregiver','patient','staff','coordinator']:
            _,browser=self.user(role,role)
            self.assertNotIn('href="/api-settings"',browser.request('GET','/')[2])
            self.assertIn(browser.request('GET','/api-settings')[0],[403,404])
            for action in ['apply','test','forget']:
                self.assertEqual(browser.post('/api-settings/'+action,{**fields(),'token':uuid4().hex,'role':'coordinator','is_admin':'1'})[0],403)
        self.assertEqual(self.server.api_settings.public()['revision'],0)

    def test_anonymous_csrf_foreign_origin_and_wrong_method_are_rejected(self):
        self.assertEqual(Browser(self.server).request('GET','/api-settings')[0],303)
        self.assertEqual(self.browser.post('/api-settings/apply',fields(csrf='wrong'))[0],403)
        self.assertEqual(self.browser.request('POST','/api-settings/apply',{'csrf':self.browser.csrf,**fields()},{'Origin':'https://foreign.invalid'})[0],403)
        self.assertEqual(self.browser.request('GET','/api-settings/apply')[0],404)
        self.assertEqual(self.server.api_settings.public()['revision'],0)

    def test_key_is_absent_from_database_errors_and_case_pages(self):
        self.assertEqual(self.apply()[0],303)
        bad=self.apply(api_key=KEY+'\ninvalid')
        self.assertEqual(bad[0],400);self.assertNotIn(KEY,bad[2])
        with self.server.store.connection() as db:
            self.assertNotIn(KEY,'\n'.join(db.iterdump()))
        for route in ['/','/help','/cases','/accounts','/api-settings']:
            self.assertNotIn(KEY,self.browser.request('GET',route)[2])
        self.assertNotIn(KEY.encode(),self.path.read_bytes())

    def test_new_settings_take_effect_on_next_request_without_process_env_changes(self):
        uid,family=self.user('p123','caregiver');self.apply()
        def fake(text,**kw):
            self.assertEqual(kw['api_key'],KEY)
            return {'category':'DOCUMENTS_ROUTE','summary':'Safe','clinical_concern':False,'uncertain':False}
        with patch('crewai_reader.run_reader',side_effect=fake) as reader,patch('crewai_assistants.run_care_crew',side_effect=lambda kind,p,**kw:demo_care(kind,p)):
            status,h,body=family.post('/care/submit',{'token':uuid4().hex,'topic':'documents','message':'Which documents do we need for palliative care?','consent':'yes'})
        self.assertEqual(status,303,body);reader.assert_called_once()
        rid=h['Location'].split('id=')[1]
        self.assertIsNone(self.server.care.detail(rid,self.admin)['active_step_id'])
        self.assertEqual(os.environ['SARVAM_API_KEY'],ENV['SARVAM_API_KEY'])

    @unittest.skipUnless(importlib.util.find_spec('crewai') is not None,'Install requirements.txt for native SDK test')
    def test_browser_connection_test_uses_replacement_key_in_native_sarvam_headers(self):
        from test_sarvam import SarvamIntegrationTests
        self.apply()
        helper=SarvamIntegrationTests('test_real_crew_marathi_request_uses_sarvam_host_header_and_strict_schema')
        with helper.transport() as (requests,_):
            status,_,body=self.browser.post('/api-settings/test',{'settings_version':'1','token':uuid4().hex})
        self.assertEqual(status,303,body);self.assertTrue(requests)
        for request in requests:
            self.assertEqual(request.url.host,'api.sarvam.ai')
            self.assertEqual(request.headers['api-subscription-key'],KEY)
        page=self.browser.request('GET','/api-settings')[2]
        self.assertIn('succeeded',page);self.assertNotIn(KEY,page)

    def test_retry_reader_retains_message_and_failed_result_and_needs_review(self):
        uid,family=self.user('p123','caregiver');staff_id,staff=self.user('staff1','staff')
        self.apply(api_key='synthetic-rejected-key')
        rejection=RuntimeError('private');rejection.status_code=401
        with patch('crewai_reader.run_reader',side_effect=rejection):
            status,h,body=family.post('/care/submit',{'token':uuid4().hex,'topic':'documents','message':'Which documents do we need for palliative care?','consent':'yes'})
        self.assertEqual(status,303,body);rid=h['Location'].split('id=')[1]
        def request():return self.server.care.detail(rid,self.admin)
        self.server.care.assign(rid,self.admin,request()['version'],uuid4().hex,'staff1')
        before=request();self.assertTrue(before['review_required'])
        self.assertIn('Retry Reader on latest saved message',staff.request('GET',h['Location']+'&view=messages')[2])
        self.assertNotIn('Retry Reader on latest saved message',family.request('GET',h['Location']+'&view=messages')[2])
        data={'request_id':rid,'version':str(before['version']),'token':uuid4().hex}
        self.assertEqual(family.post('/care/retry-reader',data)[0],403)
        self.assertEqual(self.browser.post('/care/retry-reader',data)[0],403)
        self.assertEqual(self.apply()[0],303)
        valid={'category':'DOCUMENTS_ROUTE','summary':'Safe','clinical_concern':False,'uncertain':False}
        with patch('crewai_reader.run_reader',return_value=valid) as reader,patch('crewai_assistants.run_care_crew',side_effect=lambda kind,p,**kw:demo_care(kind,p)):
            self.assertEqual(staff.post('/care/retry-reader',data)[0],303)
            self.assertEqual(staff.post('/care/retry-reader',data)[0],303)
        reader.assert_called_once();self.assertEqual(reader.call_args.kwargs['api_key'],KEY);after=request()
        self.assertEqual(after['messages'][0]['body'],before['messages'][0]['body'])
        self.assertEqual(len(after['messages']),1);self.assertEqual(after['messages'][0]['reading']['engine'],'crewai')
        self.assertTrue(after['review_required']);self.assertIsNone(after['active_step_id'])
        self.assertTrue(any(e['kind']=='PREVIOUS_FAILED_READING' and '[AUTH]' in e['detail'] for e in after['events']))

    def test_restart_drops_in_app_key_but_keeps_accounts_and_requests(self):
        self.apply()
        reopened=DemoServer(('127.0.0.1',0),Store(self.path))
        try:
            self.assertEqual(reopened.api_settings.snapshot().api_key,ENV['SARVAM_API_KEY'])
            self.assertEqual(reopened.accounts.user(self.admin)['username'],'c123')
        finally:reopened.server_close()


class BrowserKeyLauncherTests(unittest.TestCase):
    def test_app_option_launches_without_key_prompt_and_prepares_ai_dependencies(self):
        from contextlib import redirect_stdout
        from start_app import main
        with patch.dict(os.environ,{'SAHYOGI_PROVIDER':'sarvam','SARVAM_API_KEY':'','SARVAM_MODEL':''}),patch('start_app.getpass.getpass',side_effect=AssertionError('Key belongs in browser')),patch('start_app.prepare_runtime',return_value='test-python') as runtime,patch('start_app.subprocess.call',return_value=0) as child,redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--mode','app']),0)
        runtime.assert_called_once();self.assertTrue(runtime.call_args.args[1])
        self.assertEqual(child.call_args.kwargs['env']['SAHYOGI_PROVIDER'],'sarvam')
        self.assertEqual(child.call_args.kwargs['env']['SAHYOGI_READER'],'crewai')
        self.assertEqual(child.call_args.kwargs['env']['SARVAM_API_KEY'],'')


if __name__=='__main__':unittest.main()
