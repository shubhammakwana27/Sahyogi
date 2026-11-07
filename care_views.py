"""Focused, role-specific screens for the palliative medicine-access prototype."""
from urllib.parse import urlencode
from app import layout,e,form,field,check,pretty_due,local_due
from care_agents import TOPICS,BARRIERS,MEDICINE_STATUS,DOCUMENT_STATUS
from ui_components import panel,pill,link,help_button,facts,icon
from pdf_examples import EXAMPLES,FEATURED
from care_safety import URGENT_NOTICE
from access_control import AccessDenied

STATUS={'WAITING_FAMILY':'Waiting for family reply','AWAITING_EVIDENCE':'Dispensing proof still needed',
 'READING':'Message received','BARRIER_READING':'Checking the request','STAFF_REVIEW':'Clinical team review needed',
 'STAFF_CONFIRM_BARRIER':'Confirm the barrier','FOLLOWUP_READING':'Preparing follow-up draft',
 'FOLLOWUP_FAILED':'Follow-up draft needs attention','AWAITING_STAFF_APPROVAL':'Clinical team approval needed',
 'FOLLOWUP_APPROVED':'Approved next step ready','FOLLOWUP_IN_PROGRESS':'Follow-up in progress',
 'CLOSED':'Request completed','STOPPED':'Routine follow-up stopped'}


def select(name,title,options,blank=False,selected=None):
    return '<label>'+e(title)+'<select required name="'+e(name)+'">'+('<option value="">Choose after checking</option>' if blank else '')+''.join('<option value="'+e(k)+'"'+(' selected' if k==selected else '')+'>'+e(v)+'</option>' for k,v in options.items())+'</select></label>'


def textarea(name,title,value='',maximum=1000):
    return '<label>'+e(title)+'<textarea name="'+e(name)+'" required maxlength="'+str(maximum)+'">'+e(value)+'</textarea></label>'


def care_form(csrf,path,content,button,r=None):
    hidden='' if r is None else '<input type="hidden" name="request_id" value="'+e(r['id'])+'"><input type="hidden" name="version" value="'+str(r['version'])+'">'
    return form(csrf,path,hidden+content+'<button>'+e(button)+'</button>')


def url(r,view='overview'):return '/request?'+urlencode({'id':r['id'],'view':view})


def title(text,sub='',action=''):
    return '<header class="page-title"><div><h1>'+e(text)+'</h1>'+('<p>'+e(sub)+'</p>' if sub else '')+'</div>'+action+'</header>'


def notice(text,urgent=False,warn=False):return '<div class="notice'+(' urgent' if urgent else ' warn' if warn else '')+'" role="status"><p>'+e(text)+'</p></div>'


def family_next(r):
    if r.get('urgent_open'):return URGENT_NOTICE
    if not r['consent']:return 'Routine follow-up has stopped. Your saved messages remain available.'
    if r['status']=='CLOSED':return 'Read the clinical team-approved result. Start a new question if you need more help.'
    if r['review_required']:return 'Clinical team need to review your message. You can add more information under Messages.'
    if r['active_step_id']:return 'Read the approved next step, mark it as read and reply under Messages if needed.'
    return 'Your request is with the care team. Check here for their approved reply.'


ATTENTION={'STAFF_REVIEW','STAFF_CONFIRM_BARRIER','AWAITING_STAFF_APPROVAL','FOLLOWUP_FAILED'}


def status_pill(r):
    tone='sage' if r['status']=='CLOSED' else 'sand' if r['status'] in ATTENTION else 'neutral'
    return pill(STATUS.get(r['status'],r['status']),tone)


def request_item(r,family=False):
    t=r.get('access_task');overdue=bool(t and t['overdue'] and r['consent'] and not t['verified_at'])
    main='<strong>'+e(t['task_ref'] if t else TOPICS[r['topic']])+'</strong>'
    if t:main+='<small>'+e(t['target'])+'</small>'
    elif not family:main+='<small>Caregiver question · Care task not linked yet</small>'
    if family:main+='<small>'+e(family_next(r))+'</small>'
    side=pill('Urgent clinical review','red') if r.get('urgent_open') else ''
    side+=status_pill(r)
    if t and t['verified_at']:side+=pill('Verified access','sage')
    if t and not family:side+='<small>'+e(t['owner_name'])+'</small><small'+(' class="overdue"' if overdue else '')+'>'+('Overdue · ' if overdue else 'Due ')+pretty_due(t['due_at'])+'</small>'
    return '<a class="request-item" href="'+e(url(r))+'"><span class="ri-main">'+main+'</span><span class="ri-side">'+side+'</span></a>'


