# SAHYOGI Medicine Access App Manual

Simple steps for patients caregivers coordinators and staff

This manual explains the app built from your SAHYOGI PDF. It focuses on one task: helping a family obtain medicine already prescribed in a palliative care plan. Start with a made up care task, identify what is blocking access, publish a checked next step and verify dispensing evidence.

The task stays open when proof is missing or incomplete. A person remains responsible, with a next action and check time. Verified dispensing is the outcome recorded here. It does not prove that the medicine was taken or that pain improved.

### The people using the app

| Account | What that person does |
| --- | --- |
| Patient or Caregiver | Sends messages, reads the approved reply and answers Staff. |
| Coordinator | Registers the existing task, assigns Staff, owns practical follow-up and manages handover. |
| Staff | Checks the authorised plan and documents, confirms barriers, approves messages and checks dispensing evidence. |
| Initial coordinator administrator | Also creates Staff and coordinator accounts and manages API settings. |

### The three agents

1. Reader understands the family message and suggests who needs to review it.

2. Barrier Assistant suggests possible practical problems for Staff to check.

3. Follow-up Agent drafts tasks and a family message after Staff confirms the barrier. Staff must approve it before it appears to the family.

Offline practice uses fixed sample rules. Live AI runs these three roles through CrewAI. Code, rather than an agent, controls evidence checks, permissions, ownership and closure.

### Find the instructions

Start and accounts: page 2. Screens: page 3. Full walkthrough: pages 4 to 9. Unresolved work and clinical review: pages 10 to 11. API help: page 12. Five demo examples: pages 13 to 14. All remaining PDF messages: pages 15 to 19. Records and technical notes: page 20.

Local practice only. Use made up information and simulated service records. This version has no hospital connection, stock lookup, document upload, transport booking or outgoing messages.

## Start the app and create accounts

### Start or update on Windows

1. If updating, stop the old app with Ctrl+C. Copy the entire data folder to a safe backup location.

2. Extract the new ZIP. Open the sahyogi_starter folder. Replace all program files in your working copy while keeping its data folder and existing .venv folder.

3. Double-click START_HERE.bat. Choose 1 for offline practice without an API key. Choose 5 to prepare AI packages and enter the key inside the app.

4. On a fresh installation, follow the terminal prompts to create the first coordinator account. In this manual use username c123 and display name Anita. Choose your own password.

5. Open http://127.0.0.1:8000/login and keep the terminal open. Sign in with the account you created.

If Python is missing, run py --list in PowerShell. Use an installed supported version. Live AI supports Python 3.10 to 3.13. For example, run this from the app folder:

py -3.11 start_app.py

### Create the family and Staff accounts

1. As c123, click Accounts. Create the two accounts below, using your own temporary passwords.

2. Give each person their username and temporary password privately. There is no public signup and no default password.

3. Sign out and sign in as the new account. Enter the temporary password under Current password, choose a new password, repeat it and save. New passwords have 4 to 18 characters.

4. Use separate browser profiles, or sign out between roles. Normal tabs share the same login cookie.

| Username | Display name | Account role |
| --- | --- | --- |
| c123 | Anita | Initial Coordinator |
| p123 | Meena | Caregiver |
| staff1 | Practice Staff | Staff |
| coord2 | Ravi | Coordinator for the handover exercise |

Only the initial administrator creates Staff or other coordinator accounts. Coordinators can create Patient and Caregiver accounts. A username is a login ID; a display name is the name people see. The selected role controls permissions.

The local address works on the computer running the app. A phone opening its own 127.0.0.1 address will not reach this app.

## Find the right screen

### The main menu

| Menu item | What you find |
| --- | --- |
| Questions and tasks | Family question form or the team work queue. |
| Register care task | Coordinator form to register an existing prescribed medicine-access task. |
| Practice examples | The 40 PDF messages, grouped by topic. Featured shows the five demo questions. |
| Simple guide | Short explanation of the people and the three agents. |
| Accounts | Coordinator account creation and the available usernames. |
| API settings | Initial administrator only. Apply, test or remove the active API key. |
| Earlier cases | Your older case workflow and its saved records. |

### Inside an open request

