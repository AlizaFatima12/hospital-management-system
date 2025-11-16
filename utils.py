# utils.py
import sqlite3
from datetime import datetime, timedelta
import hashlib
from cryptography.fernet import Fernet
import pandas as pd
import os
from cryptography.fernet import Fernet
import os
key = b'l6uwdkD_JVmYy-JOODtYb_lzwA7quvhbEEgKfJ8chhk='
fernet = Fernet(key)
def encrypt_field(value):
    if value is None:
        return None
    return fernet.encrypt(value.encode()).decode()  

def decrypt_field(field_value):
    """Try to decrypt a field; return original only if it's truly not decryptable."""
    if not field_value:
        return ""
    try:
        return fernet.decrypt(field_value.encode()).decode()
    except Exception:
        return field_value

def is_encrypted(value):
    if not value:
        return False
    try:
        Fernet(key).decrypt(value.encode())
        return True
    except Exception:
        return False

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def ensure_db_exists():
    return os.path.exists(DB_PATH)
# -------------------- Password helpers --------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(input_password: str, stored_password: str) -> bool:
    """
    Accepts either plain stored passwords (legacy) or hashed hex strings.
    If stored_password looks like a SHA256 hex (64 chars hex) compare hashed.
    Otherwise compare plain text (legacy behavior).
    """
    if stored_password is None:
        return False
    try:
        if len(stored_password) == 64 and all(c in '0123456789abcdef' for c in stored_password.lower()):
            return hash_password(input_password) == stored_password
        else:
            return input_password == stored_password
    except Exception:
        return False

# -------------------- Logging --------------------
def log_action(user_id, role, action, details=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO logs (user_id, role, action, timestamp, details)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, role, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), details))
    conn.commit()
    conn.close()

def get_logs_df():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM logs ORDER BY timestamp DESC", conn)
    conn.close()
    return df

# -------------------- Anonymization & Encryption --------------------
def anonymize_all_unanonymized():
    """
    Mask and encrypt only patients that haven't been anonymized (anonymized_name is NULL).
    Stores encrypted original in name/contact and masked in anonymized_ fields.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id, name, contact FROM patients WHERE anonymized_name IS NULL OR anonymized_name = ''")
    patients = cursor.fetchall()

    for p in patients:
        pid, name, contact = p
        name = name or ""
        contact = contact or ""
        anon_name = f"ANON_{pid + 1000}"
        anon_contact = f"XXX-XXX-{contact[-4:]}" if contact else "XXX-XXX-XXXX"
        if name and not is_encrypted(name):
            encrypted_name = fernet.encrypt(name.encode()).decode()
        else:
            encrypted_name = name

        if contact and not is_encrypted(contact):
            encrypted_contact = fernet.encrypt(contact.encode()).decode()
        else:
            encrypted_contact = contact

        cursor.execute('''
            UPDATE patients
            SET anonymized_name = ?, anonymized_contact = ?, name = ?, contact = ?
            WHERE patient_id = ?
        ''', (anon_name, anon_contact, encrypted_name, encrypted_contact, pid))
    conn.commit()
    conn.close()
    return len(patients)  


# -------------------- Patient CRUD --------------------
def get_all_patients_raw(): 
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM patients ORDER BY patient_id", conn)
    conn.close()
    if not df.empty:
        df['name_decrypted'] = df['name'].apply(lambda x: decrypt_field(x))
        df['contact_decrypted'] = df['contact'].apply(lambda x: decrypt_field(x) if x else "")
    return df

def get_patients_for_doctor(): 
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT patient_id, anonymized_name, anonymized_contact, diagnosis, date_added FROM patients ORDER BY patient_id", conn)
    conn.close()
    return df
def add_patient_admin(name, contact, diagnosis):
    return insert_patient(name, contact, diagnosis, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def delete_patient_admin(patient_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
    conn.commit()
    conn.close()
    return True
def insert_patient(name, contact, diagnosis, date_added):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO patients (name, contact, diagnosis, date_added)
        VALUES (?, ?, ?, ?)
    """, (name, contact, diagnosis, date_added))
    conn.commit()
    conn.close()


def get_patient_by_id(patient_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    columns = [column[0] for column in cursor.description]
    patient = dict(zip(columns, row))
    conn.close()

    try:
        patient["name_decrypted"] = decrypt_field(patient["name"])
    except:
        patient["name_decrypted"] = patient["name"]

    try:
        patient["contact_decrypted"] = decrypt_field(patient["contact"])
    except:
        patient["contact_decrypted"] = patient["contact"]

    return patient

def update_patient_admin(patient_id, name=None, contact=None, diagnosis=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, contact, diagnosis FROM patients WHERE patient_id=?", (patient_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    existing_name, existing_contact, existing_diag = row

    encrypted_name = encrypt_field(name) if name and not is_encrypted(name) else existing_name

    encrypted_contact = encrypt_field(contact) if contact and not is_encrypted(contact) else existing_contact

    diag_val = diagnosis if diagnosis else existing_diag

    cursor.execute("""
        UPDATE patients
        SET name=?, contact=?, diagnosis=?
        WHERE patient_id=?
    """, (encrypted_name, encrypted_contact, diag_val, patient_id))

    conn.commit()
    conn.close()
    return True

# -------------------- CSV export --------------------
def export_patients_csv(filepath="patients_backup.csv"):
    df = get_all_patients_raw()
    if not df.empty:
        export_df = df[['patient_id', 'name_decrypted', 'contact_decrypted', 'diagnosis', 'anonymized_name', 'anonymized_contact', 'date_added']]
        export_df = export_df.rename(columns={'name_decrypted':'name', 'contact_decrypted':'contact'})
        export_df.to_csv(filepath, index=False)
    else:
        export_df = pd.DataFrame(columns=['patient_id','name','contact','diagnosis','anonymized_name','anonymized_contact','date_added'])
        export_df.to_csv(filepath, index=False)
    return filepath


# -------------------- Data retention --------------------
def apply_data_retention(retention_days):
    """
    Delete patient records older than retention_days (based on date_added).
    Returns number of deleted records.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT COUNT(*) FROM patients WHERE date_added < ?", (cutoff,))
    count = cursor.fetchone()[0]
    cursor.execute("DELETE FROM patients WHERE date_added < ?", (cutoff,))
    conn.commit()
    conn.close()
    return count

# -------------------- Helper --------------------
def ensure_db_exists():
    return os.path.exists(DB_PATH)
