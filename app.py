# app.py
import streamlit as st
import pandas as pd
import json
from services.llm_service import extract_from_transcript
from services.leadsquared_service import post_activity_by_phone # <-- IMPORT THE NEW SERVICE
import io
import re

# --- Page Configuration ---
st.set_page_config(page_title="Call Log Analyzer & Activity Logger", page_icon="📞", layout="wide")

# --- App Title ---
st.title("📞 Call Log Analyzer & Activity Logger")

# --- Session State Initialization ---
# (Cleaned up session state for the new workflow)
if 'extraction_schema' not in st.session_state:
    st.session_state.extraction_schema = [
        {"name": "call_outcome", "prompt": "Assign an outcome. Choose from: Session Booked, Not Interested, Follow-up Required.", "type": "string"},
        {"name": "call_summary", "prompt": "Provide a one-sentence summary of the call.", "type": "string"}
    ]
if 'activity_event_code' not in st.session_state:
    st.session_state.activity_event_code = 227 # Default example code
if 'activity_json_template' not in st.session_state:
    # A helpful default template to guide the user
    st.session_state.activity_json_template = json.dumps([
        {"SchemaName": "mx_Call_Outcome", "Value": "{{call_outcome}}"},
        {"SchemaName": "mx_Call_Summary", "Value": "{{call_summary}}"},
        {"SchemaName": "mx_Recording_URL", "Value": "{{recording_url}}"}
    ], indent=2)

if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
# ... other session state variables will be managed as needed

# --- Main App Logic ---
if not st.session_state.get('processing_complete', False):
    st.write("Upload a CSV of call logs, define what to extract, and post a structured activity to your CRM.")
    
    col1, col2 = st.columns(2)

    with col1:
        st.header("1. Upload Call Logs")
        uploaded_file = st.file_uploader("Upload a CSV file.", type=['csv'])
        
        st.subheader("Specify Key Columns")
        phone_column = st.text_input("Column name for Phone Number", st.session_state.get("phone_column", "PhoneNumber"))
        transcript_column = st.text_input("Column name for Transcript", st.session_state.get("transcript_column", "Transcript"))
        
        if uploaded_file:
            st.session_state.uploaded_file = uploaded_file
            try:
                df_preview = pd.read_csv(uploaded_file, nrows=5)
                st.success("File uploaded! Preview:")
                st.dataframe(df_preview, use_container_width=True)
                uploaded_file.seek(0)
            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
                st.session_state.uploaded_file = None

    with col2:
        st.header("2. Configure AI Extraction")
        with st.expander("Define Data to Extract from Transcripts", expanded=True):
            # (This section is largely unchanged)
            for i, item in enumerate(st.session_state.extraction_schema):
                # ... UI for schema definition ...
                 row_col1, row_col2 = st.columns([10, 1])
                 with row_col1:
                    st.text_input("Field Name", value=item["name"], key=f"name_{i}")
                    st.selectbox("Data Type", options=["string", "integer", "float"], index=["string", "integer", "float"].index(item.get("type", "string")), key=f"type_{i}")
                    st.text_area("LLM Prompt/Instruction", value=item["prompt"], key=f"prompt_{i}")
                    st.markdown("---")
                 with row_col2:
                    if st.button("❌", key=f"del_schema_{i}", help="Delete field"):
                        st.session_state.extraction_schema.pop(i)
                        st.rerun()
            if st.button("Add Extraction Field"):
                st.session_state.extraction_schema.append({"name": "", "prompt": "", "type": "string"})
                st.rerun()

    st.header("3. Configure Activity Payload")
    st.info("Define the payload for the Leadsquared activity. Use `{{column_name}}` to insert data from your file or from the AI extraction.")
    
    activity_event_code = st.number_input("Activity Event Code", min_value=1, step=1, value=st.session_state.activity_event_code)
    
    activity_json_template = st.text_area(
        "Activity Fields JSON Template", 
        value=st.session_state.activity_json_template, 
        height=300
    )

    st.header("4. Start Processing & Pushing")
    process_button_disabled = st.session_state.get('uploaded_file') is None
    if st.button("Process Calls and Post Activities", type="primary", disabled=process_button_disabled, use_container_width=True):
        # Store latest UI config in session state
        st.session_state.phone_column = phone_column
        st.session_state.transcript_column = transcript_column
        st.session_state.activity_event_code = activity_event_code
        st.session_state.activity_json_template = activity_json_template
        
        # (The rest of the logic is now in the 'else' block for the review step)
        st.session_state.processing_complete = 'pending'
        st.rerun()

# This new state handles the processing and pushing in one flow after confirmation
elif st.session_state.processing_complete == 'pending':
    
    # 1. Update schema from UI
    current_schema = []
    for i in range(len(st.session_state.extraction_schema)):
        current_schema.append({
            "name": st.session_state[f"name_{i}"],
            "prompt": st.session_state[f"prompt_{i}"],
            "type": st.session_state[f"type_{i}"]
        })
    st.session_state.extraction_schema = current_schema

    # 2. Validate JSON template
    try:
        json.loads(st.session_state.activity_json_template)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON in Activity Fields Template: {e}")
        st.session_state.processing_complete = False
        st.button("Go Back and Fix")
        st.stop()

    # 3. Process CSV and Push to LSQ
    with st.spinner('Processing calls and posting activities...'):
        df = pd.read_csv(st.session_state.uploaded_file)
        
        # --- Main Loop ---
        sync_log = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for index, row in df.iterrows():
            status_text.text(f"Processing row {index + 1}/{len(df)}...")
            
            # --- AI Extraction Step ---
            transcript = str(row.get(st.session_state.transcript_column, ""))
            if transcript.strip():
                extracted_data = extract_from_transcript(transcript, st.session_state.extraction_schema)
                if extracted_data:
                    # Merge extracted data into the row for placeholder replacement
                    for key, value in extracted_data.items():
                        row[key] = value
                else:
                    sync_log.append(f"Row {index+2}: ⚠️ AI extraction failed. Skipping activity post.")
                    continue
            
            # --- Payload Generation Step ---
            phone_number = str(row[st.session_state.phone_column]).strip()
            if not phone_number:
                sync_log.append(f"Row {index+2}: ❌ Missing phone number. Cannot post activity.")
                continue

            # Replace placeholders in the JSON template
            populated_template = st.session_state.activity_json_template
            for col_name in row.index:
                placeholder = f"{{{{{col_name}}}}}"
                # Handle NaN/None values gracefully
                value_to_insert = "" if pd.isna(row[col_name]) else str(row[col_name])
                populated_template = populated_template.replace(placeholder, value_to_insert)

            try:
                activity_fields = json.loads(populated_template)
            except json.JSONDecodeError:
                sync_log.append(f"Row {index+2}: ❌ Error parsing JSON template after placeholder replacement. Skipping.")
                continue

            activity_payload = {
                "ActivityEvent": st.session_state.activity_event_code,
                "Fields": activity_fields
            }

            # --- API Call Step ---
            success, message = post_activity_by_phone(phone_number, activity_payload)
            sync_log.append(f"Row {index+2} (Phone: {phone_number}): {'✅' if success else '❌'} {message}")

            progress_bar.progress((index + 1) / len(df))

        st.session_state.sync_log = sync_log
        st.session_state.processing_complete = 'done'
        st.rerun()

elif st.session_state.processing_complete == 'done':
    st.header("✅ Process Complete!")
    st.info("All call logs have been processed and activities have been posted to Leadsquared.")
    
    with st.expander("View Full Sync Log", expanded=True):
        for log_entry in st.session_state.sync_log:
            st.write(log_entry)

    if st.button("Start New Job"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()