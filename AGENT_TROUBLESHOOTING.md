# If Agent 2 says TIMEOUT or UNKNOWN

For **AUTH / key rejected**, use the new in-app **API settings** page first.
The initial coordinator applies and tests the replacement key. Assigned staff
then retries the failed Reader or Barrier Assistant on the existing request.
See API_SETTINGS.md. Startup option 5 opens the app without requiring a terminal
key prompt. The in-app key lasts until the app stops and is not saved to disk.

These labels describe a technical failure. They do not mean the family has no
barrier. Their original message stays saved and staff can still review it.

## Apply the corrected files

1. Stop the app with Ctrl+C and back up data/sahyogi.db.
2. Extract the corrected ZIP into a separate folder. Copy its files into the
   existing sahyogi_starter folder, replacing matching program files. Keep your
   existing data folder and .venv folder. portal.py alone is not enough for this update.
3. Run START_HERE.bat. Choose 2 for Sarvam and enter your own key privately.
4. Sign in as the assigned Staff account and open the existing request.
5. Click Retry Barrier Assistant once. Leave the terminal and browser open
   while it runs. Each API operation can wait up to 60 seconds by default; a
   whole CrewAI run can take longer because it also prepares and validates output.
6. Earlier failed attempts remain in saved history. Look at the latest result.
   A draft is still a suggestion that staff must check and confirm.

## What changed

- Sarvam API waits were 20 seconds. The default is now 60 seconds per network
  operation, with a longer corresponding agent execution allowance.
- For sarvam-105b, extra reasoning is disabled with reasoning_effort="none" and
  the maximum generation allowance is 4096 tokens. Sarvam documents that default
  reasoning can use the allowance before returning visible content. This is a
  plausible cause of an empty response, not a confirmed diagnosis of your account.
- Empty CrewAI responses and network timeout subclasses get clear safe error
  categories. Barrier errors name the Barrier Assistant, rather than the Reader.
- check_reader.py can test Agent 2 directly on a made up input. It does not
  open the patient database or require the Reader to succeed first.

These are app-side improvements. They do not guarantee Sarvam availability or
fix credits, key permissions or a slow/unavailable network. Provider responses
in the automated tests were simulated; no live Sarvam key was used.

## Check Agent 2 directly

Open PowerShell in sahyogi_starter and run:

```powershell
.\.venv\Scripts\python.exe check_reader.py --test --agent barrier --provider sarvam --prompt-key
```

Enter your own Sarvam API key at the hidden prompt. It is used only during this
command and is not saved. When SARVAM_MODEL is unset, this prompted Sarvam test
uses sarvam-105b. If you already set SARVAM_MODEL, that value is used instead.
The command is a separate process and does not read a key entered in the web app.

This test uses the real API and can consume quota/credits. It uses a fixed made
up document question, prints safe status information and changes no saved case.
A success should include Barrier Assistant, a validated draft and DOCUMENTS.
Actual model output may vary; a different barrier/uncertainty produces exit code 3.

To check settings without an API call:

```powershell
.\.venv\Scripts\python.exe check_reader.py --provider sarvam
```

Other explicit tests are --agent reader, --agent followup and --agent all.
The all option runs each stage separately and can use more quota. An agent may
make more than one model call while producing a validated answer.

If you need a longer wait, set this before starting the app or running the test:

```powershell
$env:SAHYOGI_API_TIMEOUT_SECONDS = "90"
```

The allowed range is 10 to 120 seconds. OpenAI and Gemini keep their previous
20-second defaults unless this override is set. This is a per-operation network
timeout, not a total workflow deadline. To remove the override in PowerShell:

```powershell
Remove-Item Env:SAHYOGI_API_TIMEOUT_SECONDS -ErrorAction SilentlyContinue
```

## Continue staff work while the API is unavailable

1. Assigned staff reads the original family message and clarifies it directly
   with the patient/caregiver if needed.
2. If Care team review is open, staff completes the actual review and records
   its outcome. A technical fix alone does not clear that review.
3. Under Staff identify the actual barrier, choose the checked barrier, explain
   how it was identified, tick the confirmation and submit.
4. The Follow-up Agent is requested. If that also fails, use Write a manual
   draft if the agent is unavailable. Save it, then check and approve it in the
   separate approval form before the family can see the message.

Staff may not treat an unavailable agent as an approval, clinical assessment or
verified collection. Medicine/document source checks and all existing role,
consent and staff approval requirements still apply.

## If it still fails

- TIMEOUT/CONNECTION: check the network and provider service, then try later.
- AUTH/ACCESS/MODEL: check your selected key, project access and model ID.
- CREDITS/SPEND_LIMIT/RATE_LIMIT: follow the reported account/quota action.
- OUTPUT: no usable structured answer was returned; staff reviews the original.
- UNKNOWN: share the diagnostic's Result/error lines and package versions.
  Keep API keys and real patient information private.

Official references, checked 4 November 2026:
- https://docs.sarvam.ai/api/token-factory/models
- https://docs.sarvam.ai/api/token-factory/models/sarvam-105b
- https://docs.sarvam.ai/api-reference/chat/chat-completions-v2
