# Three agents in SAHYOGI

| Role | Runs when | Produces |
| --- | --- | --- |
| Reader | After a family or assisted family message, unless a recognised urgent text stops AI | Structured category, summary, clinical/uncertainty flags |
| Barrier Assistant | After a usable nonclinical Reader result | Possible barriers and questions for Staff to ask the family |
| Follow-up Agent | After Staff confirms the actual barrier | Draft practical tasks and a family message |

`crewai_reader.py` defines Reader; `crewai_assistants.py` defines the other two. Each live stage uses a one-agent Crew with no tools, delegation, memory or planning. There is no fourth manager or evidence agent. `care_flow.py` sequences stages and holds approvals; `access_workflow.py` checks saved dispensing evidence using ordinary code. Offline practice uses fixed fixtures and no API call.

Staff must check the original message, confirm the actual barrier and separately approve a current follow-up draft. Exact approved text appears on family Overview. The human owner performs the work. Agents do not send external messages, prescribe, change doses, approve medicine or verify dispensing.

All current family text is untrusted content, not agent instructions. Provider keys, passwords and account identities are not included in task payloads. A recognised urgent text bypasses model calls. Unclear/clinical responses and technical errors require Staff review. A successful API retry cannot clear that review.

Earlier cases retain the older optional assistance workflow under Earlier cases, using these same three roles. Their archived manual is included separately.