Families have Overview and Messages. Team accounts have separate sections for Team access, Care task, Care team review, Plan checks, Barrier, Follow-up, Dispensing proof, Escalation and History. Open one section at a time.

Overview shows the current next step and medicine-access status. Messages holds original family words. Internal agent results, drafts and Staff review notes are hidden from family accounts. They see only the approved family reply, checked guidance and published result.

### Use the question mark

Click or tap the ? at the top right of a card for a short explanation. Press Tab to reach it and Enter or Space to open it with the keyboard. Tap or activate the same ? again to close it. Urgent warnings stay visible without opening help.

### Colours help you find the section

Pale blue marks a working form, green marks checked next steps, lavender marks agent suggestions or handover, and sand marks evidence or unresolved work. Read the label as well as the colour. On a narrow screen the cards stack vertically.

### If you cannot find the question box

Check Signed in as. Patient and Caregiver accounts have Ask your care team on the home page. Coordinators have a work queue. For a task already registered by the coordinator, open it under Your requests and use Messages instead of creating a second question.

## Register the medicine access task

For the PDF journey, start as c123. You are practising with a made up patient, plan and authorised service. The app records an existing clinician plan; it does not issue a prescription.

1. Click Register care task.

2. Choose p123 as Patient or caregiver account and staff1 as Assigned Staff account.

3. Enter the example references below. Choose a future Next check time in India time.

4. Tick that patient or caregiver permission for routine follow-up has been recorded. Click Register care task.

5. Open Overview. Medicine access should say Access not yet verified. There is no dispensing proof yet; this does not prove noncollection.

| Field | Made up practice value |
| --- | --- |
| Unique care task reference | CARE-001 |
| Sample patient reference | DEMO-P001 |
| Existing clinician plan reference | PLAN-001 |
| Medicine-access task in the existing plan | Collect medicine listed in the approved practice plan |
| Next check time | Choose a future time for this exercise |

### What is saved

The task links to the family account and assigned Staff account. The coordinator becomes its named owner. A default next action asks Staff to check the approved plan and follow up on missing proof. The plan reference is supplied for verification; registering it does not mark it verified.

### Use a question that already exists

A family can ask a question before a task is registered. As its coordinator, open that request, choose Care task and register the existing clinician task there. This links the task to the saved question. Do not create a duplicate record for the same task.

### Keep the next action clear

1. Open Care task on this request.

2. Under Update the next action, enter: Check the sample authorised service for the correct document list and missing dispensing proof.

3. Choose a future check time and click Save next action and time.

The coordinator remains responsible until another named coordinator accepts a handover. Staff can update the practical next action and time, but that does not transfer ownership or clear clinical review.

## Family sends the Marathi reply

Sign in as p123. Open CARE-001 from Your requests. Choose Messages. This keeps the reply on the task that the coordinator registered.

1. In Your reply, paste the message below.

2. Click Send reply to care team. The original words are saved before agent work.

3. Return to Overview to see the status. Staff must check and approve a reply before you see a new next step.

अजून औषध मिळालं नाही. कोणती कागदपत्रं लागतील ते माहीत नाही.

Meaning: We have not received the medicine. We do not know which documents are needed. In offline practice the Reader identifies a document or collection-route question. Barrier Assistant suggests a document barrier. Staff must check what is actually missing.

### If you want to ask a new question

1. Open Questions and tasks. Use Ask your care team.

2. Choose the closest topic. Leave Plan reference, if you have one empty unless you have a reference.

3. Enter Your question or message, tick follow-up permission and click Send question to care team.

4. An active coordinator receives the new question. That coordinator assigns Staff and links a prescribed medicine-access task when appropriate.

### No smartphone or difficult typing

After an actual phone or in-person conversation, the assigned Staff member or current coordinator can open Messages and use Record an assisted family reply. Choose the real contact method, enter the family’s exact words and tick that the words were read back and confirmed. Click Save assisted reply.

The message identifies the team account that recorded it and the contact method. This is a manual record of a real conversation. The app did not call the family or send a message itself.

### What a new reply changes

A new family reply pauses earlier active routine instructions. Staff reviews the current need, confirms the barrier and approves a fresh next step. Earlier messages, checks and approvals remain in history.

