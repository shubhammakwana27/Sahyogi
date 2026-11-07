# SAHYOGI prescribed medicine access prototype

Built around the supplied SAHYOGI PDF. Keep a prescribed palliative medicine-access task open until assigned Staff accepts authorised matching full dispensing evidence. A named coordinator, next action and check time stay attached meanwhile.

## Start

1. Back up your existing `data` folder before updating. Replace all program files, keeping `data` and `.venv`.
2. Double-click `START_HERE.bat`. Python must be installed. Choose **1** for offline practice or **5** to enter an API key inside the app.
3. On first start create your initial coordinator in the terminal. There is no default account/password. New passwords have 4–18 characters.
4. Open http://127.0.0.1:8000/login. Coordinator creates Caregiver/Patient and Staff accounts under **Accounts**. Each new user changes their temporary password.
5. As coordinator, **Register care task** with a made up plan reference, family account, Staff account, task reference and check time.
6. Family opens the registered task under **Your requests → Messages** and sends the Marathi document example below.
7. Staff reads **Messages**, records **Plan checks**, confirms **Barrier**, then checks and approves **Follow-up**. Family reads the exact approved message on **Overview**.
8. Staff checks **Dispensing proof**. Partial or insufficient proof keeps access open. Only all five evidence checks plus a matching verified plan and completed review allow acceptance.

> अजून औषध मिळालं नाही. कोणती कागदपत्रं लागतील ते माहीत नाही.

Use **USER_MANUAL.pdf** or **USER_MANUAL.docx** for the complete 20-page walkthrough, account setup, all 40 PDF examples and API troubleshooting. **PALLIATIVE_GUIDE.md** contains the same manual in text form. Open the **?** at the top right of a task card for guidance.

## Three agents

| Agent | Job | Code |
| --- | --- | --- |
| Reader | Understand current family message | `crewai_reader.py` |
| Barrier Assistant | Suggest possible practical barriers | `crewai_assistants.py` |
| Follow-up Agent | Draft administrative tasks after Staff confirms the barrier | `crewai_assistants.py` |

Live mode uses these three CrewAI roles. Each stage is a bounded one-agent Crew; no fourth manager, delegation, action tools, planning or memory. Offline mode uses fixed practice rules, not an LLM. Humans approve and perform the actual work.

Code independently controls the evidence decision (`access_workflow.py`), permissions, clinical text holds (`care_safety.py`) and closure. A recognised urgent text stops agent calls and shows a general seek-help notice. Its in-app queue flag is not a phone call or externally delivered alert. The text screen is not validated clinical triage.

## Focused screens

Families see Overview and Messages. The team has separate sections for Team access, Care task, Care team review, Plan checks, Barrier, Follow-up, Dispensing proof, Escalation and History. Team case sections are grouped in a rail that marks completed steps and steps needing attention. Cards appear side by side on wide screens and stack on narrow screens, where a bottom tab bar replaces the sidebar. Colour is reserved for status. Instructions open from **?** controls; urgent warnings stay visible.

**Care task** updates the next action/time. **Team access** requests a named coordinator handover; the current owner remains responsible until acceptance. **Messages** allows Staff/current coordinator to record an actual phone or in-person family reply with provenance. **Escalation** records unresolved work in the assigned team queue.

## Keys and records

Only the initial coordinator administrator manages **API settings**. Keys entered there are memory-only, never returned in HTML or stored in records. On restart the app uses startup settings again. The Reader-only test uses a synthetic question and can consume quota. Staff retries failed stages from Messages, Barrier or Follow-up; a successful retry does not clear human review.

SQLite records persist in `data/sahyogi.db` by default. New tables are added without deleting existing records. Stop the app and back up the data folder before updating. Earlier cases remain under **Earlier cases** with `EARLIER_CASES_MANUAL.pdf`.

## Scope

Local synthetic-data prototype. Dispensing verification is a Staff-entered record of a simulated authorised service check, not a live hospital connection. No document upload/OCR, stock lookup, transport booking, outgoing SMS/WhatsApp/email, prescribing or autonomous dose advice. Verified access does not establish medicine use, pain relief or clinical success. Real deployment requires institutional clinical, operational, privacy and security review and tested alert delivery.

See `PDF_REQUIREMENTS.md` for the source-to-implementation map and `TEST_RESULTS.txt` for actual validation.
