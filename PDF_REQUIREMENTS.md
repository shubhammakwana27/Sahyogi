# Implementation map for the supplied SAHYOGI PDF

Source: SAHYOGI.pdf, 12 pages, supplied by the user. The PDF is a strategic assessment with a focused medicine-access journey and sample questions. Its suggested deck, market positioning, research, regulatory discussion and impact claims are not validated app capabilities.

| PDF requirement | Implementation | Prototype boundary |
| --- | --- | --- |
| Pages 1–2 focus on prescribed palliative cancer medicine access | Registered medicine-access task links an existing plan reference, family and Staff | Existing decision recorded; no prescription generated |
| Page 2 plan/task before follow-up | Register care task; named coordinator, due time, default next action and permission | Simulated plan; separate human verification required |
| Pages 2–4 deterministic evidence check | `evidence_decision` checks verified matching plan and five evidence conditions | Checks the saved Staff assertions; no hospital API or document extraction |
| Pages 2–3 Marathi caregiver reply and barrier | Original text saved; Reader → Barrier Assistant → Staff confirmation | Live model requires account key; offline samples are fixed rules |
| Page 3 human next step | Staff-approved family message plus named follow-up owner and due time | Staff/coordinator performs real work outside the app |
| Pages 3–4 verified closure | Full proof closes access; partial/rejected evidence and resolved practical barriers leave it open | Accepted dispensing is not a clinical outcome |
| Page 3 unresolved access | Operations flag, escalation view, owner, next action/time, overdue filter and accepted handover | Page-refresh queue; no external notification or background alert service |
| Pages 3–4 clinical concern | Independent text-rule urgent stop; visible generic urgent-help notice; assigned Staff review; optional checked institutional guidance | Conservative text screen, not validated triage; no built-in institution protocol or live alert delivery |
| Pages 4 and 7 auditability and access | Scoped role accounts, CSRF/Origin checks, SQLite audit history, evidence/approval provenance | Local demo, not certification or production privacy compliance |
| Pages 6–8 practical demonstration and accessibility | Assisted family phone/in-person entry, focused screens, help controls, fixed scenario catalog | No automatic calling, voice interface or messaging service |
| Pages 9–12 example questions | 24 English + 7 Indic + 3 safety tests + 5 demo favorites + primary journey = 40 fixtures | Categories tested as fixture expectations; no measured AI accuracy claim |

Three CrewAI roles remain: Reader, Barrier Assistant and Follow-up Agent. Evidence is code, not another agent. The current Python HTTP server and SQLite are retained to preserve the existing local app and saved records; the PDF's suggested FastAPI/Streamlit stack is not a functional requirement.

To demonstrate the PDF's main story, follow manual pages 4–9. Also demonstrate unresolved access (page 10) and a clinical stop (page 11). All service names, document lists, plan references and dispensing entries must be made up for practice.
