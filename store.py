"""Saved cases and backend rules. All changes and history commit together."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from agent import PROMPT_VERSION, needs_review, opted_out, read_reply
from caregiver_contact import CHANNELS, LANGUAGES, OUTCOMES, contact_blocker, draft_message
from examples import EXAMPLES
from assistants import ASSISTANTS, ASSISTANT_VERSION, assistant_blocker, case_snapshot, run_assistant, validate_output
from reader_errors import safe_error_summary
from access_control import account, authorize, person_label, prepare_action, finish_action, AccessDenied


class RuleError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean(value, label, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise RuleError(f"Enter {label} using 1 to {maximum} characters.")
    return value.strip()


def due_time(value):
    try:
        value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            raise ValueError
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, TypeError):
        raise RuleError("Use a follow up time with a timezone.") from None


def occurred_time(value):
    result = due_time(value)
    if datetime.fromisoformat(result) > datetime.now(timezone.utc):
        raise RuleError("Choose a time that has already occurred.")
    return result


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY, patient_ref TEXT NOT NULL,
                    plan_ref TEXT NOT NULL UNIQUE, target TEXT NOT NULL,
                    owner TEXT NOT NULL, due_at TEXT NOT NULL,
                    consent INTEGER NOT NULL, review_required INTEGER NOT NULL DEFAULT 0,
                    access TEXT NOT NULL DEFAULT 'NOT_CONFIRMED',
                    workflow TEXT NOT NULL DEFAULT 'WAITING_REPLY',
                    handover_to TEXT, version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    body TEXT NOT NULL, status TEXT NOT NULL, reading TEXT,
                    original_review INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    source TEXT NOT NULL, reference TEXT NOT NULL,
                    target_match INTEGER NOT NULL, full_supply INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING', verifier TEXT,
                    reason TEXT, created_at TEXT NOT NULL,
                    UNIQUE(source, reference)
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL REFERENCES cases(id), actor TEXT NOT NULL,
                    kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, case_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS case_due ON cases(due_at);
                CREATE INDEX IF NOT EXISTS message_case ON messages(case_id);
                CREATE TABLE IF NOT EXISTS collection_checks (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    location TEXT NOT NULL, documents TEXT NOT NULL, source TEXT NOT NULL,
                    checked_by TEXT NOT NULL, checked_at TEXT NOT NULL,
                    language TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS caregiver_updates (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    check_id TEXT NOT NULL REFERENCES collection_checks(id),
                    body TEXT NOT NULL, approved_by TEXT NOT NULL, approved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS caregiver_contacts (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    update_id TEXT NOT NULL REFERENCES caregiver_updates(id),
                    channel TEXT NOT NULL, outcome TEXT NOT NULL, contacted_by TEXT NOT NULL,
                    contacted_at TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS collection_check_case ON collection_checks(case_id);
                CREATE INDEX IF NOT EXISTS caregiver_update_case ON caregiver_updates(case_id);
                CREATE INDEX IF NOT EXISTS caregiver_contact_case ON caregiver_contacts(case_id);
                CREATE TABLE IF NOT EXISTS practice_cases (
                    case_id TEXT PRIMARY KEY REFERENCES cases(id), example_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assistance_runs (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    kind TEXT NOT NULL, source_version INTEGER NOT NULL,
                    snapshot TEXT NOT NULL, status TEXT NOT NULL,
                    engine TEXT NOT NULL, output TEXT, error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, finished_at TEXT,
                    review_decision TEXT, reviewed_by TEXT, review_note TEXT, reviewed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS assistance_case ON assistance_runs(case_id);
            ''')

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except Exception:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def _case(self, db, case_id):
        row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            raise RuleError("Case not found.")
        return dict(row)

    def _event(self, db, case_id, actor, kind, detail):
        db.execute("INSERT INTO events(case_id,actor,kind,detail,created_at) VALUES(?,?,?,?,?)",
                   (case_id, actor, kind, detail, now()))

    def _check(self, case, version):
        if case["version"] != int(version):
            raise RuleError("This case changed. Reload the page before trying again.")

    def _change(self, db, case_id, **fields):
        # Column names below are supplied only by this module, never by the user.
        assignments = ", ".join(f"{key}=?" for key in fields)
        prefix = assignments + ", " if assignments else ""
        db.execute(f"UPDATE cases SET {prefix}version=version+1 WHERE id=?",
                   (*fields.values(), case_id))

    def _once(self, db, token, payload, case_id):
        token = clean(token, "the action identifier", 80)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        old = db.execute("SELECT * FROM operations WHERE id=?", (token,)).fetchone()
        if old:
            if old["fingerprint"] != digest:
                raise RuleError("This action identifier was already used for another request.")
            return old["case_id"]
        db.execute("INSERT INTO operations VALUES(?,?,?)", (token, digest, case_id))
        return None

    def list_cases(self):
        with self.connection() as db:
            return [dict(x) for x in db.execute("SELECT * FROM cases ORDER BY due_at,created_at")]

    def detail(self, case_id):
        with self.connection() as db:
            return self._detail(db, case_id)

    def _detail(self, db, case_id):
        case = self._case(db, case_id)
        for key, query in {
            "messages": "SELECT * FROM messages WHERE case_id=? ORDER BY rowid",
            "evidence": "SELECT * FROM evidence WHERE case_id=? ORDER BY created_at,id",
            "events": "SELECT * FROM events WHERE case_id=? ORDER BY seq",
            "collection_checks": "SELECT * FROM collection_checks WHERE case_id=? ORDER BY rowid",
            "caregiver_updates": "SELECT * FROM caregiver_updates WHERE case_id=? ORDER BY rowid",
            "caregiver_contacts": "SELECT * FROM caregiver_contacts WHERE case_id=? ORDER BY rowid",
            "assistance_runs": "SELECT * FROM assistance_runs WHERE case_id=? ORDER BY rowid",
        }.items():
            case[key] = [dict(x) for x in db.execute(query, (case_id,))]
        for message in case["messages"]:
            if message["reading"]:
                message["reading"] = json.loads(message["reading"])
        for run in case["assistance_runs"]:
            run["snapshot"] = json.loads(run["snapshot"])
            if run["output"]:
                run["output"] = json.loads(run["output"])
        case["patient_acknowledgements"] = []
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='patient_acknowledgements'").fetchone():
            case["patient_acknowledgements"] = [dict(r) for r in db.execute("SELECT * FROM patient_acknowledgements WHERE case_id=? ORDER BY rowid", (case_id,))]
        practice = db.execute("SELECT example_id FROM practice_cases WHERE case_id=?", (case_id,)).fetchone()
        case["practice_example"] = practice["example_id"] if practice else None
        return case

    def request_assistance(self, case_id, kind, version, token, role, runner=run_assistant, *, principal=None):
        """Save a request first; never hold a SQLite write lock during AI calls."""
        if role != "Coordinator" or kind not in ASSISTANTS:
            raise RuleError("Choose a listed assistant as coordinator.")
        run_id = uuid4().hex
        with self.connection(write=True) as db:
            if principal:
                authorize(db, case_id, principal, "assistance")
            if self._once(db, token, ["assistance", case_id, kind, version, role], case_id):
                return case_id
            case = self._detail(db, case_id)
            self._check(case, version)
            blocker = assistant_blocker(case, kind)
            if blocker:
                raise RuleError(blocker)
            snapshot = case_snapshot(case)
            db.execute('''INSERT INTO assistance_runs
                (id,case_id,kind,source_version,snapshot,status,engine,created_at)
                VALUES(?,?,?,?,?,'RUNNING','pending',?)''',
                (run_id, case_id, kind, case["version"], json.dumps(snapshot), now()))
            self._event(db, case_id, "Coordinator", "ASSISTANCE_REQUESTED",
                        f"Requested {ASSISTANTS[kind]}; {ASSISTANT_VERSION}. Suggestions only; no clinical team decision or access change.")
        try:
            result = runner(kind, snapshot)
            if result.engine not in {"demo", "crewai", "unavailable"}:
                raise ValueError("Invalid assistant engine")
            engine = result.engine
            if engine == "unavailable":
                # Public runner supplies an already sanitised fixed diagnostic.
                error = result.error
                output = None
            else:
                output = validate_output(result.output)
                error = ""
        except Exception as exc:
            output, engine, error = None, "unavailable", safe_error_summary(exc)
        with self.connection(write=True) as db:
            current = self._detail(db, case_id)
            stale = current["version"] != int(version) or bool(assistant_blocker(current, kind))
            status = "STALE" if stale else "FAILED" if output is None else "DRAFT"
            db.execute("UPDATE assistance_runs SET status=?,engine=?,output=?,error=?,finished_at=? WHERE id=?",
                       (status, engine, json.dumps(output, ensure_ascii=False) if output else None, error, now(), run_id))
            self._event(db, case_id, ASSISTANTS[kind], "ASSISTANCE_FINISHED",
                        f"{status}; engine={engine}; {ASSISTANT_VERSION}. No message sent, no action approved and no access change.")
        return case_id

    def create_practice(self, example_id, token, *, principal=None):
        if example_id not in EXAMPLES:
            raise RuleError("Choose a practice example from Help and examples.")
        case_id = uuid4().hex
        with self.connection(write=True) as db:
            user = account(db, principal) if principal else None
            if user and (user["role"] != "coordinator" or user["must_change"]):
                raise AccessDenied("A coordinator must create practice cases.")
            old = self._once(db, token, ["practice", example_id, principal], case_id)
            if old:
                return old
            due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(timespec="seconds")
            db.execute('''INSERT INTO cases(id,patient_ref,plan_ref,target,owner,due_at,consent,created_at)
                          VALUES(?,?,?,?,?,?,1,?)''',
                       (case_id, "PRACTICE-" + example_id.upper(), "PRACTICE-" + uuid4().hex[:12].upper(),
                        "Confirm collection for the sample approved plan", "Anita", due, now()))
            db.execute("INSERT INTO practice_cases VALUES(?,?)", (case_id, example_id))
            if user:
                db.execute("INSERT INTO case_members VALUES(?,?,'owner')", (case_id, principal))
                db.execute("UPDATE cases SET owner=? WHERE id=?", (person_label(user), case_id))
            self._event(db, case_id, "Practice setup", "PRACTICE_CASE_CREATED",
                        "Made up case only. Approved plan and contact permission are simulated for this exercise. No AI call or outgoing message.")
        return case_id

    def create(self, data, token, *, principal=None):
        if data.get("plan_approved") != "yes" or data.get("consent") != "yes":
            raise RuleError("An approved plan and contact permission are required.")
        fields = [clean(data.get(k), label) for k, label in [
            ("patient_ref", "a sample patient reference"), ("plan_ref", "a unique plan task reference"),
            ("target", "the access task"), ("owner", "the responsible person")]]
        due = due_time(data.get("due_at"))
        case_id = uuid4().hex
        try:
            with self.connection(write=True) as db:
                user = account(db, principal) if principal else None
                if user and (user["role"] != "coordinator" or user["must_change"]):
                    raise AccessDenied("A coordinator must create cases.")
                if user:
                    fields[-1] = person_label(user)
                old = self._once(db, token, ["create", data, principal], case_id)
                if old:
                    return old
                db.execute('''INSERT INTO cases(id,patient_ref,plan_ref,target,owner,due_at,
                           consent,created_at) VALUES(?,?,?,?,?,?,1,?)''',
                           (case_id, *fields, due, now()))
                if user:
                    db.execute("INSERT INTO case_members VALUES(?,?,'owner')", (case_id, principal))
                self._event(db, case_id, person_label(user) if user else "Intake demo", "CASE_CREATED",
                            "Clinical team recorded an approved plan and contact permission.")
        except sqlite3.IntegrityError:
            raise RuleError("This plan task reference is already in use. Open the existing case.") from None
        return case_id

    def add_reply(self, case_id, text, version, token, reader=read_reply, *, principal=None):
        text = clean(text, "a sample caregiver reply", 2000)
        message_id = uuid4().hex
        # Save first, before an external model call. A crash leaves a visible human review.
        with self.connection(write=True) as db:
            user = authorize(db, case_id, principal, "reply") if principal else None
            if self._once(db, token, ["reply", case_id, text, version], case_id):
                return case_id
            case = self._case(db, case_id)
            self._check(case, version)
            if not case["consent"]:
                raise RuleError("Contact permission has been withdrawn. No new demo replies accepted.")
            db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?)",
                       (message_id, case_id, text, "READING", None, case["review_required"], now()))
            withdraw = opted_out(text)
            self._change(db, case_id, consent=0 if withdraw else 1,
                         review_required=1, workflow="STOPPED" if withdraw else "HUMAN_REVIEW")
            self._event(db, case_id, person_label(user) if user else "Caregiver simulator", "REPLY_SAVED",
                        "Original reply saved. Awaiting interpretation or clinical team review.")
            if withdraw:
                db.execute("UPDATE messages SET status='OPT_OUT' WHERE id=?", (message_id,))
                self._event(db, case_id, "App rules", "CONSENT_WITHDRAWN", "Automated contact stopped.")
                return case_id
        try:
            reading = reader(text)
        except Exception:
            reading = needs_review("Reader failed. Review the original reply.", "unavailable")
        with self.connection(write=True) as db:
            current = self._case(db, case_id)
            stale = current["version"] != int(version) + 1
            review = (reading.category in {"CLINICAL", "UNCLEAR"}
                      or reading.clinical_concern or reading.uncertain
                      or bool(case["review_required"]) or stale)
            status = "HUMAN_REVIEW" if review else "PROPOSED"
            db.execute("UPDATE messages SET status=?, reading=? WHERE id=?",
                       (status, json.dumps(reading.data(), ensure_ascii=False), message_id))
            if not current["consent"]:
                workflow = "STOPPED"
            elif review:
                workflow = "HUMAN_REVIEW"
            elif current["access"] == "CONFIRMED":
                workflow = "COMPLETED"
            else:
                workflow = "AWAITING_APPROVAL"
            self._change(db, case_id, review_required=int(review), workflow=workflow)
            self._event(db, case_id, "Reader", "REPLY_INTERPRETED",
                        f"{reading.category}; engine={reading.engine}; prompt={PROMPT_VERSION}. "
                        "Suggestion only. No message sent and no access confirmation.")
        return case_id

    def act(self, case_id, action, data, version, token, role, *, principal=None):
        roles = {
            "approve": "Coordinator", "handover": "Coordinator", "accept_handover": "Coordinator",
            "add_evidence": "Coordinator", "verify": "Verifier",
            "clear_review": "Care team", "withdraw": "Coordinator",
            "check_details": "Coordinator", "approve_update": "Coordinator", "record_contact": "Coordinator",
            "reschedule": "Coordinator",
            "review_assistance": "Coordinator",
        }
        if action not in roles or roles[action] != role:
            raise RuleError("Choose the correct demo role for this action.")
        with self.connection(write=True) as db:
            audit_actor = role
            if principal:
                role, data, audit_actor = prepare_action(db, self._case(db, case_id), action, data, principal)
            if self._once(db, token, [action, case_id, data, version, role, principal], case_id):
                return case_id
            case = self._case(db, case_id)
            self._check(case, version)
            if not case["consent"] and action not in {"verify", "clear_review"}:
                raise RuleError("Contact permission was withdrawn. Routine work is stopped.")
            if action in {"check_details", "approve_update", "record_contact"}:
                blocker = contact_blocker(case)
                if blocker:
                    raise RuleError(blocker)
            if action == "review_assistance":
                run = db.execute("SELECT * FROM assistance_runs WHERE id=? AND case_id=?",
                                 (data.get("run_id"), case_id)).fetchone()
                if not run or run["status"] != "DRAFT" or run["review_decision"]:
                    raise RuleError("Choose a current, unreviewed assistant suggestion.")
                blocker = assistant_blocker(self._detail(db, case_id), run["kind"])
                if blocker:
                    raise RuleError(blocker)
                if run["source_version"] != case["version"]:
                    raise RuleError("This suggestion is from an older case version. Run the assistant again.")
                decision = data.get("decision")
                if decision not in {"use", "reject"}:
                    raise RuleError("Choose use as a reference or reject.")
                person = clean(data.get("reviewed_by"), "the clinical team member reviewing the suggestion")
                note = clean(data.get("note"), "the clinical team review note", 500)
                db.execute("UPDATE assistance_runs SET review_decision=?,reviewed_by=?,review_note=?,reviewed_at=? WHERE id=?",
                           (decision, person, note, now(), run["id"]))
                self._change(db, case_id)
                self._event(db, case_id, person, "ASSISTANCE_REVIEWED",
                            f"{ASSISTANTS[run['kind']]}: {decision}. {note} Review records a decision about the suggestion only; existing action forms still require clinical team approval.")
            elif action == "approve":
                if case["review_required"] or case["access"] == "CONFIRMED" or case["handover_to"]:
                    raise RuleError("Resolve human review or handover before routine work.")
                message = db.execute("SELECT * FROM messages WHERE id=? AND case_id=?",
                                     (data.get("message_id"), case_id)).fetchone()
                if not message or message["status"] != "PROPOSED":
                    raise RuleError("No pending suggestion is available.")
                reading = json.loads(message["reading"])
                note = clean(data.get("note"), "a checked next step", 500)
                db.execute("UPDATE messages SET status='APPROVED' WHERE id=?", (message["id"],))
                workflow = "WAITING_EVIDENCE" if reading["category"] == "RECEIPT_REPORTED" else "COORDINATOR_CHECKING"
                self._change(db, case_id, workflow=workflow)
                self._event(db, case_id, audit_actor, "STAFF_APPROVED", note)
            elif action == "clear_review":
                if not case["review_required"]:
                    raise RuleError("There is no open human review.")
                note = clean(data.get("note"), "the care team's review note", 500)
                workflow = ("STOPPED" if not case["consent"] else "COMPLETED"
                            if case["access"] == "CONFIRMED" else "HANDOVER_PENDING"
                            if case["handover_to"] else "COORDINATOR_CHECKING")
                db.execute("UPDATE messages SET status='REVIEWED' WHERE case_id=? AND status IN ('HUMAN_REVIEW','READING')", (case_id,))
                self._change(db, case_id, review_required=0, workflow=workflow)
                self._event(db, case_id, audit_actor, "HUMAN_REVIEW_RESOLVED", note)
            elif action == "check_details":
                if data.get("facts_checked") != "yes":
                    raise RuleError("Confirm that clinical team checked these collection details with the authorised service.")
                language = data.get("language")
                if language not in LANGUAGES:
                    raise RuleError("Choose a supported message language.")
                details = {k: clean(data.get(k), title, maximum) for k, title, maximum in [
                    ("location", "the verified collection location", 500),
                    ("documents", "the verified document list", 800),
                    ("source", "the authorised service or source checked", 300),
                    ("checked_by", "the clinical team member who checked", 200)]}
                checked_at = occurred_time(data.get("checked_at"))
                db.execute("INSERT INTO collection_checks VALUES(?,?,?,?,?,?,?,?,?)",
                           (uuid4().hex, case_id, details["location"], details["documents"], details["source"],
                            details["checked_by"], checked_at, language, now()))
                self._change(db, case_id)
                self._event(db, case_id, details["checked_by"], "COLLECTION_DETAILS_CHECKED",
                            "Collection location and documents checked. A new message needs clinical team approval; access remains unchanged.")
            elif action in {"approve_update", "record_contact"}:
                details = db.execute("SELECT * FROM collection_checks WHERE case_id=? ORDER BY rowid DESC LIMIT 1",
                                     (case_id,)).fetchone()
                if not details:
                    raise RuleError("Record checked collection details first.")
                if action == "approve_update":
                    if data.get("check_id") != details["id"]:
                        raise RuleError("These details were replaced. Review and approve the latest draft.")
                    if data.get("message_checked") != "yes":
                        raise RuleError("Review the message and confirm that it matches the verified details.")
                    existing = db.execute("SELECT id FROM caregiver_updates WHERE case_id=? AND check_id=?",
                                          (case_id, details["id"])).fetchone()
                    if existing:
                        raise RuleError("This message is already approved. Record contact or save revised checked details.")
                    person = clean(data.get("approved_by"), "the clinical team member approving this message")
                    # Generate server-side from the exact checked facts, never from a submitted body or model output.
                    db.execute("INSERT INTO caregiver_updates VALUES(?,?,?,?,?,?)",
                               (uuid4().hex, case_id, details["id"], draft_message(details), person, now()))
                    self._change(db, case_id)
                    self._event(db, case_id, person, "CAREGIVER_MESSAGE_APPROVED",
                                "Message approved for manual sharing. Approval does not send it or confirm caregiver receipt.")
                else:
                    update = db.execute("SELECT * FROM caregiver_updates WHERE case_id=? AND check_id=? ORDER BY rowid DESC LIMIT 1",
                                        (case_id, details["id"])).fetchone()
                    if not update or data.get("update_id") != update["id"]:
                        raise RuleError("Approve the message for the latest checked details before recording contact.")
                    channel, outcome = data.get("channel"), data.get("outcome")
                    if channel not in CHANNELS or outcome not in OUTCOMES:
                        raise RuleError("Choose a valid contact method and outcome.")
                    if outcome == "SENT" and channel not in {"SMS", "WHATSAPP"}:
                        raise RuleError("Use the sent outcome only for a WhatsApp or SMS message.")
                    if data.get("contact_permitted") != "yes":
                        raise RuleError("Confirm that you used an agreed contact route.")
                    if outcome == "INFORMED" and data.get("receipt_confirmed") != "yes":
                        raise RuleError("Confirm that you spoke with the caregiver or received their acknowledgement.")
                    person = clean(data.get("contacted_by"), "the clinical team member who contacted the caregiver")
                    contacted_at = occurred_time(data.get("contacted_at"))
                    # datetime-local fields record minutes; allow the minute in which approval occurred.
                    approval_minute = datetime.fromisoformat(update["approved_at"]).replace(second=0, microsecond=0)
                    if datetime.fromisoformat(contacted_at) < approval_minute:
                        raise RuleError("The contact time cannot be before this message was approved.")
                    note = clean(data.get("note"), "the contact outcome or acknowledgement details", 500)
                    db.execute("INSERT INTO caregiver_contacts VALUES(?,?,?,?,?,?,?,?,?)",
                               (uuid4().hex, case_id, update["id"], channel, outcome, person, contacted_at, note, now()))
                    self._change(db, case_id)
                    self._event(db, case_id, person, "CAREGIVER_CONTACT_RECORDED",
                                f"{CHANNELS[channel]}: {OUTCOMES[outcome]}. {note} Access remains unchanged.")
            elif action == "add_evidence":
                if case["access"] == "CONFIRMED":
                    raise RuleError("Access is already confirmed for this task.")
                source = clean(data.get("source"), "a sample hospital source")
                reference = clean(data.get("reference"), "a sample record reference")
                try:
                    db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,NULL,NULL,?)",
                               (uuid4().hex, case_id, source, reference,
                                int(data.get("target_match") == "yes"),
                                int(data.get("full_supply") == "yes"), "PENDING", now()))
                except sqlite3.IntegrityError:
                    raise RuleError("That source record has already been entered.") from None
                self._change(db, case_id)
                self._event(db, case_id, audit_actor, "EVIDENCE_ADDED", "Sample dispensing record awaits verifier review.")
            elif action == "verify":
                evidence = db.execute("SELECT * FROM evidence WHERE id=? AND case_id=?",
                                      (data.get("evidence_id"), case_id)).fetchone()
                if not evidence or evidence["status"] != "PENDING":
                    raise RuleError("No pending record with this identifier.")
                note = clean(data.get("note"), "a verification reason", 500)
                accept = data.get("decision") == "accept"
                if data.get("decision") not in {"accept", "reject"}:
                    raise RuleError("Choose accept or reject.")
                if accept and (not evidence["target_match"] or data.get("authority_checked") != "yes"):
                    raise RuleError("Confirm source authority and a match to this patient and access task.")
                db.execute("UPDATE evidence SET status=?,verifier=?,reason=? WHERE id=?",
                           ("ACCEPTED" if accept else "REJECTED", audit_actor, note, evidence["id"]))
                access = case["access"]
                if accept and access != "CONFIRMED":
                    access = "CONFIRMED" if evidence["full_supply"] else "PARTIAL"
                workflow = ("STOPPED" if not case["consent"] else "HUMAN_REVIEW"
                            if case["review_required"] else "COMPLETED" if access == "CONFIRMED"
                            else case["workflow"])
                fields = dict(access=access, workflow=workflow)
                if access == "CONFIRMED":
                    fields["handover_to"] = None
                self._change(db, case_id, **fields)
                self._event(db, case_id, audit_actor, "EVIDENCE_ACCEPTED" if accept else "EVIDENCE_REJECTED", note)
            elif action == "handover":
                if case["access"] == "CONFIRMED":
                    raise RuleError("This task already has confirmed access.")
                person = clean(data.get("person"), "a named recipient")
                note = clean(data.get("note"), "a handover reason", 500)
                due = due_time(data.get("due_at"))
                if person.casefold() == case["owner"].casefold():
                    raise RuleError("Name the next person taking over, rather than the current owner.")
                self._change(db, case_id, handover_to=person, due_at=due,
                             workflow="HUMAN_REVIEW" if case["review_required"] else "HANDOVER_PENDING")
                self._event(db, case_id, audit_actor, "HANDOVER_PROPOSED", f"To {person}. {note}")
            elif action == "accept_handover":
                if not case["handover_to"]:
                    raise RuleError("No handover is waiting.")
                if clean(data.get("person"), "the accepting person's name") != case["handover_to"]:
                    raise RuleError("The accepting name must match the proposed recipient.")
                self._change(db, case_id, owner=case["handover_to"], handover_to=None,
                             workflow="HUMAN_REVIEW" if case["review_required"] else "HANDOVER_ACTIVE")
                self._event(db, case_id, audit_actor, "HANDOVER_ACCEPTED", f"Accepted by {case['handover_to']}. Access remains unresolved.")
            elif action == "reschedule":
                if case["access"] == "CONFIRMED":
                    raise RuleError("This access task is already confirmed.")
                due = due_time(data.get("due_at"))
                if datetime.fromisoformat(due) <= datetime.now(timezone.utc):
                    raise RuleError("Choose a future follow-up time.")
                note = clean(data.get("note"), "the follow-up reason", 500)
                self._change(db, case_id, due_at=due)
                self._event(db, case_id, audit_actor, "FOLLOW_UP_RESCHEDULED", note)
            elif action == "withdraw":
                self._change(db, case_id, consent=0, workflow="STOPPED")
                self._event(db, case_id, audit_actor, "CONSENT_WITHDRAWN", "Routine contact and work stopped.")
            if principal:
                finish_action(db, case_id, action, principal)
        return case_id
