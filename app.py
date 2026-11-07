"""Run with: python app.py. Local, synthetic-data demonstration only."""
from datetime import datetime, timedelta, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import sys
from contextvars import ContextVar
import json
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from store import RuleError, Store
from caregiver_contact import CHANNELS, LANGUAGES, OUTCOMES, contact_blocker, contact_progress, current_update, draft_message
from examples import EXAMPLES, next_step
from agent import provider_settings
from assistants import ASSISTANTS, assistant_blocker
from access_control import Accounts, can_act, person_label
from runtime_settings import RuntimeSettings,current_settings
from ui_components import THEME_CSS,help_button,icon

sys.modules.setdefault("app", sys.modules[__name__])
UI_USER = ContextVar("sahyogi_ui_user", default=None)
UI_CSRF = ContextVar("sahyogi_ui_csrf", default="")
UI_PATH = ContextVar("sahyogi_ui_path", default="")

ROOT = Path(__file__).resolve().parent


def e(value):
    return escape(str(value), quote=True)


def label(value):
    return e(str(value).replace("_", " ").title())


def local_due(hours=2):
    return (datetime.now(timezone(timedelta(hours=5, minutes=30)))
            + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M")


def parse_due(value):
    # The demo clearly labels input times as India time, never browser-dependent.
    try:
        return datetime.fromisoformat(value).replace(
            tzinfo=timezone(timedelta(hours=5, minutes=30))).isoformat()
    except (ValueError, TypeError):
        raise RuleError("Choose a follow up date and time.") from None


def pretty_due(value):
    dt = datetime.fromisoformat(value).astimezone(timezone(timedelta(hours=5, minutes=30)))
    return e(dt.strftime("%d %b %Y, %I:%M %p IST"))


NAV_PARENT = {"/request": "/", "/case": "/cases", "/legacy-help": "/help"}


def nav_links(user):
    """(label, short label, href, icon, group) for everything this account may open."""
    items = [("Questions and tasks", "Tasks", "/", "inbox", "work")]
    if user["role"] == "coordinator":
        items.append(("Register care task", "Register", "/care-plan", "plus", "work"))
    items += [("Practice examples", "Examples", "/examples", "chat", "work"),
              ("Simple guide", "Guide", "/help", "book", "work"),
              ("Earlier cases", "Earlier", "/cases", "archive", "work")]
    if user["role"] == "coordinator":
        items.append(("Accounts", "Accounts", "/accounts", "users", "manage"))
        if user.get("is_admin"):
            items.append(("API settings", "API", "/api-settings", "key", "manage"))
    return items


def nav_anchor(item, current):
    label_text, _, href, icon_name, _ = item
    mark = ' aria-current="page"' if href == current else ''
    return f'<a href="{href}"{mark}>{icon(icon_name)}{e(label_text)}</a>'


def app_nav(user, current):
    items = nav_links(user)
    nav = '<nav class="side-nav" aria-label="Workspace">' + ''.join(nav_anchor(i, current) for i in items if i[4] == "work") + '</nav>'
    manage = [i for i in items if i[4] == "manage"]
    if manage:
        nav += '<nav class="side-nav" aria-label="Manage"><span class="side-label">Manage</span>' + ''.join(nav_anchor(i, current) for i in manage) + '</nav>'
    return nav


def tab_bar(user, current):
    """Phone navigation: the three everyday pages, then everything else under More."""
    items = nav_links(user)
    tabs = [i for i in items if i[2] in {"/", "/examples", "/help"}]
    rest = [i for i in items if i not in tabs]
    bar = ''.join(f'<a href="{i[2]}"{" aria-current=page" if i[2] == current else ""}>{icon(i[3])}{e(i[1])}</a>' for i in tabs)
    in_more = current == "/password" or any(i[2] == current for i in rest)
    menu = f'<div class="more-person"><strong>{e(user["display_name"])}</strong><small>Signed in as {e(user["role"].title())}</small></div>'
    menu += ''.join(nav_anchor(i, current) for i in rest)
    menu += f'<a href="/password"{" aria-current=page" if current == "/password" else ""}>{icon("lock")}Change password</a>'
    menu += form(UI_CSRF.get(), "/logout", '<button class="secondary">Sign out</button>')
    return (f'<nav class="tabbar" aria-label="Main">{bar}<details{" data-current" if in_more else ""}>'
            f'<summary>{icon("menu")}More</summary><div class="more-menu">{menu}</div></details></nav>')


def layout(title, body):
    config = current_settings(); user = UI_USER.get()
    brand = '<a class="brand" href="/"><span class="brand-mark" aria-hidden="true">\u0938</span>Sahyogi</a>'
    guide = help_button('Using SAHYOGI', 'This local practice app supports prescribed medicine access. Three CrewAI roles help read messages, identify barriers and draft follow-up. Human clinical team approve actions. Ordinary code checks evidence and permissions. No external message or call is sent automatically.')
    role = ''
    if not user:
        content = ('<main class="auth-page"><div class="auth-head">' + brand + guide + '</div>' + body
                   + '<p class="auth-foot">Local practice app. Use made up details only.</p></main>')
    else:
        team = user['role'] in {'coordinator', 'staff'}
        role = 'role-team' if team else 'role-family'
        path = UI_PATH.get(); current = NAV_PARENT.get(path, path)
        person = ('<div class="side-person"><span class="avatar" aria-hidden="true">' + e(user['display_name'][:1].upper()) + '</span><div><strong>'
                  + e(user['display_name']) + '</strong><small>Signed in as ' + e(user['role'].title()) + '</small></div></div>')
        account = ('<div class="side-account">' + person + '<div class="side-links"><a href="/password">Change password</a>'
                   + form(UI_CSRF.get(), '/logout', '<button>Sign out</button>') + '</div></div>')
        mode = 'Offline practice' if config.mode == 'demo' else 'Live AI configured' if config.api_key and config.model else 'AI setup needed'
        mode_badge = '<span class="pill pill-neutral">' + e(mode) + '</span>' if team else ''
        content = ('<div class="app-shell"><aside class="sidebar">' + brand + app_nav(user, current) + account + '</aside>'
                   '<main class="app-main"><div class="topbar">' + brand + '<span class="topbar-title">Practice app. Use made up details only.</span>'
                   '<div class="top-actions">' + mode_badge + guide + '</div></div>' + body + '</main>' + tab_bar(user, current) + '</div>')
    return ('<!doctype html><html lang="en"' + (f' class="{role}"' if role else '') + '><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' + e(title) + ' · SAHYOGI</title><style>'
            + THEME_CSS + '</style></head><body>' + content + '</body></html>')


def form(csrf, action, content, case=None, extra=""):
    user = UI_USER.get()
    if user and action in {"/create", "/practice"} and user["role"] != "coordinator":
        return ""
    if user and action == "/assist" and (user["role"] != "coordinator" or user.get("relation") != "owner"):
        return ""
    if user and action == "/reply" and user.get("relation") == "former_owner":
        return ""
    hidden = f'<input type="hidden" name="csrf" value="{e(csrf)}">'
    hidden += f'<input type="hidden" name="token" value="{uuid4().hex}">'
    if case:
        hidden += f'<input type="hidden" name="case_id" value="{e(case["id"])}">'
        hidden += f'<input type="hidden" name="version" value="{case["version"]}">'
    return f'<form method="post" action="{e(action)}">{hidden}{extra}{content}</form>'


def field(name, title, value="", kind="text", required=True, maximum=200, readonly=False, minimum=None):
    req = "required" if required else ""
    req += " readonly" if readonly else ""
    if minimum is not None:
        req += f' minlength="{int(minimum)}"'
    return f'<label>{e(title)}<input type="{e(kind)}" name="{e(name)}" value="{e(value)}" {req} maxlength="{maximum}"></label>'


def account_field(name, title, fallback=""):
    user = UI_USER.get()
    return field(name, title, person_label(user) if user else fallback, readonly=bool(user))


def check(name, title):
    return f'<label class="check"><input type="checkbox" name="{e(name)}" value="yes"> {e(title)}</label>'


def note(title="Checked next step or review reason"):
    return f'<label>{e(title)}<textarea name="note" required maxlength="500"></textarea></label>'


def accepting_person_field():
    user = UI_USER.get()
    if user:
        return '<p>You will accept as <strong>' + e(user['display_name']) + ' (@' + e(user['username']) + ')</strong>.</p><input type="hidden" name="person" value="' + e(user['username']) + '">'
    return field("person", "Accepting person")


def action_form(csrf, case, action, role, content, button):
    user = UI_USER.get()
    if not can_act(user, action):
        return ""
    if user and user["role"] == "coordinator":
        if action == "accept_handover" and user.get("relation") != "pending_owner":
            return ""
        if action != "accept_handover" and user.get("relation") != "owner":
            return ""
    hidden = f'<input type="hidden" name="action" value="{e(action)}"><input type="hidden" name="role" value="{e(role)}">'
    return form(csrf, "/act", content + f'<button>{e(button)}</button>', case, hidden)


def choice(name, title, options):
    return f'<label>{e(title)}<select name="{e(name)}" required>' + ''.join(
        f'<option value="{e(value)}">{e(text)}</option>' for value, text in options.items()) + '</select></label>'


def long_field(name, title, maximum):
    return f'<label>{e(title)}<textarea name="{e(name)}" required maxlength="{maximum}"></textarea></label>'


def checked_details_summary(details):
    return (f'<p><strong>Checked by:</strong> {e(details["checked_by"])}<br>'
            f'<strong>Checked at:</strong> {pretty_due(details["checked_at"])}<br>'
            f'<strong>Source:</strong> {e(details["source"])}<br>'
            f'<strong>Message language:</strong> {e(LANGUAGES[details["language"]])}</p>'
            f'<p><strong>Verified collection location</strong></p><blockquote>{e(details["location"])}</blockquote>'
            f'<p><strong>Verified documents</strong></p><blockquote>{e(details["documents"])}</blockquote>')


def caregiver_section(csrf, case):
    details, update, contacts = current_update(case)
    blocker = contact_blocker(case)
    body = '<section class="card" id="caregiver-update"><h2>Check details and inform caregiver</h2>'
    body += f'<p><strong>Caregiver update:</strong> {e(contact_progress(case))}</p>'
    body += '<p>Record checked facts and approve the message. Assigned patients and caregivers can read it in their portal. Clinical team can also contact them outside the app and record the outcome. Contact does not confirm collection.</p>'
    if blocker:
        body += f'<p class="alert">{e(blocker)}</p>'
    body += '<h3>A Record checked details</h3>'
    if details:
        body += checked_details_summary(details)
    else:
        body += '<p>No verified collection details have been recorded yet.</p>'
    if not blocker:
        fields = long_field("location", "Verified collection location", 500)
        fields += long_field("documents", "Verified documents to bring", 800)
        fields += field("source", "Authorised service or source checked", maximum=300)
        fields += account_field("checked_by", "Clinical team member who checked", case["owner"])
        fields += field("checked_at", "When details were checked in India time", local_due(0), "datetime-local")
        fields += choice("language", "Caregiver message language", LANGUAGES)
        fields += '<p>Enter the location and documents in words the caregiver understands. The message template does not translate these fields.</p>'
        fields += check("facts_checked", "I checked these details with the authorised service")
        button = "Save revised checked details" if details else "Save checked details"
        explanation = '<p>Revising details creates a new draft that needs fresh approval. Earlier records remain in history.</p>'
        new_form = action_form(csrf, case, "check_details", "Coordinator", fields, button)
        body += '<details><summary>Revise checked details</summary>' + explanation + new_form + '</details>' if details else new_form
    body += '<h3>B Review and approve the caregiver message</h3>'
    if not details:
        body += '<p>Save checked details above to prepare a message.</p>'
    elif not update:
        body += '<p><strong>Draft from checked facts</strong></p><blockquote>' + e(draft_message(details)) + '</blockquote>'
        if not blocker:
            fields = f'<input type="hidden" name="check_id" value="{e(details["id"])}">'
            fields += account_field("approved_by", "Clinical team member approving this message", case["owner"])
            fields += check("message_checked", "I reviewed the message and it matches the checked details")
            body += action_form(csrf, case, "approve_update", "Coordinator", fields, "Approve caregiver message")
    else:
        body += f'<p>Approved by {e(update["approved_by"])} at {pretty_due(update["approved_at"])}. Approval publishes the message to assigned patient and caregiver accounts. It does not send external messages.</p>'
        body += f'<label>Approved message for manual sharing<textarea readonly rows="7">{e(update["body"])}</textarea></label>'
        body += '<p>Select the approved text and copy it with Ctrl+C. Share it using your agreed contact method, or explain the same details on a call. This app sends no message.</p>'
    body += '<h3>C Record what happened when clinical team contacted the caregiver</h3>'
    if not update:
        body += '<p>Approve the message above before recording a contact.</p>'
    elif not blocker:
        fields = f'<input type="hidden" name="update_id" value="{e(update["id"])}">'
        fields += choice("channel", "Contact method used outside this app", CHANNELS)
        # Default to not reached. Staff must explicitly report acknowledgement.
        outcomes = {key: OUTCOMES[key] for key in ["NOT_REACHED", "SENT", "INFORMED"]}
        fields += choice("outcome", "Contact outcome", outcomes)
        fields += account_field("contacted_by", "Clinical team member who contacted the caregiver", case["owner"])
        fields += field("contacted_at", "When contact happened in India time", local_due(0), "datetime-local")
        fields += note("Contact note or acknowledgement details")
        fields += check("contact_permitted", "I used an agreed contact route")
        fields += check("receipt_confirmed", "I spoke with the caregiver or received their acknowledgement")
        fields += '<p>Tick the acknowledgement box only if that happened. A sent message alone does not mean the caregiver received or understood it.</p>'
        body += action_form(csrf, case, "record_contact", "Coordinator", fields, "Save caregiver contact outcome")
    if case["caregiver_contacts"]:
        body += '<h3>Saved contact history</h3>'
        updates_by_id = {u["id"]: u for u in case["caregiver_updates"]}
        for contact in reversed(case["caregiver_contacts"]):
            body += (f'<hr><p><strong>{e(OUTCOMES[contact["outcome"]])}</strong><br>'
                     f'{e(CHANNELS[contact["channel"]])} by {e(contact["contacted_by"])} at {pretty_due(contact["contacted_at"])}</p>'
                     f'<blockquote>{e(contact["note"])}</blockquote>')
            body += '<details><summary>Approved message for this contact</summary><blockquote>' + e(updates_by_id[contact["update_id"]]["body"]) + '</blockquote></details>'
    if len(case["collection_checks"]) > 1:
        body += '<details><summary>Earlier checked details</summary>'
        for previous in reversed(case["collection_checks"][:-1]):
            body += '<hr>' + checked_details_summary(previous)
        body += '</details>'
    return body + '</section>'


def home(store, csrf, search="", view="all"):
    cases = store.list_cases()
    def due(c):
        return c["access"] != "CONFIRMED" and c["consent"] and datetime.fromisoformat(c["due_at"]) < datetime.now(timezone.utc)
    filters = {"all": "All cases", "open": "Open tasks", "review": "Needs human review", "due": "Follow-up due", "completed": "Completed", "stopped": "Contact stopped"}
    if view not in filters:
        view = "all"
    selected = [c for c in cases if (view == "all" or view == "open" and c["consent"] and (c["access"] != "CONFIRMED" or c["review_required"])
        or view == "review" and c["review_required"] or view == "due" and due(c)
        or view == "completed" and c["workflow"] == "COMPLETED" or view == "stopped" and not c["consent"])
        and (not search or search.casefold() in ' '.join(str(c[k]) for k in ["patient_ref", "plan_ref", "target", "owner"]).casefold())]
    stats = '<div class="stats">' + ''.join(f'<div class="stat"><strong>{count}</strong>{e(title)}</div>' for title, count in [
        ("Total cases", len(cases)), ("Needs human review", sum(bool(c["review_required"]) for c in cases)),
        ("Follow-up due", sum(bool(due(c)) for c in cases)), ("Completed", sum(c["workflow"] == "COMPLETED" for c in cases))]) + '</div>'
    rows = ""
    for c in selected:
        overdue = due(c)
        rows += f'''<tr><td><a href="/case?id={e(c['id'])}">{e(c['patient_ref'])}</a>
        <br><small>{e(c['plan_ref'])}</small></td><td>{label(c['access'])}<br>
        <small>{label(c['workflow'])}</small></td><td>{e(c['owner'])}</td>
        <td>{pretty_due(c['due_at'])}{'<br><strong>Follow up due</strong>' if overdue else ''}</td></tr>'''
    case_list = f'''<section class="card"><h2>Cases and next steps</h2><div class="table-wrap">
    <table><thead><tr><th>Sample patient</th><th>Status</th><th>Responsible person</th><th>Next check</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="4" class="empty">No matching cases. Add a made up case below or change the filter.</td></tr>'}</tbody></table></div></section>'''
    filter_form = '<form class="filters" method="get" action="/">' + field("q", "Find patient reference, plan or owner", search, required=False)
    filter_form += '<label>Show<select name="view">' + ''.join(f'<option value="{key}"{" selected" if key == view else ""}>{e(value)}</option>' for key, value in filters.items()) + '</select></label><button>Find cases</button><a class="small-link" href="/">Clear filters</a></form>'
    content = field("patient_ref", "Sample patient reference", "P-014")
    content += field("plan_ref", "Unique plan task reference", "DEMO-PLAN-014")
    content += field("target", "What medicine access task are we checking?", "Confirm collection for the approved plan")
    content += account_field("owner", "Person responsible", "Demo coordinator")
    content += field("due_at", "Next follow up in India time", local_due(), "datetime-local")
    content += check("plan_approved", "Clinical team has checked the approved plan reference")
    content += check("consent", "The caregiver agreed to follow up contact")
    content += '<button>Create sample case</button>'
    welcome = '<section class="card"><h2>Start here</h2><p>Track one approved medicine access task at a time. Open a case to see what clinical team should do next.</p><a class="button-link" href="/help#examples">Try a practice example</a><a class="small-link" href="/help">Read the simple guide</a></section>'
    return layout("All cases", welcome + stats + filter_form + case_list + '<section class="card"><h2>Add a sample case</h2>'
                  + form(csrf, "/create", content) + '</section>')


def assistance_section(csrf, case):
    body = '<section class="card" id="agent-help"><h2>Agent help for clinical team</h2>'
    body += '<p>Three agents are available. The Reader runs with Read reply. Use the two buttons below when you want extra help. Each click in AI mode can use provider credits or quota.</p>'
    body += '<p>Suggestions are drafts for clinical team. They do not check a service, contact anyone, approve an action or confirm collection. The new assistants receive only case status codes, counts and flags.</p>'
    for kind, title in ASSISTANTS.items():
        body += f'<h3>{e(title)}</h3>'
        body += '<p>' + ('Suggests practical checks for the reported barrier.' if kind == 'barrier' else 'Highlights missing records and suggests the next clinical team checks.') + '</p>'
        blocker = assistant_blocker(case, kind)
        if blocker:
            body += f'<p class="alert">{e(blocker)}</p>'
        else:
            content = f'<input type="hidden" name="kind" value="{e(kind)}"><input type="hidden" name="role" value="Coordinator">'
            content += f'<button>Run {e(title)}</button>'
            body += form(csrf, '/assist', content, case)
    runs = case.get('assistance_runs', [])
    if runs:
        body += '<h3>Saved assistant suggestions</h3>'
    for run in reversed(runs):
        fresh = run['source_version'] == case['version'] and not assistant_blocker(case, run['kind'])
        body += f'<hr><h3>{e(ASSISTANTS[run["kind"]])}</h3><small>{pretty_due(run["created_at"])} · Engine: {e(run["engine"])} · Case version {run["source_version"]}</small>'
        if run['engine'] == 'demo':
            body += '<p>Offline practice checklist. No AI call was made.</p>'
        if run['status'] == 'RUNNING':
            body += '<p class="alert">Running or interrupted. Reload to check. If it was interrupted, make a new request; no action was approved.</p>'
        elif run['error']:
            body += f'<p class="alert">Assistant unavailable. {e(run["error"])} Existing clinical team work remains available.</p>'
        if run['review_decision']:
            body += f'<p><strong>Clinical team review:</strong> {"Use as a reference" if run["review_decision"] == "use" else "Rejected"} by {e(run["reviewed_by"])} at {pretty_due(run["reviewed_at"])}</p><blockquote>{e(run["review_note"])}</blockquote>'
        if run['output']:
            if run['status'] == 'STALE' or not fresh:
                body += '<p class="alert">Earlier case snapshot. Keep for history; run the assistant again for current suggestions.</p>'
            output = run['output']
            body += '<p><strong>Draft suggestion for clinical team review</strong></p><blockquote>' + e(output['summary']) + '</blockquote>'
            body += '<p><strong>Suggested checks</strong></p><ol>' + ''.join('<li>'+e(item)+'</li>' for item in output['checks']) + '</ol>'
            body += '<p><strong>Missing items according to this snapshot</strong></p>'
            body += '<ul>' + ''.join('<li>'+e(item)+'</li>' for item in output['missing_items']) + '</ul>' if output['missing_items'] else '<p>No missing items were listed by this assistant. This is not proof of completion.</p>'
            if run['status'] == 'DRAFT' and fresh and not run['review_decision']:
                fields = f'<input type="hidden" name="run_id" value="{e(run["id"])}">'
                fields += choice('decision', 'Clinical team decision about this suggestion', {'reject': 'Reject suggestion', 'use': 'Use as a reference after checking'})
                fields += account_field('reviewed_by', 'Clinical team member reviewing the suggestion', case['owner'])
                fields += note('What clinical team checked and decided')
                body += action_form(csrf, case, 'review_assistance', 'Coordinator', fields, 'Save clinical team review of suggestion')
    body += '<p>After reviewing a suggestion, use the existing checked next step, caregiver message, follow-up or proof form to record the actual action. Reviewing a suggestion does not perform that action.</p>'
    return body + '</section>'


def help_page(csrf):
    body = '<section class="card"><h2>How to use SAHYOGI</h2><p>This app helps clinical team follow an approved medicine access task. Three CrewAI agents can assist: the Reader understands the reply, the Barrier Assistant suggests practical checks, and the Follow-up Assistant highlights missing steps. Clinical team check the facts and make decisions.</p>'
    body += '<ol class="steps-list"><li>Create a case with the approved plan reference, contact permission, owner and next check time.</li><li>Read the caregiver reply. Approve a practical next step, or resolve the care team review after clinical team have reviewed it.</li><li>Record the checked collection location and documents.</li><li>Review and approve the caregiver message. Share it outside this app, then record the contact outcome.</li><li>Add and verify authorised dispensing proof. Only accepted full proof confirms access.</li><li>Keep unresolved work with a named owner and next check time. The next person must accept a handover.</li></ol></section>'
    body += '<section class="card"><h2>Opening the app</h2><p>Double-click START_HERE.bat on Windows. Choose 1 to practise with offline sample rules, or choose an AI provider and enter its key privately. On other systems run python3 start_app.py. Keep the terminal open and visit http://127.0.0.1:8000.</p><p>Offline mode is not AI. It recognises the exact sample sentences. Real provider summaries may vary. API use depends on your account and can consume credits or quota.</p></section>'
    body += '<section class="card"><h2>Use the three agents</h2><ol><li>Click Read reply to use the Reader as before.</li><li>Open Agent help for clinical team on the same case. Click Run Barrier Assistant for a practical checklist.</li><li>Check the draft. Choose Use as a reference after checking or Reject suggestion, enter the clinical team name and note, then click Save clinical team review of suggestion.</li><li>Use the existing action form to approve the actual next step. Agent review does not approve it.</li><li>After saving progress, click Run Follow-up Assistant to see what is missing. Review its draft in the same way.</li></ol><p>The new agents are optional and run separately. Old drafts become historical when the case changes. An open care team review, stopped permission, pending handover or confirmed access blocks routine assistance. Offline mode shows sample checklists rather than real AI.</p><p>For example, read the directions sample, request a barrier checklist, save checked details and contact, then request follow-up help. Missing acknowledgement or dispensing proof will be highlighted from the saved records.</p></section>'
    body += '<section class="card"><h2>If you cannot find an approval field</h2><p>The coordinator approval field appears below a routine reply when it is awaiting approval. If Human Review is open, use Care team review after clinical team check the original messages. The What to do next panel links to the right place.</p><p>Checking a location and telling the caregiver are separate steps. Message approval does not send it. A sent message without acknowledgement is not marked as the caregiver being informed.</p></section>'
    body += '<section class="card" id="examples"><h2>10 practice examples</h2><p>Each button creates a new made up case owned by the signed-in coordinator. The approved plan and contact permission are simulated only for that practice case. It does not call AI, submit a reply or send a message.</p>'
    for index, (key, example) in enumerate(EXAMPLES.items(), 1):
        body += f'<h3>{index}. {e(example["title"])}</h3><p>{e(example["meaning"])}</p>'
        if example["message"]:
            body += '<blockquote>' + e(example["message"]) + '</blockquote>'
        body += '<ol>' + ''.join('<li>' + e(step) + '</li>' for step in example["steps"]) + '</ol>'
        body += form(csrf, "/practice", f'<input type="hidden" name="example_id" value="{e(key)}"><button>Create practice case</button>')
    body += '</section><section class="card"><h2>Records and limits</h2><p>Cases are saved in data/sahyogi.db. Stop the app before copying that file as a backup, or run backup_records.py for a database backup. Each case also has a Download case record link for a JSON copy.</p><p>Use made up information. This is a local learning app with account logins and case permissions, no hospital integration and no outgoing messaging. It gives no medical advice. It is not ready for patient use.</p></section>'
    return layout("Help and examples", body)


def case_page(store, csrf, case_id):
    c = store.detail(case_id)
    title, instruction, target = next_step(c)
    user = UI_USER.get()
    if user and user["role"] == "staff":
        if c["review_required"]:
            title, instruction, target = "Record the care team review", "Review the original messages and record the care team's actual note and next step.", "care-review"
        elif any(ev["status"] == "PENDING" for ev in c["evidence"]):
            title, instruction, target = "Check the pending dispensing proof", "Review source authority and the patient/task match before saving your verifier decision.", "proof"
        else:
            title, instruction, target = "No clinical team check is waiting", "The coordinator manages the practical next step. You can read this assigned case and its saved history.", "history"
    elif user and user.get("relation") == "pending_owner":
        title, instruction, target = "Accept the named handover", "Review this case, then accept the handover to take responsibility. Any open care team review stays open.", "handover"
    elif user and user.get("relation") == "former_owner":
        title, instruction, target = "Earlier owner view", "Responsibility was handed over. You can read the history; routine changes belong to the current owner.", "history"
    elif user and c["review_required"]:
        title, instruction, target = "Assign clinical team for care team review", "Link an active clinical team account under Who can see this case. Assigned clinical team can sign in and record the review.", "case-access"
    body = f'<section class="card next"><h2>What to do next</h2><h3>{e(title)}</h3><p>{e(instruction)}</p><a class="button-link" href="#{e(target)}">Go to this step</a></section>'
    example = EXAMPLES.get(c.get("practice_example"))
    if example:
        body += f'<section class="card"><h2>Practice example: {e(example["title"])}</h2><p>{e(example["meaning"])}</p><ol>' + ''.join('<li>' + e(step) + '</li>' for step in example["steps"]) + '</ol><p>The reply below is prefilled for practice. Click Read reply when you are ready.</p></section>'
    body += f'''<section class="card"><h2>{e(c['patient_ref'])}</h2>
    <span class="badge">Access: {label(c['access'])}</span><span class="badge">{label(c['workflow'])}</span>
    <p><strong>Task:</strong> {e(c['target'])}<br><strong>Plan:</strong> {e(c['plan_ref'])}<br>
    <strong>Responsible:</strong> {e(c['owner'])}<br><strong>Next check:</strong> {pretty_due(c['due_at'])}</p>'''
    if c["review_required"]:
        body += '<p class="alert">Human review is open. Routine logistics stays paused until the care team records a review.</p>'
    if not c["consent"]:
        body += '<p class="alert">Contact permission withdrawn. Routine work has stopped.</p>'
    body += f'<p><strong>Caregiver update:</strong> {e(contact_progress(c))}</p>'
    body += f'<a class="small-link" href="/export?id={e(case_id)}">Download case record</a>'
    body += '<a class="small-link" href="#agent-help">Agent help for clinical team</a>'
    if c["consent"] and c["access"] != "CONFIRMED":
        body += '<details><summary>Change next follow-up time</summary>' + action_form(csrf, c, "reschedule", "Coordinator",
            field("due_at", "Next follow up in India time", local_due(), "datetime-local") + note("Reason for the new follow-up time"), "Save follow-up time") + '</details>'
    body += '</section><div class="grid"><div><section class="card" id="read-reply"><h2>1 Read a caregiver reply</h2>'
    body += '<p>Use one of these sample messages:</p><ul><li>आम्ही कुठे जायचे? कोणती कागदपत्रे लागतील?</li><li>He is in severe pain and cannot sleep.</li><li>We collected it.</li></ul>'
    if c["consent"]:
        body += form(csrf, "/reply", '<label>Sample reply<textarea name="text" required maxlength="2000">' + e(example["message"] if example and not c["messages"] else "") + '</textarea></label><button>Read reply</button>', c)
    for m in reversed(c["messages"]):
        body += f'<hr><blockquote>{e(m["body"])}</blockquote><small>{label(m["status"])}</small>'
        if m["reading"]:
            r = m["reading"]
            body += f'<p><strong>{label(r["category"])}</strong><br>{e(r["summary"])}</p><small>Reader: {e(r["engine"])}</small>'
        if m["status"] == "READING":
            body += '<p>Still reading, or the reader was interrupted. Care team review is available below.</p>'
        if (m["status"] == "PROPOSED" and c["consent"] and not c["review_required"]
                and c["access"] != "CONFIRMED" and not c["handover_to"]):
            body += action_form(csrf, c, "approve", "Coordinator",
                                f'<input type="hidden" name="message_id" value="{e(m["id"])}">'
                                + note(), "As coordinator, approve next step")
    body += '</section><section class="card" id="care-review"><h2>Care team review</h2>'
    if c["review_required"]:
        body += action_form(csrf, c, "clear_review", "Care team", note("Clinical team review note and next step"), "As care team, resolve this review")
    else:
        body += '<p>No human review is currently open.</p>'
    body += '</section>' + assistance_section(csrf, c) + caregiver_section(csrf, c) + '</div><div><section class="card" id="proof"><h2>2 Add sample proof</h2>'
    body += '<p>A caregiver collection claim is not proof. This form simulates a checked hospital dispensing record.</p>'
    if c["consent"] and c["access"] != "CONFIRMED":
        content = field("source", "Sample hospital source", "Demo hospital")
        content += field("reference", "Unique sample dispensing record", f"DEMO-{uuid4().hex[:6]}")
        content += check("target_match", "Record matches this patient, plan and access task")
        content += check("full_supply", "Record covers the whole approved access task")
        body += action_form(csrf, c, "add_evidence", "Coordinator", content, "Add pending record")
    for ev in c["evidence"]:
        body += f'<hr><strong>{e(ev["source"])}</strong> · {e(ev["reference"])}<p>Status: {label(ev["status"])}<br>Full task covered: {"Yes" if ev["full_supply"] else "No"}</p>'
        if ev["status"] == "PENDING":
            content = f'<input type="hidden" name="evidence_id" value="{e(ev["id"])}">'
            content += '<label>Verifier decision<select name="decision"><option value="reject">Reject record</option><option value="accept">Accept record</option></select></label>'
            content += check("authority_checked", "I checked that the source is authorised and the record is valid")
            content += note("Verification reason")
            body += action_form(csrf, c, "verify", "Verifier", content, "As verifier, save decision")
    body += '</section><section class="card" id="handover"><h2>3 Hand over unresolved work</h2>'
    if c["handover_to"]:
        body += f'<p>Awaiting acceptance from <strong>{e(c["handover_to"])}</strong>. The current owner stays responsible until acceptance.</p>'
        body += action_form(csrf, c, "accept_handover", "Coordinator",
                            accepting_person_field(), "Accept this handover")
    if c["consent"] and c["access"] != "CONFIRMED":
        content = field("person", "Next coordinator username")
        content += field("due_at", "Next check in India time", local_due(), "datetime-local") + note("Reason for handover")
        body += action_form(csrf, c, "handover", "Coordinator", content, "Propose a named handover")
    else:
        body += '<p>No routine handover is needed or available.</p>'
    body += '</section></div></div><section class="card" id="history"><h2>Action history</h2><div class="table-wrap"><table><tr><th>Time</th><th>Who</th><th>Action</th><th>Reason</th></tr>'
    for event in c["events"]:
        body += f'<tr><td>{pretty_due(event["created_at"])}</td><td>{e(event["actor"])}</td><td>{label(event["kind"])}</td><td>{e(event["detail"])}</td></tr>'
    body += '</table></div></section>'
    if c["consent"]:
        body += '<details class="danger-zone"><summary>Stop automated contact for this case</summary>'
        body += action_form(csrf, c, "withdraw", "Coordinator", '<p>Records withdrawal of contact permission. No messages are sent by this demo.</p>', "Record contact withdrawal") + '</details>'
    return layout(c["patient_ref"], body)


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store):
        if address[0] != "127.0.0.1":
            raise ValueError("The demonstration only binds to 127.0.0.1.")
        from portal import PortalHandler
        super().__init__(address, PortalHandler)
        self.store = store
        self.accounts = Accounts(store)
        self.api_settings = RuntimeSettings()
        from care_flow import CareFlow
        self.care = CareFlow(store, self.accounts)
        self.csrf = secrets.token_urlsafe(32)  # retained only for old local view helpers


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not print patient references or message bodies in access logs.

    def valid_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def error(self, message, status=400):
        back = '<a href="/">Return to cases</a>' if UI_USER.get() else '<a href="/login">Go to sign in</a>'
        self.send_html(layout("Please check", f'<section class="card"><h2>Please check this step</h2><p>{e(message)}</p>{back}</section>'), status)



if __name__ == "__main__":
    store = Store(os.getenv("SAHYOGI_DB", str(ROOT / "data" / "sahyogi.db")))
    port = int(os.getenv("SAHYOGI_PORT", "8000"))
    from manage_users import bootstrap_if_needed
    try:
        bootstrap_if_needed(store)
    except (ValueError, KeyboardInterrupt, EOFError) as error:
        print(str(error) or "Setup stopped. Run manage_users.py setup in a terminal, then start again.")
        raise SystemExit(1)
    server = DemoServer(("127.0.0.1", port), store)
    print(f"Open http://127.0.0.1:{server.server_port}")
    print("Local demo only. Use made up data. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
