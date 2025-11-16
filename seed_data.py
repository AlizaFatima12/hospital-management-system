import sqlite3
from datetime import datetime

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Users: Admin, Doctor, Receptionist
users = [
    ('admin', 'admin123', 'admin'),
    ('Dr. Bob', 'doc123', 'doctor'),
    ('Alice_recep', 'rec123', 'receptionist')
]

for u in users:
    try:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", u)
    except sqlite3.IntegrityError:
        pass

# Sample Patients
patients = [
    ('John Doe', '123-456-7890', 'Flu', None, None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ('Jane Smith', '987-654-3210', 'Cold', None, None, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
]

for p in patients:
    try:
        cursor.execute('''
            INSERT INTO patients (name, contact, diagnosis, anonymized_name, anonymized_contact, date_added)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', p)
    except sqlite3.IntegrityError:
        pass

conn.commit()
conn.close()
print("Seed data inserted successfully!")