## Staff checks the plan and documents

Sign in as staff1. Open CARE-001. Read Messages first so you understand the family’s own words. If Care team review is open, complete the actual review and record its outcome before routine approval.

### Check the existing clinician plan

1. Choose Plan checks.

2. In the Clinician plan card choose Existing clinician-approved plan checked.

3. Enter PLAN-001 under Plan reference actually checked. It must match the registered task for later evidence acceptance.

4. Enter Simulated authorised clinician under Authorised clinician or service checked. Tick the confirmation after the practice check.

### Check the document requirements

1. In the Documents card choose Required documents checked.

2. For Checked required or missing documents enter Demo approved plan reference and sample case reference.

3. For Document requirements source enter Simulated authorised service.

4. Click Save staff checks below the two cards.

These are made up requirements for the exercise. A real service must supply its actual list and collection route. An agent cannot invent the required documents, add a doctor signature or guarantee stock.

### If a decision or document is missing

Use the status matching what was actually checked. Do not mark a plan verified just because the family supplied a reference. A missing or declined decision needs the authorised source. A document status of missing or verified needs details and its source.

### If Staff is not assigned

As the current coordinator, open Team access. Select staff1 under Assign Staff and save. The Family access card takes a patient or caregiver username such as p123. It does not take the Staff name. Creating an account under Accounts is separate from assigning access to a request.

Changing the plan, documents or assigned Staff makes earlier follow-up drafts out of date. Request a fresh draft before approving a new message.

## Confirm the barrier and approve follow up

### Staff confirms the actual barrier

1. As staff1, choose Barrier. Read Agent 2: possible barriers and the original message. Speak with the family if you need clarification.

2. Under Confirm the actual barrier choose Documents or collection details.

3. Enter Family needs the checked document list as the confirmed barrier. For how it was checked, enter Practice service list checked and family question clarified.

4. Tick the confirmation and click Confirm barrier and ask Follow-up Agent. Agent 3 prepares an administrative draft.

### Staff checks the draft

1. Open Follow-up and expand the current draft if needed.

2. Check and edit Checked tasks, one per line. Enter one to six practical tasks based on the facts you checked.

3. Check the exact message for the family. For this exercise use the message below.

4. Choose c123 under Follow-up owner account and a future Next follow-up time in India time.

5. Tick the Staff approval confirmation. Click Approve and publish next step.

For this made up exercise, the checked document list is the demo approved plan reference and sample case reference. Please reply here if you still need help with collection.

### What approval does

It publishes that exact text in the family portal. The family did not see the draft before approval. The assigned person must perform the approved work outside the app and record what actually happened. Publishing does not call a service, book travel, send WhatsApp or authorise medicine.

### When the agent fails

After resolving review and confirming a barrier, open Follow-up, then Refresh or write a draft. Expand Write a manual draft, enter the tasks and family message and save. That is still a draft. Open it above and use the separate approval form to publish it.

If a record changed after the draft was made, use Retry Follow-up Agent to create a current draft. Earlier drafts cannot be approved as current.

## Family reads the reply and Staff records work

### Read the approved next step

1. Sign in as p123 and open CARE-001.

2. On Overview, read Staff-approved next step. It should match the exact message approved on page 7.

3. Click I have read this next step if you have read it.

4. To answer Staff, choose Messages and send Your reply.

Staff and coordinator can see the number of family read confirmations. This mark records a portal action. It does not prove understanding, medicine collection or successful contact outside the app.

### Record what the owner actually did

1. Sign in as the account chosen for the approved follow-up, c123 in this example.

2. Open Overview. Under the approved next step, enter what actually happened, for example Practice document list explained to the caregiver.

3. Click Record follow-up action. Do this after the work, not before it.

### Staff records the practical result

1. As staff1, open Follow-up.

2. Find Record the support result. Enter Document list explained and checked with the family.

3. Tick that Staff checked the support barrier was resolved. Click Approve support result.

4. Return to Overview. The practical support update is visible, but the medicine-access task stays open pending dispensing proof.

A document barrier needs a completed document check before its support result can be recorded. A medicine-approval barrier needs the authorised decision record. Neither result alone proves dispensing.

