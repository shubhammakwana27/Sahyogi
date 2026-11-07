"""Role-specific authenticated web routes. All case reads and writes are scoped."""
import json
import secrets
from urllib.parse import parse_qs,urlsplit,urlencode
from uuid import uuid4

from app import (Handler,UI_USER,UI_CSRF,UI_PATH,layout,e,label,form,field,check,note,
                 home,case_page,help_page,parse_due,pretty_due)
from store import RuleError
from access_control import (AccessDenied,ROLES,ACTION_ROLES,COOKIE,SESSION_SECONDS,
                            authorize,account,membership,person_label,
                            PASSWORD_MIN_LENGTH,PASSWORD_MAX_LENGTH,PASSWORD_LOGIN_MAX_LENGTH,PASSWORD_RULE)
from caregiver_contact import current_update,contact_progress
from care_views import care_home,request_page,care_help,care_plan_page,examples_page
from ui_components import panel,help_button
from runtime_settings import ACTIVE_SETTINGS
from api_settings import api_settings_page,require_api_admin


class ScopedStore:
    def __init__(self,store,accounts,user):self.store,self.accounts,self.user=store,accounts,user
    def list_cases(self):
        with self.store.connection() as db:
            account(db,self.user['id'])
            return [dict(c) for c in db.execute('SELECT c.* FROM cases c JOIN case_members m ON m.case_id=c.id WHERE m.user_id=? ORDER BY c.due_at,c.created_at',(self.user['id'],))]
    def detail(self,case_id):
        with self.store.connection() as db:
            authorize(db,case_id,self.user['id'])
            return self.store._detail(db,case_id)


def patient_next(case):
    if not case['consent']:return 'Routine contact is stopped. Your saved records remain available.'
    if case['review_required']:return 'The care team needs to review your message. Check here for clinical team-approved updates.'
    if case['access']=='CONFIRMED':return 'Clinical team accepted proof covering this task. Collection is recorded as confirmed.'
    _,update,_=current_update(case)
    if update:return 'Read the approved instructions below. You can mark them as read or send a question.'
    return 'The coordinator is checking the next step. You can send your question below. Approved instructions will appear here.'


def patient_home(scoped,csrf,user):
    body='<section class="card"><h2>Your tasks</h2><p>You can see only cases assigned to your account. Approved instructions appear here after the coordinator saves them. Check this page again for updates; the app does not send notifications.</p>'
    cases=scoped.list_cases()
    if not cases:body+='<p>No case is assigned yet. Ask your coordinator to link your username to the correct case.</p>'
    for c in cases:
        full=scoped.detail(c['id'])
        body+=f'<hr><h3><a href="/case?id={e(c["id"])}">{e(c["patient_ref"])}</a></h3><p>{e(c["target"])}</p><p><strong>What you need to do:</strong> {e(patient_next(full))}</p><p>Collection: {label(c["access"])}</p>'
    return layout('Your tasks',body+'</section>')


