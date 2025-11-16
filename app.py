# app.py 
import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from cryptography.fernet import Fernet
import plotly.express as px
import plotly.graph_objects as go
import time
import os

from utils import (
    verify_password, log_action, get_logs_df, anonymize_all_unanonymized,
    get_all_patients_raw, get_patients_for_doctor, add_patient_admin,
     delete_patient_admin, export_patients_csv,
    apply_data_retention, ensure_db_exists,get_patient_by_id,update_patient_admin,insert_patient, encrypt_field,decrypt_field
)

# This makes the path relative to where app.py is located
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def ensure_db_exists():
    return os.path.exists(DB_PATH)

def create_connection():
    try:
        conn = sqlite3.connect("database.db", check_same_thread=False)
        return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

# ---------------------- Session State ----------------------
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'role' not in st.session_state:
    st.session_state['role'] = None
if 'consent_given' not in st.session_state:
    st.session_state['consent_given'] = False
if 'last_uptime' not in st.session_state:
    st.session_state['last_uptime'] = datetime.now()

# ---------------------- Consent Banner ----------------------
def show_consent_banner():
    # If user already accepted consent, do nothing
    if st.session_state.get("consent_given", False):
        return

    st.warning("To continue using this system, please give your consent for data processing.")

    consent = st.checkbox("I agree to the data processing policy")

    if consent:
        st.session_state["consent_given"] = True
        st.success("Thank you! Consent recorded.")

# ---------------------- Login ----------------------
def login():
    st.title("Hospital Management System Login")
    if not ensure_db_exists():
        st.error("Database file not found. Run database_setup.py and seed_data.py first.")
        return
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, password, role FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and verify_password(password, user[1]):
            st.session_state['logged_in'] = True
            st.session_state['user_id'] = user[0]
            st.session_state['username'] = username
            st.session_state['role'] = user[2]
            log_action(user[0], user[2], "Login", "User logged in")
            # reset consent for demo but keep stored state
            if not st.session_state.get('consent_given', False):
                st.session_state['consent_given'] = False
        else:
            st.error("Invalid username or password")

