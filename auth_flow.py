import streamlit as st
import re
import random
import datetime
import yagmail
import time
import bcrypt
import psycopg2

from config import DB_CONFIG, EMAIL_CONFIG
from utils.auth import create_user, authenticate_user
# from utils.auth import load_chat, create_new_chat, save_current_chat, logout_user

# --- Helper Functions from the original code ---
def is_valid_email(email):
    """Check if email format is valid"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def check_password_strength(password):
    """Check password strength and return validation result"""
    if len(password) < 8:
        return False, " Password must be at least 8 characters long"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    if not has_upper:
        return False, " Password must contain at least one uppercase letter"
    if not has_lower:
        return False, " Password must contain at least one lowercase letter"
    if not has_digit:
        return False, " Password must contain at least one number"
    if not has_special:
        return False, " Password must contain at least one special character (!@#$%^&*)"
    
    return True, " Password strength is good!"

def get_password_strength_score(password):
    """Get password strength score from 0-5"""
    if not password:
        return 0
    
    score = 0
    if len(password) >= 8:
        score += 1
    if any(c.islower() for c in password):
        score += 1
    if any(c.isupper() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(c in '!@#$%^&*()-_=+[{]}\\|;:",<.>/?' for c in password):
        score += 1
    
    return score

def generate_otp():
    """Generate a 5-digit OTP"""
    return str(random.randint(10000, 99999))

def send_otp_email(email, otp):
    """Send OTP via email"""
    try:
        yag = yagmail.SMTP(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        subject = "Password Reset OTP - askEICE"
        body = f"""
        Hello,
        Your OTP is: {otp}
        This OTP will expire in 10 minutes.
        If you didn't request this, please ignore this email.
        Best regards,
        askEICE Team
        """
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
        st.session_state.otp_storage[email] = {
            'otp': otp,
            'expires_at': expires_at
        }
        return True, "OTP stored successfully"
    except Exception as e:
        return False, f"Storage error: {str(e)}"

def verify_otp(email, otp):
    """Verify OTP and check if it's not expired"""
    try:
        if 'otp_storage' not in st.session_state or email not in st.session_state.otp_storage:
            return False, "No OTP found for this email"
        
        stored_data = st.session_state.otp_storage[email]
        stored_otp = stored_data['otp']
        expires_at = stored_data['expires_at']
        
        if datetime.datetime.now() > expires_at:
            del st.session_state.otp_storage[email]
            return False, "OTP has expired"
        
        if stored_otp == otp:
            del st.session_state.otp_storage[email]
            return True, "OTP verified successfully"
        else:
            return False, "Invalid OTP"
            
    except Exception as e:
        return False, f"Verification error: {str(e)}"

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
            
            if cur.rowcount > 0:
                return True, "Password updated successfully"
            else:
                return False, "User not found"
                
    except Exception as e:
        return False, f"Database error: {str(e)}"

def enhanced_create_user(username, password, first_name, last_name=""):
    """Enhanced user creation with validation"""
    username = username.strip().lower()
    first_name = first_name.strip()
    last_name = last_name.strip()
    
    if not is_valid_email(username):
        return False, " Please enter a valid email address (e.g., user@gmail.com)"
    
    if not first_name:
        return False, " First name is required"
    
    is_strong, strength_msg = check_password_strength(password)
    if not is_strong:
        return False, strength_msg
    
    return create_user(username, password)

# --- Main Rendering Function for Auth Flow ---
def render_auth_flow():
    # st.set_page_config(page_title="askEice - Login", layout="centered")

    st.markdown("""
    <style>
        .container-box {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 450px;
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

    st.markdown("<h1 class='main-title'>askEICE</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>AI-Powered Document Question Answering</p>", unsafe_allow_html=True)

    # --- Main container to hold the tabs, this replaces the columns ---
    # st.markdown("<div class='tabs-container'>", unsafe_allow_html=True)
    # login_tab, signup_tab, forgot_tab = st.tabs([" Login", " Sign Up", " Forgot Password"])
    

     # Using columns to center the content
    
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
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
                        ok, result = authenticate_user(username, password)
                        if ok:
                            # result is role from auth.py
                            st.session_state["user"] = username
                            st.session_state["role"] = result
                            st.session_state["page"] = "upload"
                            st.rerun()
                        else:
                            st.error(result)
        


        with signup_tab:
            st.subheader("Create a new account")
            with st.form(key='signup_form'):
                col_name1, col_name2 = st.columns(2)
                with col_name1:
                    first_name = st.text_input("First Name *", key="signup_first_name", placeholder="Enter your first name")
                with col_name2:
                    last_name = st.text_input("Last Name (Optional)", key="signup_last_name", placeholder="Enter your last name")

                new_username = st.text_input("Email Address *", key="signup_username", placeholder="Enter your email (e.g., user@gmail.com)")

                # NEW: Role dropdown
                role = st.selectbox("Account Role *", ["user", "admin"], key="signup_role")

                if new_username and not is_valid_email(new_username):
                    st.error(" Please enter a valid email address (e.g., user@gmail.com)")
                elif new_username and is_valid_email(new_username):
                    st.success(" Valid email format")

                new_password = st.text_input("Password *", type="password", key="signup_password", placeholder="Create a strong password")
                confirm_password = st.text_input("Confirm Password *", type="password", key="confirm_password", placeholder="Re-enter your password")

                if new_password and confirm_password and        new_password != confirm_password:
                    st.error(" Passwords do not match")
                elif new_password and confirm_password:
                    st.success(" Passwords match")

                if new_password:
                    strength_score = get_password_strength_score(new_password)
                    strength_labels = ["Very Weak", "Weak", "Medium", "Strong", "Very Strong", "Excellent"]
                    strength_colors = ["#ff4b4b", "#ff944b", "#ffe14b", "#a3ff4b", "#4bffb3", "#4bbcff"]
                    st.markdown(f"<div style='margin-bottom:8px;'>Password Strength: <b style='color:{strength_colors[strength_score]}'>{strength_labels[strength_score]}</b></div>", unsafe_allow_html=True)
                    st.progress(strength_score/5)
                    st.markdown("<small>Password must be at least 8 characters, include uppercase, lowercase, digit, and special character.</small>", unsafe_allow_html=True)

                submit_button = st.form_submit_button(label="Create Account", use_container_width=True)
                if submit_button:
                    if not new_username or not new_password or not first_name or not confirm_password or not role:
                        st.warning(" Please fill in all required fields (marked with *).")
                    elif not is_valid_email(new_username):
                        st.error(" Please enter a valid email address")
                    elif new_password != confirm_password:
                        st.error(" Passwords do not match")
                    elif get_password_strength_score(new_password) < 3:
                        st.error(" Password is too weak. Please choose a stronger password.")
                    else:
                        ok, msg = create_user(new_username, new_password, role=role)  # Pass role
                        if ok:
                            st.success(msg + " Please log in now.")
                        else:
                            st.error(msg)

        
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
    