"""Palliative workflow adapters for the existing Barrier and Follow-up roles."""
from dataclasses import dataclass
import os
from agent import provider_settings,clinical_hint
from reader_errors import ReaderOutputError,safe_error_summary
from runtime_settings import current_settings

BARRIERS={
 'MEDICINE_APPROVAL':'Medicine approval record needs checking',
 'DOCUMENTS':'Documents or collection details',
 'TRAVEL':'Travel difficulty', 'COST':'Cost difficulty',
 'AVAILABILITY':'Reported medicine availability',
 'COLLECTION_SUPPORT':'Help with collection or caregiving',
 'COLLECTION_REPORTED':'Collection reported; proof still needed',
 'UNCLEAR':'Clinical team need to clarify the request', 'CLINICAL':'Care team review needed',
 'SUPPLY':'Supply running out','FOLLOWUP':'Unresolved follow-up','SCOPE':'Outside medication-access focus'}
TOPICS={'medicine':'Medicine approval or access','documents':'Documents or collection location',
        'travel':'Travel or cost','support':'Caregiver or collection support','other':'Something else'}
MEDICINE_STATUS={'NOT_CHECKED':'Not checked','NEEDS_CLINICIAN':'Authorised clinician decision needed',
                 'PLAN_VERIFIED':'Existing clinician-approved plan checked','NOT_APPROVED':'Approval not recorded / declined'}
DOCUMENT_STATUS={'NOT_CHECKED':'Not checked','MISSING':'Documents or details still missing','VERIFIED':'Required documents checked'}


@dataclass
class CareResult:
    engine:str
    output:dict|None=None
    error:str=''


def _text(value,maximum):return isinstance(value,str) and bool(value.strip()) and len(value)<=maximum


def validate_care(kind,data):
    if not isinstance(data,dict):raise ReaderOutputError('Invalid care output')
    if kind=='barrier':
        if set(data)!={'summary','barriers','clinical_concern','uncertain'} or not _text(data['summary'],600):raise ReaderOutputError('Invalid barrier output')
        if type(data['clinical_concern']) is not bool or type(data['uncertain']) is not bool:raise ReaderOutputError('Invalid flags')
        if not isinstance(data['barriers'],list) or not 1<=len(data['barriers'])<=6:raise ReaderOutputError('Invalid barriers')
        for b in data['barriers']:
            if not isinstance(b,dict) or set(b)!={'code','description','question_for_family'} or b['code'] not in BARRIERS:raise ReaderOutputError('Invalid barrier')
            if not _text(b['description'],400) or not _text(b['question_for_family'],400):raise ReaderOutputError('Invalid barrier details')
    elif kind=='followup':
        if set(data)!={'summary','staff_tasks','patient_message'} or not _text(data['summary'],600) or not _text(data['patient_message'],1600):raise ReaderOutputError('Invalid follow-up output')
        if not isinstance(data['staff_tasks'],list) or not 1<=len(data['staff_tasks'])<=6 or not all(_text(s,400) for s in data['staff_tasks']):raise ReaderOutputError('Invalid follow-up tasks')
    else:raise ReaderOutputError('Unknown care role')
    return data