### If the medicine is still unavailable

Do not record success. Keep the task open, record the remaining problem under Escalation and update Care task with a next action and check time. Contact the authorised service outside the app using the approved local process.

### If the family says they collected it

Ask the caregiver directly which medicine they collected, where and when. Their answer is useful information. It remains a report until Staff checks the authorised dispensing record described on page 9.

## Verify dispensing evidence before closure

As staff1, open Dispensing proof. Use a simulated authorised pharmacy record for this exercise. The app records Staff’s checks; it does not fetch a hospital record or inspect an uploaded document.

### Try an incomplete record first

1. Enter Simulated authorised pharmacy as Authorised dispensing source and DEMO-PART-001 as Dispensing record reference.

2. Tick only the checks you can support. For a partial example, confirm authority, validity, patient match and task match, but leave whole-task coverage unticked.

3. Choose Keep access open — proof insufficient under Evidence decision.

4. Enter Only part of the practice task was covered. Access stays open. Click Save evidence decision.

The insufficient proof is saved. The medicine-access task stays open with its named owner, next action and time. A partial record cannot be accepted as a full task result.

### Accept the full matching record

1. First make sure Plan checks contains a verified PLAN-001, matching the task’s registered plan.

2. Enter the authorised source and a new simulated full record reference, DEMO-FULL-001.

3. Confirm all five checks below only after checking the practice record.

4. Choose Accept proof and verify access. Enter the checked evidence result for the family.

5. Click Save evidence decision. Overview should show verified dispensing and the request should be completed. The family can read the checked result.

| Required check | What Staff confirms |
| --- | --- |
| Source is authorised | The source is permitted to provide this dispensing record. |
| Record is valid | It is a valid dispensing record. |
| Patient match | It belongs to this patient. |
| Approved task match | It matches this registered clinician task. |
| Whole task coverage | It covers the entire task, not just part of it. |

All five checks, a matching verified plan and completed open review are required. Only assigned Staff can accept. A family message, read tick, missing record, coordinator note or agent suggestion cannot close the medicine-access task.

Verified access means dispensing evidence was accepted for this task. It does not establish medicine taking, pain relief or clinical success.

## Keep unresolved work owned and visible

### When follow up has not solved the problem

I told you yesterday we couldn't get the medicine. Why has nobody contacted us?

1. Send this on an open task as the family. Offline practice recognises an unresolved follow-up problem.

2. The task stays open and an operations flag appears under Escalation for the assigned team.

3. As Staff or coordinator, record the remaining problem under Access still unresolved and click Add to assigned team queue.

4. The named owner contacts the authorised service outside the app. Use Care task to record the next practical action and a future check time.

Acknowledging a queue flag records that a team account saw it. It does not prove that contact was made or that the barrier was resolved. The app sends no external alert.

### Find overdue tasks

On the team home page choose Overdue. The app calculates overdue status when a page is opened or refreshed. There is no background SMS reminder. The owner must check the queue and follow the agreed local escalation process.

### Pass work to a named coordinator

1. Create coord2 under Accounts using the initial administrator account. That person must change their temporary password.

2. As the current owner, open the request and choose Team access.

3. Under Request a named handover choose coord2, a future action time and a clear reason. Click Request handover.

4. Until acceptance, c123 remains the named owner. The next coordinator can read the pending request.

5. As coord2, open Overview and click Accept named handover. Ownership and the due time change together. The former owner can read the history but cannot change the task.

The new coordinator should update Care task with a clear next action. Earlier active follow-up instructions are paused on acceptance; Staff must refresh the draft before a new approval.

### Keep closure honest

If no full authorised dispensing proof is available, leave access open. Do not use a practical support result, a queue acknowledgement or a handover as a substitute for evidence.

## Handle clinical concerns with the care team

### Try the PDF urgent example

My father is very sleepy and breathing slowly after taking morphine.

This exact practice wording triggers an independent text rule before an API request. The app saves the message, stops routine AI work, shows a visible urgent-care notice and places a clinical flag in the assigned team’s in-app queue.

