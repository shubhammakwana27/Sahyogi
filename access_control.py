"""Authenticated accounts, bounded sessions and per-case permissions.

No public signup or role selection. The first coordinator is created locally.
The operator who can read the SQLite file or run Python remains trusted.
"""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from uuid import uuid4

ROLES = {'patient':'Patient','caregiver':'Caregiver','coordinator':'Coordinator','staff':'Clinical team'}
ACTION_ROLES = {'approve':'Coordinator','handover':'Coordinator','accept_handover':'Coordinator',
    'add_evidence':'Coordinator','check_details':'Coordinator','approve_update':'Coordinator',
    'record_contact':'Coordinator','reschedule':'Coordinator','review_assistance':'Coordinator',
    'withdraw':'Coordinator','clear_review':'Care team','verify':'Verifier'}
STAFF_ACTIONS = {'verify','clear_review'}
COOKIE = 'sahyogi_session'
SESSION_SECONDS = 8 * 60 * 60
IDLE_SECONDS = 30 * 60
PASSWORD_ROUNDS = 600_000
PASSWORD_MIN_LENGTH = 4
PASSWORD_MAX_LENGTH = 18
# Keep older saved passwords usable at sign-in/current-password checks.
PASSWORD_LOGIN_MAX_LENGTH = 128
PASSWORD_RULE = f"{PASSWORD_MIN_LENGTH} to {PASSWORD_MAX_LENGTH} characters"


class AccessDenied(ValueError):
    pass


def username(value):
    value = value.strip().lower() if isinstance(value,str) else ''
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,39}',value):
        raise ValueError('Use a username with 3 to 40 letters, numbers, dots, dashes or underscores.')
    return value


def password_hash(password):
    if not isinstance(password,str) or not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValueError(f'Use a password or passphrase with {PASSWORD_RULE}.')
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),PASSWORD_ROUNDS).hex()
    return f'pbkdf2_sha256${PASSWORD_ROUNDS}${salt}${digest}'


def password_matches(password,encoded):
    try:
        if not isinstance(password,str) or len(password)>PASSWORD_LOGIN_MAX_LENGTH:return False
        algorithm,rounds,salt,expected=encoded.split('$')
        if algorithm!='pbkdf2_sha256' or int(rounds)!=PASSWORD_ROUNDS:return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(rounds)).hex()
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError):return False


def public_user(row):
    return {k:row[k] for k in ('id','username','display_name','role','is_admin','must_change','active')}


def account(db,user_id):
    row=db.execute('SELECT * FROM users WHERE id=? AND active=1',(user_id,)).fetchone()
    if not row:raise AccessDenied('Sign in with an active account.')
    return public_user(row)


def person_label(user):return f"{user['display_name']} (@{user['username']})"


def membership(db,case_id,user_id):
    row=db.execute('SELECT relation FROM case_members WHERE case_id=? AND user_id=?',(case_id,user_id)).fetchone()
    if not row:raise AccessDenied('This case is not available to your account.')
    return row['relation']


def authorize(db,case_id,user_id,operation='view'):
    user=account(db,user_id); relation=membership(db,case_id,user_id)
    if operation=='view':return user
    if user['must_change']:raise AccessDenied('Change your temporary password before continuing.')
    if operation=='reply' and relation!='former_owner':return user
    if operation=='acknowledge' and user['role'] in {'patient','caregiver'}:return user
    if operation in STAFF_ACTIONS and user['role']=='staff' and relation=='team':return user
    if operation=='accept_handover' and user['role']=='coordinator' and relation=='pending_owner':return user
    if operation not in STAFF_ACTIONS|{'reply','acknowledge','accept_handover'} and user['role']=='coordinator' and relation=='owner':return user
    raise AccessDenied('Your role cannot perform this action for this case.')


def can_act(user,action):
    if user is None:return True  # Local view helpers are also used by unit tests.
    return action in STAFF_ACTIONS if user['role']=='staff' else user['role']=='coordinator' and action not in STAFF_ACTIONS


