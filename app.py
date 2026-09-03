import os
import json
import tempfile
from pathlib import Path
import streamlit as st
from pypdf import PdfReader, PdfWriter
from google import genai
from streamlit.runtime.scriptrunner import get_script_run_ctx

# -------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -------------------------------------------------------------
st.set_page_config(
    page_title="AI Exam & Quiz Generator",
    page_icon="🎓",
    layout="wide"
)

# -------------------------------------------------------------
# 2. CONFIGURATION & SECRETS
# -------------------------------------------------------------
# Automatically reads from Streamlit Secrets or Environment
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", os.environ.get("ADMIN_PASSWORD", "mike2025"))

FREE_PAGE_LIMIT = 5
FREE_QUESTION_LIMIT = 5

VIP_DB_FILE = Path("vip_database.json")
SESSIONS_DB_FILE = Path("sessions_database.json")

def load_vip_users():
    if VIP_DB_FILE.exists():
        try:
            with open(VIP_DB_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return {"0910507548", "PREMIUM2025"}
    return {"0910507548", "PREMIUM2025"}

def save_vip_users(users_set):
    with open(VIP_DB_FILE, "w") as f:
        json.dump(list(users_set), f)

def load_device_sessions():
    if SESSIONS_DB_FILE.exists():
        try:
            with open(SESSIONS_DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_device_sessions(sessions_dict):
    with open(SESSIONS_DB_FILE, "w") as f:
        json.dump(sessions_dict, f)

def get_current_session_id():
    ctx = get_script_run_ctx()
    return ctx.session_id if ctx else "default_session"

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# -------------------------------------------------------------
# 3. PAYMENT BANNER
# -------------------------------------------------------------
def show_payment_card():
    st.markdown("""
    ---
    ### 🔒 Unlock Unlimited Pages with Student Premium

    Need to study an entire textbook, lecture slides, or 50+ page handout?
    Upgrade to **Student Premium** for only **500 ETB / Month**!

    * ✅ **Unlimited Pages:** Upload entire chapters and books at once
    * ✅ **Up to 25 Questions:** Complete exam simulation
    * ✅ **Full Explanations:** Step-by-step breakdown for every answer

    #### 💳 Payment Details:
    * **Telebirr:** `0910507548`
    * **Commercial Bank of Ethiopia (CBE):** `1000310040065`

    #### 📩 How to Activate:
    1. Transfer **500 ETB** via Telebirr or CBE.
    2. Send the transaction screenshot + your Phone Number to Telegram: **[@Mikekochito](https://t.me/Mikekochito)**.
    3. Your phone number will be activated as a VIP instantly!
    ---
    """)

# -------------------------------------------------------------
# 4. APP INTERFACE (TABS)
# -------------------------------------------------------------
tab_student, tab_admin = st.tabs(["🎓 Student Quiz Generator", "🔐 Admin Portal"])

# ------------------ TAB 1: STUDENT APP ------------------
with tab_student:
    st.title("🎓 AI Exam & Quiz Generator (PDF to MCQs)")
    st.write("Upload your lecture notes, textbook chapters, or slides to generate practice questions with answer keys and explanations instantly!")

    col1, col2 = st.columns([1, 1.5], gap="large")

    with col1:
        uploaded_file = st.file_uploader("📄 Upload PDF Document", type=["pdf"])
        num_questions = st.slider("Number of Questions", min_value=3, max_value=25, value=5, step=1)
        difficulty = st.radio("Difficulty Level", ["Easy", "Medium", "Hard"], index=1, horizontal=True)

        with st.expander("💎 Registered VIP Member?"):
            user_phone = st.text_input("Enter your registered Phone Number:", placeholder="e.g. 0912345678")

        generate_btn = st.button("🚀 Generate Quiz", type="primary", use_container_width=True)

    with col2:
        if generate_btn:
            if not client:
                st.error("❌ Gemini API key is missing. Please configure GEMINI_API_KEY in settings.")
            elif not uploaded_file:
                st.warning("⚠️ Please upload a PDF file first!")
            else:
                try:
                    with st.spinner("Analyzing document and crafting questions..."):
                        # Read PDF
                        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                        temp_pdf.write(uploaded_file.read())
                        temp_pdf.close()

                        reader = PdfReader(temp_pdf.name)
                        total_pages = len(reader.pages)

                        # VIP & Single-Device Security Check
                        active_vips = load_vip_users()
                        phone_or_code = user_phone.strip() if user_phone else ""
                        is_vip = phone_or_code in active_vips

                        device_blocked = False
                        current_session = get_current_session_id()

                        if is_vip:
                            locked_sessions = load_device_sessions()
                            if phone_or_code in locked_sessions:
                                if locked_sessions[phone_or_code] != current_session:
                                    device_blocked = True
                                    st.error(
                                        f"⛔ **Device Lock Alert: Unauthorized Device**\n\n"
                                        f"Account `{phone_or_code}` is locked to another device.\n\n"
                                        f"To transfer your account to this device, please contact **[@Mikekochito](https://t.me/Mikekochito)** on Telegram to approve your device reset."
                                    )
                            else:
                                # Lock to this device
                                locked_sessions[phone_or_code] = current_session
                                save_device_sessions(locked_sessions)

                        if not device_blocked:
                            # Apply free tier limits
                            actual_num_questions = num_questions
                            if not is_vip and num_questions > FREE_QUESTION_LIMIT:
                                actual_num_questions = FREE_QUESTION_LIMIT

                            file_to_upload = temp_pdf.name
                            if total_pages > FREE_PAGE_LIMIT and not is_vip:
                                writer = PdfWriter()
                                for i in range(FREE_PAGE_LIMIT):
                                    writer.add_page(reader.pages[i])
                                sliced_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                                writer.write(sliced_pdf.name)
                                sliced_pdf.close()
                                file_to_upload = sliced_pdf.name
                                st.info(f"ℹ️ **Free Trial:** Your document has **{total_pages} pages**. Generated {actual_num_questions} questions from **Pages 1 to {FREE_PAGE_LIMIT}** only.")
                                show_payment_card()
                            elif is_vip:
                                st.success(f"💎 **VIP Access Active!** Processed all **{total_pages} pages** with {actual_num_questions} questions.")

                            # Generate with Gemini 3.6 Flash
                            uploaded_doc = client.files.upload(file=file_to_upload)
                            prompt = f"""
You are an expert university professor and exam creator.
Analyze the provided document carefully and generate exactly {actual_num_questions} multiple-choice questions (MCQs).
Difficulty Level: {difficulty}.

Follow this exact structure for each question:

### Question [Number]: [Question Text]
- [ ] A) [Option A]
- [ ] B) [Option B]
- [ ] C) [Option C]
- [ ] D) [Option D]

**Correct Answer:** [Letter]
**Explanation:** [1-2 concise sentences explaining why this is correct based on the text]

---
Make options realistic and clear. Do not refer to "the uploaded text" in the question, phrase them as a real exam.
"""
                            response = client.models.generate_content(
                                model="gemini-3.6-flash",
                                contents=[uploaded_doc, prompt]
                            )

                            st.markdown("## 📝 Generated Quiz")
                            st.markdown(response.text)

                            st.download_button(
                                label="📥 Download Quiz (.txt)",
                                data=response.text,
                                file_name="generated_quiz.txt",
                                mime="text/plain"
                            )

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# ------------------ TAB 2: ADMIN PANEL ------------------
with tab_admin:
    st.header("👑 Admin VIP & Device Control")
    admin_input = st.text_input("Enter Admin Password:", type="password")

    if admin_input == ADMIN_PASSWORD:
        st.success("✅ Logged in as Admin")

        vips = load_vip_users()
        sessions = load_device_sessions()

        st.subheader(f"Active VIP Members ({len(vips)} total)")
        for u in sorted(vips):
            status = "🔒 Locked to a Device" if u in sessions else "🔓 Ready for first device login"
            st.write(f"• **{u}** — *{status}*")

        st.markdown("---")
        st.subheader("Manage VIP Student")
        target_phone = st.text_input("Student Phone Number (e.g. 0912345678):")

        btn_col1, btn_col2, btn_col3 = st.columns(3)

        with btn_col1:
            if st.button("➕ Approve VIP", type="primary", use_container_width=True):
                if target_phone.strip():
                    vips.add(target_phone.strip())
                    save_vip_users(vips)
                    st.success(f"Approved {target_phone.strip()} as VIP!")
                    st.rerun()

        with btn_col2:
            if st.button("🔄 Reset Device Lock", use_container_width=True):
                if target_phone.strip() in sessions:
                    del sessions[target_phone.strip()]
                    save_device_sessions(sessions)
                    st.success(f"Device lock cleared for {target_phone.strip()}! Student can now log in on a new device.")
                    st.rerun()
                else:
                    st.info(f"{target_phone.strip()} does not have an active device lock.")

        with btn_col3:
            if st.button("❌ Revoke VIP", use_container_width=True):
                phone = target_phone.strip()
                if phone in vips:
                    vips.remove(phone)
                    save_vip_users(vips)
                    if phone in sessions:
                        del sessions[phone]
                        save_device_sessions(sessions)
                    st.warning(f"Revoked VIP for {phone}.")
                    st.rerun()
