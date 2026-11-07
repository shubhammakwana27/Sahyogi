"""Deterministic care-task evidence, ownership, escalation and handover rules."""
from datetime import datetime,timezone
import json
import sqlite3
from uuid import uuid4
from access_control import account,AccessDenied,person_label
from store import clean,due_time,now,RuleError

EVIDENCE_FLAGS=('authority','valid_record','patient_match','task_match','full_coverage')


def evidence_decision(task,check,flags):
    missing=[]
    if check.get('medicine_status')!='PLAN_VERIFIED' or check.get('plan_ref')!=task['plan_ref']:
        missing.append('matching clinician-approved plan check')
    labels={'authority':'authorised source','valid_record':'valid dispensing record',
            'patient_match':'patient match','task_match':'task match','full_coverage':'whole-task coverage'}
    missing.extend(labels[k] for k in EVIDENCE_FLAGS if flags.get(k) is not True)
    return not missing,missing


class AccessWorkflow:
    def __init__(self,flow):
        self.flow=flow;self.store=flow.store
        with self.store.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS access_tasks (
                request_id TEXT PRIMARY KEY REFERENCES care_requests(id), task_ref TEXT UNIQUE NOT NULL,
                patient_ref TEXT NOT NULL, plan_ref TEXT NOT NULL, target TEXT NOT NULL,
                owner_id TEXT NOT NULL REFERENCES users(id), due_at TEXT NOT NULL,
                created_at TEXT NOT NULL, verified_at TEXT);
            CREATE TABLE IF NOT EXISTS access_evidence (
                id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES care_requests(id),
                actor_id TEXT NOT NULL REFERENCES users(id),source TEXT NOT NULL,record_ref TEXT NOT NULL,
                flags TEXT NOT NULL,decision TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS access_escalations (
                id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES care_requests(id),message_id TEXT UNIQUE,
                actor TEXT NOT NULL,priority TEXT NOT NULL,reason TEXT NOT NULL,target_id TEXT NOT NULL REFERENCES users(id),
                state TEXT NOT NULL DEFAULT 'OPEN',created_at TEXT NOT NULL,ack_by TEXT,ack_at TEXT,reviewed_at TEXT);
            CREATE TABLE IF NOT EXISTS access_handovers (
                request_id TEXT PRIMARY KEY REFERENCES care_requests(id),from_id TEXT NOT NULL REFERENCES users(id),
                to_id TEXT NOT NULL REFERENCES users(id),due_at TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_request_viewers (
                request_id TEXT NOT NULL REFERENCES care_requests(id),user_id TEXT NOT NULL REFERENCES users(id),
                PRIMARY KEY(request_id,user_id));
            CREATE TABLE IF NOT EXISTS care_support_results (
                id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES care_requests(id),barrier_id TEXT,
                actor_id TEXT NOT NULL REFERENCES users(id),note TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_clinical_guidance (
                id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES care_requests(id),
                actor_id TEXT NOT NULL REFERENCES users(id),body TEXT NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_message_sources (
                message_id TEXT PRIMARY KEY REFERENCES care_messages(id),method TEXT NOT NULL,recorded_by TEXT NOT NULL);
            ''')

            columns={row['name'] for row in db.execute('PRAGMA table_info(access_tasks)')}
            if 'next_action' not in columns:
                db.execute("ALTER TABLE access_tasks ADD COLUMN next_action TEXT NOT NULL DEFAULT 'Clinical team will check the approved plan and follow up on missing dispensing proof.'")

            guidance_columns={row['name'] for row in db.execute('PRAGMA table_info(care_clinical_guidance)')}
            if 'source_version' not in guidance_columns:
                db.execute('ALTER TABLE care_clinical_guidance ADD COLUMN source_version INTEGER NOT NULL DEFAULT -1')

    def is_viewer(self,db,rid,uid):
        return bool(db.execute('SELECT 1 FROM care_request_viewers WHERE request_id=? AND user_id=?',(rid,uid)).fetchone() or
                    db.execute('SELECT 1 FROM access_handovers WHERE request_id=? AND to_id=?',(rid,uid)).fetchone())

    def enrich(self,db,r):
        rid=r['id'];task=db.execute('SELECT * FROM access_tasks WHERE request_id=?',(rid,)).fetchone()
        r['access_task']=dict(task) if task else None
        r['evidence']=[dict(x) for x in db.execute('SELECT * FROM access_evidence WHERE request_id=? ORDER BY rowid DESC',(rid,))]
        for proof in r['evidence']:proof['flags']=json.loads(proof['flags'])
        r['escalations']=[dict(x) for x in db.execute('SELECT e.*,u.display_name AS target_name,u.username AS target_username FROM access_escalations e JOIN users u ON u.id=e.target_id WHERE request_id=? ORDER BY e.rowid DESC',(rid,))]
        r['support_results']=[dict(x) for x in db.execute('SELECT * FROM care_support_results WHERE request_id=? ORDER BY rowid DESC',(rid,))]
        r['clinical_guidance']=[dict(x) for x in db.execute('SELECT * FROM care_clinical_guidance WHERE request_id=? ORDER BY rowid DESC',(rid,))]
        handover=db.execute('SELECT h.*,u.username AS next_username,u.display_name AS next_name FROM access_handovers h JOIN users u ON u.id=h.to_id WHERE request_id=?',(rid,)).fetchone()
        r['task_handover']=dict(handover) if handover else None
        for m in r.get('messages',[]):
            source=db.execute('SELECT method,recorded_by FROM care_message_sources WHERE message_id=?',(m['id'],)).fetchone()
            m['source']=dict(source) if source else None
        if task:
            owner=db.execute('SELECT username,display_name FROM users WHERE id=?',(task['owner_id'],)).fetchone()
            r['access_task']['owner_name']=owner['display_name'];r['access_task']['owner_username']=owner['username']
            r['access_task']['state']='VERIFIED' if task['verified_at'] else 'PARTIAL' if any(all(p['flags'].get(k) for k in EVIDENCE_FLAGS[:-1]) and not p['flags'].get('full_coverage') for p in r['evidence']) else 'AWAITING_VERIFICATION' if r['evidence'] else 'OPEN'
            r['access_task']['overdue']=not task['verified_at'] and datetime.fromisoformat(task['due_at'])<datetime.now(timezone.utc)
        r['urgent_open']=any(e['priority']=='URGENT_CLINICAL' and e['state']!='REVIEWED' for e in r['escalations'])
        return r

    def register(self,uid,data,token):
        task_ref=clean(data.get('task_ref'),'the unique care task reference',100)
        patient_ref=clean(data.get('patient_ref'),'the sample patient reference',100)
        plan_ref=clean(data.get('plan_ref'),'the clinician plan reference',200)
        target=clean(data.get('target'),'the medication-access task',300)
        due=due_time(data.get('due_at'));rid=data.get('request_id') or uuid4().hex
        if data.get('consent_recorded')!='yes':raise RuleError('Record caregiver or patient permission before registering routine follow-up.')
        with self.store.connection(write=True) as db:
            user=account(db,uid)
            if user['role']!='coordinator' or user['must_change']:raise AccessDenied('A coordinator registers the care task.')
            if self.flow._op(db,token,uid,'register_task',[rid if data.get('request_id') else '',data],rid):return rid
            if data.get('request_id'):
                r,_=self.flow._auth(db,rid,uid,'assign');self.flow._version(r,int(data.get('version','0')));self.flow._routine(r)
                if db.execute('SELECT 1 FROM access_tasks WHERE request_id=?',(rid,)).fetchone():raise RuleError('This request already has a care task.')
            else:
                family=db.execute("SELECT * FROM users WHERE username=? AND active=1 AND role IN ('patient','caregiver')",(data.get('family_username','').strip().lower(),)).fetchone()
                staff=db.execute("SELECT * FROM users WHERE username=? AND active=1 AND role='staff'",(data.get('staff_username','').strip().lower(),)).fetchone()
                if not family or not staff:raise RuleError('Choose an existing family account and a clinical team account.')
                db.execute('INSERT INTO care_requests(id,creator_id,coordinator_id,staff_id,topic,family_plan_ref,status,route,review_required,created_at) VALUES(?,?,?,?,?,?,\'WAITING_FAMILY\',\'COORDINATOR\',0,?)',
                           (rid,family['id'],uid,staff['id'],'medicine',plan_ref,now()))
                db.execute('INSERT INTO care_members VALUES(?,?)',(rid,family['id']))
            try:db.execute('INSERT INTO access_tasks(request_id,task_ref,patient_ref,plan_ref,target,owner_id,due_at,created_at,verified_at) VALUES(?,?,?,?,?,?,?,?,NULL)',(rid,task_ref,patient_ref,plan_ref,target,uid,due,now()))
            except sqlite3.IntegrityError:raise RuleError('Use a unique care task reference.') from None
            self.flow._change(db,rid)
            self.flow._event(db,rid,person_label(user),'ACCESS_TASK_REGISTERED',task_ref+'; owner='+user['username']+'; due='+due+'. Plan reference supplied for clinical team verification. Missing evidence does not prove non-collection.')
        return rid

    def alert(self,db,r,mid,priority,reason):
        target=r['staff_id'] or r['coordinator_id']
        db.execute('INSERT OR IGNORE INTO access_escalations(id,request_id,message_id,actor,priority,reason,target_id,created_at) VALUES(?,?,?,?,?,?,?,?)',
                   (uuid4().hex,r['id'],mid,'Rules and workflow',priority,reason,target,now()))

    def acknowledge(self,rid,uid,version,token,alert_id):
        with self.store.connection(write=True) as db:
            r,user=self.flow._auth(db,rid,uid,'progress');self.flow._version(r,version)
            if self.flow._op(db,token,uid,'ack_escalation',[rid,alert_id,version],rid):return rid
            alert=db.execute('SELECT * FROM access_escalations WHERE id=? AND request_id=?',(alert_id,rid)).fetchone()
            if not alert:raise RuleError('Choose a recorded escalation.')
            if alert['priority'] in {'URGENT_CLINICAL','CLINICAL'} and not (user['role']=='staff' and r['staff_id']==uid):raise AccessDenied('Assigned clinical team must acknowledge a clinical escalation.')
            if alert['state']=='OPEN':db.execute("UPDATE access_escalations SET state='ACKNOWLEDGED',ack_by=?,ack_at=? WHERE id=?",(uid,now(),alert_id))
            self.flow._event(db,rid,person_label(user),'ESCALATION_ACKNOWLEDGED','In-app escalation acknowledged; this does not complete clinical review or verify access.')
        return rid

    def escalate(self,rid,uid,version,token,data):
        note=clean(data.get('note'),'the unresolved problem',1000)
        with self.store.connection(write=True) as db:
            r,user=self.flow._auth(db,rid,uid,'progress');self.flow._version(r,version);self.flow._routine(r)
            if self.flow._op(db,token,uid,'escalate',[rid,version,note],rid):return rid
            self.alert(db,r,None,'OPERATIONS',note)
            self.flow._event(db,rid,person_label(user),'ACCESS_ESCALATED',note+'. Assigned team queue updated. No external notification was sent.')
        return rid

    def guidance(self,rid,uid,version,token,data):
        body=clean(data.get('guidance'),'the institution-approved family guidance',1600)
        source=clean(data.get('guidance_source'),'the authorised clinical source',300)
        if data.get('guidance_checked')!='yes':raise RuleError('Confirm that this guidance was checked with the authorised clinical team.')
        with self.store.connection(write=True) as db:
            r,user=self.flow._auth(db,rid,uid,'checks');self.flow._version(r,version);self.flow._routine(r)
            if self.flow._op(db,token,uid,'clinical_guidance',[rid,version,body,source],rid):return rid
            if not db.execute("SELECT 1 FROM access_escalations WHERE request_id=? AND priority IN ('CLINICAL','URGENT_CLINICAL')",(rid,)).fetchone():raise RuleError('No clinical escalation is recorded.')
            db.execute('INSERT INTO care_clinical_guidance VALUES(?,?,?,?,?,?,?)',(uuid4().hex,rid,uid,body,source,now(),version))
            self.flow._event(db,rid,person_label(user),'APPROVED_CLINICAL_GUIDANCE','Clinical team recorded guidance checked with '+source+'. Review remains separate.')
        return rid

    def evidence(self,rid,uid,version,token,data):
        source=clean(data.get('proof_source'),'the authorised dispensing source',300)
        reference=clean(data.get('proof_reference'),'the dispensing record reference',300)
        note=clean(data.get('proof_note'),'the evidence review note',1000)
        flags={k:data.get(k)=='yes' for k in EVIDENCE_FLAGS}
        decision=data.get('decision')
        if decision not in {'accept','reject'}:raise RuleError('Choose accept or reject.')
        with self.store.connection(write=True) as db:
            r,user=self.flow._auth(db,rid,uid,'checks');self.flow._version(r,version);self.flow._routine(r)
            if self.flow._op(db,token,uid,'access_evidence',[rid,version,data],rid):return rid
            task=db.execute('SELECT * FROM access_tasks WHERE request_id=?',(rid,)).fetchone()
            if not task:raise RuleError('Register an access task before checking dispensing evidence.')
            check=db.execute('SELECT * FROM care_checks WHERE request_id=? ORDER BY rowid DESC LIMIT 1',(rid,)).fetchone()
            valid,missing=evidence_decision(dict(task),dict(check) if check else {},flags)
            if decision=='accept' and (not valid or r['review_required']):
                raise RuleError('Cannot verify access. Check '+', '.join(missing+(['completed clinical team review'] if r['review_required'] else []))+'.')
            db.execute('INSERT INTO access_evidence VALUES(?,?,?,?,?,?,?,?,?)',
                       (uuid4().hex,rid,uid,source,reference,json.dumps(flags),'ACCEPTED' if decision=='accept' else 'REJECTED',note,now()))
            if decision=='accept':
                db.execute('UPDATE access_tasks SET verified_at=? WHERE request_id=?',(now(),rid))
                db.execute('INSERT INTO care_resolutions VALUES(?,?,?,?,?,?,?)',(rid,uid,note,1,source,reference,now()))
                self.flow._change(db,rid,status='CLOSED',active_step_id=None)
                self.flow._event(db,rid,person_label(user),'ACCESS_VERIFIED','Authorised matching full dispensing evidence accepted. This does not establish medicine use, pain relief or clinical success.')
            else:
                self.flow._event(db,rid,person_label(user),'EVIDENCE_REJECTED',note+'. Access task remains open with its owner and due time.')
        return rid

    def handover(self,rid,uid,version,token,data):
        note=clean(data.get('note'),'the handover reason',1000);due=due_time(data.get('due_at'))
        if datetime.fromisoformat(due)<=datetime.now(timezone.utc):raise RuleError('Choose a future next action time.')
        with self.store.connection(write=True) as db:
            r,user=self.flow._auth(db,rid,uid,'assign');self.flow._version(r,version);self.flow._routine(r)
            if self.flow._op(db,token,uid,'task_handover',[rid,version,data],rid):return rid
            target=db.execute("SELECT * FROM users WHERE username=? AND role='coordinator' AND active=1",(data.get('next_owner','').strip().lower(),)).fetchone()
            if not target or target['id']==uid:raise RuleError('Choose another active coordinator account.')
            if not db.execute('SELECT 1 FROM access_tasks WHERE request_id=?',(rid,)).fetchone():raise RuleError('This request has no access task to hand over.')
            if db.execute('SELECT 1 FROM access_handovers WHERE request_id=?',(rid,)).fetchone():raise RuleError('A handover is already waiting for acceptance.')
            db.execute('INSERT INTO access_handovers VALUES(?,?,?,?,?,?)',(rid,uid,target['id'],due,note,now()))
            self.flow._change(db,rid)
            self.flow._event(db,rid,person_label(user),'HANDOVER_REQUESTED',target['username']+' must sign in and accept. Current ownership stays with '+user['username']+'. '+note)
        return rid

    def accept_handover(self,rid,uid,version,token):
        with self.store.connection(write=True) as db:
            user=account(db,uid);r=self.flow._row(db,rid);self.flow._version(r,version);self.flow._routine(r)
            h=db.execute('SELECT * FROM access_handovers WHERE request_id=?',(rid,)).fetchone()
            if not h or h['to_id']!=uid or user['role']!='coordinator' or user['must_change']:raise AccessDenied('Only the named next coordinator can accept this handover.')
            if self.flow._op(db,token,uid,'accept_task_handover',[rid,version],rid):return rid
            db.execute('INSERT OR IGNORE INTO care_request_viewers VALUES(?,?)',(rid,h['from_id']))
            db.execute('UPDATE access_tasks SET owner_id=?,due_at=? WHERE request_id=?',(uid,h['due_at'],rid))
            db.execute('DELETE FROM access_handovers WHERE request_id=?',(rid,))
            self.flow._change(db,rid,coordinator_id=uid,active_step_id=None)
            self.flow._event(db,rid,person_label(user),'HANDOVER_ACCEPTED','Named coordinator accepted responsibility and the next action time. Refresh any earlier follow-up draft.')
        return rid

    def next_action(self,rid,uid,version,token,data):
        action=clean(data.get('next_action'),'the next practical action',500);due=due_time(data.get('due_at'))
        if datetime.fromisoformat(due)<=datetime.now(timezone.utc):raise RuleError('Choose a future next check time.')
        with self.store.connection(write=True) as db:
            r,user=self.flow._auth(db,rid,uid,'progress');self.flow._version(r,version);self.flow._routine(r)
            if self.flow._op(db,token,uid,'access_next_action',[rid,version,action,due],rid):return rid
            if not db.execute('SELECT 1 FROM access_tasks WHERE request_id=?',(rid,)).fetchone():raise RuleError('Register a care task first.')
            db.execute('UPDATE access_tasks SET next_action=?,due_at=? WHERE request_id=?',(action,due,rid))
            self.flow._change(db,rid)
            self.flow._event(db,rid,person_label(user),'ACCESS_NEXT_ACTION',action+'; next check='+due+'. Named ownership unchanged.')
        return rid
