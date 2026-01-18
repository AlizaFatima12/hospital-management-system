# Hospital Management System 

## Overview
This repository implements a lightweight Hospital Management System (HMS) as a single-process Streamlit application backed by a local SQLite database. It is intended as a reference/demo system that demonstrates role-based UI workflows, audit logging, data anonymization, and simple data-protection primitives.

The implementation focuses on operational workflows for three user roles: `admin`, `doctor`, and `receptionist`. The codebase is Python-only and organized as a small monolith with core logic in:
- `app.py` — Streamlit UI, session management, role-based pages and workflows.
- `utils.py` — persistence helpers, cryptography helpers (Fernet), password helpers, anonymization, CSV export, data-retention and logging.
- `seed_data.py` — seed script that populates example users and patients into `database.db`.

## Key capabilities 
- Streamlit-based user interface and UX flows:
  - Login screen with session-based authentication (Streamlit `st.session_state`).
  - Consent banner (GDPR-style) shown at first run.
  - Role-driven navigation and pages:
    - Admin: View Data, Manage Patients (Add / Update / Delete), Manage Users (View / Add / Edit / Delete), Audit Logs Dashboard, Settings (Retention + CSV export).
    - Doctor: Read-only doctor dashboard that lists anonymized patients.
    - Receptionist: Add New Patient and Edit Existing Patient workflows.
  - Forms, tabbed UIs and modal-like confirmation flows implemented with Streamlit primitives.
  - Dashboard visualizations: KPI cards and charts (Plotly / Matplotlib used for rendering).
- Persistence and data model:
  - SQLite single-file database `database.db` (path resolved relative to project).
  - Tables used/referenced by the code: `users`, `patients`, `logs`.
  - Common patient fields accessed in code:
    - patients: `patient_id`, `name`, `contact`, `diagnosis`, `anonymized_name`, `anonymized_contact`, `date_added`
    - users: `user_id`, `username`, `password`, `role`
    - logs: `user_id`, `role`, `action`, `timestamp`, `details`
- Data protection and privacy features:
  - Field-level encryption using `cryptography.fernet.Fernet` (encrypt/decrypt helpers in `utils.py`).
  - Anonymization routine to replace identifiable patient name/contact with masked/anonymized values and store encrypted originals (`anonymize_all_unanonymized()`).
  - Audit logging: `log_action()` records user actions to `logs` table; logs surfaced in Admin Logs UI and exportable to CSV.
  - Data retention mechanism: `apply_data_retention(retention_days)` deletes patient records older than the configured window.
  - CSV export utilities for patients and logs.
- Authentication and user administration:
  - Login with username/password (authentication performed against `users` table).
  - Password helper utilities:
    - `hash_password()` implements SHA-256 hashing.
    - `verify_password()` supports hashed (SHA-256) and legacy plaintext comparison (logic present in `utils.py`).
  - Admin UI for adding, editing, and deleting user accounts.
- Operational utilities:
  - `seed_data.py` — example data seeding (creates an `admin`, a `doctor` and a `receptionist`, and two sample patients).
  - Utilities for exporting CSV backups and basic search / CRUD helper functions for patients.
- Libraries used in the implementation:
  - streamlit, pandas, plotly (plotly.express / plotly.graph_objects), matplotlib, cryptography (Fernet), sqlite3 (stdlib), hashlib, datetime, os, time.

## Tech stack (explicit, minimal)
- Language: Python 3.x
- UI framework: Streamlit
- Persistence: SQLite (`sqlite3`)
- Data processing / tables: pandas
- Visualization: Plotly, Matplotlib
- Cryptography: cryptography.Fernet
- Packaging / runtime: run as a Streamlit app (single process)

## Architectural notes
- Monolithic single-process Streamlit application: UI and business logic are colocated in `app.py`. Utilities and persistence helpers live in `utils.py`.
- Session management uses Streamlit's `st.session_state`. Login status, user id, username, role, consent flag and other transient UI flags are persisted in session state.
- Data-protection model:
  - Sensitive fields are encrypted with Fernet before being persisted; anonymized fields are used for most UI views.
  - Audit logs are stored in the DB and surfaced to admins.

## Database schema (inferred from code usage)
The code references and manipulates the following columns (representative, not a DDL dump):
- users: `user_id`, `username`, `password`, `role`
- patients: `patient_id`, `name`, `contact`, `diagnosis`, `anonymized_name`, `anonymized_contact`, `date_added`
- logs: `user_id`, `role`, `action`, `timestamp`, `details`

## Security & compliance observations (code-level)
- cryptography:
  - A Fernet key value is present in `utils.py` as a hard-coded byte string. This is a critical secret and must be rotated/replaced and removed from source before any sensitive data handling in production.
- Password handling:
  - SHA-256 hashing is used via `hash_password()`; `verify_password()` accepts SHA-256 hex digests and falls back to plaintext comparison for legacy entries.
  - For production-grade password storage, use adaptive algorithms (bcrypt, argon2) and salted hashes.
- Data storage:
  - The app stores PHI in a local SQLite file. Production deployments handling real patient data must satisfy legal/regulatory requirements (e.g., HIPAA) through appropriate administrative, technical and physical controls.
- Access control:
  - Role-based UI gating exists (admin / doctor / receptionist) but is implemented within the Streamlit process — do not assume multi-tenant or network-hardened protections by default.

## Quickstart — local development (exact commands)
1. Clone:
   git clone https://github.com/AlizaFatima12/hospital-management-system.git
   cd hospital-management-system

2. Virtualenv:
   python -m venv .venv
   source .venv/bin/activate    # macOS / Linux
   .venv\Scripts\activate       # Windows (PowerShell)

3. Install runtime dependencies:
   pip install streamlit pandas plotly matplotlib cryptography

4. Seed sample data (optional; creates `database.db` entries):
   python seed_data.py

   Note: `seed_data.py` inserts convenience test users and patients. Inspect and change before using with real data.

5. Run the app:
   streamlit run app.py

6. Default development credentials (from `seed_data.py`):
   - Admin: username `admin` / password `admin123`
   - Doctor: username `Dr. Bob` / password `doc123`
   - Receptionist: username `Alice_recep` / password `rec123`
   These are example credentials and must be replaced/disabled for production use.

7. Working:
- Login with seeded credentials (or add a user using admin workflow).
- Admin pages:
  - View Data — view anonymized patient data and reveal original data only after password verification.
  - Manage Patients — Add / Update / Delete patient records.
  - Manage Users — Create, edit role, or delete users.
  - Logs — interactive audit log table and charts (exportable to CSV).
  - Settings — set retention policy and export logs.
- Doctor / Receptionist pages provide the relevant narrower workflows (doctor sees anonymized patient list; receptionist can add and edit patients).