def care_home(flow,csrf,user,query=None):
    query=query or {};family=user['role'] in {'patient','caregiver'};requests=flow.list_requests(user['id'])
    if family:
        body=title('Questions and tasks')+notice('For an urgent health concern, seek urgent medical help through your treating team or local emergency service. Do not wait for this app.')
        sample=EXAMPLES.get(query.get('example',[''])[0]);message=sample['message'] if sample else ''
        fields=select('topic','What do you need help with?',TOPICS)+field('plan_reference','Plan reference, if you have one','',required=False)+textarea('message','Your question or message',message,2000)
        fields+=check('consent','I agree that the assigned care team may follow up on this request')
        ask=panel('Ask your care team',care_form(csrf,'/care/submit',fields,'Send question to care team'),help_text='Write in your own words, including Marathi or Hindi. This sends a new question. For an existing medicine task, open it from Your requests and use Messages. Your coordinator creates your account; there is no public signup.')
        listing='<div class="request-list">'+''.join(request_item(r,True) for r in requests)+'</div>' if requests else '<p class="empty">No requests yet.</p>'
        mine=panel('Your requests',listing,help_text='Open a request to see your clinical team-approved next step. Return here to check for updates. The app does not send SMS, WhatsApp or phone alerts.')
        # A practice message was just chosen, or there is nothing to open: the form comes first.
        first,second=(ask,mine) if sample or not requests else (mine,ask)
        body+='<div class="two-col">'+first+second+'</div>'
    else:
        register=link('Register a care task','/care-plan') if user['role']=='coordinator' else ''
        body=title('Questions and tasks','',register)
        is_open=lambda r:r['status'] not in {'CLOSED','STOPPED'}
        is_overdue=lambda r:bool(r.get('access_task') and r['access_task']['overdue'] and r['consent'])
        is_review=lambda r:bool(r['review_required'])
        is_verified=lambda r:bool(r.get('access_task') and r['access_task']['verified_at'])
        filters={'open':('Open',is_open),'overdue':('Overdue',is_overdue),'review':('Needs review',is_review),'verified':('Verified',is_verified),'all':('All',lambda r:True)}
        flt=query.get('filter',['open'])[0]
        if flt not in filters:flt='open'
        tabs=''
        for key,(name,test) in filters.items():
            n=sum(1 for r in requests if test(r));alert=key in {'overdue','review'} and n
            tabs+='<a'+(' class="active" aria-current="page"' if key==flt else '')+' href="/?filter='+key+'">'+name+'<span class="count'+(' count-alert' if alert else '')+'">'+str(n)+'</span></a>'
        body+='<nav class="filter-nav" aria-label="Request filters">'+tabs+'</nav>'
        shown=[r for r in requests if filters[flt][1](r)]
        listing='<div class="request-list">'+''.join(request_item(r) for r in shown)+'</div>' if shown else '<p class="empty">No requests in this view.</p>'
        body+=panel('Assigned requests',listing,help_text='Only requests assigned to your account are shown. Overdue is calculated when you open or refresh the page. It does not mean an external alert was sent. Former owners can read handover history.')
    return layout('Questions and tasks',body)


def task_form(accounts,csrf,user,r=None):
    if user['role']!='coordinator' or r and r['coordinator_id']!=user['id']:raise AccessDenied('Only the current coordinator registers a care task.')
    fields=''
    if r is None:
        users=accounts.users(user['id'])
        fields+=select('family_username','Patient or caregiver account',{u['username']:u['display_name']+' (@'+u['username']+')' for u in users if u['role'] in {'patient','caregiver'}},True)
        fields+=select('staff_username','Assigned clinical team account',{u['username']:u['display_name']+' (@'+u['username']+')' for u in users if u['role']=='staff'},True)
    fields+=field('task_ref','Unique care task reference',maximum=100)+field('patient_ref','Sample patient reference',maximum=100)
    fields+=field('plan_ref','Existing clinician plan reference',r.get('family_plan_ref','') if r else '',maximum=200)+field('target','Medicine-access task in the existing plan',maximum=300)
    fields+=field('due_at','Next check time (India time)',local_due(),kind='datetime-local')+check('consent_recorded','Patient or caregiver permission for routine follow-up has been recorded')
    return panel('Register the medicine-access task',care_form(csrf,'/care/task',fields,'Register care task',r),'sage','Use a made up clinician-approved plan for practice. Record its reference; assigned clinical team must separately check the authorised source. You remain the named owner until a handover is accepted. Registering a task does not prescribe or approve medicine.')


def care_plan_page(accounts,csrf,user):
    return layout('Register care task',title('Register a care task','Start with the prescribed medicine-access task')+'<div class="narrow">'+task_form(accounts,csrf,user)+'</div>')


def approved_section(r,csrf,user):
    family=user['role'] in {'patient','caregiver'};step=next((s for s in r['steps'] if s['id']==r['active_step_id']),None)
    if not step or r['review_required'] or not r['consent']:
        return panel('Next step from clinical team','<p>No current clinical team-approved next step is ready.</p>','sage','Drafts stay with the care team. Only the exact checked and approved message appears here. A new family message can make an earlier step out of date.')
    content='<div class="message approved"><blockquote>'+e(step['patient_message'])+'</blockquote></div><p class="meta-line">Next follow-up '+pretty_due(step['due_at'])+'</p>'
    if family:
        content+='<p>You marked this step as read.</p>' if any(x['user_id']==user['id'] for x in step['reads']) else care_form(csrf,'/care/read','<input type="hidden" name="step_id" value="'+e(step['id'])+'">','I have read this next step',r)
    else:
        content+='<ul>'+''.join('<li>'+e(x)+'</li>' for x in step['tasks'])+'</ul><p class="meta-line">Owner: '+e(r['people'][step['assigned_to']]['display_name'])+' · Family read confirmations: '+str(len(step['reads']))+'</p>'
        if user['id']==step['assigned_to']:content+=care_form(csrf,'/care/progress',textarea('note','What actually happened?'),'Record follow-up action',r)
    return panel('Clinical team-approved next step',content,'sage','Approval publishes the message in this portal. It does not send an external notification. The named person performs the work outside the app and records what actually happened. A read tick does not prove dispensing.')


