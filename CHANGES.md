# PDF based redesign 4 November 2026

- Added clinician-task-first registration, named owner, due time and editable next action.
- Added independent dispensing evidence checks and verified-access closure. Practical support results keep a linked medicine task open.
- Added in-app unresolved/clinical queue flags, explicit acknowledgement and accepted named coordinator handover.
- Added assisted family replies from real phone/in-person conversations with provenance.
- Added conservative urgent text stop independent of the LLM; human review and checked guidance remain separate. Older guidance is hidden after a request changes.
- Split request work into focused views, added top-right question-mark help, calm coloured cards and responsive desktop/mobile layouts.
- Retained three CrewAI roles, accounts, saved records, Staff approvals, provider choices and memory-only API controls.
- Added all 40 PDF practice messages and a matching 20-page PDF/Word manual.
- This remains a synthetic-data localhost prototype, with no external messaging or hospital integration.

## Previous changes

# Consolidated user manual update

- Replaced the older guide with one 15-page manual matching the current app.
- Added exact steps for accounts, in-app key setup, staff versus family access,
  saved-message retry and approved family replies.
- Included ten practical examples with messages, checks and expected outcomes.
- Word and PDF were rendered and all pages visually checked. Runtime code is
  unchanged; the existing 199 automated test results remain applicable.

Earlier release notes follow.

# In-app API key replacement and failed Reader retry

- Initial coordinator administrators can manage shared API settings through an
  authenticated form. Other roles cannot read, edit, test or remove credentials.
- Provider, model, live/practice mode and bounded wait are applied without a
  process restart. In-app keys live only in memory and are never prefilled in
  HTML, written to SQLite/settings files or included in case history/agent data.
- All three agent roles and the earlier-case assistants use an immutable request
  snapshot. Changes affect new requests without mutating process environment or
  another server instance. In-flight requests keep their original settings.
- Added explicit fixed-input connection testing, deduplication and stale-result
  protection. Applying a key does not test it or grant a care approval.
- Added assigned-staff retry for the latest failed Reader result. Original text
  and the earlier failed reading are retained. Open review, consent, version,
  case membership and staff approval rules remain enforced.
- Startup option 5 installs AI dependencies and opens the app without requiring
  a terminal key prompt. The initial coordinator then configures AI in the app.
- Added API_SETTINGS.md, matching in-app help and regression tests for access,
  credential privacy, live updates, isolation, native Sarvam requests and retry.

Earlier release notes follow.

# Agent 2 Sarvam wait and diagnostic update

- Changed Sarvam's default per-operation API wait from 20 to 60 seconds and
  aligned CrewAI execution allowances. Added a bounded 10-120 second override
  through SAHYOGI_API_TIMEOUT_SECONDS. Other providers retain their defaults.
- For sarvam-105b only, send reasoning_effort="none"; allow up to 4096 generated
  tokens for Sarvam structured output. Strict output validation remains required.
- Recognise empty CrewAI output, truncated/filter/parser output exceptions and
  HTTPX timeout/network subclasses without exposing provider bodies or keys.
- Error messages identify the failing role. Historical failed runs remain saved.
- Added direct fixed-input Reader/Barrier/Follow-up checks, a no-call settings
  mode and an optional hidden key prompt that restores temporary environment
  settings afterwards. No diagnostic opens the patient database.
- Added simple troubleshooting steps and staff guidance when Agent 2 fails.
- These changes mitigate request/settings issues; live Sarvam availability and
  the exact cause of a user's UNKNOWN failure remain unverified.

Earlier release notes follow.

# Browser sign-in fix

- Fixed the conflict between Referrer-Policy: no-referrer and the strict POST
  Origin check. Native form submissions can send Origin: null under the old
  policy. The new same-origin policy preserves the origin for local forms while
  withholding referrers from other sites.
- Origin, Host, session and per-session CSRF checks remain enforced. Null,
  foreign and wrong-port Origin values remain rejected.