# ---------------- Logout Prompt ----------------
def show_logout_prompt():
    # Simple rectangle bar
    st.markdown("""
        <div style="
            width: 100%;
            background-color: #2B363E; 
            border: 1px solid #ccc;
            padding: 12px 18px;
            border-radius: 5px;
            margin-bottom: 10px;
        ">
            <span style="font-size:16px; font-weight:500;">
                Are you sure you want to logout?
            </span>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1,1])

    with col1:
        if st.button("Cancel", use_container_width=True, type="secondary"):
            st.session_state["show_logout_prompt"] = False
            st.rerun()

    with col2:
        if st.button("Logout", use_container_width=True, type="primary"):
            st.session_state.update({
                "logged_in": False,
                "user_id": None,
                "username": None,
                "role": None,
                "show_logout_prompt": False
            })
            st.rerun()

# ---------------------- Admin Pages ----------------------
def admin_view_data():
    st.header("View Patient Data (Admin)")
    df = get_all_patients_raw()
    if df.empty:
        st.info("No patient data available.")
        return

    # show table with decrypted columns
    display_df = df[['patient_id', 'name', 'contact', 'diagnosis', 'anonymized_name', 'anonymized_contact', 'date_added']]
    st.dataframe(display_df)

    # allow admin to decrypt a specific record (already decrypted columns shown),
    st.subheader("Decrypt / View Original Record")
    pid = st.number_input("Enter patient_id to view original", min_value=1, value=1, step=1)

    if st.button("Show Original Record"):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE patient_id=?", (pid,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            st.error("Patient ID not found.")
        else:
            rec = dict(zip([column[0] for column in cursor.description], row))

            st.write({
                "patient_id": rec['patient_id'],
                "name (original)": decrypt_field(rec['name']),
                "contact (original)": decrypt_field(rec['contact']),
                "diagnosis": rec['diagnosis'],
                "anonymized_name": rec.get('anonymized_name', ''),
                "anonymized_contact": rec.get('anonymized_contact', ''),
                "date_added": rec['date_added']
            })

        log_action(st.session_state['user_id'], st.session_state['role'], "DecryptView", f"Viewed original patient_id {pid}")


def show_user_management_page():
    st.subheader("User Management")

    tab1, tab2, tab3, tab4 = st.tabs([
        "👁 View Users",
        "➕ Add User",
        "✏️ Edit User",
        "🗑 Delete User"
    ])

    # -----------------------------------------
    # TAB 1 : VIEW USERS
    # -----------------------------------------
    with tab1:
        st.write("### All Users")

        # Example: Fetch users (you will replace with SQL)
        try:
            conn = create_connection()
            df = pd.read_sql("SELECT user_id, username, role FROM users", conn)
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Error fetching users: {e}")

    # -----------------------------------------
    # TAB 2 : ADD USER
    # -----------------------------------------
    with tab2:
        st.subheader("➕ Add New User")

        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["doctor", "admin", "receptionist"])

        if st.button("Add User"):
            if not new_username or not new_password:
                st.error("Username and Password are mandatory.")
            else:
                try:
                    conn = create_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                        (new_username, new_password, new_role)
                    )
                    conn.commit()
                    conn.close()

                    # Log the action
                    log_action(
                        st.session_state['user_id'],
                        st.session_state['role'],
                        "AddUser",
                        f"Added user {new_username} with role {new_role}"
                    )

                    # Show temporary success message
                    msg = st.empty()
                    msg.success(f"User '{new_username}' added successfully!")
                    time.sleep(2)
                    msg.empty()  # remove the message

                    st.rerun()  # refresh page to update view users

                except Exception as e:
                    st.error(f"Error: {e}")

    # -----------------------------------------
    # TAB 3 : EDIT USER
    # -----------------------------------------
    with tab3:
        st.write("### Edit User")

        try:
            conn = create_connection()
            cur = conn.cursor()

            df = pd.read_sql("SELECT * FROM users", conn)
            user_list = df["username"].tolist()

            if user_list:
                user_to_edit = st.selectbox("Select User", user_list)
                new_role_edit = st.selectbox("New Role", ["doctor", "admin", "receptionist"])

                if st.button("Update User"):
                    cur.execute(
                        "UPDATE users SET role=? WHERE username=?",
                        (new_role_edit, user_to_edit)
                    )
                    conn.commit()

                    # Temporary success message
                    msg = st.empty()
                    msg.success(f"User '{user_to_edit}' updated successfully!")
                    time.sleep(2)
                    msg.empty()

                    # Refresh page
                    st.rerun()
            else:
                st.info("No users available to edit.")

            conn.close()

        except Exception as e:
            st.error(f"Error: {e}")

#----------------------------------------DELETION 
    with tab4:
        st.subheader("🗑 Delete User")

        try:
            conn = create_connection()
            cur = conn.cursor()

            # Step 1: Select Role
            role = st.selectbox("Select Role", ["admin", "doctor", "receptionist"])

            # Step 2: Load usernames for that role
            cur.execute("SELECT username FROM users WHERE role=?", (role,))
            users = [row[0] for row in cur.fetchall()]

            if users:
                username_to_delete = st.selectbox("Select Username to Delete", users)

                # Step 3: Admin password verification (persist across reruns)
                if "delete_verified" not in st.session_state:
                    st.session_state["delete_verified"] = False

                admin_pass = st.text_input("Enter Your Admin Password", type="password")

                if st.button("Verify Password"):
                    cur.execute("SELECT password FROM users WHERE user_id=?", (st.session_state['user_id'],))
                    row = cur.fetchone()
                    if row and row[0] == admin_pass:  # Replace with verify_password if hashed
                        st.session_state["delete_verified"] = True
                        st.success("✅ Password verified. You can now confirm deletion.")
                    else:
                        st.session_state["delete_verified"] = False
                        st.error("❌ Invalid password.")

                # Step 4: Confirm deletion
                if st.session_state["delete_verified"] and st.button("Delete User"):
                    cur.execute(
                        "DELETE FROM users WHERE username=? AND role=?",
                        (username_to_delete, role)
                    )
                    conn.commit()

                    # Log action
                    log_action(
                        st.session_state['user_id'],
                        st.session_state['role'],
                        "DeleteUser",
                        f"Deleted user '{username_to_delete}' with role '{role}'"
                    )

                    # Step 5: Temporary success message
                    msg = st.empty()
                    msg.success(f"User '{username_to_delete}' deleted successfully!")
                    time.sleep(2)
                    msg.empty()

                    # Reset verification flag
                    st.session_state["delete_verified"] = False

                    # Step 6: Refresh page
                    st.rerun()

            else:
                st.info(f"No users found with role '{role}'")

            conn.close()

        except Exception as e:
            st.error(f"Error: {e}")


def admin_manage_data():
    st.header("🛠 Manage Patient Data")

    # Tabs for Add / Update / Delete
    tab1, tab2, tab3 = st.tabs(["➕ Add Patient", "✏️ Update Patient", "🗑 Delete Patient"])

    # ============================================================
    #                         ADD PATIENT
    # ============================================================
    with tab1:
        st.subheader("➕ Add New Patient")

        with st.form("add_patient_form"):
            name = st.text_input("Full Name")
            contact = st.text_input("Contact Number")
            diagnosis = st.text_input("Diagnosis")
            submitted = st.form_submit_button("Add Patient")

            if submitted:
                if name and contact:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO patients (name, contact, diagnosis, date_added) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                        (name, contact, diagnosis)
                    )
                    conn.commit()
                    pid = cursor.lastrowid  # <-- this is the new patient_id
                    conn.close()
                    st.success(f"Patient added successfully! Assigned Patient ID: {pid}")

                    log_action(
                        st.session_state['user_id'],
                        st.session_state['role'],
                        "AddPatient",
                        f"Added patient_id {pid}"
                    )
                else:
                    st.error("Name and Contact are mandatory.")
# --------------------UPDATE PATIENT BY ADMIN DASHBOARD ----------------------# 
    with tab2:
        st.subheader("✏️ Update Existing Patient")

        # Step 1: Enter patient ID
        edit_id = st.number_input("Enter Patient ID", min_value=1, step=1, key="edit_id_btn")

        if st.button("Search Patient", key="search_update"):
            df = get_patient_by_id(edit_id)
            if not df:
                st.error("❌ Patient ID not found.")
                st.session_state["edit_found"] = False
            else:
                st.session_state["edit_found"] = True
                st.session_state["edit_patient"] = df  # single patient dict
                st.session_state["password_verified_update"] = False  # reset password verification

        # Step 2: Show anonymized data
        if st.session_state.get("edit_found"):
            patient = st.session_state["edit_patient"]

            st.markdown("### Patient Found (Anonymized View):")
            st.info(f"**Name:** {patient.get('anonymized_name', 'N/A')}  \n"
                    f"**Contact:** {patient.get('anonymized_contact', 'N/A')}  \n"
                    f"**Diagnosis:** {patient.get('diagnosis', 'N/A')}  \n"
                    f"**Date Added:** {patient.get('date_added', 'N/A')}")

            # Step 3: Admin password verification to view decrypted data
            if not st.session_state.get("password_verified_update"):
                st.warning("⚠ To view original data, please verify your admin password.")
                admin_pass = st.text_input("Enter Admin Password", type="password", key="update_admin_pass")
                if st.button("Verify Password", key="verify_update_pass"):
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("SELECT password FROM users WHERE user_id=?", (st.session_state['user_id'],))
                    row = cursor.fetchone()
                    conn.close()
                    if row and verify_password(admin_pass, row[0]):
                        st.session_state["password_verified_update"] = True
                        st.success("✅ Password verified. Original data is now visible.")
                    else:
                        st.error("❌ Invalid password. Cannot show original data.")

            # Step 4: Show decrypted fields if password verified
            if st.session_state.get("password_verified_update"):
                st.subheader("Original Data (Decrypted)")
                st.write(f"- **Name:** {decrypt_field(patient['name'])}")
                st.write(f"- **Contact:** {decrypt_field(patient['contact'])}")
                st.write(f"- **Diagnosis:** {patient.get('diagnosis', 'N/A')}")
                st.write(f"- **Date Added:** {patient.get('date_added', 'N/A')}")

            # Step 5: Editable update fields
            st.subheader("Update Fields (leave blank to keep unchanged)")
            new_name = st.text_input("New Name (optional)")
            new_contact = st.text_input("New Contact (optional)")
            new_diag = st.text_input("New Diagnosis (optional)")

            if st.button("Update Now", key="update_now"):
                name_val = new_name if new_name.strip() else None
                contact_val = new_contact if new_contact.strip() else None
                diag_val = new_diag if new_diag.strip() else None

                success = update_patient_admin(
                    edit_id,
                    name=name_val,
                    contact=contact_val,
                    diagnosis=diag_val,
                )

                if success:
                    st.success("✔ Patient record updated successfully.")
                    log_action(
                        st.session_state['user_id'],
                        st.session_state['role'],
                        "UpdatePatient",
                        f"Updated patient_id {edit_id}"
                    )
                    # Reset session keys after update
                    for key in ["edit_found", "edit_patient", "password_verified_update"]:
                        if key in st.session_state:
                            del st.session_state[key]
                else:
                    st.error("Update failed. Check ID or database.")


# ================= DELETE PATIENT =================
    with tab3:
        st.subheader("🗑 Delete Patient")

        del_id = st.number_input("Enter Patient ID to Delete", min_value=1, step=1, key="del_id_input")

        if st.button("Search Patient", key="search_delete"):
            df = get_patient_by_id(del_id)
            if not df:
                st.error("❌ Patient ID not found.")
                st.session_state["delete_found"] = False
            else:
                st.session_state["delete_found"] = True
                st.session_state["delete_patient"] = df
                st.session_state["password_verified"] = False  # reset
                st.session_state["delete_confirmed"] = False

        # Step 1: Show anonymized patient info if found
        if st.session_state.get("delete_found"):
            patient = st.session_state["delete_patient"]
            st.info("🔒 Patient Found (Anonymized View)")
            st.write(f"- **Anonymized Name:** {patient.get('anonymized_name', 'N/A')}")
            st.write(f"- **Anonymized Contact:** {patient.get('anonymized_contact', 'N/A')}")
            st.write(f"- **Diagnosis:** {patient.get('diagnosis', 'N/A')}")
            st.write(f"- **Date Added:** {patient.get('date_added', 'N/A')}")

            # Step 2: Ask for admin password if not yet verified
            if not st.session_state.get("password_verified"):
                st.warning("⚠ To delete this patient, please verify your admin password.")
                admin_pass = st.text_input("Enter Admin Password", type="password", key="del_admin_pass")
                if st.button("Verify Password", key="verify_del_pass"):
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("SELECT password FROM users WHERE user_id=?", (st.session_state['user_id'],))
                    row = cursor.fetchone()
                    conn.close()
                    if row and verify_password(admin_pass, row[0]):
                        st.session_state["password_verified"] = True
                        st.success("✅ Password verified. You can now confirm deletion.")
                    else:
                        st.error("❌ Invalid password. Cannot proceed with deletion.")

           # Step 3: Show decrypted details and confirm delete if password verified
            if st.session_state.get("password_verified") and not st.session_state.get("delete_confirmed"):
                st.info("💡 Original Data")
                st.write(f"- **Name:** {decrypt_field(patient['name'])}")
                st.write(f"- **Contact:** {decrypt_field(patient['contact'])}")
                st.write(f"- **Diagnosis:** {patient.get('diagnosis', 'N/A')}")
                st.write(f"- **Date Added:** {patient.get('date_added', 'N/A')}")

                if st.button("Confirm Delete Patient", key="confirm_final_delete"):
                    delete_patient_admin(del_id)
                    log_action(
                        st.session_state['user_id'],
                        st.session_state['role'],
                        "DeletePatient",
                        f"Deleted patient_id {del_id}"
                    )
                    # Immediately mark confirmed and clear session state to prevent rerun issue
                    st.session_state["delete_confirmed"] = True
                    st.success(f"✔ Patient ID {del_id} deleted permanently.")

                    # Clear deletion-related session keys right away
                    for key in ["delete_found", "delete_patient", "password_verified", "delete_confirmed"]:
                        if key in st.session_state:
                            del st.session_state[key]

            # Step 4: Show final success
            if st.session_state.get("delete_confirmed"):
                st.success(f"✔ Patient ID {del_id} deleted permanently.")
                # Clear session state related to deletion
                for key in ["delete_found", "delete_patient", "password_verified", "delete_confirmed"]:
                    if key in st.session_state:
                        del st.session_state[key]


def admin_logs_page():
    st.header("📊 Audit & System Analytics Dashboard")
    
    logs_df = get_logs_df()
    patients_df = get_all_patients_raw()

    # If empty logs, show clean message
    if logs_df.empty:
        st.info("No logs found yet.")
        return

    # Convert timestamp to datetime
    logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'], errors='coerce')

    # ============================
    #       TOP INFO CARDS
    # ============================
    st.markdown("""
        <style>
            .kpi-card {
                background: linear-gradient(135deg, #1E88E5, #42A5F5);
                padding: 20px;
                border-radius: 12px;
                text-align: center;
                color: white;
                box-shadow: 0px 4px 10px rgba(0,0,0,0.2);
            }
            .kpi-card-green {
                background: linear-gradient(135deg, #43A047, #66BB6A);
            }
            .kpi-card-orange {
                background: linear-gradient(135deg, #F4511E, #FB8C00);
            }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
            <div class="kpi-card">
                <h3>Total Audit Logs</h3>
                <h1>{len(logs_df)}</h1>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div class="kpi-card kpi-card-green">
                <h3>Total Patients</h3>
                <h1>{len(patients_df)}</h1>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE role='doctor'")
        doctor_count = cur.fetchone()[0]
        conn.close()

        st.markdown(f"""
            <div class="kpi-card kpi-card-orange">
                <h3>Total Doctors</h3>
                <h1>{doctor_count}</h1>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ============================
    #     RAW LOG TABLE
    # ============================
    st.subheader("📙 Complete Audit Log Records")
    st.dataframe(logs_df, use_container_width=True)

    st.markdown("---")

    # =======================================================
    #          PATIENTS ADDED PER DAY (PLOTLY LINE)
    # =======================================================
    st.subheader("📅 Patients Added Per Day")

    if not patients_df.empty:
        patients_df["date_added"] = pd.to_datetime(patients_df["date_added"], errors="coerce")

        patients_per_day = (
            patients_df.groupby(patients_df["date_added"].dt.date)
            .size()
            .reset_index(name="patients")
        )

        fig_patients = px.line(
            patients_per_day,
            x="date_added",
            y="patients",
            markers=True,
            title="Patients Added Per Day",
            color_discrete_sequence=["#43A047"]
        )
        st.plotly_chart(fig_patients, use_container_width=True)
    else:
        st.info("No patient records found.")

    st.markdown("---")

    # =======================================================
    #         MOST COMMON ACTIONS (PLOTLY BAR)
    # =======================================================
    st.subheader("🛡 Most Frequent Actions in System")

    action_counts = logs_df["action"].value_counts().reset_index()
    action_counts.columns = ["action", "count"]

    fig_actions = px.bar(
        action_counts,
        x="action",
        y="count",
        title="Most Common Actions",
        color="count",
        color_continuous_scale=px.colors.sequential.Blues,
    )
    st.plotly_chart(fig_actions, use_container_width=True)

    st.markdown("---")

    # =======================================================
    #         ROLE-BASED ACTIVITY (PLOTLY BAR)
    # =======================================================
    st.subheader("👤 Activity Distribution by User Role")

    role_counts = logs_df["role"].value_counts().reset_index()
    role_counts.columns = ["role", "count"]

    fig_roles = px.pie(
        role_counts,
        names="role",
        values="count",
        title="Role Activity Contribution",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    st.plotly_chart(fig_roles, use_container_width=True)

    st.markdown("---")
    
def admin_settings_page():
    st.header("Admin Settings")
    st.subheader("Data Retention Timer")
    # default retention in days (store in session_state for demo)
    if 'retention_days' not in st.session_state:
        st.session_state['retention_days'] = 365  # default 1 year
    rd = st.number_input("Retention period (days)", min_value=0, max_value=3650, value=st.session_state['retention_days'], step=1)
    if st.button("Apply Retention Now"):
        deleted = apply_data_retention(rd)
        st.success(f"Retention applied. Deleted {deleted} records older than {rd} days.")
        log_action(st.session_state['user_id'], st.session_state['role'], "ApplyRetention", f"{deleted} records removed, retention {rd}d")
    if st.button("Save Retention Setting"):
        st.session_state['retention_days'] = rd
        st.success(f"Retention setting saved to {rd} days.")
    st.markdown("---")
    st.subheader("System & Privacy")
    st.write("System last started at:", st.session_state.get('last_uptime'))
    st.checkbox("Show user consent banner at login (for demo)", value=not st.session_state.get('consent_given', False))
    if st.button("Export logs CSV"):
        fname = "logs_export.csv"
        logs_df = get_logs_df()
        logs_df.to_csv(fname, index=False)
        st.success(f"Logs exported to {fname}")
        log_action(st.session_state['user_id'], st.session_state['role'], "ExportLogs", f"Exported logs to {fname}")

# ---------------------- Doctor & Receptionist ----------------------
def doctor_dashboard_page():
    st.header("Doctor Dashboard")
    df = get_patients_for_doctor()
    if df.empty:
        st.info("No patient data available.")
        return
    st.dataframe(df)
def add_new_patient_page():
    st.subheader("Add New Patient")

    name = st.text_input("Name")
    contact = st.text_input("Contact")
    diagnosis = st.text_input("Diagnosis")
    date_added = st.date_input("Date Added")
    
    if st.button("Add Patient"):
        if not name or not contact or not diagnosis:
            st.warning("Please fill all fields")
            return
        
        # Encrypt sensitive fields

        # Insert into DB
        insert_patient(name, contact, diagnosis, date_added)
        st.success(f"Patient '{name}' added successfully!")
        log_action(st.session_state['user_id'], st.session_state['role'], "AddPatient", f"Added patient {name}")

def edit_existing_patient_page():
    st.subheader("Edit Existing Patient")

    # Step 1: Input Patient ID
    patient_id = st.number_input("Enter Patient ID to Edit", min_value=1, step=1, key="edit_patient_id")

    # Step 2: Search Patient Button
    if st.button("Search Patient"):
        df = get_patient_by_id(patient_id)
        if not df:
            st.warning("Patient ID not found")
            st.session_state['patient_found'] = False
            return

        # Store patient info in session_state to persist across reruns
        st.session_state['patient_found'] = True
        st.session_state['patient_data'] = df[0]

    # Step 3: If patient found, show editable fields
    if st.session_state.get('patient_found'):
        patient = st.session_state['patient_data']

        st.info("Sensitive fields are masked (****). You can edit them but cannot see current value.")

        # Editable fields with placeholder masked
        name = st.text_input("Name", value=st.session_state.get("name_edit", ""), placeholder="****", key="name_edit")
        contact = st.text_input("Contact", value=st.session_state.get("contact_edit", ""), placeholder="****", key="contact_edit")
        diagnosis = st.text_input("Diagnosis", value=st.session_state.get("diagnosis_edit", ""), placeholder="****", key="diagnosis_edit")

        # Step 4: Update Patient
        if st.button("Update Patient"):
            # Use input if typed, else keep original
            name_val = name if name.strip() != "" else decrypt_field(patient['name'])
            contact_val = contact if contact.strip() != "" else decrypt_field(patient['contact'])
            diagnosis_val = diagnosis if diagnosis.strip() != "" else patient['diagnosis']

            # Update DB
            update_patient_admin(patient['patient_id'],
                     name=name_val,
                     contact=contact_val,
                     diagnosis=diagnosis_val)

            st.success(f"Patient ID {patient['patient_id']} updated successfully!")
            log_action(st.session_state['user_id'], st.session_state['role'], "UpdatePatientReceptionist", f"Updated patient_id {patient['patient_id']}")

            # Clear session state for next edit
            for key in ['patient_found', 'patient_data', 'name_edit', 'contact_edit', 'diagnosis_edit']:
                if key in st.session_state:
                    del st.session_state[key]



# -------------------------------
# Function to handle Add New Patient
# -------------------------------
def receptionist_add_patient():
    st.subheader("➕ Add New Patient")
    with st.form("add_patient_form"):
        name = st.text_input("Full Name")
        contact = st.text_input("Contact Number")
        diagnosis = st.text_input("Diagnosis")
        submitted = st.form_submit_button("Add Patient")

        if submitted:
            if name and contact:
                pid = add_patient_admin(name, contact, diagnosis)
                st.success(f"Patient added successfully! Assigned Patient ID: {pid}")
                log_action(
                    st.session_state['user_id'],
                    st.session_state['role'],
                    "AddPatient",
                    f"Added patient_id {pid}"
                )
            else:
                st.error("Name and Contact are mandatory.")


# -------------------------------
# Function to handle Edit Existing Patient
# -------------------------------
def receptionist_edit_patient():
    st.subheader("✏️ Edit Existing Patient")

    # Step 1: Enter Patient ID
    edit_id = st.number_input("Enter Patient ID", min_value=1, step=1, key="edit_id_btn")

    if st.button("Search Patient", key="search_update"):
        df = get_patient_by_id(edit_id)
        if not df:
            st.error("❌ Patient ID not found.")
            st.session_state["edit_found"] = False
        else:
            st.session_state["edit_found"] = True
            st.session_state["edit_patient"] = df

    # Step 2: If found → show anonymized data
    if st.session_state.get("edit_found"):
        patient = st.session_state["edit_patient"]

        # Show only anonymous name/contact, plain diagnosis and date_added
        st.info(f"**Anonymous Name:** {patient['anonymized_name']}  \n"
                f"**Anonymous Contact:** {patient['anonymized_contact']}  \n"
                f"**Diagnosis:** {patient['diagnosis']}  \n"
                f"**Date Added:** {patient['date_added']}")

        st.subheader("Update Fields (leave blank to keep unchanged)")
        new_name = st.text_input("New Name (optional)")
        new_contact = st.text_input("New Contact (optional)")
        new_diag = st.text_input("New Diagnosis (optional)")

        if st.button("Update Now", key="update_now"):
            # Only send values provided; leave blank means no change
            name_val = new_name if new_name.strip() else None
            contact_val = new_contact if new_contact.strip() else None
            diag_val = new_diag if new_diag.strip() else None

            success = update_patient_admin(
                edit_id,
                name=name_val,
                contact=contact_val,
                diagnosis=diag_val
            )

            if success:
                st.success("✔ Patient record updated successfully.")
                log_action(
                    st.session_state['user_id'],
                    st.session_state['role'],
                    "UpdatePatient",
                    f"Updated patient_id {edit_id}"
                )
            else:
                st.error("Update failed. Check ID or database.")


def receptionist_page():
    st.header("Receptionist Dashboard")

    # Sidebar with round radio buttons
    page = st.sidebar.radio(
        "Receptionist Pages",
        ["Add New Patient", "Edit Existing Patient"]
    )

    if page == "Add New Patient":
        receptionist_add_patient()
    elif page == "Edit Existing Patient":
        receptionist_edit_patient()


def show_footer(role=None):
    st.markdown("---")
    st.write(f"🕒 System uptime start: {st.session_state.get('last_uptime')}")

    # Only show total audit logs for admin
    if role == "admin":
        logs_df = get_logs_df()
        st.write(f"📊 Total actions logged: {len(logs_df)}")


# ---------------------- Main ----------------------

# Ensure page config is first
st.set_page_config(page_title="GDPR Mini Hospital", layout="wide")

def main():
    show_consent_banner()
    if not st.session_state.get("consent_given"):
        return

    if not st.session_state.get('logged_in', False):
        login()
        return  # Stop rest of main until login

    # Sidebar menu
    with st.sidebar:
        st.header("Menu")
        st.write(f"User: {st.session_state['username']} ({st.session_state['role']})")
        if st.button("Logout"):
            st.session_state['show_logout_prompt'] = True
    
    # Show logout modal if requested
    if st.session_state.get('show_logout_prompt', False):
        show_logout_prompt()

    
    # Ensure role exists
    role = st.session_state.get('role')
    if not role:
        st.error("❌ User role not found. Please login again.")
        st.stop()
    role = role.lower()

    # Role-based pages
    if role == 'admin':
        page = st.sidebar.radio("Admin Pages", ["View Data", "Manage Patients","Manage Users" ,"Logs", "Settings"])
        if page == "View Data":
            admin_view_data()
            st.markdown("---")
            if st.button("Anonymize All Unanonymized (one-click)"):
                count = anonymize_all_unanonymized()
                log_action(st.session_state['user_id'], st.session_state['role'], "AnonymizeAll", f"Anonymized {count} records")
                st.success(f"Anonymized {count} records.")
        elif page == "Manage Patients":
            admin_manage_data()
        elif page == "Logs":
            admin_logs_page()
        elif page == "Settings":
            admin_settings_page()
        elif page== "Manage Users":
            show_user_management_page()

    elif role == 'doctor':
        doctor_dashboard_page()

    elif role == 'receptionist':
        receptionist_page()

    else:
        st.error("Unknown role")

    # Show footer
    show_footer(role)


if __name__ == "__main__":
    main()