def demo_care(kind,payload):
    if kind=='barrier':
        category=payload['reader_category']
        code={'DOCUMENTS_ROUTE':'DOCUMENTS','TRAVEL':'TRAVEL','COST':'COST','MEDICINE_APPROVAL':'MEDICINE_APPROVAL',
              'AVAILABILITY_REPORTED':'AVAILABILITY','CARE_SUPPORT':'COLLECTION_SUPPORT',
              'RECEIPT_REPORTED':'COLLECTION_REPORTED','CLINICAL':'CLINICAL',
              'SUPPLY_CONTINUITY':'SUPPLY','FOLLOWUP_FAILURE':'FOLLOWUP','OUT_OF_SCOPE':'SCOPE'}.get(category,'UNCLEAR')
        question={
          'DOCUMENTS':'Which collection location or document requirement would you like clinical team to check?',
          'TRAVEL':'What is making travel difficult for you?',
          'COST':'Which part of the travel or collection cost is difficult?',
          'MEDICINE_APPROVAL':'Do you have a reference for the plan already given by your clinician?',
          'AVAILABILITY':'Which authorised service did you contact, and what did they tell you?',
          'COLLECTION_SUPPORT':'What practical collection support do you need?',
          'COLLECTION_REPORTED':'Which medicine was collected, where and when? Clinical team still need the dispensing record.',
          'CLINICAL':'Clinical team need to review the original message with the care team.',
          'SUPPLY':'When will the prescribed supply run out, and which authorised service handles the next supply?',
          'FOLLOWUP':'Which access problem remains unresolved, and when was the last contact?',
          'SCOPE':'Which appropriate hospital team should receive this request? Clinical team must check.',
          'UNCLEAR':'Could you explain what help you need in a little more detail?'}[code]
        return {'summary':'Possible barrier from the family message. Clinical team must confirm it.',
                'barriers':[{'code':code,'description':BARRIERS[code],'question_for_family':question}],
                'clinical_concern':code=='CLINICAL','uncertain':code in {'UNCLEAR','SCOPE'}}
    code=payload['confirmed_barrier']['code']
    tasks={
      'DOCUMENTS':['Check the required documents and collection location with the authorised service.','Record the checked facts and confirm the next step with the family.'],
      'TRAVEL':['Check the family travel difficulty and available support.','Discuss a feasible arrangement and record what actually happened.'],
      'COST':['Check the reported cost difficulty and available authorised support.','Record the result; do not promise funding that has not been confirmed.'],
      'MEDICINE_APPROVAL':['Check the existing plan reference with the authorised clinician or service.','Record the clinician decision. Do not prescribe or change medicine.'],
      'AVAILABILITY':['Check the reported availability with the authorised dispensing service.','Record the response and arrange a clinical team-approved follow-up.'],
      'COLLECTION_SUPPORT':['Check who can provide practical collection support through the agreed route.','Record the agreed arrangement and follow up with the family.'],
      'COLLECTION_REPORTED':['Ask the patient or caregiver directly which medicine was collected, where and when.','Have clinical team check the matching authorised dispensing record; a family report is not proof.'],
      'UNCLEAR':['Clarify the original request directly with the patient or caregiver.','Record the confirmed practical need before arranging further work.'],
      'CLINICAL':['Follow the care team review recorded by clinical team.','Limit this follow-up to the administrative next step confirmed by clinical team.'],
      'SUPPLY':['Check the remaining prescribed supply and the existing approved plan with the authorised team.','Agree a checked next action and due time; do not change dose or quantity.'],
      'FOLLOWUP':['Check the unresolved access problem and the recorded contact attempts.','Escalate to the named authorised team and keep the access task open pending proof.'],
      'SCOPE':['Check which hospital team can handle this request.','Record a human handoff without claiming a scan or appointment was booked.']}[code]
    messages={
      'DOCUMENTS':'Please tell us which documents you currently have, so clinical team can check what is still needed.',
      'TRAVEL':'What is making travel difficult for you? Clinical team will check what practical support is actually available.',
      'COST':'Which part of the travel or collection cost is difficult? Clinical team will check available support without promising funding.',
      'MEDICINE_APPROVAL':'If available, please share the reference for the plan already provided by your clinician. Clinical team will check the approval record with the authorised service.',
      'AVAILABILITY':'Which authorised service did you contact, and what did they tell you about availability?',
      'COLLECTION_SUPPORT':'What practical collection or caregiving support do you need? Please explain it to clinical team here.',
      'COLLECTION_REPORTED':'Which medicine did you collect? Where and when? Clinical team still need to check the matching authorised dispensing record.',
      'UNCLEAR':'Could you explain what help you need in a little more detail? Clinical team will check the next step with you.',
      'CLINICAL':'Clinical team recorded the care team review. Please use your agreed care team contact for clinical questions; this message is only an administrative follow-up.',
      'SUPPLY':'When will the prescribed supply run out? The care team will check the next supply through the authorised service.',
      'FOLLOWUP':'Please tell us which access problem is still unresolved. The named owner will check the next action with the authorised team.',
      'SCOPE':'Clinical team will check which hospital team should handle this request. No appointment or investigation has been booked by this app.'}
    message=messages[code]
    if code=='DOCUMENTS' and payload.get('document_status')=='VERIFIED' and payload.get('checked_document_details'):
        message='Clinical team recorded the checked document requirements: '+payload['checked_document_details']+'. Please reply here if you need clarification.'
    if code=='MEDICINE_APPROVAL' and payload.get('medicine_status')=='PLAN_VERIFIED':
        message='Clinical team recorded that the existing clinician-approved plan reference was checked. Clinical team will confirm the next practical arrangement with you. This message does not change treatment.'
    return {'summary':'Draft administrative follow-up for the clinical team-confirmed barrier.',
            'staff_tasks':tasks,'patient_message':message}


def run_care_agent(kind,payload):
    config=current_settings();mode=config.mode
    if mode=='demo':return CareResult('demo',validate_care(kind,demo_care(kind,payload)))
    provider,names=provider_settings()
    if mode not in {'crewai','openai'} or not names:return CareResult('unavailable',error='[CONFIG] Choose a supported provider.')
    key,model=config.api_key,config.model
    if not key or not model or key.startswith('YOUR_') or model.startswith('YOUR_'):return CareResult('unavailable',error='[CONFIG] Set a real provider key and model before using AI.')
    try:
        from crewai_assistants import run_care_crew
        data=run_care_crew(kind,payload,model=model,api_key=key,provider=provider)
        if kind=='barrier' and any(clinical_hint(m) for m in payload.get('messages',[])):
            data['clinical_concern']=True
        return CareResult('crewai',validate_care(kind,data))
    except Exception as exc:return CareResult('unavailable',error=safe_error_summary(exc,component=kind))