def patient_case(case,csrf,user):
    body=f'<section class="card"><h2>{e(case["patient_ref"])}</h2><p>{e(case["target"])}</p><p>Collection: {label(case["access"])}</p><h3>What you need to do</h3><p>{e(patient_next(case))}</p></section>'
    details,update,_=current_update(case)
    body+='<section class="card"><h2>Approved instructions from clinical team</h2>'
    if update:
        if case['review_required']:
            body+='<p class="alert">These instructions were approved earlier. A care team review is now open. Check with clinical team for current guidance.</p>'
        body+='<blockquote>'+e(update['body'])+'</blockquote><small>Approved '+pretty_due(update['approved_at'])+'</small>'
        read=any(a['update_id']==update['id'] and a['user_id']==user['id'] for a in case.get('patient_acknowledgements',[]))
        if read:body+='<p>You marked these instructions as read.</p>'
        elif case['consent'] and not case['review_required'] and not case['handover_to']:
            body+=form(csrf,'/acknowledge',f'<input type="hidden" name="update_id" value="{e(update["id"])}"><button>I have read these instructions</button>',case)
        body+='<p>Marking instructions as read does not confirm medicine collection. Clinical team still check dispensing proof.</p>'
    else:body+='<p>No current approved instructions are available yet. Clinical team drafts and unapproved details are not shown here.</p>'
    body+='</section><section class="card"><h2>Send a question or update</h2>'
    if case['consent']:
        body+=form(csrf,'/reply','<label>Your message<textarea name="text" required maxlength="2000"></textarea></label><p>For example: Where should we go? Which documents are needed?</p><button>Send my message</button>',case)
        body+='<p>The Reader helps clinical team understand your message. It does not give medical advice. Clinical team see it in this case; this is not a live emergency service.</p>'
    else:body+='<p>New routine messages are stopped because contact permission was withdrawn.</p>'
    for m in reversed(case['messages']):body+='<hr><blockquote>'+e(m['body'])+'</blockquote><small>Saved '+pretty_due(m['created_at'])+'</small>'
    body+='</section>'
    if case['consent']:
        body+='<details class="danger-zone"><summary>Stop routine follow-up contact</summary>'+form(csrf,'/reply','<input type="hidden" name="text" value="Stop messages."><p>This records withdrawn contact permission. Saved records remain. This demo has no restore-permission button.</p><button class="secondary">Stop routine contact</button>',case)+'</details>'
    return layout('Your case',body)


