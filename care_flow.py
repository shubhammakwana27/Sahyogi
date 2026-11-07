"""Patient-first palliative requests with three bounded agent stages and clinical team approval."""
from datetime import datetime,timezone
import hashlib
import json
from uuid import uuid4

from access_control import AccessDenied,account,person_label
from agent import read_reply,needs_review,clinical_hint,opted_out,validate_reading,Reading
from care_safety import urgent_hint
from care_agents import (run_care_agent,validate_care,BARRIERS,TOPICS,MEDICINE_STATUS,DOCUMENT_STATUS)
from reader_errors import safe_error_summary
from store import RuleError,clean,due_time,now


class CareFlow:
    def __init__(self,store,accounts):
        self.store,self.accounts=store,accounts
        with store.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS care_requests (
                id TEXT PRIMARY KEY, creator_id TEXT NOT NULL REFERENCES users(id),
                coordinator_id TEXT NOT NULL REFERENCES users(id), staff_id TEXT REFERENCES users(id),
                topic TEXT NOT NULL, family_plan_ref TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'READING', route TEXT NOT NULL DEFAULT 'STAFF',
                consent INTEGER NOT NULL DEFAULT 1, review_required INTEGER NOT NULL DEFAULT 1,
                medicine_status TEXT NOT NULL DEFAULT 'NOT_CHECKED', document_status TEXT NOT NULL DEFAULT 'NOT_CHECKED',
                current_barrier_id TEXT, active_step_id TEXT, version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_members (
                request_id TEXT NOT NULL REFERENCES care_requests(id), user_id TEXT NOT NULL REFERENCES users(id),
                PRIMARY KEY(request_id,user_id));
            CREATE TABLE IF NOT EXISTS care_messages (
                id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES care_requests(id),
                author_id TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL, reading TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_runs (
                id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES care_requests(id), kind TEXT NOT NULL,
                source_version INTEGER NOT NULL, input TEXT NOT NULL, status TEXT NOT NULL,
                engine TEXT NOT NULL, output TEXT, error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, finished_at TEXT);
            CREATE TABLE IF NOT EXISTS care_checks (
                id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES care_requests(id), actor_id TEXT NOT NULL REFERENCES users(id),
                medicine_status TEXT NOT NULL, plan_ref TEXT NOT NULL, clinician_source TEXT NOT NULL,
                document_status TEXT NOT NULL, document_details TEXT NOT NULL, document_source TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_barriers (
                id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES care_requests(id), actor_id TEXT NOT NULL REFERENCES users(id),
                source_run_id TEXT, code TEXT NOT NULL, description TEXT NOT NULL, review_note TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_steps (
                id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES care_requests(id), barrier_id TEXT NOT NULL,
                run_id TEXT UNIQUE REFERENCES care_runs(id), actor_id TEXT NOT NULL REFERENCES users(id),
                patient_message TEXT NOT NULL, tasks TEXT NOT NULL, assigned_to TEXT NOT NULL REFERENCES users(id),
                due_at TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_reads (
                step_id TEXT NOT NULL REFERENCES care_steps(id), user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
                PRIMARY KEY(step_id,user_id));
            CREATE TABLE IF NOT EXISTS care_resolutions (
                request_id TEXT PRIMARY KEY REFERENCES care_requests(id), actor_id TEXT NOT NULL REFERENCES users(id),
                note TEXT NOT NULL, collection_verified INTEGER NOT NULL, proof_source TEXT NOT NULL, proof_reference TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL REFERENCES care_requests(id),
                actor TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_operations (
                token TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, request_id TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS care_queue ON care_requests(coordinator_id,staff_id,status);
            ''')
        from access_workflow import AccessWorkflow
        self.access=AccessWorkflow(self)

    def _row(self,db,request_id):
        row=db.execute('SELECT * FROM care_requests WHERE id=?',(request_id,)).fetchone()
        if not row:raise AccessDenied('This request is not available to your account.')
        return dict(row)

    def _auth(self,db,request_id,user_id,action='view'):
        user=account(db,user_id);r=self._row(db,request_id)
        owner=user['role']=='coordinator' and r['coordinator_id']==user_id
        staff=user['role']=='staff' and r['staff_id']==user_id
        family=user['role'] in {'patient','caregiver'} and bool(db.execute('SELECT 1 FROM care_members WHERE request_id=? AND user_id=?',(request_id,user_id)).fetchone())
        viewer=user['role']=='coordinator' and self.access.is_viewer(db,request_id,user_id)
        if not (owner or staff or family or (viewer and action=='view')):raise AccessDenied('This request is not available to your account.')
        if action=='view':return r,user
        if user['must_change']:raise AccessDenied('Change your temporary password first.')
        allowed=(action in {'message','read'} and family or action in {'assign','share'} and owner or
                 action in {'checks','resolve_review','confirm','followup','approve','close','manual_draft','retry_reader'} and staff or
                 action in {'progress','withdraw','assisted_message'} and (owner or staff) or action=='withdraw' and family)
        if not allowed:raise AccessDenied('Your account cannot perform that action on this request.')
        return r,user

    def _event(self,db,rid,actor,kind,detail):
        db.execute('INSERT INTO care_events(request_id,actor,kind,detail,created_at) VALUES(?,?,?,?,?)',(rid,actor,kind,detail,now()))

    def _change(self,db,rid,**fields):
        # Column names are supplied only by this module.
        db.execute('UPDATE care_requests SET '+','.join([*(k+'=?' for k in fields),'version=version+1'])+' WHERE id=?',(*fields.values(),rid))

    def _version(self,r,version):
        if r['version']!=int(version):raise RuleError('This request changed. Reload before continuing.')

    def _routine(self,r):
        if not r['consent']:raise RuleError('Routine follow-up is stopped because permission was withdrawn.')
        if r['status']=='CLOSED':raise RuleError('This request is closed. Start a new question if more help is needed.')

    def _op(self,db,token,actor,action,data,rid):
        token=clean(token,'the action identifier',80)
        digest=hashlib.sha256(json.dumps([actor,action,data],sort_keys=True).encode()).hexdigest()
        old=db.execute('SELECT * FROM care_operations WHERE token=?',(token,)).fetchone()
        if old:
            if old['fingerprint']!=digest:raise RuleError('That action identifier belongs to another request.')
            return old['request_id']
        db.execute('INSERT INTO care_operations VALUES(?,?,?)',(token,digest,rid));return None

    def _detail(self,db,rid):
        r=self._row(db,rid)
        for key,table in [('messages','care_messages'),('runs','care_runs'),('checks','care_checks'),('barriers','care_barriers'),('steps','care_steps'),('resolutions','care_resolutions'),('events','care_events')]:
            r[key]=[dict(x) for x in db.execute(f'SELECT * FROM {table} WHERE request_id=? ORDER BY rowid',(rid,))]
        for m in r['messages']:
            if m['reading']:m['reading']=json.loads(m['reading'])
        for run in r['runs']:
            run['input']=json.loads(run['input'])
            if run['output']:run['output']=json.loads(run['output'])
        for step in r['steps']:
            step['tasks']=json.loads(step['tasks'])
            step['reads']=[dict(x) for x in db.execute('SELECT * FROM care_reads WHERE step_id=?',(step['id'],))]
        ids={r['creator_id'],r['coordinator_id'],r['staff_id']} - {None}
        r['people']={uid:dict(db.execute('SELECT id,username,display_name,role FROM users WHERE id=?',(uid,)).fetchone()) for uid in ids}
        r['members']=[dict(x) for x in db.execute('SELECT u.id,u.username,u.display_name,u.role FROM care_members m JOIN users u ON u.id=m.user_id WHERE m.request_id=?',(rid,))]
        return self.access.enrich(db,r)

    def detail(self,rid,user_id):
        with self.store.connection() as db:
            self._auth(db,rid,user_id)
            return self._detail(db,rid)

    def list_requests(self,user_id):
        with self.store.connection() as db:
            user=account(db,user_id)
            rows=db.execute('''SELECT DISTINCT r.* FROM care_requests r LEFT JOIN care_members m ON m.request_id=r.id
                WHERE (r.coordinator_id=? AND ?='coordinator') OR (r.staff_id=? AND ?='staff')
                OR (m.user_id=? AND ? IN ('patient','caregiver')) ORDER BY r.created_at DESC,r.rowid DESC''',
                (user_id,user['role'],user_id,user['role'],user_id,user['role'])).fetchall()
            result=[dict(x) for x in rows]
            if user['role']=='coordinator':
                extra=db.execute('''SELECT DISTINCT r.* FROM care_requests r LEFT JOIN care_request_viewers v ON v.request_id=r.id
                    LEFT JOIN access_handovers h ON h.request_id=r.id WHERE v.user_id=? OR h.to_id=?''',(user_id,user_id)).fetchall()
                seen={r['id'] for r in result};result.extend(dict(x) for x in extra if x['id'] not in seen)
            for r in result:self.access.enrich(db,r)
            return result

    def submit(self,user_id,data,token,reader=read_reply,agent=run_care_agent):
        text=clean(data.get('message'),'your message',2000)
        topic=data.get('topic','other')
        if topic not in TOPICS:raise RuleError('Choose a listed question topic.')
        if data.get('consent')!='yes':raise RuleError('Agree to follow-up contact before sending this request.')
        ref=data.get('plan_reference','').strip()
        if len(ref)>200:raise RuleError('Keep the plan reference within 200 characters.')
        rid=uuid4().hex
        with self.store.connection(write=True) as db:
            user=account(db,user_id)
            if user['role'] not in {'patient','caregiver'} or user['must_change']:raise AccessDenied('A patient or caregiver account sends the original question.')
            old=self._op(db,token,user_id,'submit',[text,topic,ref],rid)
            if old:return old
            coord=db.execute("SELECT id FROM users WHERE active=1 AND role='coordinator' AND must_change=0 ORDER BY is_admin DESC,created_at LIMIT 1").fetchone()
            if not coord:raise RuleError('No coordinator account is available. Ask the local operator for help.')
            db.execute('INSERT INTO care_requests(id,creator_id,coordinator_id,topic,family_plan_ref,created_at) VALUES(?,?,?,?,?,?)',(rid,user_id,coord['id'],topic,ref,now()))
            db.execute('INSERT INTO care_members VALUES(?,?)',(rid,user_id))
            mid=uuid4().hex;db.execute('INSERT INTO care_messages VALUES(?,?,?,?,NULL,?)',(mid,rid,user_id,text,now()))
            self._event(db,rid,person_label(user),'QUESTION_SAVED','Family question saved before agent analysis. Any supplied plan reference is unverified.')
            if opted_out(text):
                self._change(db,rid,consent=0,status='STOPPED');return rid
        self._analyse(rid,mid,1,reader,agent)
        return rid

    def message(self,rid,user_id,text,version,token,reader=read_reply,agent=run_care_agent):
        text=clean(text,'your message',2000);mid=uuid4().hex
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'message')
            if self._op(db,token,user_id,'message',[rid,text,version],rid):return rid
            self._version(r,version);self._routine(r)
            db.execute('INSERT INTO care_messages VALUES(?,?,?,?,NULL,?)',(mid,rid,user_id,text,now()))
            self._change(db,rid,status='READING',active_step_id=None,current_barrier_id=None,review_required=1)
            self._event(db,rid,person_label(user),'QUESTION_SAVED','New family message saved. Earlier instructions require a fresh clinical team-approved next step.')
            if opted_out(text):
                self._change(db,rid,consent=0,status='STOPPED');return rid
            current=r['version']+1
        self._analyse(rid,mid,current,reader,agent,prior_review=bool(r['review_required']));return rid

    def retry_reader(self,rid,user_id,version,token,reader=read_reply,agent=run_care_agent):
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'retry_reader')
            if self._op(db,token,user_id,'retry_reader',[rid,version],rid):return rid
            self._version(r,version);self._routine(r)
            if r['status']=='READING':raise RuleError('The Reader is already running. Reload after it finishes.')
            latest=db.execute('SELECT * FROM care_messages WHERE request_id=? ORDER BY rowid DESC LIMIT 1',(rid,)).fetchone()
            previous=json.loads(latest['reading']) if latest and latest['reading'] else {}
            if previous.get('engine')!='unavailable':raise RuleError('Retry Reader is available for the latest failed reading. Use the Barrier Assistant retry if only Agent 2 failed.')
            self._event(db,rid,person_label(user),'PREVIOUS_FAILED_READING',json.dumps(previous,ensure_ascii=False))
            self._change(db,rid,status='READING',active_step_id=None,current_barrier_id=None,review_required=1)
            self._event(db,rid,person_label(user),'READER_RETRY_REQUESTED','Clinical team requested another reading of the latest saved message. Original text and earlier failure are retained. No approval is granted.')
            mid=latest['id'];current=version+1
        self._analyse(rid,mid,current,reader,agent,prior_review=bool(r['review_required']))
        return rid

    def assisted_message(self,rid,user_id,version,token,data,reader=read_reply,agent=run_care_agent):
        text=clean(data.get('message'),'the family\'s actual words',2000)
        method=data.get('method')
        if method not in {'phone','in_person'} or data.get('read_back')!='yes':raise RuleError('Choose the real contact method and confirm that you recorded the family\'s words with permission.')
        mid=uuid4().hex
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'assisted_message');self._version(r,version);self._routine(r)
            if self._op(db,token,user_id,'assisted_message',[rid,version,text,method],rid):return rid
            db.execute('INSERT INTO care_messages VALUES(?,?,?,?,NULL,?)',(mid,rid,user_id,text,now()))
            db.execute('INSERT INTO care_message_sources VALUES(?,?,?)',(mid,method,person_label(user)))
            self._change(db,rid,status='READING',active_step_id=None,current_barrier_id=None,review_required=1)
            self._event(db,rid,person_label(user),'ASSISTED_FAMILY_MESSAGE','Actual '+method+' conversation recorded with permission. The app did not place a call or send a message.')
        self._analyse(rid,mid,version+1,reader,agent,prior_review=bool(r['review_required']))
        return rid

    def _analyse(self,rid,mid,version,reader,agent,prior_review=False):
        with self.store.connection() as db:
            row=db.execute('SELECT body FROM care_messages WHERE id=?',(mid,)).fetchone();text=row['body']
        urgent=urgent_hint(text)
        if urgent:
            reading=Reading('CLINICAL','Possible urgent clinical concern. Routine AI work stopped by the safety rule.',clinical_concern=True,engine='rules')
        else:
            try:
                reading=reader(text)
                data=reading.data();engine=data.pop('engine')
                reading=(needs_review(data.get('summary','Reader unavailable; clinical team review needed.'),'unavailable') if engine=='unavailable' else validate_reading(data,text,engine if engine in {'crewai','demo'} else 'unavailable'))
            except Exception as exc:reading=needs_review(safe_error_summary(exc),'unavailable')
        with self.store.connection(write=True) as db:
            r=self._row(db,rid)
            if urgent or clinical_hint(text) or reading.category=='CLINICAL':
                self.access.alert(db,r,mid,'URGENT_CLINICAL' if urgent else 'CLINICAL','Original family message needs authorised clinical review.')
            elif reading.category in {'FOLLOWUP_FAILURE','SUPPLY_CONTINUITY'}:
                self.access.alert(db,r,mid,'OPERATIONS','Unresolved follow-up or supply continuity needs the named care team.')
            db.execute('UPDATE care_messages SET reading=? WHERE id=?',(json.dumps(reading.data(),ensure_ascii=False),mid))
            stale=r['version']!=version or not r['consent'] or r['status']=='CLOSED'
            if stale:
                if r['consent'] and r['status']!='CLOSED':
                    self._change(db,rid,review_required=1,status='STAFF_REVIEW',active_step_id=None)
                self._event(db,rid,'Reader','READER_RESULT_OLD','Request changed while reading. Clinical team must review the original and saved result.');return
            review=prior_review or reading.category in {'CLINICAL','UNCLEAR'} or reading.clinical_concern or reading.uncertain
            route='STAFF' if review or reading.category in {'MEDICINE_APPROVAL','RECEIPT_REPORTED'} else 'COORDINATOR'
            db.execute('UPDATE care_requests SET review_required=?,route=?,status=? WHERE id=?',(int(review),route,'STAFF_REVIEW' if review else 'BARRIER_READING',rid))
            self._event(db,rid,'Reader','READER_ROUTED',f'{reading.category}; engine={reading.engine}; routed to {route}. No medicine approved and no action published.')
        if reading.engine not in {'unavailable','rules'} and reading.category!='CLINICAL':self.run_agent(rid,'barrier',version,agent=agent,internal=True)

    def _payload(self,r,kind):
        if kind=='barrier':
            latest=r['messages'][-1]['reading'] or {}
            return {'scope':'Palliative care administrative assistance','reader_category':latest.get('category','UNCLEAR'),
                    'reader_summary':latest.get('summary',''),'messages':[r['messages'][-1]['body']],
                    'medicine_status':r['medicine_status'],'document_status':r['document_status']}
        barrier=next((b for b in r['barriers'] if b['id']==r['current_barrier_id']),None)
        if not barrier:raise RuleError('Clinical team must confirm the barrier before the Follow-up Agent can run.')
        check=r['checks'][-1] if r['checks'] else {}
        return {'scope':'Administrative palliative care follow-up only',
                'confirmed_barrier':{'code':barrier['code'],'description':barrier['description']},
                'medicine_status':r['medicine_status'],'document_status':r['document_status'],
                'checked_plan_reference':check.get('plan_ref','') if r['medicine_status']=='PLAN_VERIFIED' else '',
                'checked_document_details':check.get('document_details','') if r['document_status']=='VERIFIED' else '',
                'care_team_review_open':bool(r['review_required'])}

    def run_agent(self,rid,kind,version,*,user_id=None,token=None,agent=run_care_agent,internal=False):
        if kind not in {'barrier','followup'}:raise RuleError('Choose a listed agent.')
        run_id=uuid4().hex
        with self.store.connection(write=True) as db:
            if internal:r=self._row(db,rid)
            else:
                r,user=self._auth(db,rid,user_id,'followup' if kind=='followup' else 'confirm')
                if self._op(db,token,user_id,'run_'+kind,[rid,version],rid):return rid
            self._version(r,version);self._routine(r)
            if kind=='followup' and r['review_required']:raise RuleError('Resolve the open care team review first.')
            full=self._detail(db,rid);payload=self._payload(full,kind)
            db.execute('INSERT INTO care_runs(id,request_id,kind,source_version,input,status,engine,created_at) VALUES(?,?,?,?,?,\'RUNNING\',\'pending\',?)',
                       (run_id,rid,kind,version,json.dumps(payload,ensure_ascii=False),now()))
            self._event(db,rid,'App workflow','AGENT_STARTED',kind+' requested. No database lock is held during the AI request.')
        try:
            result=agent(kind,payload)
            if result.engine not in {'demo','crewai','unavailable'}:raise ValueError('Unknown engine')
            output=validate_care(kind,result.output) if result.engine!='unavailable' else None
            error=result.error if result.engine=='unavailable' else ''
        except Exception as exc:
            from care_agents import CareResult
            result=CareResult('unavailable');output=None;error=safe_error_summary(exc,component=kind)
        with self.store.connection(write=True) as db:
            r=self._row(db,rid);stale=r['version']!=version or not r['consent'] or r['status']=='CLOSED'
            status='STALE' if stale else 'FAILED' if output is None else 'DRAFT'
            db.execute('UPDATE care_runs SET status=?,engine=?,output=?,error=?,finished_at=? WHERE id=?',
                       (status,result.engine,json.dumps(output,ensure_ascii=False) if output else None,error,now(),run_id))
            if not stale:
                if kind=='barrier':
                    review=bool(r['review_required']) or bool(output and (output['clinical_concern'] or output['uncertain'])) or output is None
                    db.execute('UPDATE care_requests SET review_required=?,status=? WHERE id=?',(int(review),'STAFF_REVIEW' if review else 'STAFF_CONFIRM_BARRIER',rid))
                else:db.execute('UPDATE care_requests SET status=? WHERE id=?',('AWAITING_STAFF_APPROVAL' if output else 'FOLLOWUP_FAILED',rid))
            self._event(db,rid,kind.title()+' Agent','AGENT_FINISHED',status+'; engine='+result.engine+'. Draft only; not patient instructions.')
        return rid

    def assign(self,rid,user_id,version,token,name,*,family=False,remove=False):
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'share' if family else 'assign')
            if self._op(db,token,user_id,'share' if family else 'assign',[rid,version,name,remove],rid):return rid
            self._version(r,version)
            target=db.execute('SELECT * FROM users WHERE username=? AND active=1',(str(name).strip().lower(),)).fetchone()
            allowed={'patient','caregiver'} if family else {'staff'}
            if not target or target['role'] not in allowed:raise RuleError('Choose an active '+('patient/caregiver' if family else 'Clinical team')+' username.')
            if family:
                if remove:db.execute('DELETE FROM care_members WHERE request_id=? AND user_id=?',(rid,target['id']))
                else:db.execute('INSERT OR IGNORE INTO care_members VALUES(?,?)',(rid,target['id']))
            else:
                if remove:raise RuleError('Choose another active clinical team account to reassign clinical team responsibility.')
                db.execute('UPDATE care_requests SET staff_id=? WHERE id=?',(target['id'],rid))
                db.execute("UPDATE access_escalations SET target_id=? WHERE request_id=? AND priority IN ('CLINICAL','URGENT_CLINICAL') AND state='OPEN'",(target['id'],rid))
                self._change(db,rid,active_step_id=None)
            self._event(db,rid,person_label(user),'REQUEST_ASSIGNED',('Removed family access for ' if remove else 'Shared with family account ' if family else 'Assigned clinical team account ')+target['username']+('. Earlier drafts need refreshing.' if not family else '.'))
        return rid

    def checks(self,rid,user_id,version,token,data):
        medicine=data.get('medicine_status');documents=data.get('document_status')
        if medicine not in MEDICINE_STATUS or documents not in DOCUMENT_STATUS:raise RuleError('Choose listed check statuses.')
        ref=data.get('checked_plan_ref','').strip();source=data.get('clinician_source','').strip()
        doc_details=data.get('document_details','').strip();doc_source=data.get('document_source','').strip()
        if any(len(x)>1000 for x in [ref,source,doc_details,doc_source]):raise RuleError('Keep each check detail within 1000 characters.')
        if medicine=='NOT_APPROVED' and not source:raise RuleError('Record the authorised clinician or service source for the decision; this app does not make that decision.')
        if medicine=='PLAN_VERIFIED' and (not ref or not source or data.get('clinician_checked')!='yes'):raise RuleError('Record the approved plan reference and authorised clinician/service source, and confirm the check.')
        if documents in {'VERIFIED','MISSING'} and (not doc_details or not doc_source):raise RuleError('Record the checked document details and source.')
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'checks')
            if self._op(db,token,user_id,'checks',[rid,version,data],rid):return rid
            self._version(r,version);self._routine(r)
            db.execute('INSERT INTO care_checks VALUES(?,?,?,?,?,?,?,?,?,?)',(uuid4().hex,rid,user_id,medicine,ref,source,documents,doc_details,doc_source,now()))
            self._change(db,rid,medicine_status=medicine,document_status=documents,active_step_id=None)
            self._event(db,rid,person_label(user),'CHECKS_RECORDED','Existing clinician decision and document check recorded. AI did not approve medicine. Refresh any earlier follow-up draft.')
        return rid

    def resolve_review(self,rid,user_id,version,token,note,checked):
        note=clean(note,'the actual care team review note',1000)
        if checked!='yes':raise RuleError('Confirm that the care team reviewed the original request and you recorded the outcome.')
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'resolve_review')
            if self._op(db,token,user_id,'review',[rid,version,note],rid):return rid
            self._version(r,version)
            if not r['review_required']:raise RuleError('No open care team review is waiting.')
            self._change(db,rid,review_required=0,status='STAFF_CONFIRM_BARRIER' if r['consent'] else 'STOPPED',active_step_id=None)
            db.execute("UPDATE access_escalations SET state='REVIEWED',reviewed_at=? WHERE request_id=? AND priority IN ('CLINICAL','URGENT_CLINICAL')",(now(),rid))
            self._event(db,rid,person_label(user),'CARE_TEAM_REVIEW_RECORDED',note)
        return rid

    def confirm(self,rid,user_id,version,token,data,agent=run_care_agent):
        code=data.get('code')
        if code not in BARRIERS:raise RuleError('Choose the actual barrier clinical team identified.')
        description=clean(data.get('description'),'the clinical team-confirmed barrier',1000)
        note=clean(data.get('review_note'),'how clinical team checked the barrier',1000)
        if data.get('barrier_checked')!='yes':raise RuleError('Confirm that clinical team checked the original request and identified this barrier.')
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'confirm')
            if self._op(db,token,user_id,'confirm',[rid,version,data],rid):return rid
            self._version(r,version);self._routine(r)
            if r['review_required']:raise RuleError('Resolve the open care team review before confirming a routine barrier.')
            barrier_id=uuid4().hex
            db.execute('INSERT INTO care_barriers VALUES(?,?,?,?,?,?,?,?)',(barrier_id,rid,user_id,None,code,description,note,now()))
            self._change(db,rid,current_barrier_id=barrier_id,active_step_id=None,status='FOLLOWUP_READING')
            self._event(db,rid,person_label(user),'BARRIER_CONFIRMED',code+': '+description+'. '+note)
            new_version=version+1
        self.run_agent(rid,'followup',new_version,agent=agent,internal=True);return rid

    def manual_draft(self,rid,user_id,version,token,data):
        output=validate_care('followup',{'summary':'Manual clinical team draft; no AI was used.',
            'staff_tasks':[x.strip() for x in data.get('tasks','').splitlines() if x.strip()],
            'patient_message':data.get('patient_message','').strip()})
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'manual_draft')
            if self._op(db,token,user_id,'manual_draft',[rid,version,data],rid):return rid
            self._version(r,version);self._routine(r)
            if r['review_required'] or not r['current_barrier_id']:raise RuleError('Clinical team must resolve review and confirm the barrier first.')
            payload=self._payload(self._detail(db,rid),'followup')
            db.execute('INSERT INTO care_runs(id,request_id,kind,source_version,input,status,engine,output,created_at,finished_at) VALUES(?,?,?,?,?,\'DRAFT\',\'manual\',?,?,?)',
                       (uuid4().hex,rid,'followup',version,json.dumps(payload),json.dumps(output),now(),now()))
            db.execute('UPDATE care_requests SET status=\'AWAITING_STAFF_APPROVAL\' WHERE id=?',(rid,))
            self._event(db,rid,person_label(user),'MANUAL_DRAFT_SAVED','Manual draft saved. Separate clinical team approval is still required.')
        return rid

    def approve(self,rid,user_id,version,token,data):
        message=clean(data.get('patient_message'),'the checked message for the patient or caregiver',1600)
        tasks=[clean(x,'a checked clinical team task',400) for x in data.get('tasks','').splitlines() if x.strip()]
        if not 1<=len(tasks)<=6:raise RuleError('Enter one to six clinical team tasks, one per line.')
        due=due_time(data.get('due_at'))
        if datetime.fromisoformat(due)<=datetime.now(timezone.utc):raise RuleError('Choose a future follow-up time.')
        if data.get('staff_approved')!='yes':raise RuleError('Clinical team must review and explicitly approve the tasks and family message.')
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'approve')
            if self._op(db,token,user_id,'approve',[rid,version,data],rid):return rid
            self._version(r,version);self._routine(r)
            if r['review_required']:raise RuleError('An open care team review blocks publication.')
            run=db.execute("SELECT * FROM care_runs WHERE id=? AND request_id=? AND kind='followup'",(data.get('run_id'),rid)).fetchone()
            if not run or run['status']!='DRAFT' or run['source_version']!=r['version']:raise RuleError('Use a current follow-up draft; older drafts cannot be approved.')
            payload=json.loads(run['input'])
            barrier=db.execute('SELECT * FROM care_barriers WHERE id=?',(r['current_barrier_id'],)).fetchone()
            if not barrier or payload['confirmed_barrier']['description']!=barrier['description']:raise RuleError('The confirmed barrier changed. Create a fresh draft.')
            if db.execute('SELECT 1 FROM care_steps WHERE run_id=?',(run['id'],)).fetchone():raise RuleError('This draft was already approved.')
            assignee=db.execute('SELECT id FROM users WHERE username=? AND active=1',(str(data.get('assigned_to','')).strip().lower(),)).fetchone()
            if not assignee or assignee['id'] not in {r['staff_id'],r['coordinator_id']}:raise RuleError('Assign the follow-up to this request\u2019s coordinator or assigned clinical team username.')
            step_id=uuid4().hex
            db.execute('INSERT INTO care_steps VALUES(?,?,?,?,?,?,?,?,?,?)',(step_id,rid,r['current_barrier_id'],run['id'],user_id,message,json.dumps(tasks),assignee['id'],due,now()))
            self._change(db,rid,active_step_id=step_id,status='FOLLOWUP_APPROVED')
            self._event(db,rid,person_label(user),'FOLLOWUP_APPROVED','Clinical team approved the administrative tasks and published the exact checked family message. This is not medicine approval or collection proof.')
        return rid

    def mark_read(self,rid,user_id,version,token,step_id):
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'read')
            if self._op(db,token,user_id,'read',[rid,step_id],rid):return rid
            self._version(r,version)
            if not r['consent'] or r['review_required']:raise RuleError('Routine instructions are paused for clinical team review or withdrawn permission.')
            if not step_id or step_id!=r['active_step_id']:raise RuleError('Instructions changed. Read the current clinical team-approved step first.')
            db.execute('INSERT OR IGNORE INTO care_reads VALUES(?,?,?)',(step_id,user_id,now()))
            self._event(db,rid,person_label(user),'FAMILY_READ_STEP','Family account marked the approved instructions as read. This is not proof of collection.')
        return rid

    def progress(self,rid,user_id,version,token,note):
        note=clean(note,'what actually happened during follow-up',1000)
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'progress')
            if self._op(db,token,user_id,'progress',[rid,version,note],rid):return rid
            self._version(r,version);self._routine(r)
            if not r['active_step_id']:raise RuleError('Clinical team must approve the current follow-up before work is recorded.')
            step=db.execute('SELECT assigned_to FROM care_steps WHERE id=?',(r['active_step_id'],)).fetchone()
            if step['assigned_to']!=user_id:raise AccessDenied('Only the named follow-up owner can record this action.')
            # Progress does not change the checked facts or invalidate the approved message.
            db.execute("UPDATE care_requests SET status='FOLLOWUP_IN_PROGRESS' WHERE id=?",(rid,))
            self._event(db,rid,person_label(user),'FOLLOWUP_ACTION_RECORDED',note)
        return rid

    def withdraw(self,rid,user_id,version,token):
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'withdraw')
            if self._op(db,token,user_id,'withdraw',[rid,version],rid):return rid
            self._version(r,version)
            self._change(db,rid,consent=0,status='STOPPED',active_step_id=None)
            self._event(db,rid,person_label(user),'CONTACT_WITHDRAWN','Routine work stopped. Earlier records remain saved.')
        return rid

    def close(self,rid,user_id,version,token,data):
        note=clean(data.get('resolution_note'),'the clinical team-approved result for the family',1600)
        if data.get('resolved_checked')!='yes':raise RuleError('Clinical team must confirm the barrier was resolved before closing it.')
        with self.store.connection(write=True) as db:
            r,user=self._auth(db,rid,user_id,'close')
            if self._op(db,token,user_id,'close',[rid,version,data],rid):return rid
            self._version(r,version);self._routine(r)
            if r['review_required'] or not r['active_step_id']:raise RuleError('Resolve review and approve the current follow-up before closing this request.')
            barrier=db.execute('SELECT * FROM care_barriers WHERE id=?',(r['current_barrier_id'],)).fetchone()
            if barrier['code']=='MEDICINE_APPROVAL' and r['medicine_status'] not in {'PLAN_VERIFIED','NOT_APPROVED'}:raise RuleError('Record the authorised clinician decision before resolving a medicine-approval request.')
            if barrier['code']=='DOCUMENTS' and r['document_status']!='VERIFIED':raise RuleError('Finish the document check before marking that barrier resolved.')
            task=db.execute('SELECT * FROM access_tasks WHERE request_id=?',(rid,)).fetchone()
            if task and not task['verified_at']:
                if barrier['code']=='COLLECTION_REPORTED':raise RuleError('Use Dispensing proof to verify the care task. A collection report cannot close it.')
                db.execute('INSERT INTO care_support_results VALUES(?,?,?,?,?,?)',(uuid4().hex,rid,r['current_barrier_id'],user_id,note,now()))
                self._change(db,rid,status='AWAITING_EVIDENCE')
                self._event(db,rid,person_label(user),'SUPPORT_RESOLVED_ACCESS_OPEN',note+'. The medicine-access task stays open pending authorised dispensing proof.')
                return rid
            collection=barrier['code']=='COLLECTION_REPORTED'
            source=data.get('proof_source','').strip();reference=data.get('proof_reference','').strip()
            if collection:
                if r['medicine_status']!='PLAN_VERIFIED':raise RuleError('Clinical team must verify the existing clinician-approved plan before confirming medicine collection.')
                if data.get('proof_authority')!='yes' or data.get('proof_match')!='yes' or data.get('proof_full')!='yes':raise RuleError('A collection report needs an authorised matching dispensing record covering the whole task.')
                source=clean(source,'the authorised dispensing source',300);reference=clean(reference,'the dispensing record reference',300)
            else:source=reference=''
            db.execute('INSERT INTO care_resolutions VALUES(?,?,?,?,?,?,?)',(rid,user_id,note,int(collection),source,reference,now()))
            self._change(db,rid,status='CLOSED',active_step_id=None)
            self._event(db,rid,person_label(user),'REQUEST_RESOLVED',note+(' Clinical team checked authorised full dispensing proof.' if collection else ' Support request closed; this does not itself confirm medicine collection.'))
        return rid
