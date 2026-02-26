import streamlit as st
import json
import PyPDF2
from db.database import save_user_profile, get_user_profile, init_db, save_preferences, get_preferences
from agent.llm import get_llm

st.set_page_config(page_title="OpenApply Agent Setup", page_icon="📝")

# Ensure database tables exist before querying
init_db()

st.title("Welcome to OpenApply Agent")
st.subheader("Step 1: Upload your Resume")
st.write("Upload your PDF resume. Our local AI will extract and structure your profile into the database.")

existing_profile = get_user_profile()
if existing_profile:
    st.success("✅ Profile is already set up in the database.")
    with st.expander("View current profile"):
        st.json(existing_profile)
    st.write("You can upload a new resume below to overwrite your profile.")

uploaded_file = st.file_uploader("Choose a PDF Resume", type="pdf")

if uploaded_file is not None:
    if st.button("Extract Profile"):
        with st.spinner("Reading PDF..."):
            try:
                reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = ""
                for page in reader.pages:
                    raw_text += page.extract_text() + "\n"
            except Exception as e:
                st.error(f"Error reading PDF: {e}")
                st.stop()
                
        with st.spinner("Extracting structure with AI..."):
            try:
                llm = get_llm(max_tokens=None)  # No cap — full resume JSON can be long
                prompt_text = f"""
                Parse this resume into a JSON object with these exact fields:
                name, email, phone, location, 
                skills (list of strings),
                experiences (list of {{title, company, dates, bullets}}),
                education (list of {{degree, institution, year}}),
                links {{linkedin, github, portfolio}}
                
                Return ONLY valid JSON, nothing else. Do not hallucinate fields.
                
                RESUME TEXT:
                {raw_text}
                """
                
                response = llm.invoke(prompt_text)
                
                # Cleanup markdown output if exists
                clean_json = response.content.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:-3].strip()
                elif clean_json.startswith("```"):
                    clean_json = clean_json[3:-3].strip()
                    
                # Fix trailing string truncation
                if clean_json.endswith(', "bullet'):
                    clean_json += ']}]}'
                elif clean_json.endswith('} ] }, {'):
                    clean_json = clean_json[:-8] + ']}]}'
                
                # Extract first { and last }
                start = clean_json.find('{')
                end = clean_json.rfind('}')
                if start != -1 and end != -1:
                    clean_json = clean_json[start:end+1]
                    
                profile_data = json.loads(clean_json)
                
            except json.JSONDecodeError:
                st.error(f"AI returned invalid JSON: {clean_json}")
                st.stop()
            except Exception as e:
                st.error(f"AI Extraction failed: {e}")
                st.stop()
                
        with st.spinner("Saving to database..."):
            try:
                profile_data["raw_text"] = raw_text # Save raw text for context later
                save_user_profile(profile_data)
                
                skill_count = len(profile_data.get("skills", []))
                exp_count = len(profile_data.get("experiences", []))
                
                st.success(f"Success! Extracted {skill_count} skills and {exp_count} experiences.")
                
                with st.expander("View Parsed Data"):
                    st.json(profile_data)
                    
            except Exception as e:
                st.error(f"Database error: {e}")

st.divider()

st.subheader("Step 2: Job Preferences")
st.write("Configure what kind of jobs you are looking for.")

existing_prefs = get_preferences()
if not existing_prefs:
    existing_prefs = {
        "target_titles": [],
        "locations": [],
        "remote_preference": "Remote Only",
        "salary_floor": None,
        "blocked_companies": [],
        "min_fit_score": 80,
        "daily_run_time": "09:00"
    }

with st.form("job_preferences_form"):
    target_titles = st.text_input(
        "Target Job Titles (comma-separated)",
        value=", ".join(existing_prefs.get("target_titles", [])),
        help="e.g. ML Engineer, AI Engineer, Backend Developer"
    )
    
    locations = st.text_input(
        "Locations (comma-separated)",
        value=", ".join(existing_prefs.get("locations", [])),
        help="e.g. Remote, San Francisco, Bangalore"
    )
    
    # Need to get index of existing preference
    remote_options = ["Remote Only", "Hybrid OK", "Onsite OK"]
    try:
        remote_idx = remote_options.index(existing_prefs.get("remote_preference", "Remote Only"))
    except ValueError:
        remote_idx = 0
        
    remote_preference = st.selectbox(
        "Remote Preference",
        options=remote_options,
        index=remote_idx
    )
    
    salary_floor = st.number_input(
        "Minimum Salary (USD/year, approx)",
        value=existing_prefs.get("salary_floor", 0) or 0,
        step=5000,
        min_value=0
    )
    
    blocked_companies = st.text_area(
        "Blocked Companies (one per line)",
        value="\n".join(existing_prefs.get("blocked_companies", [])),
        help="Do not apply to jobs at these companies."
    )
    
    min_fit_score = st.slider(
        "Minimum Fit Score to Apply",
        min_value=50,
        max_value=95,
        value=existing_prefs.get("min_fit_score", 80),
        help="Jobs scored lower than this will be automatically skipped."
    )
    
    daily_run_time = st.time_input(
        "Daily automated run time",
        value=None # Streamlit will parse from string safely if needed later, but defaults to current time if None. Let's do simple strings below.
    )
    # Streamlit time_input returns a datetime.time object. Let's provide a safe default string.
    
    save_btn = st.form_submit_button("Save Preferences")
    
    if save_btn:
        # Process and clean inputs
        titles_list = [t.strip() for t in target_titles.split(",") if t.strip()]
        locs_list = [l.strip() for l in locations.split(",") if l.strip()]
        blocks_list = [b.strip() for b in blocked_companies.split("\n") if b.strip()]
        
        # Streamlit time input logic
        time_str = daily_run_time.strftime("%H:%M") if daily_run_time else "09:00"
        
        prefs_dict = {
            "target_titles": titles_list,
            "locations": locs_list,
            "remote_preference": remote_preference,
            "salary_floor": salary_floor if salary_floor > 0 else None,
            "blocked_companies": blocks_list,
            "min_fit_score": min_fit_score,
            "daily_run_time": time_str
        }
        
        try:
            save_preferences(prefs_dict)
            st.success("✅ Preferences saved successfully!")
            # Optional: st.rerun() if you want to cleanly reload
        except Exception as e:
            st.error(f"Error saving preferences: {e}")