def prepare_action(db,case,action,data,user_id):
    if action not in ACTION_ROLES:raise AccessDenied('This action is not available.')
    user=authorize(db,case['id'],user_id,action); data=dict(data); label=person_label(user)
    for key in ('checked_by','approved_by','contacted_by','reviewed_by'):
        if key in data:data[key]=label
    if action=='handover':
        name=data.get('person','').strip().lower().removeprefix('@')
        target=db.execute("SELECT * FROM users WHERE username=? AND role='coordinator' AND active=1",(name,)).fetchone()
        if not target or target['id']==user_id:raise AccessDenied('Enter another active coordinator username for the handover.')
        old=db.execute("SELECT user_id FROM case_members WHERE case_id=? AND relation='pending_owner'",(case['id'],)).fetchall()
        for row in old:db.execute("DELETE FROM case_members WHERE case_id=? AND user_id=? AND relation='pending_owner'",(case['id'],row['user_id']))
        db.execute("INSERT INTO case_members VALUES(?,?,'pending_owner') ON CONFLICT(case_id,user_id) DO UPDATE SET relation='pending_owner'",(case['id'],target['id']))
        data['person']=person_label(target)
    elif action=='accept_handover':
        if label!=case['handover_to']:raise AccessDenied('Only the named next coordinator can accept this handover.')
        data['person']=label
    return ACTION_ROLES[action],data,label


def finish_action(db,case_id,action,user_id):
    if action=='accept_handover':
        db.execute("UPDATE case_members SET relation='former_owner' WHERE case_id=? AND relation='owner'",(case_id,))
        db.execute("UPDATE case_members SET relation='owner' WHERE case_id=? AND user_id=?",(case_id,user_id))
    elif action=='verify':
        case=db.execute('SELECT access FROM cases WHERE id=?',(case_id,)).fetchone()
        if case['access']=='CONFIRMED':db.execute("DELETE FROM case_members WHERE case_id=? AND relation='pending_owner'",(case_id,))