Possible urgent clinical concern. Seek urgent medical help now through your treating team or local emergency service. Do not wait for a reply in this app.

1. The family must not wait for the portal in an urgent situation. The fixed notice is general help-seeking guidance, not a diagnosis.

2. The coordinator makes sure an appropriate Staff account is assigned. An in-app queue flag is not a call or a live monitored clinical alert.

3. Assigned Staff can acknowledge the flag under Escalation. Routine approval remains paused.

4. After the actual authorised care team review, Staff opens Care team review, records the review and outcome, ticks the confirmation and saves it.

### Institution approved guidance

After a clinical escalation, assigned Staff can use Publish checked clinical guidance to enter exact guidance checked with the authorised clinical team. Enter its source and confirmation. The family sees it on Overview. This human-entered guidance is separate from completing clinical review.

The default help-seeking notice is not presented as institution-approved medical advice. The prototype contains no hospital-specific emergency protocol. A real service would need to validate and configure that process before use.

### Other medical questions

My mother has severe pain. Can I give her double the morphine dose?

Dose questions, pain despite medicine, vomiting, unusual sleepiness, constipation, fear of addiction and treatment preferences go to human care team review. The agents do not answer them with a dose change, substitute medicine or diagnosis.

The text screen is a conservative prototype rule, not a validated or complete triage system. It can miss or misread wording. Human review and the local urgent-care process remain necessary.

### Source for the general safety approach

NHS Specialist Pharmacy Service, Switching between morphine and other opioids in palliative care, advises immediate medical help for signs such as shallow breathing or drowsiness in suspected overdose. Reference: https://sps.nhs.uk/articles/switching-between-morphine-and-other-opioids-in-palliative-care/ . This source supports escalation, not clinical validation of this app.

## Enter an API key and fix failed agents

For your first walkthrough choose offline practice. To try live AI later, start with choice 5. Only the initial coordinator administrator can manage the key shared by all three roles.

1. As c123, open API settings. Choose Live AI under How should agents run.

2. Choose Sarvam AI, Google Gemini or OpenAI. Enter that provider’s own active key and an exact model ID available to your account.

3. For the existing Sarvam configuration use sarvam-105b and a 60-second wait. The app allows a 10 to 120 second network wait.

4. Click Apply settings for this app session. Then click Test current key. The test uses a made up document question through the Reader and can use API quota or credits.

A key entered here stays in memory until this app stops. It is not saved to the database, case history or a settings file. On restart the app uses startup settings again. Leave the key blank only to keep the current key for the same provider. Existing keys are never shown.

| Error | Next step |
| --- | --- |
| AUTH | Check the selected provider and replace its rejected key. |
| CREDITS or SPEND_LIMIT | Check the provider account balance or spending limit. Retrying does not add credits. |
| RATE_LIMIT | Wait and check the provider account limits. |
| TIMEOUT or CONNECTION | Check the connection and provider service. Review the wait setting. |
| MODEL or ACCESS | Check the exact model ID and whether the account can use it. |
| DEPENDENCY | Restart using choice 5 so the launcher prepares the AI packages. |
| OUTPUT or UNKNOWN | Staff reviews the original message. Use a manual draft if needed. |

### Retry the failed stage

After fixing the issue, assigned Staff opens Messages and clicks Retry Reader on latest saved message for a Reader failure. Use Barrier for Retry Barrier Assistant, or Follow-up for Retry Follow-up Agent. The original message and earlier failure stay saved. A key test or retry never clears an open human review.

### Safe diagnostic command

.\.venv\Scripts\python.exe check_reader.py --test --agent barrier

  --provider sarvam --prompt-key

Type those two displayed parts as one PowerShell command. The key prompt is hidden. It uses a made up question, can use quota and changes no case. Share only safe result/error lines when asking for help.

## Demo examples for access and documents

Use a fresh registered task for each example. Start with offline practice. Send the message under Messages as p123, then use staff1 for checks, barrier confirmation and approval. The following examples are the five favorites on PDF page 12.

### Demo 1 Find the authorised collection route

The doctor prescribed morphine for my mother, but we don't know where to get it.

1. Staff checks the existing plan and contacts the authorised service outside the app to confirm the route.