def overview(r,csrf,user):
    family=user['role'] in {'patient','caregiver'};staff=user['role']=='staff';owner=r['coordinator_id']==user['id'];t=r['access_task']
    if family:next_text=family_next(r);target='messages';button='Open messages'
    elif r['review_required']:next_text='Assigned clinical team must record the actual care team review.';target='review';button='Open care team review'
    elif owner and not r['staff_id']:next_text='Assign a clinical team account to this request.';target='team';button='Assign clinical team'
    elif staff and r['medicine_status']!='PLAN_VERIFIED':next_text='Check the existing clinician plan and document requirements.';target='checks';button='Open plan checks'
    elif staff and not r['current_barrier_id']:next_text='Read the original message and confirm the actual barrier.';target='barrier';button='Review the barrier'
    elif staff and not r['active_step_id'] and r['current_barrier_id']:next_text='Check the follow-up draft and approve the next step.';target='followup';button='Open follow-up'
    else:next_text='Carry out the approved next action and keep the access task open until dispensing proof is accepted.';target='evidence' if staff else 'plan';button='Check dispensing proof' if staff else 'Update next action'
    next_body='<p class="next-text">'+e(next_text)+'</p>'+link(button,url(r,target if not family else 'messages'))
    access_body=pill('Verified dispensing' if t and t['verified_at'] else 'Access not yet verified','sage' if t and t['verified_at'] else 'sand')
    if t:access_body+='<p>'+e(t['target'])+'</p>'+facts([('Owner',e(t['owner_name'])),('Due',pretty_due(t['due_at'])),('Next action',e(t.get('next_action','Clinical team will check the approved plan and follow up on missing dispensing proof.')))])
    else:access_body+='<p>No medicine-access task is linked yet.</p>'+(link('Link existing clinician task',url(r,'plan'),True) if owner else '')
    next_panel=panel('What happens next',next_body,'primary','Families read approved instructions. Coordinators own practical arrangements. Assigned clinical team confirm barriers, record existing clinician decisions and approve follow-up.')
    access_panel=panel('Medicine access',access_body,'sand','Missing proof means access is not verified; it does not prove that medicine was not collected. Only authorised matching dispensing proof covering the whole task closes a medicine-access task. This does not prove use, pain relief or clinical success.')
    if family:
        # The approved step is why a family opens this page. During an urgent hold the red
        # banner is the only instruction: no card pointing them to messages instead.
        body=('' if r.get('urgent_open') else next_panel)+approved_section(r,csrf,user)+access_panel
    else:body='<div class="split">'+next_panel+access_panel+'</div>'+approved_section(r,csrf,user)
    if r['support_results']:
        body+=panel('Practical support update','<blockquote>'+e(r['support_results'][0]['note'])+'</blockquote><p>Medicine access is still open until dispensing proof is accepted.</p>','lavender','Finishing a document, travel or contact task does not establish dispensing.')
    if r['resolutions']:body+=panel('Clinical team-approved result','<blockquote>'+e(r['resolutions'][-1]['note'])+'</blockquote><p>'+('Authorised full dispensing evidence was accepted.' if r['resolutions'][-1]['collection_verified'] else 'Support request resolved. Medicine access was not verified by this result.')+'</p>','sage','This is the recorded access outcome, not a clinical outcome.')
    current_guidance=next((g for g in r['clinical_guidance'] if g['source_version']==r['version']),None)
    if current_guidance:
        g=current_guidance;body+=panel('Guidance checked by clinical team','<blockquote>'+e(g['body'])+'</blockquote><p class="meta-line">Checked source: '+e(g['source'])+'</p>','sand','A human clinical team member recorded this guidance after checking an authorised clinical source. The agents did not generate it.')
    h=r['task_handover']
    if h:
        b='<p>Waiting for '+e(h['next_name'])+' (@'+e(h['next_username'])+') to accept. The current owner remains responsible.</p>'
        if h['to_id']==user['id']:b+=care_form(csrf,'/care/accept-handover','','Accept named handover',r)
        body+=panel('Handover waiting',b,'lavender','Responsibility transfers only when the named coordinator signs in and accepts. Saved history remains available to the former owner.')
    return body


