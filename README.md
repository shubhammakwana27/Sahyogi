Click here - [**Open the Live App**](https://sahyogi-appapppy-ayzlejhtk3o7wxtm3zkoex.streamlit.app/)

# SAHYOGI

### A palliative cancer care coordination prototype

SAHYOGI helps patients, caregivers and hospital teams follow up on access to **already-prescribed medicines**. A family can ask for help in its own words. The care team checks the problem, publishes an approved reply, assigns someone to follow up and records dispensing evidence.

**An approved reply does not mean that medicine was collected.** Medicine access stays open until the Clinical Team accepts matching, complete dispensing evidence.

> Demonstration only. Use made-up information. SAHYOGI supports non-diagnostic care coordination; it does not diagnose, prescribe, change doses or replace clinical judgement.

## Try the shared demo

Open the [live application](https://sahyogi-appapppy-ayzlejhtk3o7wxtm3zkoex.streamlit.app/) and use the demo accounts provided by the project team:

| Role | Username | Password |
| --- | --- | --- |
| Patient/caregiver | `p001` | `123456` |
| Coordinator | `c123` | `123456` |
| Clinical Team | `s001` | `123456` |

These credentials are for the shared demonstration only. **A fresh source installation does not contain these accounts.** The owner creates accounts during setup. If shared demo records or accounts have been reset, contact the project team.

### First example: missing documents

1. **Patient/caregiver:** Sign in as `p001`. Under **Questions and tasks**, send:

   > अजून औषध मिळालं नाही. कोणती कागदपत्रं लागतील ते माहीत नाही.

   Meaning: “We have not received the medicine yet. We do not know which documents are needed.”

2. **Coordinator:** Sign out and sign in as `c123`. Open the request, assign `s001` through **Team access**, and complete **Care task** with made-up task and existing plan references, an owner and a next check time. Record permission for routine follow-up.
3. **Clinical Team:** Sign in as `s001`. Read **Messages**. Complete **Care team review** if required. In **Plan checks**, save the checked plan reference, document details and the source of the check.
4. **Clinical Team:** Open **Barrier**, confirm the actual document barrier and click **Confirm barrier and ask Follow-up Agent**.
5. **Clinical Team:** Open **Follow-up**, check or edit the draft, choose the follow-up owner and time, and click **Approve and publish next step**.
6. **Patient/caregiver:** Sign in again as `p001`. Open the same request's **Overview** to read the approved reply and acknowledge it. Send an update through **Messages** when needed.
7. **Coordinator and Clinical Team:** Record the follow-up result. When simulated pharmacy evidence is available, the Clinical Team checks **Dispensing proof**. Incomplete or mismatched evidence keeps medicine access open.

Sign out before switching roles, or use separate browser profiles. If the family sees that no approved next step is ready, check that the Clinical Team published the current reply and completed any required review.

More examples and detailed button instructions are in [USER_MANUAL.pdf](USER_MANUAL.pdf) and [PALLIATIVE_GUIDE.md](PALLIATIVE_GUIDE.md).

## Who does what?

| Role | Main responsibilities |
| --- | --- |
| Patient or caregiver | Ask a question, read the approved reply, acknowledge it and share updates. |
| Coordinator | Register or link the care task, assign case access, name the follow-up owner, set the next check time and record progress. |
| Clinical Team | Review messages, check the existing plan and documents, confirm barriers, approve replies and check dispensing evidence. |
| Initial coordinator administrator | Create Clinical Team and coordinator accounts, create family accounts and manage **API settings**. |

Other coordinators can create patient/caregiver accounts under **Accounts**. Creating an account and assigning it to a request are separate steps. New account holders change their temporary password at first sign-in. There is no public self-registration.

The **follow-up owner** is a named human account, such as the coordinator. The Follow-up Agent drafts the work; the human owner carries it out.

## Three CrewAI agents

| Agent | When it works | What it produces | Source |
| --- | --- | --- | --- |
| Reader | After a family message, unless a recognised urgent message stops AI processing | A summary, suggested route and uncertainty or clinical flags | [crewai_reader.py](crewai_reader.py) |
| Barrier Assistant | After a usable, nonclinical Reader result | Possible practical barriers and questions for human review | [crewai_assistants.py](crewai_assistants.py) |
| Follow-up Agent | After the Clinical Team confirms the actual barrier | Draft practical tasks and a family reply | [crewai_assistants.py](crewai_assistants.py) |

Each live stage uses a separate, bounded one-agent Crew. There is no fourth manager agent. The agents do not publish replies or accept dispensing evidence themselves. Application code controls permissions, review requirements and evidence decisions.

| Mode | How it works | API key |
| --- | --- | --- |
| Offline practice | Uses fixed practice rules and made-up examples. It demonstrates the workflow, not live CrewAI performance. | Not needed |
| Live AI | Runs the three CrewAI roles using Sarvam AI, Google Gemini or OpenAI. Each stage runs when its workflow conditions are met. | Required for the selected provider |

## Technology

The prototype uses a **Streamlit web interface**, a **Python backend**, and **SQLite** for case records and decision history. The Streamlit host displays the original portal screens through a frontend component, preserving their layout and human approval workflow.

| File or folder | Purpose |
| --- | --- |
| [streamlit_app.py](streamlit_app.py) | Streamlit entry point and first-account setup from Secrets |
| [streamlit_bridge.py](streamlit_bridge.py) | Connects each viewer's session to the Python portal |
| [streamlit_frontend/](streamlit_frontend/) | Displays the portal screens and forwards forms and navigation |
| [app.py](app.py) | Original local application server |
| [care_flow.py](care_flow.py) | Request stages and human approval workflow |
| [access_control.py](access_control.py) | Accounts, permissions and case access |
| [access_workflow.py](access_workflow.py) | Care tasks and dispensing evidence checks |
| [care_safety.py](care_safety.py) | Rule-based handling of recognised urgent text |
| [manage_users.py](manage_users.py) | Initial coordinator setup and local password recovery |
| [requirements.txt](requirements.txt) | Streamlit and original application dependencies |

## Run locally on Windows

Use Python **3.11 or 3.12** for this package. Open PowerShell in the extracted project folder containing `streamlit_app.py` and `requirements.txt`.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:SAHYOGI_READER = "demo"

.\.venv\Scripts\python.exe manage_users.py setup
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

If using Python 3.12, replace `py -3.11` with `py -3.12` in the first command. Run `py --list` to see installed Python versions.

On a fresh database, setup asks for the initial coordinator's username, display name and password. The current app accepts new passwords of **4 to 18 characters**. Keep the terminal running and open the local address printed by Streamlit, normally [http://localhost:8501](http://localhost:8501).

Sign in as the initial coordinator. Under **Accounts**, create a patient/caregiver account and a Clinical Team account. You can use `p001` and `s001` as sample usernames for your own demonstration.

To start the app again later, set `SAHYOGI_READER` in the new PowerShell window and run the final Streamlit command. You do not need to recreate the virtual environment or accounts.

## Enable live AI

The initial coordinator administrator can configure live AI inside the app:

1. Open **API settings**.
2. Select **Live AI** and choose **Sarvam AI**, **Google Gemini** or **OpenAI**.
3. Enter a model ID supported by that provider and your API account.
4. Enter the provider's API key, choose the wait time and apply the settings.
5. Click **Test current key**. This tests the **Reader only** using a made-up question. It does not test all three agents or approve a saved case.
6. Return to the request. The assigned Clinical Team member can retry the failed stage from **Messages**, **Barrier** or **Follow-up**.

Get a key from your chosen provider's account dashboard. Live requests use that provider's quota or billing. The project owner can configure live access for evaluators; offline practice requires no key.

Keys entered in **API settings** are held in server memory until the app stops. They are not saved in SQLite. After restart, startup configuration applies again. These settings apply to the running app, not just one viewer.

For startup configuration, the app recognises:

| Provider | `SAHYOGI_PROVIDER` | Key variable | Model variable |
| --- | --- | --- | --- |
| Sarvam AI | `sarvam` | `SARVAM_API_KEY` | `SARVAM_MODEL` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `GEMINI_MODEL` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` |

Live startup mode uses `SAHYOGI_READER = "crewai"`; offline mode uses `"demo"`. Do not put a Sarvam key in `OPENAI_API_KEY`.

## Deploy on Streamlit Community Cloud

1. Add the cloud package's contents to your GitHub repository. Keep `streamlit_app.py`, `requirements.txt`, `requirements_original.txt`, `.streamlit/`, `streamlit_frontend/` and the original Python modules together at the repository root.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app connected to the repository and choose `streamlit_app.py` as the main file.
3. Select Python 3.11 or 3.12 for this package where available. Add the following under **Advanced settings → Secrets**, replacing the sample password:

```toml
SAHYOGI_READER = "demo"

[sahyogi]
bootstrap_username = "c123"
bootstrap_display_name = "Anita"
bootstrap_password = "YOUR_NEW_PASSWORD"
```

4. Deploy, sign in with the configured coordinator account, and create the family and Clinical Team accounts under **Accounts**.

The bootstrap account is created only when the database has no users. Changing its password in Secrets later does **not** reset an existing account.

To start in live Sarvam mode, replace the single top-level `SAHYOGI_READER = "demo"` line with the following values, all **before** `[sahyogi]`:

```toml
SAHYOGI_READER = "crewai"
SAHYOGI_PROVIDER = "sarvam"
SARVAM_MODEL = "YOUR_SUPPORTED_MODEL_ID"
SARVAM_API_KEY = "YOUR_API_KEY"
```

Use real values only in private Secrets. Never commit `.streamlit/secrets.toml`, API keys, account databases or saved family records to GitHub. The package includes a [secrets.example.toml](secrets.example.toml) template.

Keep the full `streamlit_frontend/` folder in the repository. Missing component files can prevent the interface from opening.

See [DEPLOY_TO_STREAMLIT.md](DEPLOY_TO_STREAMLIT.md) for package details and the official [deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app) and [Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) documentation for hosting guidance. Use the actual URL assigned by your Streamlit dashboard when sharing a new deployment.

## Records and dispensing checks

SQLite stores accounts, requests, messages, approvals and decision history in `data/sahyogi.db` by default. `SAHYOGI_DB` can select another database path.

Dispensing verification requires a matching checked clinician-approved plan and all five evidence checks: **authorised source, valid record, patient match, task match and full task coverage**. Any required human review must also be completed. Missing evidence does not prove that medicine was not collected.

Local files on Streamlit Community Cloud are not durable application storage. Accounts and records may be lost when the environment is recreated. This prototype needs a separate durable-storage integration before reliable hospital use.

For a local backup, run:

```powershell
.\.venv\Scripts\python.exe backup_records.py
```

## Checks and troubleshooting

Run the included automated tests from the project folder:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

Automated tests can use simulated provider responses. Passing them does not establish real provider accuracy or patient benefit. See [STREAMLIT_TEST_RESULTS.txt](STREAMLIT_TEST_RESULTS.txt) for the recorded checks and their limits.

To check live agents separately with made-up inputs, set the selected provider's model variable and run the diagnostic tool. For Sarvam:

```powershell
$env:SARVAM_MODEL = "YOUR_SUPPORTED_MODEL_ID"
.\.venv\Scripts\python.exe check_reader.py --test --agent all --provider sarvam --prompt-key
```

Replace the model placeholder first. The tool prompts privately for the key, tests each role separately and does not open the case database. Live tests consume API quota.

| Problem | What to check |
| --- | --- |
| No suitable Python runtime | Run `py --list`; install Python 3.11 or 3.12 and use the matching command. |
| No requests after sign-in | Confirm the account's role and that the coordinator assigned access to the request. |
| No approved reply for the family | Complete required review and publish the current Follow-up draft. |
| Rejected key or quota error | Check the selected provider, key, supported model, available credits and limits. |
| Timeout | Check provider availability, adjust the available wait setting and retry the relevant stage. Human review remains separate. |
| Cannot verify access | Check the linked care task, matching plan reference, completed review and all dispensing evidence checks. |
| Forgotten local password | Run `manage_users.py reset-password` using the virtual environment's Python and follow the hidden prompts. |

## Scope and limits

- The Clinical Team approves family replies and records dispensing decisions. Agents do not approve medicines.
- Dispensing checks record a human review of evidence; the prototype is not connected to a live hospital or pharmacy system.
- There is no automatic stock lookup, document upload/OCR, transport booking or outgoing SMS, WhatsApp or email.
- Urgent flags are rule-based and not validated clinical triage. An in-app flag does not deliver an external emergency alert.
- Verified dispensing does not establish medicine use, pain relief or clinical success. Real patient outcomes have not been measured.

## Documentation

- [User manual](USER_MANUAL.pdf)
- [Detailed text guide and examples](PALLIATIVE_GUIDE.md)
- [Account and login guide](LOGIN_GUIDE.md)
- [Three-agent explanation](THREE_AGENTS.md)
- [API settings](API_SETTINGS.md)
- [Streamlit hosting guide](DEPLOY_TO_STREAMLIT.md)

Built by **Team CareThread** for **Health-a-thon 2026**, with The Innovation Story, Mumbai.
