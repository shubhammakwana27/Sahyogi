"""Deterministic caregiver updates from clinical team-checked facts. No network or AI calls."""

LANGUAGES = {"en": "English", "mr": "Marathi", "hi": "Hindi"}
CHANNELS = {"PHONE": "Phone call", "WHATSAPP": "WhatsApp", "SMS": "SMS", "IN_PERSON": "In person"}
OUTCOMES = {"INFORMED": "Spoke to caregiver or received acknowledgement",
            "SENT": "Message sent but not yet acknowledged",
            "NOT_REACHED": "Could not reach caregiver"}


def draft_message(details):
    source, location, documents = details["source"], details["location"], details["documents"]
    if details["language"] == "mr":
        return (f"आम्ही {source} यांच्याकडून औषध घेण्याची माहिती तपासली आहे.\n"
                f"कुठे जायचे: {location}\nसोबत आणायची कागदपत्रे: {documents}")
    if details["language"] == "hi":
        return (f"हमने {source} से दवा लेने की जानकारी की पुष्टि की है।\n"
                f"कहाँ जाना है: {location}\nसाथ लाने वाले दस्तावेज़: {documents}")
    return (f"We checked the medicine collection details with {source}.\n"
            f"Where to go: {location}\nDocuments to bring: {documents}")


def contact_blocker(case):
    if not case["consent"]:
        return "Contact permission was withdrawn. Routine contact is stopped."
    if case["review_required"]:
        return "Resolve the open care team review before checking details or recording routine contact."
    if case["handover_to"]:
        return "The named handover must be accepted before routine coordination continues."
    if case["access"] == "CONFIRMED":
        return "Access is already confirmed for this task. The saved contact history remains available."
    if case["workflow"] not in {"COORDINATOR_CHECKING", "HANDOVER_ACTIVE", "WAITING_EVIDENCE"}:
        return "First approve the next step under the caregiver reply, or resolve its care team review."
    return ""


def current_update(case):
    checks = case["collection_checks"]
    if not checks:
        return None, None, []
    latest = checks[-1]
    updates = [u for u in case["caregiver_updates"] if u["check_id"] == latest["id"]]
    update = updates[-1] if updates else None
    contacts = [c for c in case["caregiver_contacts"] if update and c["update_id"] == update["id"]]
    return latest, update, contacts


def contact_progress(case):
    latest, update, contacts = current_update(case)
    if not latest:
        return "Collection details not recorded"
    if not update:
        return "Details checked and message needs approval"
    if any(update and a["update_id"] == update["id"] for a in case.get("patient_acknowledgements", [])):
        return "Patient or caregiver marked the current approved instructions as read"
    if any(c["outcome"] == "INFORMED" for c in contacts):
        return "Caregiver informed according to clinical team record"
    if contacts:
        return "Message sent and awaiting acknowledgement" if contacts[-1]["outcome"] == "SENT" else "Caregiver not reached"
    return "Message approved and contact not yet recorded"
