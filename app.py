import streamlit as st
import pandas as pd
from datetime import datetime
import io

# Securely attempt to import the Supabase backend framework
try:
    from supabase import create_client, Client
except ImportError:
    st.error("Missing architecture packages. Please run: pip install supabase")
    st.stop()

# 1. Initialize Configuration and Global API Connections
st.set_page_config(page_title="Enterprise Automation Hub", page_icon="📈", layout="wide")

# Safe retrieval of environment secrets
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "").strip()

@st.cache_resource
def init_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Internal Connection Error: {str(e)}")
        return None

supabase = init_supabase()

if supabase is None:
    st.error("🚨 Critical Error: Could not connect to the database. Please verify your Streamlit Secrets.")
    st.stop()

if "user" not in st.session_state:
    st.session_state.user = None

# =====================================================================
# INTERFACE ROUTING: AUTHENTICATION GATEWAY
# =====================================================================
if not st.session_state.user:
    st.title("🔒 Enterprise Automation Hub — Secure Portal")
    st.write("Login or create an account instantly to access your isolated automation dashboard.")
    
    auth_tab1, auth_tab2 = st.tabs(["Sign In", "Register New Account"])
    
    with auth_tab1:
        login_email = st.text_input("Account Email", key="login_em")
        login_password = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Access Dashboard"):
            try:
                res = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                st.session_state.user = res.user
                st.success("Authentication successful!")
                st.rerun()
            except Exception as ex:
                st.error(f"Authentication Failed: {str(ex)}")
                
    with auth_tab2:
        reg_email = st.text_input("Email Address", key="reg_em")
        reg_password = st.text_input("Secure Password", type="password", key="reg_pwd")
        if st.button("Create Free Account"):
            try:
                res = supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                st.success("Account created! Please check your email for confirmation link or sign in.")
            except Exception as ex:
                st.error(f"Registration Failed: {str(ex)}")

# =====================================================================
# INTERFACE ROUTING: MAIN AUTOMATION DASHBOARD
# =====================================================================
else:
    st.sidebar.title("🤖 Automation Control")
    st.sidebar.info(f"Logged in as:\n{st.session_state.user.email}")
    if st.sidebar.button("Logout / Disconnect"):
        st.session_state.user = None
        st.rerun()

    st.title("📈 Enterprise Automation Dashboard")
    st.write("Manage client operations and background workflow automations efficiently.")

    tab_view, tab_add = st.tabs(["View Automations", "🚀 Trigger New Automation"])

    with tab_view:
        st.subheader("Active Pipelines")
        try:
            # Force inclusion of the current session's auth header
            supabase.postgrest.auth(st.session_state.user.access_token)
            response = supabase.table("client_automation").select("*").execute()
            data = response.data

            if len(data) == 0:
                st.info("No active automations found. Head over to the trigger tab to start one!")
            else:
                df = pd.DataFrame(data)
                df_visual = df.rename(columns={
                    "client_name": "Client Name",
                    "client_email": "Client Email",
                    "status": "Pipeline Status",
                    "created_at": "Triggered At"
                })
                st.dataframe(df_visual[["id", "Client Name", "Client Email", "Pipeline Status", "Triggered At"]], use_container_width=True)
                
                st.markdown("---")
                st.subheader("🔧 Update Pipeline State")
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    client_options = {f"{row['client_name']} ({row['client_email']})": row['id'] for row in data}
                    selected_client_label = st.selectbox("Select Target Pipeline", options=list(client_options.keys()))
                    target_id = client_options[selected_client_label]
                    
                with col2:
                    new_status = st.selectbox("Assign New Status", options=["Pending Actions", "In Progress", "Completed", "Failed"])
                    
                with col3:
                    st.write(" ") 
                    st.write(" ") 
                    if st.button("Update Status", use_container_width=True):
                        try:
                            # Attach auth header explicitly before making changes
                            supabase.postgrest.auth(st.session_state.user.access_token)
                            supabase.table("client_automation").update({"status": new_status}).eq("id", target_id).eq("user_id", st.session_state.user.id).execute()
                            st.success(f"Pipeline updated to '{new_status}'!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Status update failed: {str(e)}")
                        
        except Exception as e:
            st.error(f"Failed to fetch real-time pipelines: {str(e)}")

    with tab_add:
        st.subheader("Configure New Operations Client")
        with st.form("automation_form", clear_on_submit=True):
            c_name = st.text_input("Client Full Name")
            c_email = st.text_input("Client Contact Email")
            raw_notes = st.text_area("Automation Scope / Raw Metadata")
            
            submit_btn = st.form_submit_button("Inject into Pipeline")
            
            if submit_btn:
                if not c_name or not c_email:
                    st.error("Client Name and Email are mandatory fields.")
                else:
                    try:
                        # Extract the true string representation of the active User ID
                        active_uid = str(st.session_state.user.id)
                        
                        payload = {
                            "user_id": active_uid,
                            "client_name": c_name,
                            "client_email": c_email,
                            "raw_data": raw_notes,
                            "status": "Pending Actions"
                        }
                        
                        # CRITICAL FIX: Explicitly bind the logged-in user's access token to the database connection headers
                        supabase.postgrest.auth(st.session_state.user.access_token)
                        
                        supabase.table("client_automation").insert(payload).execute()
                        st.success(f"Successfully deployed automation pipeline for {c_name}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Database insertion failed: {str(e)}")