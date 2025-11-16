import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)
''')

# Patients table
cursor.execute('''
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    contact TEXT,
    diagnosis TEXT,
    anonymized_name TEXT,
    anonymized_contact TEXT,
    date_added TEXT
)
''')

# Logs table
cursor.execute('''
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    role TEXT,
    action TEXT,
    timestamp TEXT,
    details TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
)
''')

conn.commit()
conn.close()
print("Database and tables created successfully!")