def messages_view(r,csrf,user):
    family=user['role'] in {'patient','caregiver'};staff=user['role']=='staff';live=r['consent'] and r['status']!='CLOSED';body=''
    content=''
    for m in r['messages']:
        content+='<div class="message"><blockquote>'+e(m['body'])+'</blockquote><small>'+pretty_due(m['created_at'])+(' · Recorded by team from '+e(m['source']['method']) if m.get('source') else ' · Family portal')+'</small></div>'
        if not family and m['reading']:
            reading=m['reading'];content+='<details><summary>Agent 1: Reader result · '+e(reading['category'].replace('_',' ').title())+'</summary><p>'+e(reading['summary'])+'</p><small>'+e(reading['engine'])+'</small></details>'
    if not content:content='<p>No family reply yet.</p>'
    failed=bool(r['messages'] and r['messages'][-1]['reading'] and r['messages'][-1]['reading']['engine']=='unavailable')
    if not family and failed:
        content+=notice('Reader could not finish. Clinical team review is required.')
        if user.get('is_admin'):content+=link('Open API settings','/api-settings',True)
        if staff and live:content+=care_form(csrf,'/care/retry-reader','','Retry Reader on latest saved message',r)
    body+=panel('Messages from the patient or caregiver',content,'blue','Original family words stay saved. Open the Reader result for its interpretation. If the API failed, the initial coordinator can replace or test the key in API settings. A retry uses quota and never approves anything.')
    if live and family:
        body+=panel('Reply to your care team',care_form(csrf,'/care/message',textarea('message','Your reply','',2000),'Send reply to care team',r),'sage','This stays on the same request. Clinical team see your reply when they open or refresh their queue. A reply pauses earlier routine instructions until they are checked again.')
    elif live and (user['id']==r['coordinator_id'] or user['id']==r['staff_id']):
        fields=select('method','How the family replied',{'phone':'Phone conversation','in_person':'In person'})+textarea('message','Exact words from the patient or caregiver','',2000)+check('read_back','I read this back and the patient or caregiver confirmed these words')
        body+=panel('Record an assisted family reply',care_form(csrf,'/care/assisted-message',fields,'Save assisted reply',r),'sage','Use this after a real conversation, for example when the family has no smartphone. The record identifies the team account and channel. The app did not make a phone call or invent a reply.')
    return body


def team_view(r,accounts,csrf,user):
    if user['role']!='coordinator' or r['coordinator_id']!=user['id']:return panel('Team access','<p>You can read this request. Only its current coordinator can change access.</p>')
    users=accounts.users(user['id']);opts={u['username']:u['display_name']+' (@'+u['username']+')' for u in users if u['role']=='staff'}
    staff_content=care_form(csrf,'/care/assign',select('username','Clinical team account',opts,True),'Assign clinical team account',r) if opts else '<p>Create a clinical team account under Accounts first.</p>'
    family_content=care_form(csrf,'/care/share',field('username','Patient or caregiver username')+select('change','Access change',{'assign':'Assign access','remove':'Remove access'}),'Save family access',r)+'<p class="meta-line">Family accounts: '+e(', '.join(m['username'] for m in r['members']))+'</p>'
    body='<div class="two-col">'+panel('Assign clinical team',staff_content,'blue','Use the clinical team account username. Clinical team check plans, confirm the actual barrier and approve follow-up. They ask questions directly to the family through the approved next-step message.')+panel('Family access',family_content,'sage','Enter an existing patient or caregiver username, such as p123. Do not enter a clinical team name here. This links portal access to this request; it does not create an account.')+'</div>'
    if r['access_task'] and not r['task_handover'] and r['status']!='CLOSED' and r['consent']:
        options={u['username']:u['display_name']+' (@'+u['username']+')' for u in users if u['role']=='coordinator' and u['id']!=user['id']}
        if options:
            fields=select('next_owner','Named next coordinator',options,True)+field('due_at','Next action time (India time)',local_due(),kind='datetime-local')+textarea('note','Handover reason and action needed')
            body+=panel('Request a named handover',care_form(csrf,'/care/handover',fields,'Request handover',r),'lavender','The next coordinator must sign in and accept from the request Overview. You remain responsible until acceptance. A handover invalidates old approval drafts.')
    return body


def plan_view(r,accounts,csrf,user):
    t=r['access_task'];owner=user['id']==r['coordinator_id'];body=''
    if not t:return task_form(accounts,csrf,user,r) if owner else panel('Medicine-access task','<p>Ask the current coordinator to link the existing clinician task.</p>')
    content='<p><strong>'+e(t['task_ref'])+'</strong></p><p>Patient reference: '+e(t['patient_ref'])+'<br>Plan reference: '+e(t['plan_ref'])+'</p><p>'+e(t['target'])+'</p><p>Named owner: '+e(t['owner_name'])+'<br>Next check '+pretty_due(t['due_at'])+'</p><p>Next action: '+e(t['next_action'])+'</p>'
    body+=panel('Registered care task',content,'sage','The plan reference must match the plan that clinical team verify under Plan checks. The app records an existing clinician decision; it does not create a prescription.')
    if user['id'] in {r['coordinator_id'],r['staff_id']} and r['status']!='CLOSED' and r['consent']:
        fields=textarea('next_action','Next practical action',t['next_action'],500)+field('due_at','Next check time (India time)',local_due(),kind='datetime-local')
        body+=panel('Update the next action',care_form(csrf,'/care/next-action',fields,'Save next action and time',r),'blue','The named coordinator remains the owner. Record a specific practical action and a future check time. This does not verify dispensing or clear clinical review.')
    return body


