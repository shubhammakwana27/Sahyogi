"""Patient-first palliative pipeline: routing, human confirmation and publication gates."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from access_control import Accounts,AccessDenied
from agent import demo_read,Reading
from app import DemoServer
from care_agents import CareResult,demo_care,run_care_agent
from care_flow import CareFlow
from http_test_client import Browser,Forms,TEST_PASSWORD,NEW_PASSWORD
from store import Store,RuleError

DOCS='Which documents do we need for palliative care?'
HAS_CREWAI=importlib.util.find_spec('crewai') is not None


def token():return uuid4().hex

def due():return (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()


class CareFlowTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SAHYOGI_READER':'demo'});self.env.start()
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'care.db';self.store=Store(self.path);self.accounts=Accounts(self.store)
        self.coord=self.accounts.create_user('anita','Anita','coordinator',TEST_PASSWORD,bootstrap=True)
        self.family=self.add('meena','caregiver');self.staff=self.add('staff1','staff')
        self.flow=CareFlow(self.store,self.accounts);self.id=None
    def tearDown(self):self.tmp.cleanup();self.env.stop()
    def add(self,name,role):
        user=self.accounts.create_user(name,name.title(),role,TEST_PASSWORD,creator=self.coord)
        self.accounts.change_password(user,TEST_PASSWORD,NEW_PASSWORD);return user
    def submit(self,message=DOCS,**kw):
        self.id=self.flow.submit(self.family,{'message':message,'topic':'documents','consent':'yes'},token(),**kw)
        return self.id
    def r(self):return self.flow.detail(self.id,self.coord)
    def assign(self):self.flow.assign(self.id,self.coord,self.r()['version'],token(),'staff1')
    def checks(self,medicine='NOT_CHECKED',documents='VERIFIED'):
        self.flow.checks(self.id,self.staff,self.r()['version'],token(),{'medicine_status':medicine,'document_status':documents,
            'checked_plan_ref':'DEMO-PLAN','clinician_source':'Demo authorised clinician','clinician_checked':'yes',
            'document_details':'Demo document list','document_source':'Demo authorised service'})
    def confirm(self,code='DOCUMENTS',**kw):
        self.flow.confirm(self.id,self.staff,self.r()['version'],token(),{'code':code,'description':'Clinical team checked the actual '+code.lower()+' barrier.',
            'review_note':'Read original question and clarified with the family.','barrier_checked':'yes'},**kw)
    def approval_data(self,**extra):
        run=[x for x in self.r()['runs'] if x['kind']=='followup'][-1]
        return {'run_id':run['id'],'patient_message':'STAFF CHECKED: Please bring the demo document reference. Reply here if you need help.',
            'tasks':'Check the family has the instructions\nRecord the actual follow-up result','assigned_to':'anita','due_at':due(),'staff_approved':'yes',**extra}
    def approve(self,**extra):self.flow.approve(self.id,self.staff,self.r()['version'],token(),self.approval_data(**extra))
    def ready(self,code='DOCUMENTS'):
        self.submit('We collected it.' if code=='COLLECTION_REPORTED' else DOCS);self.assign();self.checks();self.confirm(code)

    def test_patient_can_start_without_an_approved_plan_and_reader_then_barrier_run(self):
        calls=[]
        def reader(text):calls.append('reader');return demo_read(text)
        def agent(kind,payload):calls.append(kind);return CareResult('demo',demo_care(kind,payload))
        self.submit(reader=reader,agent=agent)
        r=self.r();self.assertEqual(calls,['reader','barrier'])
        self.assertEqual(r['status'],'STAFF_CONFIRM_BARRIER');self.assertEqual(r['route'],'COORDINATOR')
        self.assertEqual(r['medicine_status'],'NOT_CHECKED');self.assertIsNone(r['active_step_id']);self.assertFalse(r['checks'])
        self.assertEqual(r['messages'][0]['body'],DOCS)
        self.assertEqual(r['runs'][0]['kind'],'barrier')

    def test_medicine_request_routes_to_staff_without_ai_approving_medicine(self):
        self.submit('We need approval for the medicine prescribed in our palliative care plan.')
        self.assertEqual(self.r()['route'],'STAFF');self.assertFalse(self.r()['review_required'])
        self.assertEqual(self.r()['medicine_status'],'NOT_CHECKED')
        self.assertEqual(self.r()['runs'][0]['output']['barriers'][0]['code'],'MEDICINE_APPROVAL')

    def test_followup_waits_for_staff_confirmed_barrier_and_coordinator_cannot_confirm(self):
        self.submit();self.assign()
        with self.assertRaises(RuleError):self.flow.run_agent(self.id,'followup',self.r()['version'],user_id=self.staff,token=token())
        data={'code':'DOCUMENTS','description':'Actual documents barrier','review_note':'Checked.','barrier_checked':'yes'}
        with self.assertRaises(AccessDenied):self.flow.confirm(self.id,self.coord,self.r()['version'],token(),data)
        seen=[]
        def agent(kind,payload):seen.append((kind,payload));return CareResult('demo',demo_care(kind,payload))
        self.confirm(agent=agent)
        self.assertEqual(seen[0][0],'followup')
        self.assertEqual(seen[0][1]['confirmed_barrier']['description'],'Clinical team checked the actual documents barrier.')
        self.assertNotIn('messages',seen[0][1])
        self.assertIsNone(self.r()['active_step_id']);self.assertEqual(self.r()['status'],'AWAITING_STAFF_APPROVAL')

    def test_checks_require_authorised_sources_and_are_never_model_decisions(self):
        self.submit();self.assign()
        bad={'medicine_status':'PLAN_VERIFIED','document_status':'NOT_CHECKED','checked_plan_ref':'DEMO'}
        with self.assertRaises(RuleError):self.flow.checks(self.id,self.staff,self.r()['version'],token(),bad)
        with self.assertRaises(AccessDenied):self.flow.checks(self.id,self.coord,self.r()['version'],token(),{**bad,'clinician_source':'Doctor','clinician_checked':'yes'})
        self.checks('PLAN_VERIFIED')
        self.assertEqual(self.r()['medicine_status'],'PLAN_VERIFIED');self.assertEqual(self.r()['checks'][-1]['actor_id'],self.staff)
        self.assertEqual(self.r()['document_status'],'VERIFIED')

    def test_only_staff_explicit_approval_publishes_exact_checked_text(self):
        self.ready()
        for user in [self.coord,self.family]:
            with self.assertRaises(AccessDenied):self.flow.approve(self.id,user,self.r()['version'],token(),self.approval_data())
        with self.assertRaises(RuleError):self.approve(staff_approved='')
        self.approve()
        r=self.r();step=next(s for s in r['steps'] if s['id']==r['active_step_id'])
        self.assertEqual(step['patient_message'],self.approval_data()['patient_message'])
        self.assertEqual(step['actor_id'],self.staff);self.assertEqual(step['assigned_to'],self.coord)
        self.assertEqual(r['status'],'FOLLOWUP_APPROVED')

    def test_staff_fact_change_invalidates_an_old_followup_draft(self):
        self.ready();old=self.approval_data();self.checks('PLAN_VERIFIED')
        with self.assertRaises(RuleError):self.flow.approve(self.id,self.staff,self.r()['version'],token(),old)
        self.flow.run_agent(self.id,'followup',self.r()['version'],user_id=self.staff,token=token())
        self.approve();self.assertTrue(self.r()['active_step_id'])

    def test_clinical_and_mixed_messages_hold_review_until_staff_record_it(self):
        self.submit('We need help with travel and the patient has pain.');self.assign()
        self.assertTrue(self.r()['review_required']);self.assertEqual(self.r()['route'],'STAFF')
        with self.assertRaises(RuleError):self.confirm('TRAVEL')
        with self.assertRaises(AccessDenied):self.flow.resolve_review(self.id,self.coord,self.r()['version'],token(),'Checked.','yes')
        self.flow.resolve_review(self.id,self.staff,self.r()['version'],token(),'Sample care team review recorded.','yes')
        self.confirm('TRAVEL');self.assertEqual(self.r()['status'],'AWAITING_STAFF_APPROVAL')

    def test_reader_failure_keeps_original_and_staff_review_without_running_another_model(self):
        calls=[]
        def reader(text):raise RuntimeError('private-provider-body')
        def agent(*args):calls.append(args);self.fail('Do not make another paid request after reader failure')
        self.submit(reader=reader,agent=agent)
        r=self.r();self.assertEqual(r['messages'][0]['body'],DOCS);self.assertEqual(r['messages'][0]['reading']['engine'],'unavailable')
        self.assertTrue(r['review_required']);self.assertFalse(r['runs']);self.assertNotIn('private-provider',str(r))

    def test_failed_followup_can_be_replaced_with_a_manual_draft_then_separate_approval(self):
        self.submit();self.assign()
        self.confirm(agent=lambda *args:CareResult('unavailable',error='[CREDITS] API credits exhausted.'))
        self.assertEqual(self.r()['status'],'FOLLOWUP_FAILED');self.assertIsNone(self.r()['active_step_id'])
        self.flow.manual_draft(self.id,self.staff,self.r()['version'],token(),{'tasks':'Check actual document requirements','patient_message':'Clinical team are checking your document question.'})
        self.assertEqual(self.r()['runs'][-1]['engine'],'manual');self.assertIsNone(self.r()['active_step_id'])
        self.approve();self.assertEqual(self.r()['status'],'FOLLOWUP_APPROVED')

    def test_duplicate_submit_confirm_and_approval_do_not_repeat_agent_calls_or_steps(self):
        counts=[]
        def agent(kind,payload):counts.append(kind);return CareResult('demo',demo_care(kind,payload))
        t=token();data={'topic':'documents','message':DOCS,'consent':'yes'}
        self.id=self.flow.submit(self.family,data,t,agent=agent)
        self.assertEqual(self.flow.submit(self.family,data,t,agent=agent),self.id);self.assertEqual(counts,['barrier'])
        self.assign();v=self.r()['version'];t=token();data={'code':'DOCUMENTS','description':'Needs document details','review_note':'Clinical team checked.','barrier_checked':'yes'}
        self.flow.confirm(self.id,self.staff,v,t,data,agent=agent);self.flow.confirm(self.id,self.staff,v,t,data,agent=agent)
        self.assertEqual(counts,['barrier','followup'])
        v=self.r()['version'];t=token();data=self.approval_data()
        self.flow.approve(self.id,self.staff,v,t,data);self.flow.approve(self.id,self.staff,v,t,data)
        self.assertEqual(len(self.r()['steps']),1)

    def test_case_change_during_followup_marks_result_stale_without_overwriting_work(self):
        self.submit();self.assign()
        def agent(kind,payload):
            self.checks('PLAN_VERIFIED')
            return CareResult('demo',demo_care(kind,payload))
        self.confirm(agent=agent)
        self.assertEqual(self.r()['runs'][-1]['status'],'STALE');self.assertEqual(self.r()['medicine_status'],'PLAN_VERIFIED')
        with self.assertRaises(RuleError):self.approve()

    def test_withdrawal_during_reading_preserves_stop_and_makes_no_barrier_call(self):
        def reader(text):
            rid=self.flow.list_requests(self.family)[0]['id']
            r=self.flow.detail(rid,self.family)
            self.flow.withdraw(rid,self.family,r['version'],token())
            return demo_read(text)
        self.submit(reader=reader,agent=lambda *args:self.fail('Stopped request must not start barrier analysis'))
        self.assertEqual(self.r()['status'],'STOPPED');self.assertFalse(self.r()['consent'])
        with self.assertRaises(RuleError):self.flow.message(self.id,self.family,'More information',self.r()['version'],token())

    def test_new_family_message_hides_old_instructions_and_preserves_previous_records(self):
        self.ready();self.approve();old=self.r()['active_step_id']
        self.flow.message(self.id,self.family,'We need help with travel.',self.r()['version'],token())
        self.assertIsNone(self.r()['active_step_id']);self.assertEqual(self.r()['steps'][0]['id'],old)
        self.assertIsNone(self.r()['current_barrier_id'])
        with self.assertRaises(RuleError):self.flow.run_agent(self.id,'followup',self.r()['version'],user_id=self.staff,token=token())
        self.assertEqual(len(self.r()['messages']),2)
        with self.assertRaises(RuleError):self.flow.mark_read(self.id,self.family,self.r()['version'],token(),old)

    def test_approved_step_read_is_not_collection_proof_and_only_owner_records_progress(self):
        self.ready();self.approve();r=self.r()
        self.flow.mark_read(self.id,self.family,r['version'],token(),r['active_step_id'])
        self.assertEqual(self.r()['status'],'FOLLOWUP_APPROVED');self.assertFalse(self.r()['resolutions'])
        with self.assertRaises(AccessDenied):self.flow.progress(self.id,self.staff,self.r()['version'],token(),'Not my assigned task.')
        self.flow.progress(self.id,self.coord,self.r()['version'],token(),'Called the caregiver and checked the actual question.')
        self.assertEqual(self.r()['status'],'FOLLOWUP_IN_PROGRESS')

    def test_collection_claim_needs_matching_full_authorised_proof_before_resolution(self):
        self.ready('COLLECTION_REPORTED');self.approve()
        data={'resolution_note':'Clinical team verified the sample record.','resolved_checked':'yes'}
        with self.assertRaises(RuleError):self.flow.close(self.id,self.staff,self.r()['version'],token(),data)
        data.update(proof_source='Demo authorised pharmacy',proof_reference='DISP-DEMO-1',proof_authority='yes',proof_match='yes',proof_full='yes')
        with self.assertRaises(RuleError):self.flow.close(self.id,self.staff,self.r()['version'],token(),data)
        self.checks('PLAN_VERIFIED')
        self.flow.run_agent(self.id,'followup',self.r()['version'],user_id=self.staff,token=token())
        self.approve()
        self.flow.close(self.id,self.staff,self.r()['version'],token(),data)
        self.assertEqual(self.r()['status'],'CLOSED');self.assertTrue(self.r()['resolutions'][0]['collection_verified'])

    def test_document_and_medicine_resolution_require_recorded_staff_checks(self):
        self.submit();self.assign();self.confirm();self.approve()
        data={'resolution_note':'Document issue checked.','resolved_checked':'yes'}
        with self.assertRaises(RuleError):self.flow.close(self.id,self.staff,self.r()['version'],token(),data)
        self.checks();self.flow.run_agent(self.id,'followup',self.r()['version'],user_id=self.staff,token=token());self.approve()
        self.flow.close(self.id,self.staff,self.r()['version'],token(),data)
        self.assertFalse(self.r()['resolutions'][0]['collection_verified'])

    def test_request_and_agent_drafts_persist_after_restart_and_old_cases_remain(self):
        legacy=self.store.create_practice('travel',token(),principal=self.coord)
        self.ready();before=self.r();reopened=CareFlow(Store(self.path),self.accounts)
        self.assertEqual(reopened.detail(self.id,self.coord),before)
        self.assertEqual(self.store.detail(legacy)['practice_example'],'travel')

    def test_unassigned_accounts_and_role_spoofing_cannot_read_or_change_request(self):
        self.submit();stranger=self.add('stranger','caregiver');other_staff=self.add('otherstaff','staff')
        for uid in [stranger,self.staff,other_staff]:
            self.assertEqual(self.flow.list_requests(uid),[])
            with self.assertRaises(AccessDenied):self.flow.detail(self.id,uid)
        with self.assertRaises(AccessDenied):self.flow.assign(self.id,self.family,self.r()['version'],token(),'staff1')
        self.assign()
        with self.assertRaises(AccessDenied):self.flow.checks(self.id,self.family,self.r()['version'],token(),{'medicine_status':'NOT_CHECKED','document_status':'NOT_CHECKED'})

    def test_shared_family_access_can_be_revoked_without_changing_approved_instructions(self):
        patient=self.add('ravi','patient');self.ready();self.approve();before=self.r()['active_step_id']
        self.flow.assign(self.id,self.coord,self.r()['version'],token(),'ravi',family=True)
        self.assertEqual(self.flow.detail(self.id,patient)['active_step_id'],before)
        self.flow.assign(self.id,self.coord,self.r()['version'],token(),'ravi',family=True,remove=True)
        with self.assertRaises(AccessDenied):self.flow.detail(self.id,patient)
        self.assertEqual(self.r()['active_step_id'],before)


class CareHttpTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SAHYOGI_READER':'demo'});self.env.start()
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'http.db')
        self.server=DemoServer(('127.0.0.1',0),self.store);self.accounts=self.server.accounts
        self.coord=self.accounts.create_user('anita','Anita','coordinator',TEST_PASSWORD,bootstrap=True)
        self.family=self.accounts.create_user('meena','Meena','caregiver',TEST_PASSWORD,creator=self.coord)
        self.staff=self.accounts.create_user('staff1','Clinical team','staff',TEST_PASSWORD,creator=self.coord)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.c=Browser(self.server).login('anita',TEST_PASSWORD)
        self.f=Browser(self.server).login('meena',TEST_PASSWORD,NEW_PASSWORD)
        self.s=Browser(self.server).login('staff1',TEST_PASSWORD,NEW_PASSWORD)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup();self.env.stop()
    def submit(self,text=DOCS):
        status,h,body=self.f.post('/care/submit',{'token':token(),'topic':'documents','message':text,'consent':'yes'})
        self.assertEqual(status,303,body);self.id=h['Location'].split('id=')[1];return h['Location']
    def r(self):return self.server.care.detail(self.id,self.coord)
    def payload(self,**data):return {'request_id':self.id,'version':self.r()['version'],'token':token(),**data}
    def test_patient_first_login_and_question_box_are_the_default_entry(self):
        anonymous=Browser(self.server)
        self.assertIn('Patient or caregiver sign in',anonymous.request('GET','/login')[2])
        self.assertIn('Clinical team or coordinator sign in',anonymous.request('GET','/login?team=1')[2])
        html=self.f.request('GET','/')[2]
        self.assertIn('Ask your care team',html);self.assertIn('Your question or message',html)
        self.assertNotIn('Run Barrier Assistant',html)
        self.assertEqual(self.c.post('/care/submit',{'token':token(),'topic':'documents','message':DOCS,'consent':'yes'})[0],403)

    def test_full_question_staff_confirmation_followup_approval_and_family_reply_flow(self):
        path=self.submit()
        family_html=self.f.request('GET',path)[2]
        self.assertIn('No current clinical team-approved next step',family_html)
        self.assertNotIn('Agent 2: possible barriers',family_html)
        self.assertIn('Agent 2: possible barriers',self.c.request('GET',path+'&view=barrier')[2])
        self.assertEqual(self.c.post('/care/assign',self.payload(username='staff1'))[0],303)
        staff_html=self.s.request('GET',path+'&view=barrier')[2];parser=Forms();parser.feed(staff_html)
        confirm=next(f for f in parser.forms if f['action']=='/care/confirm')
        status,_,body=self.s.request('POST','/care/confirm',{**confirm['hidden'],'code':'DOCUMENTS','description':'The caregiver needs the checked document list.','review_note':'Read the family request.','barrier_checked':'yes'})
        self.assertEqual(status,303,body)
        self.assertEqual(self.r()['status'],'AWAITING_STAFF_APPROVAL')
        family_html=self.f.request('GET',path)[2]
        self.assertNotIn('Draft administrative follow-up',family_html)
        staff_html=self.s.request('GET',path+'&view=followup')[2];parser=Forms();parser.feed(staff_html)
        approve=next(f for f in parser.forms if f['action']=='/care/approve')
        local=(datetime.now(timezone(timedelta(hours=5,minutes=30)))+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
        status,_,body=self.s.request('POST','/care/approve',{**approve['hidden'],'tasks':'Check the actual document requirements','patient_message':'STAFF APPROVED: Please tell us which documents you currently have.','assigned_to':'anita','due_at':local,'staff_approved':'yes'})
        self.assertEqual(status,303,body)
        family_html=self.f.request('GET',path)[2]
        self.assertIn('STAFF APPROVED: Please tell us',family_html);self.assertNotIn('Read the family request.',family_html)
        step=self.r()['active_step_id'];self.assertEqual(self.f.post('/care/read',self.payload(step_id=step))[0],303)
        self.assertIn('Family read confirmations: 1',self.c.request('GET',path)[2])
        self.assertEqual(self.c.post('/care/progress',self.payload(note='Contacted caregiver and clarified the documents.'))[0],303)
        self.assertEqual(self.f.post('/care/message',self.payload(message='We need help with travel.'))[0],303)
        self.assertIsNone(self.r()['active_step_id'])

    def test_role_and_csrf_bypasses_cannot_publish_or_approve_medicine(self):
        self.submit();self.c.post('/care/assign',self.payload(username='staff1'))
        for path in ['/care/confirm','/care/approve','/care/checks','/care/review']:
            status,_,_=self.f.post(path,self.payload(role='staff',medicine_status='PLAN_VERIFIED',document_status='VERIFIED'))
            self.assertIn(status,[400,403]);self.assertIsNone(self.r()['active_step_id']);self.assertEqual(self.r()['medicine_status'],'NOT_CHECKED')
        self.assertEqual(self.f.post('/care/message',self.payload(csrf='wrong',message='We collected it.'))[0],403)
        self.assertEqual(len(self.r()['messages']),1)
        self.assertEqual(self.c.post('/care/checks',self.payload(medicine_status='NOT_CHECKED',document_status='NOT_CHECKED'))[0],403)

    def test_family_cannot_read_another_request_by_guessing_its_id(self):
        path=self.submit()
        uid=self.accounts.create_user('ravi','Ravi','patient',TEST_PASSWORD,creator=self.coord)
        outsider=Browser(self.server).login('ravi',TEST_PASSWORD,NEW_PASSWORD)
        self.assertEqual(outsider.request('GET',path)[0],404)
        self.assertEqual(outsider.post('/care/message',self.payload(message='Forged'))[0],403)
        self.assertNotIn(self.id,outsider.request('GET','/')[2])

    def test_html_escaping_and_no_raw_internal_drafts_in_family_page(self):
        path=self.submit('<script>alert(1)</script>')
        page=self.f.request('GET',path+'&view=messages')[2]
        self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)
        self.assertNotIn('Saved clinical team history',page);self.assertNotIn('AGENT_FINISHED',page)

    def test_unknown_routes_gets_and_withdrawn_permission_do_not_execute_actions(self):
        self.submit()
        self.assertEqual(self.f.request('GET','/care/approve')[0],404)
        self.assertEqual(self.f.post('/care/unknown',self.payload())[0],403)
        self.assertEqual(self.f.post('/care/withdraw',self.payload())[0],303)
        self.assertEqual(self.f.post('/care/message',self.payload(message='More'))[0],400)
        self.assertEqual(self.r()['status'],'STOPPED')


@unittest.skipUnless(HAS_CREWAI,'Install requirements.txt for real CrewAI tests')
class PalliativeCrewTests(unittest.TestCase):
    def test_same_three_roles_have_no_action_tools_or_delegation(self):
        from crewai_reader import build_reader_crew
        from crewai_assistants import build_care_crew
        from test_crewai_integration import OfflineLLM
        crews=[build_reader_crew(OfflineLLM()),build_care_crew('barrier',OfflineLLM()),build_care_crew('followup',OfflineLLM())]
        self.assertEqual(len({c.agents[0].role for c in crews}),3)
        for c in crews:
            self.assertEqual(len(c.agents),1);self.assertEqual(len(c.tasks),1);self.assertEqual(c.agents[0].tools,[])
            self.assertFalse(c.agents[0].allow_delegation);self.assertFalse(c.memory);self.assertFalse(c.planning)

    def test_both_palliative_roles_execute_native_sarvam_with_strict_schemas(self):
        from crewai_assistants import run_care_crew
        from test_sarvam import SarvamIntegrationTests
        helper=SarvamIntegrationTests('test_real_crew_marathi_request_uses_sarvam_host_header_and_strict_schema')
        payloads={'barrier':demo_care('barrier',{'reader_category':'DOCUMENTS_ROUTE'}),
                  'followup':demo_care('followup',{'confirmed_barrier':{'code':'DOCUMENTS'}})}
        for kind,payload in payloads.items():
            with helper.transport(payload) as (requests,_):
                result=run_care_crew(kind,{'reader_category':'DOCUMENTS_ROUTE','confirmed_barrier':{'code':'DOCUMENTS','description':'Clinical team confirmed'}},model='sarvam-105b',api_key='synthetic-key',provider='sarvam')
            self.assertEqual(result,payload)
            for request in requests:
                self.assertEqual(request.url.host,'api.sarvam.ai');self.assertEqual(request.url.path,'/v2/chat/completions')
                schema=json.loads(request.content)['response_format']['json_schema']
                self.assertTrue(schema['strict']);self.assertEqual(set(schema['schema']['properties']),set(payload))

    def test_invalid_new_output_is_rejected_without_clinical_or_publication_actions(self):
        from care_agents import validate_care
        from reader_errors import ReaderOutputError
        for kind,payload in [('barrier',{'summary':'Approve medicine','barriers':[],'clinical_concern':False,'uncertain':False}),
                             ('followup',{'summary':'Draft','staff_tasks':['Check'],'patient_message':'Draft','medicine_status':'APPROVED'})]:
            with self.assertRaises(ReaderOutputError):validate_care(kind,payload)


if __name__=='__main__':unittest.main()