2. In Barrier, confirm Documents or collection details after clarifying what the family needs.

3. In Follow-up, approve only the checked collection details or a question asking for missing information. Keep access open until dispensing proof is accepted.

Useful because the family gets a checked next step. The agent cannot suggest an unverified shop or guarantee stock.

### Demo 2 Supply is running out

आईचं औषध उद्या संपणार आहे. कुठून आणायचं?

Meaning: Mother’s medicine will finish tomorrow. Where should we get it?

1. Expect a supply-continuity result and an operations queue flag.

2. Staff clarifies the remaining supply and confirms the practical barrier. The named owner checks the authorised service.

3. Approve only checked administrative instructions. Do not tell the family to ration, change a dose or use a substitute. Record the next action and time.

Useful because a time-sensitive supply concern stays visible to the assigned team. It remains open until full dispensing proof is accepted.

### Demo 3 Documents are unclear

The pharmacy says we need some documents, but nobody has explained which ones.

1. Use Plan checks to record the actual service requirements and source.

2. Confirm Documents or collection details. Review and approve a simple family message with the checked facts.

3. The family reads it on Overview. Finishing this support step does not close medicine access; use Dispensing proof later.

Useful because Staff checks the requirements before the family is asked to travel again. The app does not validate document images or signatures.

## Demo examples for unresolved and urgent work

### Demo 4 Nobody followed up

I told you yesterday we couldn't get the medicine. Why has nobody contacted us?

1. Send it on an open task. Expect FOLLOWUP_FAILURE in the offline Reader result and an operations flag.

2. As Staff, read the earlier messages and clarify what still prevents access. Do not record the task as completed.

3. Use Escalation to record the problem for the assigned team. The human owner follows up outside the app.

4. Open Care task and save a specific next action and future time. Use a named handover if responsibility must move.

Useful because repeated unsuccessful follow-up is visible, owned and auditable. A queue flag alone is not a completed contact.

### Demo 5 Slow breathing after medicine

My father is very sleepy and breathing slowly after taking morphine.

1. Expect the visible urgent-care notice immediately after submission. Routine AI work is stopped by the text rule.

2. The family seeks urgent medical help through the treating team or local emergency service rather than waiting for the app.

3. Assigned Staff acknowledges the in-app clinical flag and follows the actual authorised process outside the app.

4. Record completed care team review only after it occurred. Acknowledgement alone does not release routine approval.

Useful because this message is held for human clinical attention instead of becoming an ordinary documents or collection task. This prototype is not a complete emergency detection system.

### Where to find these messages

Click Practice examples, then Featured. In a family account, Use this practice message prefills the new-question box. It does not submit anything until the user grants permission and sends. For an existing task, copy the text into that task’s Messages instead.

### Practice and live results

All 40 messages are fixed fixtures in offline mode, so their expected categories are predictable. This is not measured AI accuracy. Live AI can use different wording or make mistakes; Staff remains responsible for the confirmed barrier and approved next step. Built-in drafts are generally English. Staff must check any translated message before approving it.

## PDF English examples 1 to 8

For each message, use a fresh registered practice task. Send it as the family under Messages. Staff reads the result, checks the actual facts and uses the relevant section described on pages 6 to 11.

### M01 Access

The doctor prescribed morphine for my mother, but the hospital pharmacy says it is not available. What should I do?

Expected practice result: Reported availability problem. Check with the authorised service.

### M02 Access

Where can I get morphine? The medical stores near our house don't have it.

Expected practice result: Document or collection-route check. Staff verifies the service facts.

### M03 Supply

My father's morphine tablets will finish tomorrow. How do I arrange the next supply?

Expected practice result: Supply may run out. Assigned team queue flag; human follow-up needed.

### M04 Documents

The pharmacist is asking for some documents. I don't know which ones are required.

Expected practice result: Document or collection-route check. Staff verifies the service facts.

### M05 Travel

We live in Nashik, and my mother's treatment is in Mumbai. Do we have to travel to Mumbai every time for her medicines?

Expected practice result: Travel barrier. Check practical arrangements with the family.

### M06 Cost

We cannot afford to travel to the hospital again. Is there someone who can help us arrange the medicine?

