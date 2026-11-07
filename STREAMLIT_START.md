# Open the same SAHYOGI app through Streamlit

This package uses the second uploaded app. Its page text, layout, colours,
navigation, account permissions, saved records and human approval rules are kept.
The smaller Sahyogi-main sample is a reference for Streamlit hosting only.

The three CrewAI roles remain Reader, Barrier Assistant and Follow-up Agent.
Offline practice uses the existing sample rules. Choose Live AI in API settings
to use the three agents with your provider key and supported model.

## Run on Windows

1. Extract this ZIP. Open PowerShell inside the `sahyogi_starter` folder.
2. Install Python 3.11 or 3.12 if needed. Use the installed version below.
3. Run:

```powershell
py -3.11 -m venv .venv_streamlit
.\.venv_streamlit\Scripts\python.exe -m pip install -r requirements_streamlit.txt
$env:SAHYOGI_READER = "demo"
.\.venv_streamlit\Scripts\python.exe manage_users.py setup
.\.venv_streamlit\Scripts\python.exe -m streamlit run streamlit_app.py
```

Or double-click `run_streamlit.bat` after installing Python 3.11. The browser
usually opens at http://localhost:8501. Keep the terminal running.

The local package keeps the uploaded `data/sahyogi.db` exactly. Sign in with the
same account and password. Setup asks for a coordinator only on a fresh database.
If you forgot a local password, run `python manage_users.py reset-password` with
the same virtual-environment Python. The next sign-in requires a password change.

## Use the app

The same buttons and screens are available:

- Patient/caregiver: sign in, send a question under **Questions and tasks**,
  read the approved reply under the request's **Overview**, and send an update.
- Coordinator: assign the clinical team, link the existing care task, choose
  who follows up and record what happened.
- Clinical team: review the request, check the plan and documents, confirm the
  barrier, approve the exact follow-up reply, and check dispensing evidence.
- Initial administrator: use **Accounts** to create accounts and **API settings**
  to configure or test the provider key.

Your existing manuals are included without changing their contents.

## What was added

- `streamlit_app.py`: Streamlit entrypoint and deployment settings.
- `streamlit_bridge.py`: private per-viewer sessions into the original routes.
- `streamlit_frontend/`: displays the original complete HTML/CSS and forwards
  its forms/navigation. The original application screens are not rewritten.
- `.streamlit/config.toml`: removes extra hosting controls around the app.
- `requirements_original.txt`: a copy of the original requirements.
- `requirements_streamlit.txt`: adds Streamlit to the original requirements.
  The cloud package also has Streamlit in `requirements.txt` for automatic setup.
- `secrets.example.toml`: configuration example; it contains no actual key.
- `DEPLOY_TO_STREAMLIT.md`: the exact settings for a public demo link.

The original Python application files and local database are unchanged.
Installed environments and temporary caches are omitted; install dependencies
on your own computer with the commands above.
