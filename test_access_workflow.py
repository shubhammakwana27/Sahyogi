"""PDF requirements: deterministic proof, safe holds, ownership and role privacy."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import os,tempfile,threading,unittest
from unittest.mock import patch,Mock
from uuid import uuid4
from urllib.parse import parse_qs,urlsplit
from access_control import Accounts,AccessDenied
from store import Store,RuleError
from care_flow import CareFlow
from agent import demo_read,validate_reading
from care_safety import clinical_screen,urgent_hint
from pdf_examples import EXAMPLES
from access_workflow import evidence_decision,EVIDENCE_FLAGS
from app import DemoServer
from http_test_client import Browser,Forms,TEST_PASSWORD,NEW_PASSWORD


def token():return uuid4().hex

def due():return (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()


class PdfMessageTests(unittest.TestCase):
    def test_all_pdf_examples_have_expected_offline_category_and_urgent_stop(self):
        self.assertEqual(len(EXAMPLES),40)
        for x in EXAMPLES.values():
            with self.subTest(x=x['id']):
                self.assertEqual(demo_read(x['message']).category,x['category'])
                self.assertEqual(urgent_hint(x['message']),x['urgent'])
    def test_pain_medicine_supply_is_not_automatically_a_symptom(self):
        self.assertFalse(clinical_screen(EXAMPLES['hi01']['message']))
        self.assertFalse(clinical_screen('Our pain medicine will finish tomorrow.'))
        self.assertTrue(clinical_screen('Pain medicine is not helping the pain.'))
        self.assertTrue(clinical_screen('नींद बहुत आ रही है'))
    def test_mixed_clinical_content_overrides_a_logistical_model_result(self):
        out=validate_reading({'category':'DOCUMENTS_ROUTE','summary':'Documents','clinical_concern':False,'uncertain':False},'Which papers? Father is vomiting.','crewai')
        self.assertEqual(out.category,'CLINICAL')
    def test_evidence_checker_requires_all_five_fields_and_matching_plan(self):
        task={'plan_ref':'PLAN1'};check={'medicine_status':'PLAN_VERIFIED','plan_ref':'PLAN1'};flags=dict.fromkeys(EVIDENCE_FLAGS,True)
        self.assertTrue(evidence_decision(task,check,flags)[0])
        for key in flags:
            self.assertFalse(evidence_decision(task,check,{**flags,key:False})[0])
        self.assertFalse(evidence_decision(task,{**check,'plan_ref':'OLD'},flags)[0])
        self.assertFalse(evidence_decision(task,{},flags)[0])


class AccessTaskTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SAHYOGI_READER':'demo'});self.env.start()
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.db';self.store=Store(self.path);self.accounts=Accounts(self.store)
        self.co=self.accounts.create_user('anita','Anita','coordinator',TEST_PASSWORD,bootstrap=True)
        self.family=self.add('meena','caregiver');self.staff=self.add('staff1','staff');self.flow=CareFlow(self.store,self.accounts)
        self.data={'task_ref':'TASK1','patient_ref':'P1','plan_ref':'PLAN1','target':'Access to medicine in the existing practice plan','due_at':due(),'family_username':'meena','staff_username':'staff1','consent_recorded':'yes'}
        self.id=self.flow.access.register(self.co,self.data,token())
    def tearDown(self):self.tmp.cleanup();self.env.stop()
    def add(self,name,role):
        uid=self.accounts.create_user(name,name,role,TEST_PASSWORD,creator=self.co);self.accounts.change_password(uid,TEST_PASSWORD,NEW_PASSWORD);return uid
    def r(self):return self.flow.detail(self.id,self.co)
    def v(self):return self.r()['version']
    def checks(self,plan='PLAN1'):
        self.flow.checks(self.id,self.staff,self.v(),token(),{'medicine_status':'PLAN_VERIFIED','checked_plan_ref':plan,'clinician_source':'Simulated authorised clinician','clinician_checked':'yes','document_status':'VERIFIED','document_details':'Practice list checked','document_source':'Simulated service'})
    def proof(self,**extra):return {'proof_source':'Simulated authorised pharmacy','proof_reference':'DISP1','proof_note':'Clinical team checked the full sample dispensing record.','decision':'accept',**dict.fromkeys(EVIDENCE_FLAGS,'yes'),**extra}
    def test_registration_has_owner_due_next_action_and_unverified_plan(self):
        r=self.r();self.assertEqual(r['access_task']['owner_id'],self.co);self.assertTrue(r['access_task']['next_action']);self.assertFalse(r['access_task']['verified_at']);self.assertEqual(r['medicine_status'],'NOT_CHECKED');self.assertFalse(r['messages'])
    def test_duplicate_reference_invalid_role_and_missing_consent_are_rejected(self):
        with self.assertRaises(RuleError):self.flow.access.register(self.co,self.data,token())
        with self.assertRaises(AccessDenied):self.flow.access.register(self.family,{**self.data,'task_ref':'TASK2'},token())
        with self.assertRaises(RuleError):self.flow.access.register(self.co,{**self.data,'consent_recorded':'no'},token())
    def test_missing_record_keeps_access_open_without_claiming_noncollection(self):
        self.assertEqual(self.r()['access_task']['state'],'OPEN');self.assertNotEqual(self.r()['status'],'CLOSED')
    def test_proof_cannot_close_without_matching_verified_plan(self):
        for plan in [None,'OTHER']:
            if plan:self.checks(plan)
            with self.assertRaises(RuleError):self.flow.access.evidence(self.id,self.staff,self.v(),token(),self.proof())
            self.assertFalse(self.r()['access_task']['verified_at'])
    def test_each_missing_proof_condition_blocks_acceptance(self):
        self.checks()
        for key in EVIDENCE_FLAGS:
            with self.subTest(key=key),self.assertRaises(RuleError):self.flow.access.evidence(self.id,self.staff,self.v(),token(),self.proof(**{key:''}))
        self.assertNotEqual(self.r()['status'],'CLOSED')
    def test_partial_record_is_saved_but_open_and_invalid_record_is_not_called_partial(self):
        self.flow.access.evidence(self.id,self.staff,self.v(),token(),self.proof(decision='reject',authority='',full_coverage=''))
        self.assertEqual(self.r()['access_task']['state'],'AWAITING_VERIFICATION')
        self.flow.access.evidence(self.id,self.staff,self.v(),token(),self.proof(decision='reject',full_coverage=''))
        self.assertEqual(self.r()['access_task']['state'],'PARTIAL');self.assertNotEqual(self.r()['status'],'CLOSED')
    def test_only_assigned_staff_can_accept_full_proof(self):
        self.checks()
        for uid in [self.co,self.family,self.add('staff2','staff')]:
            with self.assertRaises(AccessDenied):self.flow.access.evidence(self.id,uid,self.v(),token(),self.proof())
        self.flow.access.evidence(self.id,self.staff,self.v(),token(),self.proof());r=self.r()
        self.assertEqual(r['status'],'CLOSED');self.assertTrue(r['access_task']['verified_at']);self.assertTrue(r['resolutions'][-1]['collection_verified'])
        self.assertIn('not establish',r['events'][-1]['detail'])
    def test_collection_claim_never_verifies_task(self):
        self.flow.message(self.id,self.family,'We collected it.',self.v(),token())
        self.assertFalse(self.r()['access_task']['verified_at']);self.assertNotEqual(self.r()['status'],'CLOSED')
    def test_document_support_result_does_not_close_medicine_task(self):
        self.flow.message(self.id,self.family,'Which documents do we need for palliative care?',self.v(),token());self.checks()
        self.flow.confirm(self.id,self.staff,self.v(),token(),{'code':'DOCUMENTS','description':'Document list needed','review_note':'Clarified with family','barrier_checked':'yes'})
        run=self.r()['runs'][-1];self.flow.approve(self.id,self.staff,self.v(),token(),{'run_id':run['id'],'tasks':'Check the approved document list','patient_message':'The checked practice document list is ready.','assigned_to':'anita','due_at':due(),'staff_approved':'yes'})
        self.flow.close(self.id,self.staff,self.v(),token(),{'resolution_note':'Document list explained and checked.','resolved_checked':'yes'})
        self.assertEqual(self.r()['status'],'AWAITING_EVIDENCE');self.assertFalse(self.r()['access_task']['verified_at']);self.assertTrue(self.r()['support_results'])
    def test_urgent_message_bypasses_ai_and_ack_does_not_clear_review(self):
        reader=Mock(side_effect=AssertionError('LLM must not run'));agent=Mock(side_effect=AssertionError('Agent must not run'))
        self.flow.message(self.id,self.family,EXAMPLES['safety_a']['message'],self.v(),token(),reader=reader,agent=agent)
        reader.assert_not_called();agent.assert_not_called();r=self.r();self.assertTrue(r['urgent_open']);self.assertTrue(r['review_required']);self.assertEqual(r['messages'][-1]['reading']['engine'],'rules')
        with self.assertRaises(AccessDenied):self.flow.access.acknowledge(self.id,self.co,self.v(),token(),r['escalations'][0]['id'])
        self.flow.access.acknowledge(self.id,self.staff,self.v(),token(),r['escalations'][0]['id']);self.assertTrue(self.r()['review_required'])
        self.checks()
        with self.assertRaises(RuleError):self.flow.access.evidence(self.id,self.staff,self.v(),token(),self.proof())
        self.flow.resolve_review(self.id,self.staff,self.v(),token(),'Actual authorised team review completed and recorded.','yes')
        self.assertFalse(self.r()['urgent_open']);self.assertFalse(self.r()['review_required'])
    def test_unresolved_reply_adds_operations_flag_and_keeps_owner(self):
        self.flow.message(self.id,self.family,EXAMPLES['demo04']['message'],self.v(),token());r=self.r()
        self.assertEqual(r['escalations'][0]['priority'],'OPERATIONS');self.assertEqual(r['access_task']['owner_id'],self.co);self.assertFalse(r['access_task']['verified_at'])
    def test_next_action_requires_future_time_and_never_changes_owner(self):
        with self.assertRaises(RuleError):self.flow.access.next_action(self.id,self.co,self.v(),token(),{'next_action':'Call authorised service','due_at':datetime.now(timezone.utc).isoformat()})
        self.flow.access.next_action(self.id,self.staff,self.v(),token(),{'next_action':'Call the simulated service for missing proof','due_at':due()})
        self.assertEqual(self.r()['access_task']['owner_id'],self.co);self.assertIn('missing proof',self.r()['access_task']['next_action'])
    def test_named_handover_waits_for_acceptance_then_previous_owner_is_read_only(self):
        next_id=self.add('coord2','coordinator');outsider=self.add('coord3','coordinator')
        self.flow.access.handover(self.id,self.co,self.v(),token(),{'next_owner':'coord2','due_at':due(),'note':'Next shift checks the sample dispensing proof'})
        self.assertEqual(self.r()['access_task']['owner_id'],self.co);self.assertEqual(len(self.flow.list_requests(next_id)),1)
        with self.assertRaises(AccessDenied):self.flow.access.accept_handover(self.id,outsider,self.v(),token())
        self.flow.access.accept_handover(self.id,next_id,self.v(),token())
        self.assertEqual(self.r()['access_task']['owner_id'],next_id);self.assertEqual(self.r()['coordinator_id'],next_id)
        with self.assertRaises(AccessDenied):self.flow.access.next_action(self.id,self.co,self.v(),token(),{'next_action':'Try to change','due_at':due()})
    def test_assisted_reply_records_source_actor_and_actual_words(self):
        text='We need help with travel.'
        self.flow.assisted_message(self.id,self.staff,self.v(),token(),{'message':text,'method':'phone','read_back':'yes'})
        m=self.r()['messages'][-1];self.assertEqual(m['body'],text);self.assertEqual(m['source']['method'],'phone');self.assertIn('staff1',m['source']['recorded_by'])
        with self.assertRaises(AccessDenied):self.flow.assisted_message(self.id,self.family,self.v(),token(),{'message':text,'method':'phone','read_back':'yes'})
    def test_checked_clinical_guidance_is_not_carried_into_a_new_family_message(self):
        from care_views import overview
        self.flow.message(self.id,self.family,EXAMPLES['safety_a']['message'],self.v(),token())
        self.flow.access.guidance(self.id,self.staff,self.v(),token(),{'guidance':'CURRENT CHECKED TEAM GUIDANCE','guidance_source':'Simulated authorised team','guidance_checked':'yes'})
        self.assertIn('CURRENT CHECKED TEAM GUIDANCE',overview(self.r(),'csrf',self.accounts.user(self.family)))
        self.flow.message(self.id,self.family,'We need help with travel.',self.v(),token())
        self.assertNotIn('CURRENT CHECKED TEAM GUIDANCE',overview(self.r(),'csrf',self.accounts.user(self.family)))
        self.assertTrue(self.r()['clinical_guidance'])
    def test_withdrawn_consent_blocks_assisted_contact_guidance_and_proof(self):
        self.flow.message(self.id,self.family,EXAMPLES['safety_a']['message'],self.v(),token());self.flow.withdraw(self.id,self.family,self.v(),token())
        for call in [lambda:self.flow.assisted_message(self.id,self.staff,self.v(),token(),{'message':'Family words','method':'phone','read_back':'yes'}),lambda:self.flow.access.guidance(self.id,self.staff,self.v(),token(),{'guidance':'Checked source text','guidance_source':'Demo team','guidance_checked':'yes'}),lambda:self.flow.access.evidence(self.id,self.staff,self.v(),token(),self.proof())]:
            with self.assertRaises(RuleError):call()
    def test_additive_schema_preserves_tasks_on_reopen_and_no_keys_in_database(self):
        reopened=CareFlow(Store(self.path),self.accounts);self.assertEqual(reopened.detail(self.id,self.family)['access_task']['task_ref'],'TASK1')


class FocusedScreenTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SAHYOGI_READER':'demo'});self.env.start();self.tmp=tempfile.TemporaryDirectory()
        self.server=DemoServer(('127.0.0.1',0),Store(Path(self.tmp.name)/'web.db'));a=self.server.accounts
        self.co=a.create_user('anita','Anita','coordinator',TEST_PASSWORD,bootstrap=True)
        for name,role in [('meena','caregiver'),('staff1','staff')]:a.create_user(name,name,role,TEST_PASSWORD,creator=self.co)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.c=Browser(self.server).login('anita',TEST_PASSWORD);self.f=Browser(self.server).login('meena',TEST_PASSWORD,NEW_PASSWORD);self.s=Browser(self.server).login('staff1',TEST_PASSWORD,NEW_PASSWORD)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup();self.env.stop()
    def task(self):
        local=(datetime.now(timezone(timedelta(hours=5,minutes=30)))+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
        st,h,b=self.c.post('/care/task',{'token':token(),'task_ref':'TASKWEB','patient_ref':'PWEB','plan_ref':'PLANWEB','target':'Practice medicine access','due_at':local,'family_username':'meena','staff_username':'staff1','consent_recorded':'yes'});self.assertEqual(st,303,b)
        self.id=parse_qs(urlsplit(h['Location']).query)['id'][0];return h['Location']
    def page(self,view,browser=None):return (browser or self.s).request('GET','/request?'+urlsplit('id='+self.id).path+'&view='+view)
    def test_registration_forms_and_focused_views_have_help_and_role_privacy(self):
        self.assertIn('Unique care task reference',self.c.request('GET','/care-plan')[2]);self.assertEqual(self.f.request('GET','/care-plan')[0],404)
        path=self.task();family=self.f.request('GET',path)[2];self.assertIn('Medicine access',family);self.assertNotIn('/care/evidence',family)
        self.assertEqual(self.f.request('GET',path+'&view=checks')[0],404)
        for v in ['overview','messages','plan','team','review','checks','barrier','followup','evidence','escalation','history']:
            status,_,html=self.page(v);self.assertEqual(status,200,(v,html));self.assertIn('context-help',html)
        checks=self.page('checks')[2];self.assertIn('/care/checks',checks);self.assertNotIn('/care/confirm',checks);self.assertNotIn('/care/approve',checks)
        self.assertIn('/care/evidence',self.page('evidence')[2]);self.assertNotIn('/care/evidence',self.page('overview')[2])
    def test_assisted_reply_form_and_key_failure_retry_are_on_messages_view(self):
        self.task();html=self.page('messages')[2];self.assertIn('Record an assisted family reply',html);self.assertIn('value="in_person"',html)
    def test_examples_prefill_only_after_explicit_family_send(self):
        page=self.f.request('GET','/examples')[2];self.assertIn('Use this practice message',page)
        html=self.f.request('GET','/?example=demo02')[2];self.assertIn(EXAMPLES['demo02']['message'],html);
        with self.server.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM care_requests').fetchone()[0],0)
    def test_new_mutations_still_require_origin_and_session_csrf(self):
        self.task();data={'token':token(),'request_id':self.id,'version':'2','next_action':'Check sample proof','due_at':due()}
        self.assertEqual(self.f.post('/care/evidence',{**data,'proof_source':'x','proof_reference':'x','proof_note':'x','decision':'reject'})[0],403)
        self.assertEqual(self.c.post('/care/next-action',{**data,'csrf':'wrong'})[0],403)
