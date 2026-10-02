import io
import sqlite3
import pandas as pd
import streamlit as st
from werkzeug.security import check_password_hash

import database as db

st.set_page_config(
    page_title="MAFA Attendance",
    page_icon="📋",
    layout="wide",
)

db.initialize_database()

if "admin" not in st.session_state:
    st.session_state.admin = None


# ---------- Shared helpers ----------

def logout():
    st.session_state.admin = None
    st.rerun()


def subject_options():
    subjects = db.get_subjects()
    return {s["name"]: s["id"] for s in subjects}, subjects


# ---------- Public attendance page ----------

def attendance_page():
    st.markdown("## 📋 MAFA Attendance")
    st.write("Select your subject and enter your details.")

    name_to_id, subjects = subject_options()

    if not subjects:
        st.warning("No subjects have been set up yet.")
        return

    with st.form("attendance_form", clear_on_submit=True):
        subject_name = st.selectbox("Subject", list(name_to_id.keys()))
        student_name = st.text_input("Full name")
        school = st.text_input("School")
        submitted = st.form_submit_button("Submit Attendance", type="primary")

        if submitted:
            clean_name = db.clean(student_name)
            clean_school = db.clean(school)

            if len(clean_name) < 2 or len(clean_school) < 2:
                st.error("Please enter your full name and school.")
            else:
                try:
                    db.mark_attendance(
                        clean_name, clean_school, name_to_id[subject_name]
                    )
                    st.success(f"Attendance recorded for {subject_name}.")
                except sqlite3.IntegrityError:
                    st.error(
                        f"{clean_name} is already recorded for "
                        f"{subject_name} today."
                    )

    st.divider()
    st.caption("Your attendance is visible only to authorized administrators.")


# ---------- Admin login ----------

def login_page():
    st.markdown("## 🔐 Administrator Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary")

        if submitted:
            admin = db.get_admin_by_username(db.clean(username))
            if admin and check_password_hash(admin["password_hash"], password):
                st.session_state.admin = dict(admin)
                st.rerun()
            else:
                st.error("Invalid username or password.")


# ---------- Admin dashboard ----------

def dashboard_page():
    admin = st.session_state.admin
    is_super = admin["role"] == "super_admin"

    st.markdown("## 📊 Attendance Dashboard")

    name_to_id, subjects = subject_options()
    id_to_name = {v: k for k, v in name_to_id.items()}

    fixed_subject_id = None if is_super else admin["subject_id"]
    total, today_total = db.get_totals(fixed_subject_id)

    c1, c2 = st.columns(2)
    c1.metric("Total records", total)
    c2.metric("Recorded today", today_total)

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    if is_super:
        subject_filter = col1.selectbox(
            "Subject", ["All"] + list(name_to_id.keys())
        )
        subject_id = None if subject_filter == "All" else name_to_id[subject_filter]
    else:
        subject_id = admin["subject_id"]
        col1.text_input("Subject", value=id_to_name.get(subject_id, ""), disabled=True)

    schools = ["All"] + db.get_schools(subject_id)
    school_filter = col2.selectbox("School", schools)
    school = None if school_filter == "All" else school_filter

    date_filter = col3.date_input("Date", value=None)
    search = col4.text_input("Search by name")

    sort = st.selectbox(
        "Sort by", ["newest", "oldest", "name", "school"]
        + (["subject"] if is_super else [])
    )

    rows = db.get_attendance(subject_id, school, date_filter, db.clean(search), sort)

    st.write(f"**{len(rows)} record(s) found**")

    if rows:
        data = [{
            "Student Name": r["student_name"],
            "School": r["school"],
            "Subject": r["subject_name"],
            "Date": r["attendance_date"],
            "Time": r["attendance_time"],
        } for r in rows]
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            "⬇️ Export to CSV",
            data=csv_buffer.getvalue(),
            file_name="mafa_attendance.csv",
            mime="text/csv",
        )
    else:
        st.info("No attendance records match the current filters.")


# ---------- Subjects management (super admin only) ----------

def subjects_page():
    st.markdown("## 📚 Manage Subjects")

    with st.form("add_subject_form", clear_on_submit=True):
        new_subject = st.text_input("New subject name")
        submitted = st.form_submit_button("Add Subject", type="primary")
        if submitted:
            name = db.clean(new_subject)
            if not name:
                st.error("Please enter a subject name.")
            else:
                try:
                    db.add_subject(name)
                    st.success(f"Added subject: {name}")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That subject already exists.")

    st.divider()
    rows = db.get_subjects_with_counts()
    if rows:
        df = pd.DataFrame([
            {"Subject": r["name"], "Attendance Records": r["count"]}
            for r in rows
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)


# ---------- User management (super admin only) ----------

def users_page():
    st.markdown("## 👤 Manage Administrators")

    name_to_id, subjects = subject_options()

    with st.form("add_user_form", clear_on_submit=True):
        username = st.text_input("Username")
        password = st.text_input("Password (8+ characters)", type="password")
        role = st.selectbox("Role", ["subject_admin", "super_admin"])
        subject_name = None
        if role == "subject_admin":
            subject_name = st.selectbox("Subject", list(name_to_id.keys()))
        submitted = st.form_submit_button("Create Administrator", type="primary")

        if submitted:
            clean_username = db.clean(username)
            if len(password) < 8 or not clean_username:
                st.error("Username and a password of 8+ characters are required.")
            else:
                subject_id = name_to_id[subject_name] if role == "subject_admin" else None
                try:
                    db.create_admin(clean_username, password, role, subject_id)
                    st.success(f"Administrator '{clean_username}' created.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That username already exists.")

    st.divider()
    admins = db.get_all_admins()
    if admins:
        df = pd.DataFrame([
            {
                "Username": a["username"],
                "Role": a["role"],
                "Subject": a["subject_name"] or "—",
            } for a in admins
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)


# ---------- Sidebar navigation ----------

with st.sidebar:
    st.markdown("### MAFA Attendance")

    if st.session_state.admin:
        admin = st.session_state.admin
        st.caption(f"Logged in as **{admin['username']}** ({admin['role']})")

        pages = ["Dashboard"]
        if admin["role"] == "super_admin":
            pages += ["Subjects", "Users"]

        page = st.radio("Navigation", pages)

        st.divider()
        if st.button("Log Out", use_container_width=True):
            logout()
    else:
        page = st.radio("Navigation", ["Submit Attendance", "Admin Login"])

if st.session_state.admin:
    if page == "Dashboard":
        dashboard_page()
    elif page == "Subjects":
        subjects_page()
    elif page == "Users":
        users_page()
else:
    if page == "Submit Attendance":
        attendance_page()
    elif page == "Admin Login":
        login_page()
