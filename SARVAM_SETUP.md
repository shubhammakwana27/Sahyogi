Palliative request update: the provider/key settings below now power all three stages. After login, patients/caregivers use the question box; staff confirm barriers and approve follow-up. Earlier Read reply case examples remain under Earlier cases. See PALLIATIVE_GUIDE.md for the main flow.

# Use Sarvam AI in SAHYOGI

The updated app can use Sarvam to power the Reader, Barrier Assistant and Follow-up Assistant. Each role runs when requested. See THREE_AGENTS.md for the new buttons. Keep the
same browser screens, saved cases and staff approval steps. Select the provider
explicitly; the app does not switch to another provider after a failed request.

## 1 Get your Sarvam key

1. Open https://indus.sarvam.ai and create or sign in to your account.
2. Complete any required account verification.
3. Open API Keys and generate a new API subscription key.
4. Copy it immediately and store it privately. Sarvam displays the value only
   when it is created. Do not paste the key into a chat or a screenshot.
5. Check your available credits and model access in the dashboard.

Sarvam currently documents Rs 100 in signup credits for verified users. This is
an initial credit balance, not unlimited free API use. Check the actual credit
balance in your own account. Requests consume credits; add funds if you choose
to continue after the balance runs out. ChatGPT Plus is not required for Sarvam.

## 2 Update your existing app

Stop the app with Ctrl+C in PowerShell. Copy the updated files from this ZIP
into your existing sahyogi_starter folder. Keep data/sahyogi.db and .venv.
The download contains no database, credentials or virtual environment.

Open PowerShell inside sahyogi_starter, where app.py and requirements.txt are.
If you already have .venv, skip its creation. For a first installation:

```powershell
py -3.11 -m venv .venv
```

Then install the requirements and select Sarvam:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:SAHYOGI_READER = "crewai"
$env:SAHYOGI_PROVIDER = "sarvam"
$env:SARVAM_API_KEY = "YOUR_SARVAM_API_KEY"
$env:SARVAM_MODEL = "sarvam-105b"

.\.venv\Scripts\python.exe app.py
```

Replace YOUR_SARVAM_API_KEY locally with your real key. The model identifier
sarvam-105b is the documented model used by this integration. Do not use the
retired sarvam-m model. The reader also accepts sarvam/sarvam-105b and removes
that provider prefix before sending the request.

You do not need to put the Sarvam key in OPENAI_API_KEY or GEMINI_API_KEY.
Those providers' settings are ignored while SAHYOGI_PROVIDER is sarvam.
Environment values need to be set again if you open a new PowerShell window.

## 3 Try the reader

1. Open http://127.0.0.1:8000 in your browser. Keep PowerShell running.
2. Create a fresh made up case with a unique plan reference, an owner and a
   follow up time. Tick the approved plan and contact permission checkboxes.
3. Under Read a caregiver reply, enter:

   > आम्ही कुठे जायचे? कोणती कागदपत्रे लागतील?

4. Click Read reply. The expected category is Documents Route, with a short
   factual summary and Reader: crewai. Actual model wording may vary.
5. Enter a checked next step and approve it as coordinator. Access stays
   Not Confirmed until staff accept suitable dispensing proof.

For a medical question, the existing rules still require human review. A failed
API call also leaves a review open. Use a fresh sample case after fixing setup,
or have staff record the review on the old case before routine work continues.

## Change a rejected key inside the app

The initial coordinator can open API settings, choose Live AI and Sarvam AI,
use the existing sarvam-105b model ID, paste a new key and click Apply settings
for this app session. Click Test current key separately. The test can use API
credits and uses only a made-up question. No saved patient request is approved.

The key is kept only in memory until the app stops. Startup option 5 lets you
open this page without first entering a key in the terminal. After the key is
corrected, assigned Staff can retry the latest failed Reader or Barrier result
in the existing request. See API_SETTINGS.md.

## Agent 2 TIMEOUT or UNKNOWN update

See AGENT_TROUBLESHOOTING.md for the current repair steps. Sarvam now uses a
60-second network-operation timeout and a 4096-token generation cap. The
sarvam-105b model uses reasoning_effort="none" for these bounded tasks. The
corresponding CrewAI execution allowance leaves time for parsing.

Test the Barrier Assistant directly, with a hidden key prompt:

```powershell
.\.venv\Scripts\python.exe check_reader.py --test --agent barrier --provider sarvam --prompt-key
```

The optional test uses quota/credits and only made up inputs. It does not open
the database or approve a request. No live Sarvam response was tested when
validating this update. The settings address possible causes, not a confirmed
diagnosis of every timeout or UNKNOWN error.

## 4 Check setup or test without changing cases

This command checks the selected provider and package versions without making
an API request. It does not display secret values:

```powershell
.\.venv\Scripts\python.exe check_reader.py
```

This optional command runs the real CrewAI reader on one fixed synthetic
message. It does not open or change case records, but it consumes API quota and
may incur usage charges. A crew can make more than one provider call:

```powershell
.\.venv\Scripts\python.exe check_reader.py --test
```

## 5 Understand errors

- AUTH: check your Sarvam key. Sarvam can return HTTP 403 for an invalid key.
- CREDITS: check the Sarvam balance. HTTP 402 with insufficient_quota_error
  means the balance is exhausted. Retrying does not add credits.
- RATE_LIMIT: wait and follow any retry delay. HTTP 429 can indicate request
  limits or model capacity. Keep retries limited.
- SPEND_LIMIT: check the account or seat spending limit; waiting may not fix it.
- MODEL: check the exact model ID and whether your account can use it.
- TIMEOUT or CONNECTION: check the network and try later.
- REQUEST or OUTPUT: the request was rejected or a validated answer was not
  returned. The app keeps the original reply available for human review.

The app displays fixed safe error descriptions. Framework terminal logs can
still include provider payloads; remove secrets and personal details before
sharing logs.

## 6 What is connected

The chat API is connected through CrewAI's OpenAI-compatible transport, pointed
explicitly at https://api.sarvam.ai/v2. It calls /chat/completions with the
api-subscription-key header and the selected Sarvam model. The underlying SDK
also adds Bearer authentication, which Sarvam documents as supported.

The request includes the same strict JSON schema used by the reader. The app
checks the answer again before using it. The agent has no database, messaging,
prescribing or proof verification tools. It can only suggest a category,
summary and review flags. No speech, translation, document or calling API has
been added; those would be separate features.

The OpenAI-compatible library name in a terminal error does not by itself mean
the request used OpenAI. The selected provider and configured host determine
where the request goes. Sarvam's host is fixed in this adapter.

Use made up patient information in this starter. It is not ready for patient
use. Python 3.11 setup is supported by the dependencies; validation here used
Python 3.12.14. All 64 tests passed using simulated provider responses. The
Sarvam tests run a real CrewAI agent and SDK against an in-memory HTTP transport.
No live Sarvam account or paid request was used to test this update.

## Official references

- Quickstart: https://docs.sarvam.ai/api/getting-started/quickstart
- Authentication: https://docs.sarvam.ai/api-reference/authentication
- Chat API: https://docs.sarvam.ai/api/token-factory/chat-completions
- V2 reference: https://docs.sarvam.ai/api-reference/chat/chat-completions-v2
- Credits and prices: https://docs.sarvam.ai/api/getting-started/pricing
- Errors: https://docs.sarvam.ai/api/getting-started/errors-troubleshooting
