"""One bounded reader. It suggests labels; it cannot act on cases."""
from dataclasses import asdict, dataclass
import os
import re
from reader_errors import safe_error_summary
from runtime_settings import current_settings,PROVIDER_NAMES
from care_safety import clinical_screen,norm

CATEGORIES = ["DOCUMENTS_ROUTE", "TRAVEL", "AVAILABILITY_REPORTED",
              "RECEIPT_REPORTED", "CLINICAL", "UNCLEAR", "MEDICINE_APPROVAL", "COST", "CARE_SUPPORT",
              "SUPPLY_CONTINUITY","FOLLOWUP_FAILURE","OUT_OF_SCOPE"]
PROMPT_VERSION = "palliative-access-reader-v6"


@dataclass
class Reading:
    category: str
    summary: str
    clinical_concern: bool = False
    uncertain: bool = False
    engine: str = "demo"

    def data(self):
        return asdict(self)


def normalise(text):
    return re.sub(r"\s+", " ", text.casefold()).strip(" .!?।\n")


def clinical_hint(text):
    # Extra stop screen only. This is NOT a medical assessment or complete detector.
    return clinical_screen(text)


def opted_out(text):
    return normalise(text) in {"stop", "stop messages", "stop messaging me",
                              "संदेश बंद करा", "मेसेज बंद करा", "संदेश बंद करें"}


def needs_review(reason="Meaning is unclear. A person must review the original reply.",
                 engine="demo"):
    return Reading("UNCLEAR", reason, uncertain=True, engine=engine)


def demo_read(text):
    """Small fixture reader, NOT an AI model. Unknown sentences go to a person."""
    from pdf_examples import EXAMPLES
    sample=next((x for x in EXAMPLES.values() if norm(x['message'])==norm(text)),None)
    if sample:
        category=sample['category']
        return Reading(category,'Practice classification from the supplied PDF. Human review and evidence checks still apply.',
                       clinical_concern=category=='CLINICAL',uncertain=category=='OUT_OF_SCOPE')
    if clinical_hint(text):
        return Reading("CLINICAL", "Possible medical question. Send to the care team.", True)
    fixtures = {
        "where should we go? which documents are needed":
            ("DOCUMENTS_ROUTE", "Caregiver asks about the route and documents."),
        "आम्ही कुठे जायचे? कोणती कागदपत्रे लागतील":
            ("DOCUMENTS_ROUTE", "Caregiver asks about the route and documents."),
        "amhi kuthe jayache? konti kagadpatre lagtil":
            ("DOCUMENTS_ROUTE", "Caregiver asks about the route and documents."),
        "हमें कहाँ जाना है? कौन से दस्तावेज़ चाहिए":
            ("DOCUMENTS_ROUTE", "Caregiver asks about the route and documents."),
        "we need help with travel": ("TRAVEL", "Caregiver reports a travel problem."),
        "medicine is not available":
            ("AVAILABILITY_REPORTED", "Caregiver reports an availability problem; clinical team must check."),
        "we collected it":
            ("RECEIPT_REPORTED", "Caregiver reports collection. Authorised proof is still required."),
    }
    fixtures.update({
        "we need approval for the medicine prescribed in our palliative care plan":
            ("MEDICINE_APPROVAL", "Family asks clinical team to check an existing clinician-approved medicine plan."),
        "which documents do we need for palliative care":
            ("DOCUMENTS_ROUTE", "Family needs the document requirements checked."),
        "we cannot afford the travel cost": ("COST", "Family reports a cost barrier."),
        "there is nobody to collect the medicine": ("CARE_SUPPORT", "Family needs practical collection support."),
    })
    entry = fixtures.get(normalise(text))
    return Reading(*entry) if entry else needs_review()


def validate_reading(data, text, engine):
    required = {"category", "summary", "clinical_concern", "uncertain"}
    if not isinstance(data, dict) or set(data) != required:
        return needs_review("AI returned an invalid answer. Clinical team review is required.", engine)
    if (data["category"] not in CATEGORIES
            or not isinstance(data["summary"], str)
            or not 1 <= len(data["summary"]) <= 600
            or type(data["clinical_concern"]) is not bool
            or type(data["uncertain"]) is not bool):
        return needs_review("AI returned an invalid answer. Clinical team review is required.", engine)
    result = Reading(**data, engine=engine)
    if clinical_hint(text) or result.clinical_concern or result.category == "CLINICAL":
        return Reading("CLINICAL", "Possible medical content. Care team review is required.",
                       True, engine=engine)
    if result.category=='OUT_OF_SCOPE':
        return Reading('OUT_OF_SCOPE','Outside the medication-access focus. Assigned clinical team must route this request.',uncertain=True,engine=engine)
    if result.uncertain or result.category == "UNCLEAR":
        return needs_review(engine=engine)
    return result


def provider_settings():
    """Select explicitly; never switch provider because one fails or lacks credits."""
    provider = current_settings().provider
    names = PROVIDER_NAMES
    if provider not in names:
        return provider, ()
    return provider, names[provider]


def read_reply(text):
    """One CrewAI reader proposes an answer; existing backend rules decide actions."""
    config=current_settings();mode=config.mode
    if mode == "demo":
        return demo_read(text)
    # Keep old launch commands working, but route them through CrewAI too.
    if mode not in {"crewai", "openai"}:
        return needs_review("Reader configuration is invalid. Clinical team review is required.", "unavailable")
    provider, names = provider_settings()
    if not names:
        return needs_review("[CONFIG] Set SAHYOGI_PROVIDER to openai, gemini or sarvam, then restart. Clinical team review is required.", "unavailable")
    key,model=config.api_key,config.model
    if not key or not model:
        return needs_review(f"CrewAI needs {names[0]} and {names[1]}. Clinical team review is required.", "unavailable")
    if key in {"YOUR_API_KEY", "YOUR_OPENAI_API_KEY", "YOUR_GEMINI_API_KEY", "YOUR_SARVAM_API_KEY"} or model in {"YOUR_SUPPORTED_MODEL_ID", "YOUR_MODEL_ID", "YOUR_GEMINI_MODEL_ID", "YOUR_SARVAM_MODEL_ID"}:
        return needs_review("[CONFIG] Replace the API key and model placeholders in PowerShell, then restart the app. Clinical team review is required.", "unavailable")
    try:
        from crewai_reader import run_reader
        # Preserve the existing OpenAI adapter call for compatibility.
        kwargs = {"provider": provider} if provider != "openai" else {}
        data = run_reader(text, model=model, api_key=key, **kwargs)
        return validate_reading(data, text, "crewai")
    except Exception as error:
        # Fail closed. Never expose provider responses, secrets or raw tracebacks.
        return needs_review(safe_error_summary(error), "unavailable")
