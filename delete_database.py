import os

db_path = "D:\\hospital_project\\database.db"
if os.path.exists(db_path):
    os.remove(db_path)
    print("Database deleted.")
else:
    print("Database file does not exist.")