- HTTP test clients now send the same-origin Origin header for every POST.
  Added regression checks for document headers, coordinator sign-in, caregiver
  creation, password change and the question box, plus rejected origins and
  supported localhost sign-in.
- Added simple repair steps to LOGIN_GUIDE.md. Existing accounts and records
  require no migration or reset. The existing Word/PDF workflow guide still applies.

Earlier release notes follow.

# Patient-first palliative care workflow

- The first login screen is for patients and caregivers. Team accounts use
  Staff / coordinator sign in; saved account roles still control permissions.
- Patients/caregivers start with a question box. A previously approved plan is
  not required to ask for help. Family plan references stay unverified.
- Reader interprets the current message and routes attention. Barrier Assistant
  suggests barriers for the coordinator and assigned staff. Staff identifies the
  actual barrier; only then does Follow-up Agent draft tasks and a family message.
- Staff records external clinician decisions and document checks with sources.
  AI does not approve medicines, prescribe, assess urgency or change doses.
- Staff checks/edits the draft and publishes the exact approved next step with
  a named owner and due time. Only that message appears in the family portal.
  Staff can ask the caregiver directly; the caregiver replies in that request.
- New family messages require fresh barrier confirmation and approval. Changed
  checks, staff reassignment and stale agent results invalidate earlier drafts.
- Original questions are saved before calls. Failed reads open staff review
  without automatically making another paid call. Manual staff drafts still
  require a separate approval. Consent withdrawal blocks routine work.
- Named owners record actual follow-up; staff reviews the result. Collection
  reports require the verified existing plan and full matching authorised
  dispensing proof before they can be resolved as verified collection.
- Added separate care_* tables and kept existing users, passwords and cases.
  Earlier cases retains the original workflow and its archived manual.
- Added an eight-page simple Word/PDF guide and ten practice messages.
- Validation: 167 tests passed, zero skipped, using simulated provider replies.
  Updated launcher wording was also checked with its existing tests.

Earlier release notes follow.

# Password length update

- New passwords must contain 4 to 18 characters, inclusive. Central settings are
  PASSWORD_MIN_LENGTH and PASSWORD_MAX_LENGTH in access_control.py.
- The same limit applies to initial setup, account creation, password changes
  and local resets. New/repeat/temporary password fields show the matching
  browser limits. Prompts, errors and manuals show the new wording.
- Existing saved longer passwords still work at sign-in and as the current
  password when changing it. Passwords are not silently truncated or replaced.
- Kept password hashing, sign-in throttling, session expiry and all case permissions.
- Validation: 139 tests passed, zero skipped. Four added checks cover boundary
  lengths, create/change/reset flows, browser/server checks and legacy sign-in.

Earlier release notes follow.

# Account logins and task portals

- Added Patient, Caregiver, Coordinator and Staff accounts. Account roles come
  from the database, with server-side checks on every protected route/action.
- Patients and caregivers see only their assigned cases and current approved
  instructions. They can send a question/update, mark instructions as read or
  withdraw routine contact. Internal drafts and staff review notes stay hidden.
- Coordinators manage their own cases and case membership. Assigned Staff
  accounts handle care team review and proof verification. Submitted role and
  staff-name fields cannot impersonate another account.
- Added password hashing with unique salts, bounded server-side sessions,
  per-session CSRF, login/session rotation, sign-out, password changes, temporary
  password changes at first sign-in, and local operator password recovery.
- No default passwords or public signup. Only the initial coordinator admin
  can create other coordinator/staff accounts. Existing accounts cannot choose
  their own role at sign-in.
- Case access follows actual account IDs. Handover requires the named next
  coordinator to sign in and accept; the former owner becomes read-only.
- Added portal read acknowledgements, separate from dispensing proof. The
  coordinator progress label and Follow-up Assistant see the current read flag.
- Added users, case_members, sessions, login_attempts, account_events and
  patient_acknowledgements tables. Original case columns and records are kept.
  The initial coordinator takes account responsibility for legacy cases; old
  recorded owners are retained in migration history and versions are advanced.
