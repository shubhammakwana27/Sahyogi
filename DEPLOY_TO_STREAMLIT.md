# Publish the Streamlit demo

Requested address: https://sahyogi-demo.streamlit.app/

This is the requested address, not a claim that deployment has happened. It
works for this app only after Streamlit accepts the name and finishes deployment.
If the name is owned by a different account, choose another available name.
If it is already your app, update that app's repository settings or source.

## 1. Upload the cloud package to GitHub

Use `SAHYOGI_Streamlit_Cloud_Deploy.zip`. Extract it, then upload its contents
into a new PRIVATE GitHub repository you control. Put `streamlit_app.py`,
`requirements.txt`, `.streamlit/` and `streamlit_frontend/` at the repository root.
Keep all the included original Python files together.

The cloud package starts with an empty database. It deliberately contains no
uploaded account database, saved conversations or API keys. The separate local
package retains your original database. Do not upload that local database to a
public repository or publish saved family records in a public demo.

## 2. Create the app

1. Open https://share.streamlit.io/ and sign in.
2. Click **Create app**, then **Yup, I have an app** if asked.
3. Select your GitHub repository and the `main` branch.
4. Main file path: `streamlit_app.py`.
5. App URL / custom subdomain: `sahyogi-demo`.
6. Open **Advanced settings**. Select Python **3.11** (3.12 also works).
7. Add the secrets below, replacing the password before saving.

```toml
SAHYOGI_READER = "demo"

[sahyogi]
bootstrap_username = "anita"
bootstrap_display_name = "Anita"
bootstrap_password = "YOUR_NEW_PASSWORD"
```

Use your chosen password of 4 to 18 characters, matching the app's existing
password rule. This account is created only when the database is empty.
Changing this secret later does not reset an existing account's password.
Use **Change password** in the app for an existing account.

8. Save, then click **Deploy**. Wait for the app's sign-in page.
9. Sign in with the coordinator username and your chosen password.
10. Open **Accounts** to create the caregiver/patient and clinical team accounts.
    Give temporary passwords privately. Account holders change them on first login.

## 3. Optional live agents

For a first test, `demo` runs without an API key. The existing offline examples
use fixed sample rules. To run the three CrewAI agents, the initial administrator
can open **API settings**, choose a provider, enter a supported model and API key,
apply the settings and test the connection. The app's existing memory-only key
behaviour is kept. A restart removes settings entered only in the app.

To restore provider configuration automatically after a restart, use top-level
Secrets ABOVE `[sahyogi]`, for example:

```toml
SAHYOGI_READER = "crewai"
SAHYOGI_PROVIDER = "sarvam"
SARVAM_MODEL = "YOUR_SUPPORTED_MODEL_ID"
SARVAM_API_KEY = "YOUR_API_KEY"

[sahyogi]
bootstrap_username = "anita"
bootstrap_display_name = "Anita"
bootstrap_password = "YOUR_NEW_PASSWORD"
```

OpenAI and Gemini remain available through the original API settings screen.
Do not commit a real `.streamlit/secrets.toml` file to GitHub.

## 4. Share and store records

After Streamlit confirms deployment, copy the actual URL from its dashboard.
The example name cannot be reserved by placing it in this document or in code.

Use made-up cases for this public demonstration. Streamlit Community Cloud does
not guarantee persistence of local SQLite files. Accounts and new demo records
can disappear on a rebuild/restart; the initial coordinator is then recreated
from Secrets. This conversion preserves the original local database design.
A durable hosted database requires a separate storage integration.

## Official references

- Deployment and subdomains: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- SQLite persistence: https://docs.streamlit.io/develop/concepts/connections/connecting-to-data