def checks_view(r,csrf,user):
    if user['role']!='staff':return panel('Clinical team checks','<p>Assigned clinical team record these checks.</p>')
    if not r['consent'] or r['status']=='CLOSED':return panel('Saved checks','<p>'+e(MEDICINE_STATUS[r['medicine_status']])+' · '+e(DOCUMENT_STATUS[r['document_status']])+'</p>')
    previous=r['checks'][-1] if r['checks'] else {}
    med=select('medicine_status','Clinician decision status',MEDICINE_STATUS,selected=r['medicine_status'])+field('checked_plan_ref','Plan reference actually checked',previous.get('plan_ref',''),required=False,maximum=1000)+field('clinician_source','Authorised clinician or service checked',previous.get('clinician_source',''),required=False,maximum=1000)+check('clinician_checked','I checked the existing clinician-approved plan with the authorised source')
    docs=select('document_status','Document check status',DOCUMENT_STATUS,selected=r['document_status'])+field('document_details','Checked required or missing documents',previous.get('document_details',''),required=False,maximum=1000)+field('document_source','Document requirements source',previous.get('document_source',''),required=False,maximum=1000)
    content='<div class="two-col">'+panel('Clinician plan',med,'blue','Record an existing authorised decision, not your own approval. To mark a plan verified, enter its reference, the authorised source and confirm that you checked it.')+panel('Documents',docs,'sand','Check requirements with the actual authorised service. The AI cannot invent a document list, referral rule, collection location or stock guarantee.')+'</div>'
    return care_form(csrf,'/care/checks',content,'Save clinical team checks',r)


def review_view(r,csrf,user):
    if user['role']!='staff':return panel('Care team review','<p>Assigned clinical team must record the actual clinical or unclear-message review.</p>')
    body=''
    if r['review_required']:
        fields=textarea('review_note','Actual care team review and outcome')+check('review_checked','The care team reviewed the original request and I recorded the outcome')
        body+=panel('Record completed care team review',care_form(csrf,'/care/review',fields,'Record completed care team review',r),'sand','Use only after the real care team has reviewed the concern. Acknowledging a queue flag is separate and cannot clear this review. The app does not diagnose, change doses or decide clinical priority.')
    else:body+=panel('Care team review','<p>No open care team review is waiting.</p>','sage')
    if r['consent'] and r['status']!='CLOSED' and any(x['priority'] in {'CLINICAL','URGENT_CLINICAL'} for x in r['escalations']):
        fields=textarea('guidance','Exact guidance checked by the authorised team','',1600)+field('guidance_source','Authorised clinical source',maximum=300)+check('guidance_checked','I checked this guidance with the authorised clinical team')
        body+=panel('Publish checked clinical guidance',care_form(csrf,'/care/guidance',fields,'Publish checked guidance',r),'blue','Optional: record human-checked institutional guidance for the family. This is not generated by an agent. Publishing guidance does not by itself complete clinical review.')
    return body


def run_label(run):
    engine='Offline practice' if run['engine']=='demo' else run['engine']
    return e(engine)+' · '+e(run['status'].replace('_',' ').capitalize())


def barrier_view(r,csrf,user):
    content='';runs=[x for x in r['runs'] if x['kind']=='barrier']
    for index,run in enumerate(reversed(runs)):
        b=''
        if run['source_version']!=r['version']:b+='<p>Earlier snapshot. Confirm the current need.</p>'
        if run['output']:
            b+='<p>'+e(run['output']['summary'])+'</p>'
            for item in run['output']['barriers']:b+='<h3>'+e(BARRIERS[item['code']])+'</h3><p>'+e(item['description'])+'</p><p>Ask the family: '+e(item['question_for_family'])+'</p>'
        else:b+='<p>'+e(run['error'] or 'No result yet. Reload to check progress.')+'</p>'
        content+='<details'+(' open' if index==0 else '')+'><summary>Barrier suggestion · '+run_label(run)+'</summary>'+b+'</details>'
    if not content:content='<p>No suggestion is ready. Clinical team can clarify the original message and confirm the actual barrier.</p>'
    staff=user['role']=='staff';live=r['consent'] and r['status']!='CLOSED'
    if staff and live and not r['review_required']:content+=care_form(csrf,'/care/run','<input type="hidden" name="kind" value="barrier">','Retry Barrier Assistant',r)
    body=panel('Agent 2: possible barriers',content,'lavender','These are suggestions. Clinical team must read the original question and confirm the actual barrier. A provider failure never approves a plan or supplies missing facts.')
    if staff and live:
        fields=select('code','Barrier confirmed by clinical team',BARRIERS,True)+textarea('description','Confirmed barrier in simple words')+textarea('review_note','How clinical team checked or clarified it')+check('barrier_checked','I reviewed the original request and identified this barrier')
        body+=panel('Confirm the actual barrier',notice('Complete Care team review first.') if r['review_required'] else care_form(csrf,'/care/confirm',fields,'Confirm barrier and ask Follow-up Agent',r),'blue','Ask the patient or caregiver directly when needed. You can correct the suggestion. Confirming asks Agent 3 for an administrative draft; it does not publish it.')
    return body