- All three agents remain. No extra AI dependencies or agents were added.
- Updated the manual and added LOGIN_GUIDE.md. Still localhost only, for made up
  data, with no automatic outgoing messages or reviewed online deployment.
- Validation: 135 tests passed, zero skipped. 27 new account/HTTP tests cover
  identity, roles, case isolation, privacy, CSRF, session expiry/revocation,
  password flows, handover, migration, approved updates and acknowledgements.

Earlier release notes follow.

# Three agent update

- Kept the original Reply Reader. Added Barrier Assistant and Follow-up Assistant
  as distinct CrewAI agent roles with structured checklist output.
- Added explicit request buttons and staff review forms on each case. Reviewing
  a suggestion records use/reject only; it does not approve or execute an action.
- All roles share the selected provider and key. Each runs in its own fresh Crew
  when requested. Offline practice uses clearly labelled fixed checklists.
- The new agents receive status codes, counts and flags, without raw messages,
  names, patient references, checked free text or credentials in their task input.
- Added an assistance_runs table with immutable output, snapshot version, engine,
  error and review history. Existing records and case columns are preserved.
- Database locks are released before AI calls. Duplicate submissions do not
  repeat calls. Changed cases invalidate draft suggestions and in-flight results.
- Human review, contact withdrawal, pending handover and confirmed access block
  routine assistance. Existing evidence and caregiver approval gates still pass.
- Original messages now use insertion order so replies saved within the same
  second are presented and read by the new assistants in the correct order.
- Updated the app help, README, Word and PDF manual. Added THREE_AGENTS.md.
- Validation: 108 tests passed, zero skipped, with simulated provider responses.
  This includes real CrewAI execution and native OpenAI, Sarvam and Gemini SDK
  request construction. No live provider or outgoing message call was made.

Earlier release notes follow.

# Guided local app update

- Added START_HERE.bat and a simple provider menu. Offline practice needs no key.
- Added a dashboard with search, filters and due/review counters.
- Added What to do next with links to the relevant case section.
- Added Help and examples with 10 separate, labelled practice cases. Creating
  a practice case does not call AI or simulate a staff approval.
- Added follow-up time changes, case JSON downloads and a SQLite backup tool.
- Added USER_MANUAL.docx with simple steps, a complete caregiver update example,
  10 practical exercises, troubleshooting and backup instructions.
- Added one practice_cases table. Existing case records are preserved.
- Kept the single CrewAI reader, staff approval gates and manual contact workflow.
- Validation: 87 tests passed with zero skipped. The eight new tests cover the
  launcher, practices, guidance, filters, follow-up time, backups and HTTP routes.
  No live provider request or outgoing message was made.

Earlier release notes follow.

# CrewAI reader update

## Checked details and caregiver contact update

- Added a case section for verified location, documents, source, named checker
  and check time. A deterministic English, Marathi or Hindi template uses only
  the entered facts. Existing input facts are not automatically translated.
- Staff must approve the message before recording contact. The exact approved
  text is saved and available for manual copying. The app has no sending API.
- Staff separately record contact method, time and outcome. Sent messages do
  not count as acknowledged. Confirmed contact requires a staff acknowledgement
  checkbox; these remain simulated staff records, not external delivery proof.
- Revised checked facts need a new approval. Previous details, exact approved
  messages and contact records remain available. Old approvals cannot be used
  for the revised facts. Stale or duplicate submissions remain protected.
- Added three tables with CREATE TABLE IF NOT EXISTS; original case columns
  and data are preserved. Back up the database before upgrading as documented.
- Human review, withdrawn permission, pending handover and confirmed access
  block routine contact actions. Existing proof rules still control access.
- Added CAREGIVER_UPDATES.md with a complete simple walkthrough and 15 tests
  for migration, forms, approvals, contact outcomes, revisions and backend gates.
- Validation: 79 tests passed with zero skipped using simulated AI responses.
  No real messages, phone calls or paid provider requests were made.