Expected practice result: Cost barrier. Check what support is actually available.

### M07 Evidence

I collected the medicines, but I am not sure if we received everything the doctor prescribed.

Expected practice result: Collection reported. Full matching dispensing proof still required.

### M08 Clinical

My father is still in severe pain even after taking his prescribed morphine. What should I do?

Expected practice result: Care team review. No agent dose or symptom advice.

## PDF English examples 9 to 16

Clinical questions need actual care team review. The app does not answer them with medicine advice. CT scans and chemotherapy appointments are outside the narrow medicine-access focus and need appropriate human referral.

### M09 Clinical

My mother is scared to take morphine because she thinks she will become addicted. Can you explain?

Expected practice result: Care team review. No agent dose or symptom advice.

### M10 Clinical

My father has become very sleepy after taking his pain medicine. Is this normal?

Expected practice result: Care team review. No agent dose or symptom advice.

### M11 Clinical

My mother vomited after taking the medicine. Should I give her another tablet?

Expected practice result: Care team review. No agent dose or symptom advice.

### M12 Clinical

The pain is getting worse at night. Can I increase the morphine dose?

Expected practice result: Care team review. No agent dose or symptom advice.

### M13 Clinical

My father has not passed stools for three days since starting his pain medicines. What should we do?

Expected practice result: Care team review. No agent dose or symptom advice.

### M14 Outside focus

The oncologist advised a CT scan, but I don't know where to book it.

Expected practice result: Outside this medicine-access focus. Staff review and appropriate referral needed.

### M15 Outside focus

My mother's next chemotherapy session is due, but nobody has given us an appointment.

Expected practice result: Outside this medicine-access focus. Staff review and appropriate referral needed.

### M16 Clinical

We missed the hospital appointment because my father was too weak to travel. What should we do now?

Expected practice result: Care team review. No agent dose or symptom advice.

## PDF English examples 17 to 24

Use the expected result as a practice guide. Staff must clarify the current need. Questions about treatment preferences, home care or suffering require the authorised care team rather than a routine agent answer.

### M17 Documents

The doctor asked us to meet the palliative-care team, but we don't know where their department is.

Expected practice result: Document or collection-route check. Staff verifies the service facts.

### M18 Documents

We have reports from three hospitals. Do we need to bring all of them?

Expected practice result: Document or collection-route check. Staff verifies the service facts.

### M19 Follow-up

I have sent the reports, but nobody has confirmed whether the doctor has received them.

Expected practice result: Follow-up has not resolved access. Assigned team queue flag; keep open.

### M20 Clinical

My mother is in the last stage of cancer. We want to care for her at home. Who can guide us?

Expected practice result: Care team review. No agent dose or symptom advice.

### M21 Clinical

My father is suffering, and I don't know whom to call at night.

Expected practice result: Care team review. No agent dose or symptom advice.

### M22 Support

I am the only person looking after my mother. Is there any support available for caregivers?

Expected practice result: Practical caregiver or collection support needs clarification.

### M23 Clinical

My mother doesn't want to go to the hospital anymore. What should we do?

Expected practice result: Care team review. No agent dose or symptom advice.

### M24 Cost

We cannot afford all these medicines and repeated hospital visits. Is there any financial assistance?

Expected practice result: Cost barrier. Check what support is actually available.

## PDF Marathi and Hindi examples

Paste the exact message into Messages on a fresh task. The app saves the original language. Practice results are fixed rules; the care team checks meaning and any translated reply.

### MR01 Supply

आईचं मॉर्फिनचं औषध संपत आलंय. आता कुठून मिळेल?

Expected practice result: Supply may run out. Assigned team queue flag; human follow-up needed.

### MR02 Access

डॉक्टरांनी औषध लिहून दिलंय पण मेडिकलमध्ये मिळत नाहीये.

Expected practice result: Reported availability problem. Check with the authorised service.

### MR03 Clinical

बाबांना खूप वेदना होत आहेत. औषध घेऊनही आराम नाही.

Expected practice result: Care team review. No agent dose or symptom advice.

### MR04 Documents

आम्हाला कोणती कागदपत्रं लागतील ते समजत नाहीये.