def followup_view(r,csrf,user):
    staff=user['role']=='staff';live=r['consent'] and r['status']!='CLOSED';content='';runs=[x for x in r['runs'] if x['kind']=='followup']
    for run in reversed(runs):
        current=run['source_version']==r['version'] and run['status']=='DRAFT';b=''
        if run['output']:
            out=run['output'];b+='<p>'+e(out['summary'])+'</p><ul>'+''.join('<li>'+e(x)+'</li>' for x in out['staff_tasks'])+'</ul><blockquote>'+e(out['patient_message'])+'</blockquote>'
            if staff and live and current and not r['review_required']:
                people={r['people'][uid]['username']:r['people'][uid]['display_name'] for uid in [r['coordinator_id'],r['staff_id']] if uid}
                fields='<input type="hidden" name="run_id" value="'+e(run['id'])+'">'+textarea('tasks','Checked tasks, one per line','\n'.join(out['staff_tasks']),2400)+textarea('patient_message','Checked message for the family',out['patient_message'],1600)+select('assigned_to','Follow-up owner account',people,True)+field('due_at','Next follow-up (India time)',local_due(),kind='datetime-local')+check('staff_approved','I checked and approve these tasks and this exact family message')
                b+=care_form(csrf,'/care/approve',fields,'Approve and publish next step',r)
            elif not current:b+='<small>Earlier or already reviewed draft. Refresh the draft after a record change.</small>'
        else:b+='<p>'+e(run['error'] or 'No result yet. Reload to check progress.')+'</p>'
        content+='<details'+(' open' if current else '')+'><summary>Follow-up · '+run_label(run)+'</summary>'+b+'</details>'
    body=panel('Agent 3: follow-up draft',content or '<p>Confirm a barrier first to prepare a draft.</p>','lavender','Check and edit every task and word of the family message, choose an owner and future time, then approve. Only the exact approved text appears in the family portal. The agent does not call services, send external messages or approve medicine.')
    if staff and live and r['current_barrier_id'] and not r['review_required']:
        fields=textarea('tasks','Clinical team tasks, one per line','',2400)+textarea('patient_message','Draft administrative message for family','',1600)
        manual='<details><summary>Write a manual draft</summary>'+care_form(csrf,'/care/manual',fields,'Save manual draft for separate approval',r)+'</details>'
        body+=panel('Refresh or write a draft',care_form(csrf,'/care/run','<input type="hidden" name="kind" value="followup">','Retry Follow-up Agent',r)+manual,'blue','If the API is unavailable, a human can write a manual draft. Saving it does not publish it. Open the saved draft above and separately approve it.')
    body+=approved_section(r,csrf,user)
    if staff and live and r['active_step_id'] and not r['review_required']:
        barrier=next(b for b in r['barriers'] if b['id']==r['current_barrier_id']);fields=textarea('resolution_note','Checked practical support result for family','',1600)+check('resolved_checked','Clinical team checked that this support barrier was resolved')
        if barrier['code']=='COLLECTION_REPORTED' and r['access_task']:
            body+=panel('Collection report needs evidence',link('Open dispensing proof',url(r,'evidence')),'sand','A caregiver report cannot close the medicine-access task.')
        else:
            if barrier['code']=='COLLECTION_REPORTED':fields+=field('proof_source','Authorised dispensing source',maximum=300)+field('proof_reference','Matching record reference',maximum=300)+check('proof_authority','I checked authority and validity')+check('proof_match','The record matches this patient and task')+check('proof_full','The record covers the whole task')
            body+=panel('Record the support result',care_form(csrf,'/care/close',fields,'Approve support result',r),'sage','For a linked medicine task this records the practical result and keeps access open until dispensing proof is accepted. A document or travel result does not prove dispensing.')
    return body


def evidence_view(r,csrf,user):
    t=r['access_task'];body=''
    if not t:return panel('Dispensing proof','<p>Ask the coordinator to link the existing clinician task under Care task first.</p>','sand')
    if user['role']=='staff' and r['consent'] and r['status']!='CLOSED':
        flags=[('authority','Source is authorised'),('valid_record','Dispensing record is valid'),('patient_match','Record matches this patient'),('task_match','Record matches this approved task'),('full_coverage','Record covers the whole task')]
        fields=field('proof_source','Authorised dispensing source',maximum=300)+field('proof_reference','Dispensing record reference',maximum=300)+''.join(check(k,v) for k,v in flags)+select('decision','Evidence decision',{'reject':'Keep access open — proof insufficient','accept':'Accept proof and verify access'})+textarea('proof_note','Checked evidence result for the family')
        body+=panel('Check dispensing evidence',care_form(csrf,'/care/evidence',fields,'Save evidence decision',r),'sage','Use a simulated service record in practice. Clinical team must independently check the source, validity, patient/task match and whole-task coverage. The last verified clinician plan must match the registered plan reference. All five checks and completed review are required to accept. No AI makes this decision.')
    content=pill('Access verified' if t['verified_at'] else 'Access remains open','sage' if t['verified_at'] else 'sand')
    if not r['evidence']:content+='<p>No dispensing evidence has been checked. This does not prove noncollection.</p>'
    for proof in r['evidence']:
        content+='<div class="activity-item">'+pill('Accepted' if proof['decision']=='ACCEPTED' else 'Insufficient proof','sage' if proof['decision']=='ACCEPTED' else 'sand')+'<p>'+e(proof['note'])+'</p><small>'+pretty_due(proof['created_at'])+' · '+e(proof['source'])+' · '+e(proof['record_ref'])+'</small></div>'
    body+=panel('Saved evidence decisions',content,'blue','Accepted full dispensing proof verifies access for this task only. It does not establish medicine taking, pain relief, symptom control or clinical success. A rejected or partial record leaves the named owner and follow-up time in place.')
    return body