class PortalHandler(Handler):
    def cookie_token(self):
        # Not SimpleCookie: it drops the whole header at the first cookie it cannot parse, and
        # browsers send this app cookies from every other local app on 127.0.0.1.
        for part in self.headers.get('Cookie','').split(';'):
            name,_,value=part.strip().partition('=')
            if name==COOKIE:return value
        return ''

    def set_cookie(self,token):
        self.pending_cookie=f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS}' if token else f'{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'

    def send_html(self,html,status=200):
        body=html.encode('utf-8');self.send_response(status)
        self.send_header('Content-Type','text/html; charset=utf-8');self.security_headers()
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

    def security_headers(self):
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        # no-referrer makes native form POSTs send Origin: null (Fetch standard),
        # which our origin check correctly rejects. Keep the origin on our own
        # forms while withholding referrers from other sites.
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        if getattr(self,'pending_cookie',None):self.send_header('Set-Cookie',self.pending_cookie)

    def redirect(self,path):
        self.send_response(303);self.send_header('Location',path);self.security_headers()
        self.send_header('Content-Length','0');self.end_headers()

    def context(self,session):
        self.user=session['user'] if session else None
        self.csrf=session['csrf'] if session else ''
        self.ui_tokens=(UI_USER.set(self.user),UI_CSRF.set(self.csrf),UI_PATH.set(urlsplit(self.path).path))
        self.settings_token=ACTIVE_SETTINGS.set(self.server.api_settings.snapshot())

    def end_context(self):
        if hasattr(self,'ui_tokens'):
            UI_USER.reset(self.ui_tokens[0]);UI_CSRF.reset(self.ui_tokens[1]);UI_PATH.reset(self.ui_tokens[2])
            del self.ui_tokens
        if hasattr(self,'settings_token'):
            ACTIVE_SETTINGS.reset(self.settings_token);del self.settings_token

    def scoped(self):return ScopedStore(self.server.store,self.server.accounts,self.user)

    def do_GET(self):
        if not self.valid_host():return self.error('Use the local app address.',403)
        self.pending_cookie=None
        session=self.server.accounts.session(self.cookie_token());self.context(session)
        try:
            path=urlsplit(self.path).path
            if path=='/login':
                if self.user:return self.redirect('/password' if self.user['must_change'] else '/')
                if not self.server.accounts.has_users():
                    return self.send_html(layout('Set up the app','<section class="card"><h2>First coordinator account needed</h2><p>Use the terminal to run manage_users.py setup, or restart app.py and follow the setup prompts. There is no public signup or default password.</p></section>'))
                if not session:
                    token,session=self.server.accounts.new_session();self.set_cookie(token)
                    self.end_context();self.context(session)
                fields=field('username','Username',maximum=40)+field('password','Password',kind='password',maximum=PASSWORD_LOGIN_MAX_LENGTH)
                is_team=bool(parse_qs(urlsplit(self.path).query).get('team'))
                switch='<div class="auth-switch" aria-label="Account type"><a href="/login"'+(' class="active" aria-current="page"' if not is_team else '')+'>Patient / caregiver</a><a href="/login?team=1"'+(' class="active" aria-current="page"' if is_team else '')+'>Clinical team / coordinator</a></div>'
                expired='<div class="notice warn" role="status"><p>That sign-in page had expired. Please sign in again.</p></div>' if parse_qs(urlsplit(self.path).query).get('expired') else ''
                intro=expired+switch+form(self.csrf,'/login',fields+'<button>Sign in</button>')+'<p class="meta-line">Forgot your password? Ask your coordinator.</p>'
                return self.send_html(layout('Sign in',panel('Clinical team or coordinator sign in' if is_team else 'Patient or caregiver sign in',intro,help_text='Ask your coordinator for a username and temporary password. You must change the password at first sign-in. There is no public signup.')))
            if not self.user:return self.redirect('/login')
            if self.user['must_change'] and path!='/password':return self.redirect('/password')
            if path=='/password':
                fields=field('current','Current password',kind='password',maximum=PASSWORD_LOGIN_MAX_LENGTH)+field('new','New password or passphrase',kind='password',maximum=PASSWORD_MAX_LENGTH,minimum=PASSWORD_MIN_LENGTH)+field('repeat','Repeat new password',kind='password',maximum=PASSWORD_MAX_LENGTH,minimum=PASSWORD_MIN_LENGTH)
                return self.send_html(layout('Change password','<section class="card"><h2>Change your password</h2><p>Use '+e(PASSWORD_RULE)+'. Temporary passwords must be changed before opening cases.</p>'+form(self.csrf,'/password',fields+'<button>Save new password</button>')+'</section>'))
            if path=='/':return self.send_html(care_home(self.server.care,self.csrf,self.user,parse_qs(urlsplit(self.path).query)))
            if path=='/care-plan':return self.send_html(care_plan_page(self.server.accounts,self.csrf,self.user))
            if path=='/examples':return self.send_html(examples_page(self.user,parse_qs(urlsplit(self.path).query).get('group',['Featured'])[0]))
            if path=='/request':
                rid=parse_qs(urlsplit(self.path).query).get('id',[''])[0]
                return self.send_html(request_page(self.server.care,self.server.accounts,self.csrf,self.user,rid,parse_qs(urlsplit(self.path).query).get('view',['overview'])[0]))
            if path=='/help':return self.send_html(care_help(self.csrf,self.user))
            if path=='/cases':
                if self.user['role'] in {'patient','caregiver'}:return self.send_html(patient_home(self.scoped(),self.csrf,self.user))
                if self.user['role']=='staff':
                    body='<section class="card"><h2>What you need to do</h2><p>Open an assigned case to record a care team review or verify pending dispensing proof. The coordinator manages practical follow-up.</p>'
                    cases=self.scoped().list_cases()
                    if not cases:body+='<p>No case is assigned yet. Ask the coordinator to add your clinical team username.</p>'
                    for c in cases:
                        detail=self.scoped().detail(c['id'])
                        task='Care team review needed' if c['review_required'] else 'Dispensing proof needs review' if any(v['status']=='PENDING' for v in detail['evidence']) else 'Read saved progress; no clinical team check waiting'
                        body+=f'<hr><h3><a href="/case?id={e(c["id"])}">{e(c["patient_ref"])}</a></h3><p>{e(task)}</p>'
                    return self.send_html(layout('Clinical team tasks',body+'</section>'))
                query=parse_qs(urlsplit(self.path).query)
                page=home(self.scoped(),self.csrf,query.get('q',[''])[0][:200],query.get('view',['all'])[0])
                message='Create or open your assigned cases. Assign the patient, caregiver and clinical team accounts, check barriers, approve instructions and follow up.' if self.user['role']=='coordinator' else 'Open assigned cases that need care team review or dispensing proof checks. Record only the checks you actually completed.'
                return self.send_html(page.replace('<section class="card"><h2>Start here</h2>',f'<section class="card"><h2>What you need to do</h2><p>{e(message)}</p></section><section class="card"><h2>Start here</h2>',1))
            if path=='/legacy-help':
                if self.user['role'] in {'patient','caregiver'}:
                    return self.send_html(layout('Help','<section class="card"><h2>How to use your account</h2><ol><li>Open Your tasks.</li><li>Open an assigned case and read What you need to do.</li><li>Read clinical team-approved instructions and mark them as read.</li><li>Send a question or collection update.</li><li>Check here again for the coordinator response.</li></ol><p>A collection update is a report. Clinical team still need proof before confirming access.</p></section>'))
                return self.send_html(help_page(self.csrf))
            if path=='/accounts':return self.send_html(self.accounts_page())
            if path=='/api-settings':return self.send_html(api_settings_page(self.server,self.csrf,self.user))
            if path in {'/case','/export'}:
                case_id=parse_qs(urlsplit(self.path).query).get('id',[''])[0]
                case=self.scoped().detail(case_id)
                if path=='/export':
                    if self.user['role'] not in {'coordinator','staff'}:raise AccessDenied('This download is for assigned clinical team only.')
                    body=json.dumps(case,ensure_ascii=False,indent=2).encode('utf-8')
                    self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8')
                    self.send_header('Content-Disposition','attachment; filename="sahyogi_case_'+uuid4().hex[:8]+'.json"')
                    self.security_headers();self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                if self.user['role'] in {'patient','caregiver'}:return self.send_html(patient_case(case,self.csrf,self.user))
                with self.server.store.connection() as db:relation=membership(db,case_id,self.user['id'])
                UI_USER.set({**self.user,'relation':relation})
                html=case_page(self.scoped(),self.csrf,case_id)
                if self.user['role']=='coordinator' and relation=='owner':html=html.replace('</main>',self.members_page(case)+'</main>')
                if self.user['role']=='coordinator' and case['review_required']:html=html.replace('<section class="card next">','<section class="card"><h2>Assigned clinical team must review this case</h2><p>Assign a clinical team account below. That person can sign in and record the care team review. A coordinator account cannot clear it.</p></section><section class="card next">',1)
                return self.send_html(html)
            return self.error('Page not found.',404)
        except AccessDenied:return self.error('This page or case is not available to your account.',404)
        except RuleError as exc:return self.error(str(exc),404)
        finally:self.end_context()

    def accounts_page(self):
        users=self.server.accounts.users(self.user['id'])
        roles=ROLES if self.user['is_admin'] else {k:ROLES[k] for k in ['patient','caregiver']}
        fields=field('username','New username',maximum=40)+field('display_name','Display name',maximum=100)
        fields+='<label>Account role<select name="role">'+''.join(f'<option value="{e(k)}">{e(v)}</option>' for k,v in roles.items())+'</select></label>'
        fields+=field('password','Temporary password or passphrase',kind='password',maximum=PASSWORD_MAX_LENGTH,minimum=PASSWORD_MIN_LENGTH)
        body='<div class="page-title"><h1>Accounts</h1></div><div class="two-col">'+panel('Create an account',form(self.csrf,'/accounts/create',fields+'<button>Create account</button>'),'blue','Give temporary passwords privately. The account holder changes it at first sign-in. Only the initial administrator can create clinical team or coordinator accounts. Creating an account does not assign access to any request.')+'<section class="card"><h2>Available accounts</h2>'
        body+='<div class="table-wrap"><table><tr><th>Username</th><th>Name</th><th>Role</th></tr>'
        for u in users:body+=f'<tr><td>{e(u["username"])}</td><td>{e(u["display_name"])}</td><td>{e(ROLES[u["role"]])}</td></tr>'
        return layout('Accounts',body+'</table></div></section></div>')

    def members_page(self,case):
        members=self.server.accounts.members(case['id'],self.user['id'])
        body='<section class="card" id="case-access"><h2>Who can see this case</h2><p>Assign a Patient, Caregiver or clinical team account by its exact username. Patients and caregivers see only approved instructions and their case messages. Use handover with a coordinator username to transfer responsibility.</p><ul>'
        for m in members:body+=f'<li>{e(m["display_name"])} (@{e(m["username"])}) · {e(m["role"])} · {label(m["relation"])}</li>'
        body+='</ul>'
        fields=field('username','Account username to assign')+'<label>Change<select name="change"><option value="assign">Assign access</option><option value="remove">Remove access</option></select></label>'
        body+=form(self.csrf,'/members',fields+'<button>Save case access</button>',case)
        return body+'</section>'

    def do_POST(self):
        if not self.valid_host():return self.error('Use the local app address.',403)
        origin=self.headers.get('Origin')
        if origin and origin!=f"http://{self.headers.get('Host')}":return self.error('Use the form on the local app page.',403)
        self.pending_cookie=None
        session=self.server.accounts.session(self.cookie_token());self.context(session)
        try:
            if not session:
                # A sign-in page left open across a restart has nothing to lose: just reload it.
                if urlsplit(self.path).path=='/login':return self.redirect('/login?expired=1')
                return self.error('Sign in again before continuing.',401)
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=32000:return self.error('The form is too large or empty.',413)
            if self.headers.get('Content-Type','').split(';')[0]!='application/x-www-form-urlencoded':return self.error('Unsupported form format.',415)
            parsed=parse_qs(self.rfile.read(length).decode('utf-8'),keep_blank_values=True)
            if any(len(v)!=1 for v in parsed.values()):raise RuleError('Duplicate form fields are not allowed.')
            data={k:v[0] for k,v in parsed.items()}
            if not secrets.compare_digest(data.pop('csrf',''),self.csrf):return self.error('Reload the page and try again.',403)
            path=urlsplit(self.path).path;accounts=self.server.accounts;store=self.server.store;token=data.pop('token','')
            if path=='/login':
                user=accounts.login(data.get('username',''),data.get('password',''),self.client_address[0])
                new_token,_=accounts.new_session(user['id'],self.cookie_token());self.set_cookie(new_token)
                return self.redirect('/password' if user['must_change'] else '/')
            if not self.user:return self.error('Sign in before continuing.',401)
            if path=='/logout':
                accounts.logout(self.cookie_token());self.set_cookie('');return self.redirect('/login')
            if path=='/password':
                if data.get('new')!=data.get('repeat'):raise RuleError('The new passwords do not match.')
                accounts.change_password(self.user['id'],data.get('current'),data.get('new'))
                new_token,_=accounts.new_session(self.user['id'],self.cookie_token());self.set_cookie(new_token);return self.redirect('/')
            if self.user['must_change']:raise AccessDenied('Change your temporary password before continuing.')
            if path.startswith('/api-settings/'):
                require_api_admin(accounts,self.user['id'])
                if path=='/api-settings/apply':self.server.api_settings.apply(data)
                elif path=='/api-settings/test':self.server.api_settings.test(data.get('settings_version'),token)
                elif path=='/api-settings/forget':self.server.api_settings.forget(data.get('settings_version'))
                else:return self.error('API settings action not found.',404)
                return self.redirect('/api-settings')
            if path=='/accounts/create':
                accounts.create_user(data.get('username'),data.get('display_name'),data.get('role'),data.get('password'),creator=self.user['id'])
                return self.redirect('/accounts')
            if path.startswith('/care/'):
                rid=self.care_post(path,data,token)
                view={'/care/assign':'team','/care/share':'team','/care/checks':'checks','/care/review':'review','/care/confirm':'followup','/care/manual':'followup','/care/approve':'overview','/care/progress':'overview','/care/evidence':'evidence','/care/escalate':'escalation','/care/acknowledge':'escalation','/care/guidance':'review','/care/handover':'team','/care/next-action':'plan','/care/retry-reader':'messages','/care/message':'messages','/care/assisted-message':'messages'}.get(path,'barrier' if path=='/care/run' and data.get('kind')=='barrier' else 'followup' if path=='/care/run' else 'overview')
                return self.redirect('/request?'+urlencode({'id':rid} if view=='overview' else {'id':rid,'view':view}))
            if path=='/practice':case_id=store.create_practice(data.get('example_id'),token,principal=self.user['id'])
            elif path=='/create':
                data['due_at']=parse_due(data.get('due_at'));data['owner']=person_label(self.user)
                case_id=store.create(data,token,principal=self.user['id'])
            elif path in {'/reply','/assist','/act','/members','/acknowledge'}:
                case_id=data.get('case_id','');version=int(data.get('version','0'))
                self.scoped().detail(case_id)
                if path=='/reply':store.add_reply(case_id,data.get('text'),version,token,principal=self.user['id'])
                elif path=='/assist':store.request_assistance(case_id,data.get('kind'),version,token,'Coordinator',principal=self.user['id'])
                elif path=='/members':
                    if data.get('change') not in {'assign','remove'}:raise RuleError('Choose assign or remove.')
                    accounts.assign(case_id,data.get('username'),self.user['id'],version,remove=data['change']=='remove')
                elif path=='/acknowledge':accounts.acknowledge(case_id,data.get('update_id'),self.user['id'],version)
                else:
                    action=data.pop('action','');role=ACTION_ROLES.get(action)
                    if not role:raise AccessDenied('This action is not available.')
                    for key in ('due_at','checked_at','contacted_at'):
                        if key in data:data[key]=parse_due(data[key])
                    store.act(case_id,action,data,version,token,role,principal=self.user['id'])
            else:return self.error('Action not found.',404)
            return self.redirect('/case?'+urlencode({'id':case_id}))
        except AccessDenied as exc:return self.error(str(exc),403)
        except (RuleError,ValueError,KeyError,UnicodeError) as exc:return self.error(str(exc) if isinstance(exc,(RuleError,ValueError)) else 'The form is incomplete. Reload and try again.')
        except Exception:return self.error('The action could not finish. Reopen the case and review its saved history.',500)
        finally:self.end_context()


    def care_post(self,path,data,token):
        flow=self.server.care;uid=self.user['id']
        if path=='/care/submit':return flow.submit(uid,data,token)
        if path=='/care/task':
            data['due_at']=parse_due(data.get('due_at'))
            return flow.access.register(uid,data,token)
        rid=data.get('request_id','');version=int(data.get('version','0'))
        if path=='/care/assisted-message':return flow.assisted_message(rid,uid,version,token,data)
        if path in {'/care/handover','/care/next-action'}:
            data['due_at']=parse_due(data.get('due_at'))
            return (flow.access.handover if path=='/care/handover' else flow.access.next_action)(rid,uid,version,token,data)
        if path=='/care/accept-handover':return flow.access.accept_handover(rid,uid,version,token)
        if path=='/care/evidence':return flow.access.evidence(rid,uid,version,token,data)
        if path=='/care/guidance':return flow.access.guidance(rid,uid,version,token,data)
        if path=='/care/escalate':return flow.access.escalate(rid,uid,version,token,data)
        if path=='/care/acknowledge':return flow.access.acknowledge(rid,uid,version,token,data.get('alert_id'))
        if path=='/care/message':return flow.message(rid,uid,data.get('message'),version,token)
        if path=='/care/retry-reader':return flow.retry_reader(rid,uid,version,token)
        if path in {'/care/assign','/care/share'}:return flow.assign(rid,uid,version,token,data.get('username'),family=path=='/care/share',remove=data.get('change')=='remove')
        if path=='/care/checks':return flow.checks(rid,uid,version,token,data)
        if path=='/care/review':return flow.resolve_review(rid,uid,version,token,data.get('review_note'),data.get('review_checked'))
        if path=='/care/confirm':return flow.confirm(rid,uid,version,token,data)
        if path=='/care/run':return flow.run_agent(rid,data.get('kind'),version,user_id=uid,token=token)
        if path=='/care/manual':return flow.manual_draft(rid,uid,version,token,data)
        if path=='/care/approve':
            data['due_at']=parse_due(data.get('due_at'))
            return flow.approve(rid,uid,version,token,data)
        if path=='/care/read':return flow.mark_read(rid,uid,version,token,data.get('step_id'))
        if path=='/care/progress':return flow.progress(rid,uid,version,token,data.get('note'))
        if path=='/care/withdraw':return flow.withdraw(rid,uid,version,token)
        if path=='/care/close':return flow.close(rid,uid,version,token,data)
        raise AccessDenied('This request action is not available.')
