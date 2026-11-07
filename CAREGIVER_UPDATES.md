Earlier-case guide: the forms below remain under Earlier cases. For the new patient-first palliative request flow, use PALLIATIVE_GUIDE.md. New requests publish follow-up messages only after assigned Staff approval.

Account update: sign in as the case coordinator for these forms. Assigned patients and caregivers can now read the approved message in their portal and mark it as read. External contact recording remains manual. See LOGIN_GUIDE.md.

# Record checked details and inform the caregiver

SAHYOGI now separates planning a check, recording checked facts, approving a
message and recording what happened during contact. The one CrewAI reader
continues to read replies. These new steps use staff decisions and normal app
rules; the reader cannot send a message or confirm receipt.

## Update without losing saved cases

1. Stop the app with Ctrl+C.
2. Make a backup copy of data/sahyogi.db while the app is stopped.
3. Copy the updated project files into your existing sahyogi_starter folder.
   Keep data/sahyogi.db and .venv. This download contains no database.
4. Start the app using your existing provider settings. For example:

```powershell
$env:SAHYOGI_READER = "crewai"
$env:SAHYOGI_PROVIDER = "sarvam"
$env:SARVAM_API_KEY = "YOUR_SARVAM_API_KEY"
$env:SARVAM_MODEL = "sarvam-105b"
.\.venv\Scripts\python.exe app.py
```

The app automatically creates three additional tables when it opens the
existing database. It does not delete or rewrite existing cases, replies,
proof, action history or owners. No extra package is required for this feature.

## Try one complete example

Use made up details. This local learning app uses authenticated account roles; hospital proof checks remain practice records.

### 1 Approve the next step

Create a fresh sample case with a unique plan reference, Anita as responsible
person, a follow up time, approved plan confirmation and contact permission.
Enter this caregiver reply and click Read reply:

> Where should we go? Which documents are needed?

Under its routine suggestion, enter a next step and click As coordinator,
approve next step. The case should show Coordinator Checking. If Human Review
is open, staff must review the original message and record the appropriate
review first. An old failed API call can also leave a review open.

### 2 Find the new section

On the case page, look below Care team review for:

**Check details and inform caregiver**

The same progress is also shown near the top as Caregiver update. If the form
cannot be used, the section explains the reason. An open review, pending
handover, withdrawn permission or already confirmed access blocks new routine
actions. Before staff approve a next step, the section asks for that approval.

### 3 Record the details staff checked

In A Record checked details, fill in these sample values:

| Field | Sample value |
|---|---|
| Verified collection location | Demo Hospital collection counter 2 |
| Verified documents to bring | Demo approved prescription and sample case reference |
| Authorised service or source checked | Demo pharmacy coordinator |
| Staff member who checked | Anita |
| When details were checked in India time | The time the sample check occurred |
| Caregiver message language | English, Marathi or Hindi |

Tick I checked these details with the authorised service, then click Save
checked details. In actual work, staff must really check the details before
recording them. The sample list above is not a real hospital document list.

The new progress should say Details checked and message needs approval.
The main workflow stays Coordinator Checking and access stays Not Confirmed.

The draft uses the location, documents and source exactly as staff entered
them. The selected language changes the template labels; it does not translate
the entered facts. Enter those facts in language the caregiver understands.

### 4 Review and approve the message

Under B Review and approve the caregiver message, read the draft. An English
draft based on the sample above reads:

> We checked the medicine collection details with Demo pharmacy coordinator.
> Where to go: Demo Hospital collection counter 2
> Documents to bring: Demo approved prescription and sample case reference

Check that the source, location, documents and language are correct. Enter the
approving staff member's name, tick the review confirmation and click Approve
caregiver message. Approval saves the exact text. It does not send anything.

Progress should say Message approved and contact not yet recorded.

### 5 Contact the caregiver outside the app

Select the text under Approved message for manual sharing and copy it with
Ctrl+C. Staff can paste it into their agreed WhatsApp or SMS conversation, or
explain the approved facts on a phone call or in person.

This app has no messaging service connection. It does not send messages, read
WhatsApp delivery ticks, place calls or verify that someone received a message.
Real automatic sending requires a separate service integration and account.
Do not record the caregiver as informed until there is a staff-observed basis.

### 6 Record the actual outcome

Under C Record what happened when staff contacted the caregiver, choose the
method used and the outcome. Enter the contacting staff member, the time in
India time, and a short note. Confirm the contact route was agreed.

| Outcome | What it means |
|---|---|
| Could not reach caregiver | A contact attempt did not reach them |
| Message sent but not yet acknowledged | Staff sent WhatsApp or SMS outside the app and have no acknowledgement yet |
| Spoke to caregiver or received acknowledgement | Staff spoke to them or have their acknowledgement |

For the last outcome, also tick I spoke with the caregiver or received their
acknowledgement. For this sample exercise, you can simulate a phone call and
record: Sample call completed. Caregiver acknowledged the location and documents.
Click Save caregiver contact outcome.

The progress now says Caregiver informed according to staff record. This is a
staff record, not a delivery receipt from an external service. A sent message
without acknowledgement stays visibly unconfirmed. Future times and contact
times before message approval are not accepted. Time inputs have minute
precision, so contact can be recorded within the approval minute.

If the caregiver raises a medical or unclear issue, enter the original reply
under Read a caregiver reply so the existing care team review process applies.

### 7 Check history and continue the access task

The new section lists contact outcomes with staff names, times, notes and the
approved message for each contact. Action history records checking, approval
and contact. Closing and reopening the app keeps these records.

Access stays Not Confirmed, or Partial if partial proof was already accepted.
Only the existing dispensing proof verification process can confirm the whole
access task. Checking directions and informing the caregiver do not prove
that medicine was collected.

## If the details change

Expand Revise checked details and save a new checked record. Review and approve
the new draft. Previous messages and contact records stay available, but the
old approval cannot be used for the revised details. The latest progress
returns to needing approval and then to needing contact for that version.

An open care team review or withdrawal of contact permission always takes
priority over this routine process. A pending handover must be accepted first.
The latest contact progress describes staff records; read it together with the
main workflow and any review warning.

## What has been tested

Validation includes the complete HTTP form flow, old database upgrade, restart,
language templates, HTML escaping, duplicate submissions, required approvals,
contact acknowledgement, revised details and existing review and proof rules.
The project has 79 passing tests with simulated AI responses. No live message,
phone call or paid AI request was made during this validation.