def escalation_view(r,csrf,user):
    content=''
    for alert in r['escalations']:
        b=pill(alert['priority'].replace('_',' ').title(),'red' if alert['priority']=='URGENT_CLINICAL' else 'sand')+pill(alert['state'].title())+'<p>'+e(alert['reason'])+'</p><p class="meta-line">Assigned queue: '+e(alert['target_name'])+' (@'+e(alert['target_username'])+')</p>'
        if alert['state']=='OPEN' and (user['role']=='staff' or alert['priority']=='OPERATIONS') and user['id'] in {r['coordinator_id'],r['staff_id']}:
            b+=care_form(csrf,'/care/acknowledge','<input type="hidden" name="alert_id" value="'+e(alert['id'])+'">','Acknowledge queue flag',r)
        content+='<div class="activity-item">'+b+'</div>'
    body=panel('Team escalation queue',content or '<p>No escalation is recorded.</p>','sand','These are in-app queue flags. No call, SMS, WhatsApp or hospital alert was sent. Acknowledging does not complete clinical review or verify medicine access. Assigned clinical team record the actual review separately.')
    if r['consent'] and r['status']!='CLOSED' and user['id'] in {r['coordinator_id'],r['staff_id']}:
        body+=panel('Access still unresolved?',care_form(csrf,'/care/escalate',textarea('note','Unresolved problem and human action needed'),'Add to assigned team queue',r),'blue','Keep the task open, contact the responsible service outside this app and update the next action/time. Escalation is a request for human attention, not proof of completed contact.')
    return body


SECTION_GROUPS=[('',['overview','messages']),('Workflow',['review','checks','barrier','followup','evidence']),('Case admin',['plan','team','escalation','history'])]


def section_marks(r):
    """What each team section's rail entry shows. Reads saved state only; decides nothing."""
    t=r['access_task']
    return {'team':'attention' if not r['staff_id'] else '','plan':'attention' if not t else '',
     'review':'attention' if r['review_required'] else '','checks':'done' if r['medicine_status']=='PLAN_VERIFIED' else '',
     'barrier':'done' if r['current_barrier_id'] else '','followup':'done' if r['active_step_id'] else '',
     'evidence':'done' if t and t['verified_at'] else '','escalation':'attention' if any(a['state']=='OPEN' for a in r['escalations']) else ''}


def section_link(r,key,name,view,mark):
    badge={'done':'<span class="mark-done">'+icon('check')+'<span class="sr-only"> done</span></span>','attention':'<span class="mark-attention"></span><span class="sr-only"> needs attention</span>'}.get(mark,'')
    return '<a'+(' class="active" aria-current="page"' if key==view else '')+' href="'+e(url(r,key))+'"><span>'+e(name)+'</span>'+badge+'</a>'


def section_nav(r,views,view,family):
    if family:return '<nav class="filter-nav" aria-label="Request sections">'+''.join(section_link(r,k,v,view,'') for k,v in views.items())+'</nav>'
    marks=section_marks(r);rail=''
    for group,keys in SECTION_GROUPS:
        rail+=('<div class="case-nav-group">'+group+'</div>' if group else '')+''.join(section_link(r,k,views[k],view,marks.get(k,'')) for k in keys)
    nav='<nav class="case-nav" aria-label="Request sections">'+rail+'</nav>'
    return nav+'<details class="case-nav-mobile"><summary>'+e(views[view])+'</summary>'+nav+'</details>'


