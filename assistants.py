"""Two advisory roles. No database writes, action tools or outgoing messages.

The model receives a small app-built snapshot of categories, counts and flags.
Patient references, names, raw messages, credentials and checked free text are
not included. Offline mode remains dependency free and is labelled as rules.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os

from agent import provider_settings
from caregiver_contact import current_update
from reader_errors import ReaderOutputError, safe_error_summary
from runtime_settings import current_settings

ASSISTANT_VERSION = "three-agents-v1"
ASSISTANTS = {"barrier": "Barrier Assistant", "followup": "Follow-up Assistant"}
PRACTICAL = {"DOCUMENTS_ROUTE", "TRAVEL", "AVAILABILITY_REPORTED", "RECEIPT_REPORTED"}


def latest_category(case):
    if not case["messages"]:
        return "NONE"
    reading = case["messages"][-1].get("reading") or {}
    category = reading.get("category")
    return category if category in PRACTICAL | {"CLINICAL", "UNCLEAR"} else "NONE"


def assistant_blocker(case, kind):
    if kind not in ASSISTANTS:
        return "Choose a listed assistant."
    if not case["consent"]:
        return "Contact permission was withdrawn. Routine assistance is stopped."
    if case["review_required"]:
        return "The care team must resolve the open review before routine assistance."
    if case["handover_to"]:
        return "The named next person must accept the handover before routine assistance."
    if case["access"] == "CONFIRMED":
        return "Access is already confirmed. Earlier suggestions remain in history."
    if kind == "barrier" and latest_category(case) not in PRACTICAL:
        return "Read a practical caregiver reply first. Medical or unclear replies need clinical team review."
    return ""


def case_snapshot(case):
    """Only app-owned status codes and simple facts go to the new agents."""
    details, update, contacts = current_update(case)
    return {
        "latest_category": latest_category(case),
        "workflow": case["workflow"], "access": case["access"],
        "owner_recorded": bool(case["owner"]),
        "followup_due": datetime.fromisoformat(case["due_at"]) < datetime.now(timezone.utc),
        "reply_count": len(case["messages"]),
        "checked_details_recorded": bool(details),
        "current_message_approved": bool(update),
        "contact_attempt_recorded": bool(contacts),
        "caregiver_informed_recorded": any(c["outcome"] == "INFORMED" for c in contacts) or any(update and a["update_id"] == update["id"] for a in case.get("patient_acknowledgements", [])),
        "latest_contact_outcome": contacts[-1]["outcome"] if contacts else "NONE",
        "pending_proof_count": sum(e["status"] == "PENDING" for e in case["evidence"]),
        "accepted_partial_proof_count": sum(e["status"] == "ACCEPTED" and not e["full_supply"] for e in case["evidence"]),
    }


def validate_output(data):
    if not isinstance(data, dict) or set(data) != {"summary", "checks", "missing_items"}:
        raise ReaderOutputError("Invalid assistant output")
    def short(value, maximum):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum
    if not short(data["summary"], 600):
        raise ReaderOutputError("Invalid assistant summary")
    for key, minimum, maximum in [("checks", 1, 5), ("missing_items", 0, 5)]:
        values = data[key]
        if not isinstance(values, list) or not minimum <= len(values) <= maximum or not all(short(v, 240) for v in values):
            raise ReaderOutputError("Invalid assistant checklist")
    return data


def demo_assistance(kind, snapshot):
    """Fixed practice checklists. This is not CrewAI or a language model."""
    if kind == "barrier":
        category = snapshot["latest_category"]
        checks = {
            "DOCUMENTS_ROUTE": ["Check the collection location with the authorised service.",
                                "Check which documents this case requires. Do not assume the list.",
                                "Save checked details, approve the caregiver message, then share it outside the app."],
            "TRAVEL": ["Ask clinical team to check what travel support is actually available.",
                       "Check the caregiver's practical travel arrangements outside the app.",
                       "Record the checked next step and next follow-up time."],
            "AVAILABILITY_REPORTED": ["Check the caregiver's availability report with the authorised service.",
                                      "Record the service's actual response. Do not promise stock.",
                                      "Record a checked next step and follow-up time."],
            "RECEIPT_REPORTED": ["Request the matching authorised dispensing record through the agreed route.",
                                 "Have the verifier check the source, patient/task match and full coverage.",
                                 "Keep access unconfirmed until suitable proof is accepted."],
        }[category]
        return {"summary": "Practice checklist for the reported practical barrier. Clinical team must check it.",
                "checks": checks, "missing_items": ["Actual service checks and clinical team decisions must be recorded separately."]}
    missing, checks = [], []
    if not snapshot["reply_count"]:
        missing.append("No caregiver reply is recorded.")
        checks.append("Read a caregiver reply when clinical team have one.")
    elif snapshot["workflow"] == "AWAITING_APPROVAL":
        missing.append("The practical next step still needs coordinator approval.")
        checks.append("Review the reply and enter a checked next step in the existing approval form.")
    if snapshot["latest_category"] == "DOCUMENTS_ROUTE":
        if not snapshot["checked_details_recorded"]:
            missing.append("Checked collection details are not recorded.")
            checks.append("Check the location and documents with the authorised service.")
        elif not snapshot["current_message_approved"]:
            missing.append("The current caregiver message is not approved.")
            checks.append("Review the draft against the checked details before approving it.")
        elif not snapshot["caregiver_informed_recorded"]:
            missing.append("No caregiver acknowledgement is recorded for the current approved message.")
            checks.append("Follow up through the agreed route and record what actually happened.")
    if snapshot["pending_proof_count"]:
        missing.append("A dispensing record is waiting for verifier review.")
        checks.append("Have the verifier review the pending record; a pending record is not accepted proof.")
    elif snapshot["access"] != "CONFIRMED":
        missing.append("Accepted proof of the whole task is still missing.")
        checks.append("Follow up for authorised dispensing proof. Partial proof does not complete the task.")
    if snapshot["followup_due"]:
        missing.append("The saved follow-up time is due.")
        checks.append("The responsible person should check progress and record the next follow-up time.")
    return {"summary": "Practice review of the saved case. Missing records do not prove that an action never happened.",
            "checks": checks[:5] or ["Review progress and keep a named owner and next follow-up time."],
            "missing_items": missing[:5]}


@dataclass
class AssistanceResult:
    engine: str
    output: dict | None = None
    error: str = ""


def run_assistant(kind, snapshot):
    if kind not in ASSISTANTS:
        raise ValueError("Unknown assistant")
    config=current_settings();mode=config.mode
    if mode == "demo":
        return AssistanceResult("demo", validate_output(demo_assistance(kind, snapshot)))
    provider, names = provider_settings()
    if mode not in {"crewai", "openai"} or not names:
        return AssistanceResult("unavailable", error="[CONFIG] Choose a supported provider and restart the app.")
    key, model = config.api_key,config.model
    if not key or not model or key.startswith("YOUR_") or model.startswith("YOUR_"):
        return AssistanceResult("unavailable", error=f"[CONFIG] Set a real {names[0]} and {names[1]}, then restart.")
    try:
        from crewai_assistants import run_crew_assistant
        output = run_crew_assistant(kind, snapshot, model=model, api_key=key, provider=provider)
        return AssistanceResult("crewai", validate_output(output))
    except Exception as error:
        return AssistanceResult("unavailable", error=safe_error_summary(error,component=kind))
