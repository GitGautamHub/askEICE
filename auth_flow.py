import streamlit as st
import re
import random
import datetime
import yagmail
import time
import bcrypt
import psycopg2

from config import DB_CONFIG, EMAIL_CONFIG, ORGANIZATIONS, AVAILABLE_ROLES, AVAILABLE_ORGANIZATIONS
from utils.auth import create_user, authenticate_user
# from utils.auth import user_exists, update_password
from utils.validation import is_valid_email, check_password_strength, get_password_strength_score

from auth_helpers import (
    generate_otp, send_otp_email, store_otp, verify_otp, enhanced_create_user, user_exists, update_password
)


import streamlit as st
from utils.auth import get_user_info # Assuming you have a function to fetch user details

# --- Helper functions for welcome messages (from your previous code) ---

def render_admin_welcome(user_info):
    st.title(f"Welcome {user_info['first_name']} (Admin) 👋")
    st.write(
        """
        As an *administrator*, you can manage the organization's knowledge base here.  

        • Use *Upload Documents* to add or update resources for your team.  
        
        • The system will automatically update the shared knowledge base so users can benefit right away.  

        • You can also start a *New Chat* to test the knowledge base after updates.  
        """
    )


def render_user_welcome(user_info):
    st.title(f"Welcome {user_info['first_name']} to AskEICE 👋")
    st.write(
        """
        You can now start interacting with the knowledge base by clicking on *New Chat*.  

        • Use the *Previous Chats* menu in the sidebar to manage and revisit your earlier conversations.  

        • Explore AskEICE and make the most out of it 🚀
        """
    )

# --- The main render_welcome_page function ---
def render_welcome_page():
    # Check if user info is available in session state
    if 'user' not in st.session_state:
        st.warning("Please log in to continue.")
        # Optionally, redirect to the login page
        st.session_state.page = "login"
        st.rerun()
        return # Exit the function

    user_info = get_user_info(st.session_state['user'])
    
    # Render welcome message based on user role
    if user_info and user_info.get("role") == "admin":
        render_admin_welcome(user_info)

    elif user_info:
        render_user_welcome(user_info)
    else:
        # Handle case where user_info is not found
        st.error("User information not found. Please log in again.")
        st.session_state.page = "login"
        st.rerun()


def get_password_strength_indicator(password):
    """
    Checks password strength and returns an indicator and a list of missing requirements.
    
    Args:
        password (str): The password to check.
        
    Returns:
        tuple: A tuple containing:
            - str: A label indicating the strength ("Very Weak", "Strong", etc.).
            - str: A formatted string of missing requirements.
    """
    if not password:
        return "No password", "Enter a password"
    
    score = 0
    missing = []
    
    # Check for length
    if len(password) >= 8:
        score += 1
    else:
        missing.append("8+ characters")
        
    # Check for lowercase letters
    if any(c.islower() for c in password):
        score += 1
    else:
        missing.append("lowercase letter")
        
    # Check for uppercase letters
    if any(c.isupper() for c in password):
        score += 1
    else:
        missing.append("uppercase letter")
        
    # Check for digits
    if any(c.isdigit() for c in password):
        score += 1
    else:
        missing.append("number")
        
    # Check for special characters
    special_chars = '!@#$%^&*()-_=+[{]}\\|;:",<.>/?'
    if any(c in special_chars for c in password):
        score += 1
    else:
        missing.append("special character")
        
    strength_labels = ["Very Weak", "Weak", "Medium", "Strong", "Very Strong", "Excellent"]
    strength_level = strength_labels[min(score, 5)]
    
    missing_text = ", ".join(missing) if missing else "All requirements met!"
    
    return strength_level, missing_text

