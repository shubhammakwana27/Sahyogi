"""Made up practice exercises shared by the app and its manual."""
EXAMPLES = {
    "directions": {"title":"Where to go and what to bring", "message":"Where should we go? Which documents are needed?",
        "meaning":"The caregiver needs the collection location and document list.",
        "steps":["Click Read reply. Expect Documents Route and Awaiting Approval.",
                 "Enter a checked next step, then approve it as coordinator.",
                 "Record checked details, approve the caregiver message, share it manually and record the outcome.",
                 "Access stays Not Confirmed until suitable dispensing proof is accepted."]},
    "travel": {"title":"Help with travel", "message":"We need help with travel.",
        "meaning":"The caregiver has a travel problem that clinical team must check.",
        "steps":["Click Read reply. Expect Travel.","Approve a next step to check available travel support outside the app.",
                 "Keep the responsible person and next follow-up time visible. The app does not book transport."]},
    "availability": {"title":"Reported availability problem", "message":"Medicine is not available.",
        "meaning":"This is a caregiver report. Clinical team must check availability with the authorised service.",
        "steps":["Click Read reply. Expect Availability Reported.","Approve a next step to check the report.",
                 "Do not promise stock. Access remains Not Confirmed."]},
    "collected": {"title":"Caregiver says medicine was collected", "message":"We collected it.",
        "meaning":"A collection claim needs a matching dispensing record.",
        "steps":["Click Read reply. Expect Receipt Reported.","Approve a next step to verify proof. Workflow becomes Waiting Evidence.",
                 "Add a sample record, tick matching and whole task coverage, then accept it as verifier after checking authority.",
                 "Access becomes Confirmed if the full proof is accepted; an open care team review remains open."]},
    "medical": {"title":"A medical question", "message":"The patient has pain. Should we change the dose?",
        "meaning":"The care team must handle the medical question. AI does not answer it.",
        "steps":["Click Read reply. Expect Clinical and Human Review.","Routine coordination pauses.",
                 "For practice only, simulate care team review and record its note and next step. Resolve the review only after it has been reviewed."]},
    "mixed": {"title":"Travel and a medical concern together", "message":"We need help with travel, and the patient has pain.",
        "meaning":"Medical content takes priority even when a practical question is also present.",
        "steps":["Click Read reply. Expect Clinical and Human Review.","The care team reviews the medical concern first.",
                 "After the review is resolved, clinical team can continue the travel follow-up. A handover does not clear a review."]},
    "unclear": {"title":"An unclear reply", "message":"It happened again. Please do something.",
        "meaning":"There is not enough information to choose a reliable next step.",
        "steps":["Click Read reply. Expect Unclear and Human Review. Real model wording may vary.",
                 "Clinical team clarify the meaning outside the app, then record what they learned in the review note.",
                 "Resolve the review after checking. A reader failure also needs review, but is a technical problem."]},
    "partial": {"title":"Only part of the task is covered", "message":"",
        "meaning":"An accepted record can confirm partial access without completing the task.",
        "steps":["Go directly to 2 Add sample proof. Enter a made up source and unique record reference.",
                 "Tick the patient and task match box. Leave whole task coverage unticked.",
                 "Add the record, choose Accept record, confirm source authority, enter a reason and save.",
                 "Access becomes Partial. The remaining work stays open."]},
    "handover": {"title":"Another coordinator takes over", "message":"",
        "meaning":"The current person stays responsible until the named next person accepts.",
        "steps":["Go to 3 Hand over unresolved work. Enter Rahul, a future check time and a reason.",
                 "Propose the handover. Anita remains responsible.","Enter Rahul exactly under Accepting person and click Accept this handover.",
                 "Rahul becomes responsible. Access stays unresolved."]},
    "stop": {"title":"The caregiver asks to stop contact", "message":"Stop messages.",
        "meaning":"Routine follow-up stops when contact permission is withdrawn.",
        "steps":["Click Read reply. The exact stop phrase is handled by an app rule without calling AI.",
                 "Workflow becomes Stopped. The case and history remain saved.",
                 "There is no restore-permission button in this demo. Use another sample case for further practice."]},
}


def next_step(case):
    """Return one clear clinical team action without changing a case or calling a model."""
    from caregiver_contact import current_update
    if not case["consent"]:
        return "Contact is stopped", "Keep the saved history. Routine contact is blocked because permission was withdrawn.", "history"
    if case["review_required"]:
        return "Care team review is needed", "Read the original messages. Record the care team's review and next step before routine coordination continues.", "care-review"
    if case["access"] == "CONFIRMED":
        return "Access is confirmed", "Accepted proof covers this task. You can read the history or download the case record.", "history"
    if case["handover_to"]:
        return "Accept the named handover", "The current owner stays responsible until the named next person accepts.", "handover"
    if case["workflow"] == "WAITING_REPLY":
        return "Read a caregiver reply", "Enter the caregiver's message and click Read reply. The reader suggests its meaning for clinical team.", "read-reply"
    if case["workflow"] == "AWAITING_APPROVAL":
        return "Approve the next practical step", "Below the reader's result, enter a checked next step and click As coordinator, approve next step.", "read-reply"
    if case["workflow"] == "WAITING_EVIDENCE" or any(e["status"] == "PENDING" for e in case["evidence"]):
        return "Check the dispensing proof", "A collection claim is not proof. Add or verify the matching authorised dispensing record.", "proof"
    details, update, contacts = current_update(case)
    if not details:
        return "Record the checked collection details", "Check the location and documents with the authorised service, then save the facts and who checked them.", "caregiver-update"
    if not update:
        return "Review the caregiver message", "Check the draft against the verified facts, then approve it for manual sharing.", "caregiver-update"
    if any(c["outcome"] == "INFORMED" for c in contacts):
        return "Follow up for dispensing proof", "Clinical team recorded that the caregiver was informed. Access still needs accepted dispensing proof.", "proof"
    if contacts:
        return "Follow up on caregiver contact", "Check whether the caregiver received the details. Record a call or acknowledgement when it happens.", "caregiver-update"
    return "Contact the caregiver and record the outcome", "Copy the approved message for your agreed contact channel, or explain it by phone. Then record what happened.", "caregiver-update"