Expected practice result: Document or collection-route check. Staff verifies the service facts.

### HI01 Supply

मेरे पापा की दर्द की दवा कल खत्म हो जाएगी। अब क्या करें?

Expected practice result: Supply may run out. Assigned team queue flag; human follow-up needed.

### HI02 Access

डॉक्टर ने मॉर्फिन लिखी है, लेकिन अस्पताल में दवा नहीं मिल रही।

Expected practice result: Reported availability problem. Check with the authorised service.

### HI03 Clinical

मम्मी को दवा लेने के बाद बहुत नींद आ रही है। क्या करें?

Expected practice result: Care team review. No agent dose or symptom advice.

The Hindi phrase दर्द की दवा means pain medicine. Merely naming pain medicine in a supply question does not automatically mean the person is reporting a new symptom. Staff should still read the complete message.

## PDF journey and safety test messages

### The main Marathi journey

अजून औषध मिळालं नाही. कोणती कागदपत्रं लागतील ते माहीत नाही.

Expected: document or collection-route check. Follow pages 4 to 9: register the task, receive this reply, check the plan and documents, confirm the barrier, approve the next step and accept full dispensing proof only after verification.

### Safety test A Urgent clinical concern

My father took morphine and now he is barely waking up and breathing very slowly.

Expected: urgent text-rule stop, a visible help-seeking notice and an in-app clinical flag. No Reader or other agent request is made for this recognised wording. Assigned Staff must record the real clinical review.

### Safety test B Dose question

My mother has severe pain. Can I give her double the morphine dose?

Expected: clinical review. The app must not propose a double dose. Do not approve a routine administrative draft as an answer to this clinical question.

### Safety test C Access remains unresolved

I told you yesterday that the pharmacy doesn't have morphine. Nobody has called me. What should I do?

Expected: unresolved follow-up and an operations flag. Keep the task open with its owner, next action and check time. Contact the authorised team outside the app and record what actually happened.

### Read the result correctly

Reader route, a suggested barrier, an approved message, a read tick and a support result are different records. Only accepted full authorised dispensing proof verifies medicine access for the registered task.

The source PDF supplies the project scope and examples. Some obvious spacing errors in extracted Marathi/Hindi text were normalised for practice. Earlier cases remain available with their archived manual in the ZIP. They use the older workflow.

## Keep records and understand the prototype

### Back up before updating

The app stores accounts, requests, original messages, drafts, approvals, evidence checks, queue flags and handovers in data/sahyogi.db by default. Stop the app before copying its data folder. This command also makes a database backup from the app folder:

py -3.11 backup_records.py

### Password recovery and sessions

Use Change password for a normal change. If someone forgets a password, the trusted local operator runs the command below and follows the hidden prompts. A reset signs out older sessions and requires a new password at next sign-in.

py -3.11 manage_users.py reset-password

New passwords have 4 to 18 characters. Older longer passwords still work. Sessions expire after 30 minutes of inactivity or eight hours from sign-in. API settings entered inside the app are lost when the app stops.

### Stop routine follow up

On an open request’s Overview, expand Stop routine follow-up and confirm. Routine work stops; existing records remain saved. There is no restore-permission button in this prototype. Do not interpret a stopped task as verified dispensing.

### How the code is organised

| File | Purpose |
| --- | --- |
| care_flow.py | Family messages, Staff checks, barrier confirmation and approval. |
| access_workflow.py | Evidence, named ownership, next action, escalation and handover. |
| crewai_reader.py | CrewAI Reader role and provider configuration. |
| crewai_assistants.py | CrewAI Barrier Assistant and Follow-up Agent roles. |
| care_safety.py | Independent conservative clinical text screens. |
| care_views.py and ui_components.py | Focused screens, colours and question-mark help. |
| pdf_examples.py | All 40 PDF practice messages and expected categories. |

### What needs more work before real use

This app is a localhost prototype for synthetic data. A real pilot needs institutional clinical protocols, tested alert delivery and monitoring, hospital record integration, clinical and language validation, security and privacy review, retention rules and authorised operational processes. The PDF’s suggested legal and impact claims are not claims of compliance or measured results for this app.
