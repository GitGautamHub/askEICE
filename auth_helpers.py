# auth_helpers.py
import streamlit as st
import re
import random
import datetime
import yagmail
import time
import bcrypt
import psycopg2

from config import DB_CONFIG, EMAIL_CONFIG
# from auth_flow import user_exists, update_password
from utils.validation import is_valid_email, check_password_strength, get_password_strength_score
from config import ORGANIZATIONS


# --- PostgreSQL Connection Helper ---
# @st.cache_resource
def get_pg_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- Create User ---
def create_user(username, password, first_name, last_name, role, organization):
    username = username.strip().lower()
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, password, first_name, last_name, role, organization) VALUES (%s, %s, %s, %s, %s, %s)",
                    (username, hashed_pw, first_name, last_name, role, organization)
                )
                conn.commit()
        return True, "Account created successfully!"
    except psycopg2.IntegrityError:
        return False, "Username already exists."
    except Exception as e:
        return False, f"DB Error: {str(e)}"
    
# --- Authenticate User ---
def authenticate_user(username, password):
    username = username.strip().lower()
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password FROM users WHERE username = %s", (username,))
                row = cur.fetchone()
                if row and bcrypt.checkpw(password.encode(), row[0].tobytes()):
                    return True, "Login successful!"
                elif row:
                    return False, "Incorrect password."
                else:
                    return False, "User not found."
    except Exception as e:
        return False, f"DB Error: {str(e)}"

def user_exists(email):
    """Check if user exists in database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM users WHERE username = %s", (email,))
            return cur.fetchone() is not None
    except Exception as e:
        print(f"Error checking user existence: {e}")
        return False
    


def update_password(email, new_password):
    """Update user's password in database"""
    try:
        hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password = %s WHERE username = %s", (hashed_pw, email))
            conn.commit()
            if cur.rowcount > 0: return True, "Password updated successfully"
            else: return False, "User not found"
    except Exception as e:
        return False, f"Database error: {str(e)}"



def generate_otp():
    """Generate a 5-digit OTP"""
    return str(random.randint(10000, 99999))

def send_otp_email(email, otp):
    """Send OTP via email"""
    try:
        yag = yagmail.SMTP(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        subject = "Password Reset OTP - askEICE"
        body = f"Hello,\n\nYour OTP is: {otp}\n\nThis OTP will expire in 10 minutes.\n\nIf you didn't request this, please ignore this email.\n\nBest regards,\naskEICE Team"
        yag.send(email, subject, body)
        return True, "OTP sent successfully"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"
    

def store_otp(email, otp):
    """Store OTP in database with expiration"""
    try:
        if 'otp_storage' not in st.session_state:
            st.session_state.otp_storage = {}
        expires_at = datetime.datetime.now() + datetime.timedelta(minutes=10)
        st.session_state.otp_storage[email] = {'otp': otp, 'expires_at': expires_at}
        return True, "OTP stored successfully"
    except Exception as e:
        return False, f"Storage error: {str(e)}"
    

def verify_otp(email, otp):
    """Verify OTP and check if it's not expired"""
    try:
        if 'otp_storage' not in st.session_state or email not in st.session_state.otp_storage:
            return False, "No OTP found for this email"
        stored_data = st.session_state.otp_storage[email]
        if datetime.datetime.now() > stored_data['expires_at']:
            del st.session_state.otp_storage[email]
            return False, "OTP has expired"
        if stored_data['otp'] == otp:
            del st.session_state.otp_storage[email]
            return True, "OTP verified successfully"
        else:
            return False, "Invalid OTP"
    except Exception as e:
        return False, f"Verification error: {str(e)}"



def enhanced_create_user(username, password, first_name, last_name, role, organization):
    """
    Enhanced user creation with email domain validation,
    and role/organization assignment.
    """
    username = username.strip().lower()
    first_name = first_name.strip()
    
    if not is_valid_email(username):
        return False, "Please enter a valid email address."

    # New Logic: Check email domain for role and organization
    domain = username.split('@')[1]
    if domain not in ORGANIZATIONS[organization]["domains"]:
        return False, f"The email domain '{domain}' does not match the selected organization."

    # Baaki ka validation same rahega
    if not is_valid_email(username): return False, "Please enter a valid email address."
    if not first_name: return False, "First name is required"
    is_strong, strength_msg = check_password_strength(password)
    if not is_strong: return False, strength_msg

    return create_user(username, password, first_name, last_name, role, organization)


    # Call the create_user function with the new fields
    return create_user(username, password, first_name, last_name, role, organization)