def request_page(flow,accounts,csrf,user,rid,view='overview'):
    r=flow.detail(rid,user['id']);family=user['role'] in {'patient','caregiver'}
    views={'overview':'Overview','messages':'Messages'}
    if not family:views.update({'team':'Team access','plan':'Care task','review':'Care team review','checks':'Plan checks','barrier':'Barrier','followup':'Follow-up','evidence':'Dispensing proof','escalation':'Escalation','history':'History'})
    if view not in views:raise AccessDenied('This request view is not available to your account.')
    t=r['access_task']
    body='<a class="back" href="/">'+icon('back')+'Questions and tasks</a><div class="case-title"><h1>'+e(t['task_ref'] if t else TOPICS[r['topic']])+'</h1>'+status_pill(r)+'</div>'
    if not family:
        meta=[('Coordinator',e(r['people'][r['coordinator_id']]['display_name'])),('Clinical team',e(r['people'][r['staff_id']]['display_name']) if r['staff_id'] else 'Not assigned')]
        if t:meta+=[('Patient reference',e(t['patient_ref'])),('Next check',pretty_due(t['due_at']))]
        body+='<dl class="case-meta">'+''.join('<div><dt>'+k+'</dt><dd>'+v+'</dd></div>' for k,v in meta)+'</dl>'
    if r['urgent_open']:body+=notice(URGENT_NOTICE,True)
    elif r['review_required']:body+=notice('Care team review is open. Routine approval is paused.',warn=True)
    if t and t['overdue'] and r['consent']:body+=notice('The next check is overdue. The named owner must follow up and record the next action.',warn=True)
    functions={'overview':lambda:overview(r,csrf,user),'messages':lambda:messages_view(r,csrf,user),'team':lambda:team_view(r,accounts,csrf,user),'plan':lambda:plan_view(r,accounts,csrf,user),'checks':lambda:checks_view(r,csrf,user),'review':lambda:review_view(r,csrf,user),'barrier':lambda:barrier_view(r,csrf,user),'followup':lambda:followup_view(r,csrf,user),'evidence':lambda:evidence_view(r,csrf,user),'escalation':lambda:escalation_view(r,csrf,user),'history':lambda:panel('Saved clinical team history',''.join('<div class="activity-item"><small>'+pretty_due(ev['created_at'])+' · '+e(ev['actor'])+'</small><h3>'+e(ev['kind'].replace('_',' ').title())+'</h3><p>'+e(ev['detail'])+'</p></div>' for ev in r['events']),'blue','The audit history records human actions, agent runs, checks and handovers. Earlier records stay saved.')}
    content=functions[view]()
    if view=='overview' and r['consent'] and r['status']!='CLOSED' and user['id'] in {r['coordinator_id'],r['staff_id'],*[m['id'] for m in r['members']]}:
        content+='<details class="danger-zone"><summary>Stop routine follow-up</summary>'+care_form(csrf,'/care/withdraw','<p>This stops routine follow-up. Saved records remain.</p>','Stop routine follow-up',r)+'</details>'
    body+='<div class="case-frame'+(' family' if family else '')+'">'+section_nav(r,views,view,family)+'<div class="case-main">'+content+'</div></div>'
    return layout('Care request',body)


def examples_page(user,group='Featured'):
    groups=['Featured']+sorted({x['group'] for x in EXAMPLES.values()})
    if group not in groups:group='Featured'
    guide=help_button('Practice examples','Use made up records. These are predefined offline examples, not a measured AI accuracy result. Live AI wording can differ. Clinical team checks and approvals remain required.')
    family=user['role'] in {'patient','caregiver'}
    sub='Choose a message to practise with.' if family else 'Family accounts can copy these into Messages on an existing task.'
    body=title('Practice examples',sub,guide)
    body+='<nav class="filter-nav" aria-label="Example groups">'+''.join('<a'+(' class="active" aria-current="page"' if g==group else '')+' href="/examples?'+urlencode({'group':g})+'">'+e(g)+'</a>' for g in groups)+'</nav>'
    chosen=[EXAMPLES[k] for k in FEATURED] if group=='Featured' else [x for x in EXAMPLES.values() if x['group']==group]
    body+='<div class="example-grid">'
    for x in chosen:
        tag=pill('Urgent clinical stop','red') if x['urgent'] else pill(x['category'].replace('_',' ').capitalize())
        action=link('Use this practice message','/?'+urlencode({'example':x['id']}),True) if family else ''
        body+='<section class="card example"><blockquote>'+e(x['message'])+'</blockquote><div class="example-foot">'+tag+action+'</div></section>'
    body+='</div>'
    return layout('Practice examples',body)


def care_help(csrf,user):
    body=title('Simple guide','Open the ? on any card for help with that step. For a full worked example, see the user manual.')
    items=[('Family accounts','Ask the coordinator for an account. Change your temporary password after first sign-in. Open Questions and tasks to ask, or open an existing request and choose Messages.','blue'),('Coordinators','Create accounts under Accounts. Register the existing medicine-access task, assign clinical team and keep a named owner, next action and check time. Use Team access for a named handover.','sage'),('Clinical team checks','Read Messages. Complete Care team review when required. Check the existing clinician plan and documents, confirm the Barrier, then check and approve the Follow-up draft.','lavender'),('Verify medicine access','Use Dispensing proof. Only authorised valid records matching the patient and whole approved task can verify access. A family report or resolved practical problem is not enough.','sand')]
    body+='<div class="two-col">'+''.join(panel(a,'<p>'+e(b)+'</p>') for a,b,c in items)+'</div>'
    body+=panel('The three agents','<p><strong>1. Reader</strong> understands the family message.</p><p><strong>2. Barrier Assistant</strong> suggests possible practical barriers.</p><p><strong>3. Follow-up Agent</strong> drafts work after clinical team confirm the barrier.</p>','blue','CrewAI runs these roles in live mode. Offline practice uses fixed rules without API calls. Code controls permissions, evidence, ownership and closure. Humans carry out work and approve messages.')
    body+=link('Open practice examples','/examples')
    return layout('Simple guide',body)
