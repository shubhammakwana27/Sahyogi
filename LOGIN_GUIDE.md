# Accounts and login

Follow USER_MANUAL.pdf pages 2–3 for the current screens. The terminal creates the first coordinator; Accounts creates Patient, Caregiver and Staff users. Only the initial administrator creates Staff and coordinator accounts. Users change temporary passwords at first sign-in. New passwords are 4–18 characters; old longer passwords still work.

Families see Ask your care team on Questions and tasks. For an existing registered task use Your requests → Messages. Coordinators see their work queue. Staff sees only requests assigned to them. Separate browser profiles or signing out is required when trying several roles; normal tabs share login cookies.

Team access → Assign Staff takes the Staff username. Family access takes an existing patient/caregiver username. Creating an account is separate from assigning access. The current owner remains responsible until a named coordinator accepts a handover on Overview.

For recovery, the trusted local operator uses `py -3.11 manage_users.py reset-password` in the app folder and follows hidden prompts. There is no public signup or email/SMS recovery. Keep the terminal open and use http://127.0.0.1:8000/login on the app computer.
