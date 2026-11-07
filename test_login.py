"""Login, role and case-isolation regression tests. No live provider calls."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from access_control import COOKIE,Accounts,AccessDenied,PASSWORD_ROUNDS,SESSION_SECONDS,IDLE_SECONDS,password_hash,password_matches
from agent import demo_read
from app import DemoServer
from assistants import case_snapshot
from caregiver_contact import contact_progress
from http_test_client import Browser,TEST_PASSWORD,NEW_PASSWORD,Forms
from portal import ScopedStore
from store import Store,RuleError


def future():return (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'auth.db');self.accounts=Accounts(self.store)
        self.admin=self.accounts.create_user('anita','Anita','coordinator',TEST_PASSWORD,bootstrap=True)
        self.id=self.store.create_practice('directions',uuid4().hex,principal=self.admin)
    def tearDown(self):self.tmp.cleanup()
    def add(self,name,role):
        user=self.accounts.create_user(name,name.title(),role,TEST_PASSWORD,creator=self.admin)
        self.accounts.change_password(user,TEST_PASSWORD,NEW_PASSWORD)
        return user
    def case(self):return self.store.detail(self.id)
    def assign(self,name):self.accounts.assign(self.id,name,self.admin,self.case()['version'])
    def act(self,action,data,user=None):
        from access_control import ACTION_ROLES
        return self.store.act(self.id,action,data,self.case()['version'],uuid4().hex,ACTION_ROLES[action],principal=user or self.admin)
    def approved_message(self):
        self.store.add_reply(self.id,'Where should we go? Which documents are needed?',self.case()['version'],uuid4().hex,demo_read,principal=self.admin)
        self.act('approve',{'message_id':self.case()['messages'][0]['id'],'note':'Check real details.'})
        self.act('check_details',{'location':'Approved demo location','documents':'Approved demo documents','source':'Demo source',
            'checked_by':'FORGED NAME','checked_at':datetime.now(timezone.utc).isoformat(),'language':'en','facts_checked':'yes'})
        self.act('approve_update',{'check_id':self.case()['collection_checks'][-1]['id'],'approved_by':'FORGED NAME','message_checked':'yes'})
        return self.case()['caregiver_updates'][-1]['id']

    def test_passwords_are_salted_and_not_saved_as_plain_text(self):
        with self.store.connection() as db:encoded=db.execute('SELECT password_hash FROM users WHERE id=?',(self.admin,)).fetchone()[0]
        self.assertNotIn(TEST_PASSWORD,encoded);self.assertTrue(password_matches(TEST_PASSWORD,encoded));self.assertFalse(password_matches('wrong',encoded))
        second=password_hash(TEST_PASSWORD);self.assertNotEqual(encoded,second)
        with self.assertRaises(ValueError):password_hash('abc')

    def test_new_password_boundaries_are_four_to_eighteen(self):
        for value in ['abcd', 'a'*18]:
            self.assertTrue(password_matches(value,password_hash(value)))
        for value in ['', 'abc', 'a'*19, 'a'*128]:
            with self.assertRaisesRegex(ValueError,'4 to 18'):
                password_hash(value)

    def test_account_creation_change_and_reset_enforce_the_same_boundaries(self):
        user=self.accounts.create_user('shortpass','Short pass','patient','abcd',creator=self.admin)
        self.accounts.login('shortpass','abcd','policy-test')
        self.accounts.change_password(user,'abcd','b'*18)
        for value in ['abc','c'*19]:
            with self.assertRaises(ValueError):self.accounts.change_password(user,'b'*18,value)
            with self.assertRaises(ValueError):self.accounts.reset_local('shortpass',value)
            with self.assertRaises(ValueError):self.accounts.create_user('badlength','Bad length','patient',value,creator=self.admin)
        self.accounts.login('shortpass','b'*18,'policy-test')
        self.accounts.reset_local('shortpass','wxyz')
        self.assertTrue(self.accounts.login('shortpass','wxyz','policy-test')['must_change'])

    def test_only_initial_admin_creates_privileged_roles_and_no_public_signup(self):
        other=self.add('othercoord','coordinator')
        with self.assertRaises(AccessDenied):self.accounts.create_user('fakeadmin','Fake','staff',TEST_PASSWORD,creator=other)
        with self.assertRaises(AccessDenied):self.accounts.create_user('again','Again','coordinator',TEST_PASSWORD,bootstrap=True)
        with self.assertRaises(AccessDenied):self.accounts.create_user('public','Public','patient',TEST_PASSWORD)
        patient=self.add('patient','patient')
        with self.assertRaises(AccessDenied):self.accounts.create_user('evil','Evil','staff',TEST_PASSWORD,creator=patient)

    def test_new_accounts_must_change_password_before_writes(self):
        user=self.accounts.create_user('caregiver','Caregiver','caregiver',TEST_PASSWORD,creator=self.admin)
        self.assign('caregiver')
        with self.assertRaises(AccessDenied):self.store.add_reply(self.id,'We collected it.',self.case()['version'],uuid4().hex,demo_read,principal=user)
        self.accounts.change_password(user,TEST_PASSWORD,NEW_PASSWORD)
        self.store.add_reply(self.id,'We collected it.',self.case()['version'],uuid4().hex,demo_read,principal=user)
        self.assertEqual(self.case()['access'],'NOT_CONFIRMED')

    def test_sessions_rotate_expire_and_store_only_token_hash(self):
        token,session=self.accounts.new_session(self.admin)
        with self.store.connection() as db:
            row=db.execute('SELECT * FROM sessions').fetchone()
            self.assertEqual(row['token_hash'],hashlib.sha256(token.encode()).hexdigest());self.assertNotEqual(row['token_hash'],token)
        new,_=self.accounts.new_session(self.admin,token)
        self.assertIsNone(self.accounts.session(token));self.assertIsNotNone(self.accounts.session(new))
        with self.store.connection(write=True) as db:db.execute('UPDATE sessions SET created_at=?',(time.time()-SESSION_SECONDS-1,))
        self.assertIsNone(self.accounts.session(new))
        new,_=self.accounts.new_session(self.admin)
        with self.store.connection(write=True) as db:db.execute('UPDATE sessions SET last_seen=?',(time.time()-IDLE_SECONDS-1,))
        self.assertIsNone(self.accounts.session(new))

    def test_password_change_and_local_reset_revoke_existing_sessions(self):
        token,_=self.accounts.new_session(self.admin)
        self.accounts.change_password(self.admin,TEST_PASSWORD,NEW_PASSWORD)
        self.assertIsNone(self.accounts.session(token))
        with self.assertRaises(AccessDenied):self.accounts.login('anita',TEST_PASSWORD,'test')
        self.accounts.login('anita',NEW_PASSWORD,'test')
        token,_=self.accounts.new_session(self.admin)
        self.accounts.reset_local('anita',TEST_PASSWORD)
        self.assertIsNone(self.accounts.session(token));self.assertTrue(self.accounts.user(self.admin)['must_change'])

    def test_repeated_failed_logins_are_limited_and_errors_do_not_reveal_account(self):
        for name in ['missing','anita']:
            try:self.accounts.login(name,'wrong','peer-'+name)
            except AccessDenied as e:self.assertEqual(str(e),'Username or password is incorrect.')
        for i in range(7):
            with self.assertRaises(AccessDenied):self.accounts.login('anita','wrong','limited')
        with self.assertRaisesRegex(AccessDenied,'Too many'):self.accounts.login('anita',TEST_PASSWORD,'limited')

    def test_unassigned_users_cannot_read_write_or_run_assistants(self):
        patient=self.add('patient','patient');staff=self.add('staff','staff')
        for user in [patient,staff]:
            scoped=ScopedStore(self.store,self.accounts,self.accounts.user(user));self.assertEqual(scoped.list_cases(),[])
            with self.assertRaises(AccessDenied):scoped.detail(self.id)
            with self.assertRaises(AccessDenied):self.store.add_reply(self.id,'We collected it.',self.case()['version'],uuid4().hex,demo_read,principal=user)
            with self.assertRaises(AccessDenied):self.store.request_assistance(self.id,'followup',self.case()['version'],uuid4().hex,'Coordinator',principal=user)

    def test_assigned_patient_cannot_create_approve_verify_or_assign_cases(self):
        user=self.add('patient','patient');self.assign('patient')
        with self.assertRaises(AccessDenied):self.store.create_practice('directions',uuid4().hex,principal=user)
        for action,data in [('approve',{'note':'Forged'}),('verify',{'note':'Forged'}),('clear_review',{'note':'Forged'})]:
            with self.assertRaises(AccessDenied):self.act(action,data,user)
        with self.assertRaises(AccessDenied):self.accounts.assign(self.id,'patient',user,self.case()['version'])

    def test_staff_proof_and_review_rights_are_separate_from_coordinator(self):
        staff=self.add('staff','staff');self.assign('staff')
        self.store.add_reply(self.id,'The patient has pain.',self.case()['version'],uuid4().hex,demo_read,principal=self.admin)
        with self.assertRaises(AccessDenied):self.act('clear_review',{'note':'Not a clinical team account.'})
        self.act('clear_review',{'note':'Sample care team review completed.'},staff)
        self.assertFalse(self.case()['review_required'])
        self.act('add_evidence',{'source':'Demo','reference':'PROOF1','target_match':'yes','full_supply':'yes'})
        data={'evidence_id':self.case()['evidence'][0]['id'],'decision':'accept','authority_checked':'yes','note':'Actual verifier checks simulated.'}
        with self.assertRaises(AccessDenied):self.act('verify',data)
        self.act('verify',data,staff)
        self.assertEqual(self.case()['access'],'CONFIRMED');self.assertIn('@staff',self.case()['evidence'][0]['verifier'])

    def test_account_names_cannot_be_forged_in_approval_or_checked_details(self):
        self.approved_message()
        self.assertEqual(self.case()['collection_checks'][-1]['checked_by'],'Anita (@anita)')
        self.assertEqual(self.case()['caregiver_updates'][-1]['approved_by'],'Anita (@anita)')

    def test_real_portal_acknowledgement_is_saved_without_confirming_collection(self):
        user=self.add('caregiver','caregiver');self.assign('caregiver');update=self.approved_message()
        self.accounts.acknowledge(self.id,update,user,self.case()['version'])
        self.assertEqual(self.case()['access'],'NOT_CONFIRMED');self.assertEqual(len(self.case()['patient_acknowledgements']),1)
        self.assertIn('marked',contact_progress(self.case()));self.assertTrue(case_snapshot(self.case())['caregiver_informed_recorded'])
        self.accounts.acknowledge(self.id,update,user,self.case()['version'])
        self.assertEqual(len(self.case()['patient_acknowledgements']),1)

    def test_revised_message_and_removed_access_block_old_acknowledgements(self):
        user=self.add('patient','patient');self.assign('patient');update=self.approved_message()
        self.act('check_details',{'location':'New location','documents':'New docs','source':'Demo','checked_by':'Anita',
            'checked_at':datetime.now(timezone.utc).isoformat(),'language':'en','facts_checked':'yes'})
        with self.assertRaises(RuleError):self.accounts.acknowledge(self.id,update,user,self.case()['version'])
        self.accounts.assign(self.id,'patient',self.admin,self.case()['version'],remove=True)
        with self.assertRaises(AccessDenied):self.accounts.acknowledge(self.id,update,user,self.case()['version'])

    def test_handover_requires_the_actual_named_account_and_changes_ownership_atomically(self):
        next_owner=self.add('rahul','coordinator');outsider=self.add('other','coordinator')
        self.act('handover',{'person':'rahul','due_at':future(),'note':'New owner needed.'})
        self.assertEqual(self.case()['owner'],'Anita (@anita)')
        with self.assertRaises(AccessDenied):self.act('accept_handover',{'person':'Rahul'},outsider)
        with self.assertRaises(AccessDenied):self.act('accept_handover',{'person':'Rahul'})
        self.act('accept_handover',{'person':'FORGED'},next_owner)
        self.assertEqual(self.case()['owner'],'Rahul (@rahul)')
        with self.assertRaises(AccessDenied):self.act('reschedule',{'due_at':future(),'note':'Former owner.'})
        self.act('reschedule',{'due_at':future(),'note':'Actual new owner.'},next_owner)

    def test_bootstrap_preserves_legacy_case_data_and_assigns_it_to_initial_coordinator(self):
        path=Path(self.tmp.name)/'legacy.db';store=Store(path)
        case_id=store.create_practice('travel',uuid4().hex)
        accounts=Accounts(store);admin=accounts.create_user('legacyadmin','Operator','coordinator',TEST_PASSWORD,bootstrap=True)
        self.assertEqual(store.detail(case_id)['practice_example'],'travel')
        self.assertIn(case_id,accounts.case_ids(admin));self.assertEqual(store.detail(case_id)['owner'],'Operator (@legacyadmin)')
        self.assertIn('Previous recorded owner: Anita',store.detail(case_id)['events'][-1]['detail'])


class PortalHttpTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SAHYOGI_READER':'demo'});self.env.start()
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'http.db')
        self.server=DemoServer(('127.0.0.1',0),self.store);self.accounts=self.server.accounts
        self.admin=self.accounts.create_user('anita','Anita','coordinator',TEST_PASSWORD,bootstrap=True)
        self.coord=Browser(self.server)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.coord.login('anita',TEST_PASSWORD)
        self.id=self.store.create_practice('directions',uuid4().hex,principal=self.admin)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup();self.env.stop()
    def case(self):return self.store.detail(self.id)
    def user_browser(self,name,role,assign=True):
        user=self.accounts.create_user(name,name.title(),role,TEST_PASSWORD,creator=self.admin)
        if assign:self.accounts.assign(self.id,name,self.admin,self.case()['version'])
        return user,Browser(self.server).login(name,TEST_PASSWORD,NEW_PASSWORD)
    def payload(self,**extra):return {'case_id':self.id,'version':self.case()['version'],'token':uuid4().hex,**extra}

    def test_anonymous_direct_links_and_posts_cannot_expose_cases(self):
        anonymous=Browser(self.server)
        for path in ['/','/case?id='+self.id,'/export?id='+self.id,'/accounts','/help']:
            status,h,body=anonymous.request('GET',path);self.assertEqual(status,303);self.assertEqual(h['Location'],'/login');self.assertNotIn('PRACTICE',body)
        self.assertEqual(anonymous.post('/reply',self.payload(text='We collected it.'))[0],401)
        self.assertFalse(self.case()['messages'])

    def test_stale_sign_in_page_reloads_and_then_signs_in(self):
        browser=Browser(self.server);browser.request('GET','/login');browser.cookie=COOKIE+'=gone'
        status,h,_=browser.post('/login',{'username':'anita','password':TEST_PASSWORD})
        self.assertEqual((status,h['Location']),(303,'/login?expired=1'))
        self.assertIn('sign-in page had expired',browser.request('GET',h['Location'])[2])
        self.assertEqual(browser.post('/login',{'username':'anita','password':TEST_PASSWORD})[0],303)
        self.assertEqual(browser.request('GET','/')[0],200)

    def test_other_local_apps_cookies_do_not_break_sign_in(self):
        # Browsers share cookies across ports on 127.0.0.1, and other apps' cookies may not parse.
        for other in ['a[b]=1','prefs={"x": 1}','ui=dark mode','novalue']:
            with self.subTest(other=other):
                browser=Browser(self.server);browser.request('GET','/login');browser.cookie=other+'; '+browser.cookie
                status,h,_=browser.post('/login',{'username':'anita','password':TEST_PASSWORD})
                self.assertEqual(status,303);self.assertNotIn('expired',h['Location'])

    def test_signed_out_error_links_to_sign_in_not_cases(self):
        body=Browser(self.server).post('/reply',self.payload(text='Hello'))[2]
        self.assertIn('href="/login"',body);self.assertNotIn('Return to cases',body)

    def test_login_rotates_cookie_and_uses_http_only_same_site_cookie(self):
        browser=Browser(self.server);_,h,_=browser.request('GET','/login');old=browser.cookie
        status,h,_=browser.post('/login',{'username':'anita','password':TEST_PASSWORD,'role':'staff'})
        self.assertEqual(status,303);self.assertNotEqual(old,browser.cookie)
        self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('SameSite=Strict',h['Set-Cookie'])
        browser.request('GET','/');self.assertIn('Coordinator',browser.request('GET','/')[2])
        invalid=Browser(self.server);invalid.cookie=old;self.assertEqual(invalid.request('GET','/')[0],303)

    def test_native_form_policy_allows_login_create_account_and_family_question(self):
        # no-referrer turns native form Origin into null under Fetch. Check the
        # document policy as well as submitting with the real same-origin header.
        browser=Browser(self.server)
        status,h,_=browser.request('GET','/login')
        self.assertEqual(status,200)
        self.assertEqual(h['Referrer-Policy'],'same-origin')
        status,h,body=browser.post('/login',{'username':'anita','password':TEST_PASSWORD})
        self.assertEqual(status,303,body)
        status,h,body=browser.request('GET',h['Location'])
        self.assertEqual(status,200)
        self.assertIn('href="/accounts"',body)
        self.assertEqual(h['Referrer-Policy'],'same-origin')
        self.assertEqual(browser.post('/accounts/create',{'username':'familyform','display_name':'Family',
            'role':'caregiver','password':TEST_PASSWORD})[0],303)
        family=Browser(self.server).login('familyform',TEST_PASSWORD,NEW_PASSWORD)
        status,h,body=family.request('GET','/')
        self.assertEqual(status,200);self.assertIn('Your question or message',body)
        self.assertEqual(h['Referrer-Policy'],'same-origin')
        status,h,body=family.post('/care/submit',{'topic':'documents','message':'Which documents do we need for palliative care?',
            'consent':'yes','token':uuid4().hex})
        self.assertEqual(status,303,body)
        self.assertIn('/request?',h['Location'])

    def test_null_foreign_and_wrong_port_origins_cannot_sign_in(self):
        browser=Browser(self.server);browser.request('GET','/login')
        for origin in ['null','https://evil.invalid',f'http://127.0.0.1:{self.server.server_port+1}']:
            status,_,_=browser.request('POST','/login',{'csrf':browser.csrf,'username':'anita','password':TEST_PASSWORD},
                {'Origin':origin})
            self.assertEqual(status,403)
        self.assertEqual(browser.request('GET','/accounts')[0],303)

    def test_localhost_forms_also_sign_in_with_the_matching_origin(self):
        browser=Browser(self.server)
        host=f'localhost:{self.server.server_port}'
        self.assertEqual(browser.request('GET','/login',headers={'Host':host})[0],200)
        status,h,body=browser.request('POST','/login',{'csrf':browser.csrf,'username':'anita','password':TEST_PASSWORD},
            {'Host':host,'Origin':'http://'+host})
        self.assertEqual(status,303,body)
        self.assertEqual(browser.request('GET',h['Location'],headers={'Host':host})[0],200)

    def test_temp_password_must_change_before_dashboard_or_case_access(self):
        self.accounts.create_user('patient','Patient','patient',TEST_PASSWORD,creator=self.admin)
        browser=Browser(self.server).login('patient',TEST_PASSWORD)
        status,h,_=browser.request('GET','/case?id='+self.id)
        self.assertEqual(status,303);self.assertEqual(h['Location'],'/password')
        self.assertEqual(browser.post('/practice',{'example_id':'travel','token':uuid4().hex})[0],403)

    def test_patient_and_caregiver_see_assigned_tasks_but_not_other_cases(self):
        other=self.store.create_practice('travel',uuid4().hex,principal=self.admin)
        for name,role in [('patient','patient'),('caregiver','caregiver')]:
            _,b=self.user_browser(name,role)
            status,_,html=b.request('GET','/cases');self.assertEqual(status,200)
            self.assertIn('PRACTICE-DIRECTIONS',html);self.assertNotIn('PRACTICE-TRAVEL',html)
            self.assertEqual(b.request('GET','/case?id='+other)[0],404)
            self.assertEqual(b.request('GET','/export?id='+self.id)[0],404)
            self.assertEqual(b.request('GET','/accounts')[0],404)

    def test_patient_view_hides_drafts_ai_outputs_review_notes_and_case_management(self):
        _,b=self.user_browser('patient','patient')
        self.store.add_reply(self.id,'Where should we go? Which documents are needed?',self.case()['version'],uuid4().hex,demo_read,principal=self.admin)
        self.store.request_assistance(self.id,'barrier',self.case()['version'],uuid4().hex,'Coordinator',principal=self.admin)
        status,_,html=b.request('GET','/case?id='+self.id)
        self.assertEqual(status,200)
        for text in ['Draft suggestion','Run Barrier Assistant','Who can see this case','Action history','As verifier','Checked next step or review reason']:
            self.assertNotIn(text,html)
        self.assertIn('No current approved instructions',html)

    def test_forged_patient_role_and_case_id_cannot_execute_staff_actions(self):
        _,b=self.user_browser('patient','patient')
        for action in ['verify','clear_review','approve','handover','check_details']:
            status,_,_=b.post('/act',self.payload(action=action,role='Verifier',note='Forged',person='anita'))
            self.assertEqual(status,403)
        self.assertEqual(b.post('/assist',self.payload(kind='followup',role='Coordinator'))[0],403)
        self.assertEqual(b.post('/members',self.payload(username='patient',change='assign'))[0],403)
        self.assertEqual(b.post('/accounts/create',{'username':'badstaff','display_name':'Bad','role':'staff','password':TEST_PASSWORD})[0],403)
        self.assertEqual(self.case()['access'],'NOT_CONFIRMED')

    def test_staff_and_coordinator_have_clear_and_separate_task_pages(self):
        _,staff=self.user_browser('staff','staff')
        self.store.add_reply(self.id,'The patient has pain.',self.case()['version'],uuid4().hex,demo_read,principal=self.admin)
        staff_html=staff.request('GET','/case?id='+self.id)[2];coord_html=self.coord.request('GET','/case?id='+self.id)[2]
        self.assertIn('As care team, resolve this review',staff_html)
        self.assertNotIn('As care team, resolve this review',coord_html)
        self.assertIn('Who can see this case',coord_html);self.assertNotIn('Who can see this case',staff_html)
        self.assertIn('Care team review needed',staff.request('GET','/cases')[2])
        self.assertNotIn('Create sample case',staff.request('GET','/cases')[2])
        self.assertEqual(self.coord.post('/act',self.payload(action='clear_review',role='Care team',note='Forged'))[0],403)
        self.assertEqual(staff.post('/act',self.payload(action='clear_review',role='Coordinator',note='Clinical team review actually recorded.'))[0],303)
        self.assertFalse(self.case()['review_required'])

    def test_in_app_instructions_and_acknowledgement_complete_the_user_flow(self):
        _,caregiver=self.user_browser('caregiver','caregiver')
        status,_,_=caregiver.post('/reply',self.payload(text='Where should we go? Which documents are needed.'))
        # Use the exact recognised sample for this offline walkthrough.
        if self.case()['review_required']:
            staff_id,_=self.user_browser('staff','staff')
            self.store.act(self.id,'clear_review',{'note':'Clarified sample text.'},self.case()['version'],uuid4().hex,'Care team',principal=staff_id)
        self.store.add_reply(self.id,'Where should we go? Which documents are needed?',self.case()['version'],uuid4().hex,demo_read,principal=self.admin)
        m=self.case()['messages'][-1]
        self.store.act(self.id,'approve',{'message_id':m['id'],'note':'Check details.'},self.case()['version'],uuid4().hex,'Coordinator',principal=self.admin)
        local=datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime('%Y-%m-%dT%H:%M')
        status,_,body=self.coord.post('/act',self.payload(action='check_details',role='Coordinator',location='Demo counter 2',documents='Demo approved plan reference',source='Demo service',checked_by='Fake',checked_at=local,language='en',facts_checked='yes'))
        self.assertEqual(status,303,body)
        self.assertNotIn('Demo counter 2',caregiver.request('GET','/case?id='+self.id)[2])
        status,_,body=self.coord.post('/act',self.payload(action='approve_update',role='Coordinator',check_id=self.case()['collection_checks'][-1]['id'],approved_by='Fake',message_checked='yes'))
        self.assertEqual(status,303,body)
        page=caregiver.request('GET','/case?id='+self.id)[2]
        self.assertIn('Demo counter 2',page);self.assertIn('I have read these instructions',page)
        update=self.case()['caregiver_updates'][-1]['id']
        self.assertEqual(caregiver.post('/acknowledge',self.payload(update_id=update))[0],303)
        self.assertIn('marked the current approved instructions as read',self.coord.request('GET','/case?id='+self.id)[2])
        self.assertEqual(self.case()['access'],'NOT_CONFIRMED')
        self.assertIn('You marked these instructions as read',caregiver.request('GET','/case?id='+self.id)[2])

    def test_csrf_is_specific_to_session_and_origin_and_host_are_checked(self):
        _,patient=self.user_browser('patient','patient')
        self.assertEqual(patient.post('/reply',self.payload(csrf=self.coord.csrf,text='We collected it.'))[0],403)
        self.assertEqual(patient.request('POST','/reply',{'csrf':patient.csrf,**self.payload(text='We collected it.')},{'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(patient.request('GET','/',headers={'Host':'evil.invalid'})[0],403)
        self.assertFalse(self.case()['messages'])

    def test_logout_and_removed_case_membership_block_old_sessions_and_links(self):
        _,b=self.user_browser('patient','patient');old=b.cookie
        self.accounts.assign(self.id,'patient',self.admin,self.case()['version'],remove=True)
        self.assertEqual(b.request('GET','/case?id='+self.id)[0],404)
        self.assertEqual(b.post('/reply',self.payload(text='We collected it.'))[0],403)
        self.assertEqual(b.post('/logout')[0],303)
        b.cookie=old;self.assertEqual(b.request('GET','/')[0],303)

    def test_deactivated_user_loses_existing_session(self):
        user,b=self.user_browser('patient','patient')
        with self.store.connection(write=True) as db:db.execute('UPDATE users SET active=0 WHERE id=?',(user,))
        self.assertEqual(b.request('GET','/')[0],303)

    def test_patient_can_withdraw_contact_without_model_call(self):
        _,b=self.user_browser('patient','patient')
        with patch('crewai_reader.run_reader',side_effect=AssertionError('Opt out must not call AI')):
            self.assertEqual(b.post('/reply',self.payload(text='Stop messages.'))[0],303)
        self.assertFalse(self.case()['consent']);self.assertEqual(self.case()['workflow'],'STOPPED')
        self.assertNotIn('Send my message',b.request('GET','/case?id='+self.id)[2])

    def test_coordinator_creates_and_assigns_an_account_through_actual_forms(self):
        status,_,page=self.coord.request('GET','/accounts');self.assertEqual(status,200)
        parsed=Forms();parsed.feed(page)
        create=next(f for f in parsed.forms if f['action']=='/accounts/create')
        status,_,body=self.coord.request('POST',create['action'],{**create['hidden'],
            'username':'portalcare','display_name':'Portal Caregiver','role':'caregiver','password':TEST_PASSWORD})
        self.assertEqual(status,303,body)
        caregiver=Browser(self.server).login('portalcare',TEST_PASSWORD,NEW_PASSWORD)
        self.assertIn('No case is assigned',caregiver.request('GET','/cases')[2])
        def set_access(change):
            status,_,page=self.coord.request('GET','/case?id='+self.id);self.assertEqual(status,200)
            parsed=Forms();parsed.feed(page)
            access=next(f for f in parsed.forms if f['action']=='/members')
            status,_,body=self.coord.request('POST',access['action'],{**access['hidden'],'username':'portalcare','change':change})
            self.assertEqual(status,303,body)
        set_access('assign')
        self.assertEqual(caregiver.request('GET','/case?id='+self.id)[0],200)
        set_access('remove')
        self.assertEqual(caregiver.request('GET','/case?id='+self.id)[0],404)

    def test_password_length_policy_in_browser_forms_and_server_requests(self):
        from html.parser import HTMLParser
        class Inputs(HTMLParser):
            def __init__(self):super().__init__();self.values={}
            def handle_starttag(self,tag,attrs):
                values=dict(attrs)
                if tag=='input' and values.get('name'):self.values[values['name']]=values
        html=self.coord.request('GET','/accounts')[2];parser=Inputs();parser.feed(html)
        self.assertEqual(parser.values['password']['minlength'],'4')
        self.assertEqual(parser.values['password']['maxlength'],'18')
        for value in ['abc','x'*19]:
            status,_,body=self.coord.post('/accounts/create',{'username':'badlength','display_name':'Bad length','role':'caregiver','password':value})
            self.assertEqual(status,400);self.assertIn('4 to 18',body)
        self.assertEqual(self.coord.post('/accounts/create',{'username':'fourchars','display_name':'Four chars','role':'caregiver','password':'abcd'})[0],303)
        browser=Browser(self.server).login('fourchars','abcd')
        parser=Inputs();parser.feed(browser.request('GET','/password')[2])
        for key in ['new','repeat']:
            self.assertEqual(parser.values[key]['minlength'],'4');self.assertEqual(parser.values[key]['maxlength'],'18')
        self.assertEqual(parser.values['current']['maxlength'],'128')
        for value in ['abc','y'*19]:
            self.assertEqual(browser.post('/password',{'current':'abcd','new':value,'repeat':value})[0],400)
        self.assertEqual(browser.post('/password',{'current':'abcd','new':'z'*18,'repeat':'z'*18})[0],303)

    def test_existing_long_password_still_signs_in_and_can_change_to_four_chars(self):
        from access_control import PASSWORD_ROUNDS
        legacy='Previously saved long password 12345!'
        salt='12'*16
        digest=hashlib.pbkdf2_hmac('sha256',legacy.encode(),bytes.fromhex(salt),PASSWORD_ROUNDS).hex()
        encoded=f'pbkdf2_sha256${PASSWORD_ROUNDS}${salt}${digest}'
        with self.store.connection(write=True) as db:
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(encoded,self.admin))
        browser=Browser(self.server).login('anita',legacy)
        old_cookie=browser.cookie
        status,_,body=browser.post('/password',{'current':legacy,'new':'abcd','repeat':'abcd'})
        self.assertEqual(status,303,body)
        self.assertEqual(browser.request('GET','/')[0],200)
        old=Browser(self.server);old.cookie=old_cookie
        self.assertEqual(old.request('GET','/')[0],303)
        self.assertEqual(Browser(self.server).login('anita','abcd').request('GET','/')[0],200)


if __name__=='__main__':unittest.main()