def render_auth_flow():
    st.markdown("""
    <style>
        .container-box {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            width: 100%;
            margin: 0 auto;
        }
        .main-title {
            font-size: 2.5em;
            font-weight: bold;
            text-align: center;
            color: #1a73e8;
            margin-bottom: 5px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 20px;
        }
        .tabs-container {
            margin-top: 20px;
            max-width: 450px; 
            margin: 0 auto;
        }
    </style>
    """, unsafe_allow_html=True)

    # st.set_page_config is now in main.py
    st.markdown("<h1 class='main-title'>askEICE</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>AI-Powered Doc Analyzer</p>", unsafe_allow_html=True)

    # Using columns to center the content
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # st.markdown("<div class='container-box'>", unsafe_allow_html=True)
        login_tab, signup_tab, forgot_tab = st.tabs([" Login", " Sign Up", " Forgot Password"])

        with login_tab:
            st.subheader("Login to your account")
            with st.form(key='login_form'):
                username = st.text_input("Email", key="login_username", placeholder="Enter your email")
                password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
                submit_button = st.form_submit_button(label='Login', use_container_width=True)
                
                if submit_button:
                    if not username or not password:
                        st.warning(" Please fill in both fields.")
                    else:
                        ok, msg = authenticate_user(username, password)
                        if ok:
                            st.session_state["user"] = username
                            st.session_state["page"] = "upload"
                            st.rerun()
                        else:
                            st.error(msg)
                            print(f"Error during login: {msg}")
        
        with signup_tab:
            st.subheader("Create a new account")

            # Input fields directly (no st.form)
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("First Name *", key="signup_first_name", placeholder="Enter your first name")
            with col2:
                last_name = st.text_input("Last Name *", key="signup_last_name", placeholder="Enter your last name")

            new_username = st.text_input("Email Address *", key="signup_username", placeholder="Enter your email (e.g., user@gmail.com)")

            # Live email validation
            if new_username:
                if not is_valid_email(new_username):
                    st.error(" Please enter a valid email address (e.g., user@mail.com)")

            organization = st.selectbox("Select Organization *", list(ORGANIZATIONS.keys()), key="signup_org_select")

            # Role handling
            if "admin" in ORGANIZATIONS[organization]["roles"]:
                role = st.radio("Select Role *", ORGANIZATIONS[organization]["roles"], key="signup_role_radio")
            else:
                role = "user"
                st.info("Role is automatically set to 'user' for this organization.")

            new_password = st.text_input("Password *", type="password", key="signup_password", placeholder="Create a strong password")
            confirm_password = st.text_input("Confirm Password *", type="password", key="confirm_password", placeholder="Re-enter your password")

            # Live password validation
            if new_password:
                score = get_password_strength_score(new_password)
                labels = ["Very Weak", "Weak", "Medium", "Strong", "Very Strong", "Excellent"]
                colors = ["#ff4b4b", "#ff944b", "#ffe14b", "#a3ff4b", "#4bffb3", "#4bbcff"]

                st.markdown(f"Password Strength: <b style='color:{colors[score]}'>{labels[score]}</b>", unsafe_allow_html=True)
                st.progress(score/5)

                _, missing_text = get_password_strength_indicator(new_password)
                if missing_text != "All requirements met!":
                    st.markdown(f"<small style='color:red;'>Missing: {missing_text}</small>", unsafe_allow_html=True)
                else:
                    st.markdown("<small style='color:green;'>All requirements met!</small>", unsafe_allow_html=True)

            # Confirm password live check
            if new_password and confirm_password:
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    st.success("Passwords match")

            # Actual Submit Button (outside form for live updates)
            if st.button("Create Account", use_container_width=True):
                if not new_username or not new_password or not first_name or not confirm_password:
                    st.warning(" Please fill in all required fields (marked with *).")
                elif new_password != confirm_password:
                    st.error(" Passwords do not match")
                elif get_password_strength_score(new_password) < 3:
                    st.error(" Password is too weak. Please choose a stronger password.")
                else:
                    ok, msg = enhanced_create_user(new_username, new_password, first_name, last_name, role, organization)
                    if ok:
                        st.success(msg + " Please log in now.")
                        st.session_state["page"] = "login"
                        st.rerun()
                    else:
                        st.error(msg)
                        print(f"Error during signup: {msg}")
        
        with forgot_tab:
            st.subheader("Reset Your Password")
            
            if "forgot_password_step" not in st.session_state: st.session_state.forgot_password_step = "email"
            if "forgot_password_email" not in st.session_state: st.session_state.forgot_password_email = ""
            
            if st.session_state.forgot_password_step == "email":
                with st.form(key='forgot_email_form'):
                    st.write("Enter your email address to receive an OTP.")
                    forgot_email = st.text_input("Email Address", key="forgot_email", placeholder="Enter your registered email")
                    submit_button = st.form_submit_button("Send OTP", use_container_width=True)
                    
                    if submit_button:
                        if not forgot_email: st.warning("Please enter your email address.")
                        elif not is_valid_email(forgot_email): st.error("Please enter a valid email address.")
                        elif not user_exists(forgot_email.strip().lower()): st.error("No account found with this email address.")
                        else:
                            otp = generate_otp()
                            with st.spinner("Sending OTP..."):
                                email_sent, email_msg = send_otp_email(forgot_email, otp)
                                if email_sent:
                                    store_success, store_msg = store_otp(forgot_email.strip().lower(), otp)
                                    if store_success:
                                        st.session_state.forgot_password_email = forgot_email.strip().lower()
                                        st.session_state.forgot_password_step = "verify_otp"
                                        st.success("OTP sent to your email! Please check your inbox.")
                                        st.rerun()
                                    else: st.error(f"Failed to store OTP: {store_msg}")
                                else: st.error(f" {email_msg}")

            elif st.session_state.forgot_password_step == "verify_otp":
                with st.form(key='verify_otp_form'):
                    st.write(f"An OTP has been sent to **{st.session_state.forgot_password_email}**")
                    st.write("Enter the 5-digit OTP to verify your identity.")
                    entered_otp = st.text_input("Enter OTP", key="entered_otp", placeholder="Enter 5-digit OTP", max_chars=5)
                    
                    col_reset, col_back = st.columns(2)
                    with col_reset: submit_button_verify = st.form_submit_button("Verify OTP", use_container_width=True)
                    with col_back: submit_button_back = st.form_submit_button("Back to Email", use_container_width=True, type="secondary")
                    
                    if submit_button_verify:
                        if not entered_otp: st.warning("Please enter the OTP.")
                        elif len(entered_otp) != 5 or not entered_otp.isdigit(): st.error("Please enter a valid 5-digit OTP.")
                        else:
                            otp_valid, otp_msg = verify_otp(st.session_state.forgot_password_email, entered_otp)
                            if otp_valid:
                                st.session_state.forgot_password_step = "reset_password"
                                st.success("OTP verified! You can now set a new password.")
                                st.rerun()
                            else: st.error(f" {otp_msg}")
                    if submit_button_back:
                        st.session_state.forgot_password_step = "email"
                        st.session_state.forgot_password_email = ""
                        st.rerun()
                
                if st.button("Resend OTP", type="secondary"):
                    otp = generate_otp()
                    with st.spinner("Resending OTP..."):
                        email_sent, email_msg = send_otp_email(st.session_state.forgot_password_email, otp)
                        if email_sent:
                            store_success, store_msg = store_otp(st.session_state.forgot_password_email, otp)
                            if store_success: st.success("New OTP sent to your email!")
                            else: st.error(f"Failed to store OTP: {store_msg}")
                        else: st.error(f" {email_msg}")
            
            elif st.session_state.forgot_password_step == "reset_password":
                with st.form(key='reset_password_form'):
                    st.write("**Set Your New Password**")
                    st.write(f"Creating new password for: **{st.session_state.forgot_password_email}**")
                    new_password = st.text_input("New Password *", type="password", key="new_password", placeholder="Enter your new password")
                    confirm_new_password = st.text_input("Confirm New Password *", type="password", key="confirm_new_password", placeholder="Re-enter your new password")
                    
                    if new_password and confirm_new_password and new_password != confirm_new_password: st.error(" Passwords do not match")
                    elif new_password and confirm_new_password: st.success(" Passwords match")
                    
                    if new_password:
                        strength_score = get_password_strength_score(new_password)
                        strength_labels = ["Very Weak", "Weak", "Medium", "Strong", "Very Strong", "Excellent"]
                        strength_colors = ["#ff4b4b", "#ff944b", "#ffe14b", "#a3ff4b", "#4bffb3", "#4bbcff"]
                        st.markdown(f"<div style='margin-bottom:8px;'>Password Strength: <b style='color:{strength_colors[strength_score]}'>{strength_labels[strength_score]}</b></div>", unsafe_allow_html=True)
                        st.progress(strength_score/5)
                        st.markdown("<small>Password must be at least 8 characters, include uppercase, lowercase, digit, and special character.</small>", unsafe_allow_html=True)
                    
                    col_update, col_cancel = st.columns(2)
                    with col_update: submit_button_update = st.form_submit_button("Update Password", use_container_width=True)
                    with col_cancel: submit_button_cancel = st.form_submit_button("Cancel", use_container_width=True, type="secondary")
                    
                    if submit_button_update:
                        if not new_password or not confirm_new_password: st.warning("Please fill in both password fields.")
                        elif new_password != confirm_new_password: st.error("Passwords do not match")
                        elif get_password_strength_score(new_password) < 3: st.error("Password is too weak. Please choose a stronger password.")
                        else:
                            is_strong, strength_msg = check_password_strength(new_password)
                            if not is_strong: st.error(strength_msg)
                            else:
                                update_success, update_msg = update_password(st.session_state.forgot_password_email, new_password)
                                if update_success:
                                    st.success("Password updated successfully! You can now login with your new password.")
                                    st.session_state.forgot_password_step = "email"
                                    st.session_state.forgot_password_email = ""
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                else: st.error(f" {update_msg}")
                    if submit_button_cancel:
                        st.session_state.forgot_password_step = "email"
                        st.session_state.forgot_password_email = ""
                        st.rerun()

