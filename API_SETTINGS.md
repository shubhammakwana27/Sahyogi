# API settings in the running app

Start with choice 5 in START_HERE.bat to prepare AI dependencies without a terminal key prompt. Sign in as the initial coordinator administrator and open API settings. Choose Live AI, the provider, its supported model ID, your key and a wait of 10–120 seconds. Apply, then separately test. Sarvam's existing configuration uses sarvam-105b with a 60-second default wait.

The entered key is kept in memory until the app stops. It is never shown again or saved in SQLite, case history or a settings file. Leaving it blank keeps the current key only for the same provider. Switching provider requires that provider's key. On restart startup settings apply again. Each running call retains its own settings snapshot.

Test current key sends a fixed synthetic document question through Reader only. It can use quota and does not access a case or approve anything. After correcting a failure, assigned Staff uses Messages → Retry Reader on latest saved message, Barrier → Retry Barrier Assistant, or Follow-up → Retry Follow-up Agent. Human review remains separate.

If packages are missing, restart with choice 5. Offline practice needs no key but cannot test one. AUTH means a rejected key; CREDITS/SPEND_LIMIT needs a provider balance/limit check; RATE_LIMIT needs a wait; MODEL/ACCESS needs a supported model/account check; TIMEOUT/CONNECTION needs connection/provider review. Do not share keys in messages or screenshots.