The provider updates below describe earlier releases. app.py and store.py now
include the new caregiver coordination workflow described above.

## Sarvam provider update

- Added SAHYOGI_PROVIDER=sarvam with SARVAM_API_KEY and SARVAM_MODEL.
- One existing CrewAI agent uses the OpenAI-compatible transport on the fixed
  https://api.sarvam.ai/v2/chat/completions endpoint with the subscription key
  header and strict ReplyOutput JSON schema. No provider fallback was added.
- CrewAI is explicitly kept on Chat Completions for this compatible host.
  No new SDK dependency is required. Requests use a 20 second timeout, zero SDK
  retries and a 2048 token generation cap.
- Added safe handling for Sarvam 402 credit exhaustion, 403 invalid key errors,
  model capacity, account rate limits and seat spend limits.
- Added SARVAM_SETUP.md with API key steps, Python 3.11 PowerShell commands,
  sample use, diagnostic commands, credits and official source links.
- Added eight tests. Native integration tests use real CrewAI and a real SDK
  with an in-memory HTTP transport to verify host, auth, request schema,
  Marathi input, staff approval, medical review and malformed output handling.
- Validation: 64 tests passed, zero skipped. No live provider calls were made.
- app.py and store.py are unchanged. The schema, saved cases, screens and
  staff approval steps are preserved. Existing OpenAI and Gemini modes remain.

## Gemini provider update

- Added explicit SAHYOGI_PROVIDER=openai or gemini. OpenAI remains the default.
- Gemini uses GEMINI_API_KEY and GEMINI_MODEL through CrewAI's native Google
  provider. No automatic provider fallback or change in reader agent count.
- Requirements now include crewai[google-genai]==1.15.30.
- Gemini requests use the same strict ReplyOutput model, no action tools,
  a 20 second HTTP timeout and one SDK attempt. Reasoning text is not requested.
- Added Google SDK status handling to safe diagnostics. check_reader.py reports
  the selected provider and checks its variables without revealing their values.
- Added nine routing and native integration tests, including a real CrewAI run
  with a mocked Google SDK response to the Marathi sample and the staff gate.
- Storage and app screen source files are unchanged. Existing records remain
  compatible. Updated Windows Python 3.11 commands are at the top of README.md.
- Validation: 56 tests passed with zero skipped. Google and OpenAI responses are
  simulated; no live request or API key was used to validate the update.

## Reader diagnostics update

- Failed reads now show safe error labels for exhausted credits, key rejection,
  access, missing API resources, rate limits, timeout, connection, request format,
  dependencies, output validation and service failures.
- Billing codes such as `credit_balance_exhausted` are distinguished from ordinary
  HTTP 429 rate limits. Wrapped SDK exceptions retain their safe classification.
- Literal API key/model placeholders are rejected before making requests.
- New `check_reader.py` checks setup without network calls by default; `--test`
  tests the real reader on one fixed synthetic message without touching cases.
- New diagnostics tests cover billing codes, wrappers, privacy and command modes.
- No database, screen layout, agent count or human approval changes. Previously
  failed replies still need a recorded human review, or use a fresh practice case.
- Root cause reported in the user's log: API `credit_balance_exhausted`. Code
  diagnostics do not restore API credits; billing must be resolved separately.

- The real reader now uses one CrewAI Agent, one Task and one sequential Crew.
- CrewAI mode is the default. The old `openai` mode name routes to CrewAI too.
- The agent only proposes a category and summary; staff still approves actions.
- `store.py` and the database schema are unchanged. Existing cases are compatible.
- The screens keep the same forms. Only the reader status label changed.
- The explicit `demo` mode remains available as limited offline sample rules.
- CrewAI 1.15.30 is pinned in `requirements.txt`. Python 3.12 is used for validation.
- Tests execute real CrewAI with a simulated model and a simulated provider response.
- Setup and upgrade steps are in `README.md`. Keep your existing `data/sahyogi.db`.

No live paid model request was made. This remains a local, synthetic-data demonstration.
