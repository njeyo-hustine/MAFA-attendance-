# MAFA Attendance (Streamlit version)

A Streamlit + SQLite rebuild of the MAFA attendance system.

## Run locally
pip install -r requirements.txt
streamlit run app.py

## Default login
Username: mafa_admin
Password: change-this-password

Change these before real use by editing DEFAULT_SUPER_ADMIN_USERNAME
and DEFAULT_SUPER_ADMIN_PASSWORD in database.py, then delete
mafa_attendance.db so it regenerates with the new credentials.

## Roles
- super_admin: sees all subjects, can manage subjects and administrators
- subject_admin: only sees attendance for their assigned subject

## Deploying on Streamlit Community Cloud
1. Push app.py, database.py, requirements.txt to a public GitHub repo
2. On share.streamlit.io, deploy with:
   - Branch: main
   - Main file path: app.py