class Accounts:
    def __init__(self,store):
        self.store=store
        with store.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
                role TEXT NOT NULL, password_hash TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0,
                must_change INTEGER NOT NULL DEFAULT 1, active INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS case_members (
                case_id TEXT NOT NULL REFERENCES cases(id), user_id TEXT NOT NULL REFERENCES users(id),
                relation TEXT NOT NULL, PRIMARY KEY(case_id,user_id));
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), csrf TEXT NOT NULL,
                created_at REAL NOT NULL, last_seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS login_attempts (
                username TEXT NOT NULL, peer TEXT NOT NULL, attempted_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS account_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT, kind TEXT NOT NULL,
                detail TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS patient_acknowledgements (
                case_id TEXT NOT NULL REFERENCES cases(id), update_id TEXT NOT NULL REFERENCES caregiver_updates(id),
                user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
                PRIMARY KEY(update_id,user_id));
            ''')
        self.dummy_hash=password_hash(secrets.token_hex(8))

    def has_users(self):
        with self.store.connection() as db:return bool(db.execute('SELECT 1 FROM users LIMIT 1').fetchone())

    def _event(self,db,actor,kind,detail):
        db.execute('INSERT INTO account_events(actor_id,kind,detail,created_at) VALUES(?,?,?,?)',(actor,kind,detail,time.time()))

    def create_user(self,name,display,role,password,*,creator=None,bootstrap=False):
        name=username(name)
        if not isinstance(display,str) or not 1<=len(display.strip())<=100:raise ValueError('Enter a display name using 1 to 100 characters.')
        if role not in ROLES:raise ValueError('Choose a listed role.')
        digest=password_hash(password); user_id=uuid4().hex
        try:
            with self.store.connection(write=True) as db:
                if bootstrap:
                    if db.execute('SELECT 1 FROM users LIMIT 1').fetchone() or role!='coordinator':raise AccessDenied('The first coordinator is already set up.')
                else:
                    owner=account(db,creator)
                    if owner['role']!='coordinator' or owner['must_change']:raise AccessDenied('A coordinator must create accounts.')
                    if role in {'coordinator','staff'} and not owner['is_admin']:raise AccessDenied('Only the initial administrator can create clinical team or coordinator accounts.')
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?,?,?)',(user_id,name,display.strip(),role,digest,int(bootstrap),0 if bootstrap else 1,1,time.time()))
                if bootstrap:
                    legacy=db.execute('SELECT * FROM cases WHERE id NOT IN (SELECT case_id FROM case_members)').fetchall()
                    for case in legacy:
                        db.execute("INSERT INTO case_members VALUES(?,?,'owner')",(case['id'],user_id))
                        new_owner=f'{display.strip()} (@{name})'
                        self.store._change(db,case['id'],owner=new_owner)
                        self.store._event(db,case['id'],new_owner,'LOGIN_ACCESS_MIGRATED',
                            'Initial coordinator account now manages this existing case. Previous recorded owner: '+case['owner']+'. Existing review, contact and proof records are retained. Review ownership and arrange a named handover if needed.')
                self._event(db,creator or user_id,'ACCOUNT_CREATED',f'Account {name}; role={role}.')
        except sqlite3.IntegrityError:raise ValueError('That username is already in use.') from None
        return user_id

    def user(self,user_id):
        with self.store.connection() as db:return account(db,user_id)

    def users(self,viewer):
        with self.store.connection() as db:
            user=account(db,viewer)
            if user['role']!='coordinator':raise AccessDenied('Only coordinators can manage case access.')
            return [public_user(r) for r in db.execute('SELECT * FROM users WHERE active=1 ORDER BY role,username')]

    def new_session(self,user_id=None,old_token=None):
        token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32); now=time.time()
        with self.store.connection(write=True) as db:
            db.execute('DELETE FROM sessions WHERE created_at<? OR last_seen<?',(now-SESSION_SECONDS,now-IDLE_SECONDS))
            if old_token:db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(old_token.encode()).hexdigest(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user_id,csrf,now,now))
        return token,{'user':self.user(user_id) if user_id else None,'csrf':csrf}

    def session(self,token):
        if not token or len(token)>200:return None
        digest=hashlib.sha256(token.encode()).hexdigest(); now=time.time()
        with self.store.connection(write=True) as db:
            row=db.execute('SELECT * FROM sessions WHERE token_hash=?',(digest,)).fetchone()
            if not row:return None
            if row['created_at']<now-SESSION_SECONDS or row['last_seen']<now-IDLE_SECONDS:
                db.execute('DELETE FROM sessions WHERE token_hash=?',(digest,));return None
            try:user=account(db,row['user_id']) if row['user_id'] else None
            except AccessDenied:
                db.execute('DELETE FROM sessions WHERE token_hash=?',(digest,));return None
            db.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?',(now,digest))
            return {'user':user,'csrf':row['csrf']}

    def login(self,name,password,peer):
        name=str(name).strip().lower()[:100]; now=time.time()
        with self.store.connection(write=True) as db:
            db.execute('DELETE FROM login_attempts WHERE attempted_at<?',(now-600,))
            count=db.execute('SELECT COUNT(*) FROM login_attempts WHERE username=? OR peer=?',(name,peer)).fetchone()[0]
            if count>=8:raise AccessDenied('Too many sign-in attempts. Wait ten minutes and try again.')
            row=db.execute('SELECT * FROM users WHERE username=? AND active=1',(name,)).fetchone()
            valid=password_matches(password,row['password_hash'] if row else self.dummy_hash)
            if not valid:
                db.execute('INSERT INTO login_attempts VALUES(?,?,?)',(name,peer,now))
            else:
                db.execute('DELETE FROM login_attempts WHERE username=? AND peer=?',(name,peer))
                self._event(db,row['id'],'LOGIN','Signed in.')
        if not valid:raise AccessDenied('Username or password is incorrect.')
        return public_user(row)

    def logout(self,token):
        with self.store.connection(write=True) as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))

    def change_password(self,user_id,current,new):
        digest=password_hash(new)
        with self.store.connection(write=True) as db:
            row=db.execute('SELECT * FROM users WHERE id=? AND active=1',(user_id,)).fetchone()
            if not row or not password_matches(current,row['password_hash']):raise AccessDenied('Current password is incorrect.')
            if password_matches(new,row['password_hash']):raise ValueError('Choose a different new password.')
            db.execute('UPDATE users SET password_hash=?,must_change=0 WHERE id=?',(digest,user_id))
            db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
            self._event(db,user_id,'PASSWORD_CHANGED','Password changed; previous sessions revoked.')

    def reset_local(self,name,new):
        digest=password_hash(new)
        with self.store.connection(write=True) as db:
            row=db.execute('SELECT id FROM users WHERE username=?',(username(name),)).fetchone()
            if not row:raise ValueError('Account not found.')
            db.execute('UPDATE users SET password_hash=?,must_change=1 WHERE id=?',(digest,row['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
            self._event(db,None,'LOCAL_PASSWORD_RESET','Local operator reset '+name)

    def case_ids(self,user_id):
        with self.store.connection() as db:
            account(db,user_id)
            return {r[0] for r in db.execute('SELECT case_id FROM case_members WHERE user_id=?',(user_id,))}

    def assign(self,case_id,member_name,actor,version,*,remove=False):
        with self.store.connection(write=True) as db:
            user=authorize(db,case_id,actor,'manage_members')
            case=self.store._case(db,case_id);self.store._check(case,version)
            target=db.execute('SELECT * FROM users WHERE username=? AND active=1',(username(member_name),)).fetchone()
            if not target or target['role']=='coordinator':raise ValueError('Choose an active patient, caregiver or clinical team username. Use handover for another coordinator.')
            if remove:db.execute('DELETE FROM case_members WHERE case_id=? AND user_id=?',(case_id,target['id']))
            else:db.execute("INSERT INTO case_members VALUES(?,?,'team') ON CONFLICT(case_id,user_id) DO UPDATE SET relation='team'",(case_id,target['id']))
            self.store._change(db,case_id)
            self.store._event(db,case_id,person_label(user),'CASE_ACCESS_CHANGED',('Removed ' if remove else 'Assigned ')+target['username']+' ('+target['role']+').')

    def members(self,case_id,user_id):
        with self.store.connection() as db:
            authorize(db,case_id,user_id)
            return [dict(r) for r in db.execute('SELECT u.username,u.display_name,u.role,m.relation FROM case_members m JOIN users u ON u.id=m.user_id WHERE m.case_id=? ORDER BY u.role,u.username',(case_id,))]

    def acknowledge(self,case_id,update_id,user_id,version):
        from store import now,RuleError
        with self.store.connection(write=True) as db:
            user=authorize(db,case_id,user_id,'acknowledge');case=self.store._detail(db,case_id)
            self.store._check(case,version)
            if not case['consent'] or case['review_required'] or case['handover_to']:raise RuleError('Routine updates are paused. Clinical team need to review this case.')
            latest=case['collection_checks'][-1] if case['collection_checks'] else None
            update=next((u for u in reversed(case['caregiver_updates']) if latest and u['check_id']==latest['id']),None)
            if not update or update['id']!=update_id:raise RuleError('These instructions changed. Reload and read the current approved message.')
            exists=db.execute('SELECT 1 FROM patient_acknowledgements WHERE update_id=? AND user_id=?',(update_id,user_id)).fetchone()
            if exists:return
            db.execute('INSERT INTO patient_acknowledgements VALUES(?,?,?,?)',(case_id,update_id,user_id,now()))
            self.store._change(db,case_id)
            self.store._event(db,case_id,person_label(user),'PORTAL_INSTRUCTIONS_READ','Patient or caregiver marked the current approved instructions as read. This does not confirm collection.')
