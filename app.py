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
        {
            "name": "call_outcome", 
            "prompt": "Analyze the transcript to determine the final outcome. You must select ONLY ONE of the following: Confirmed for Tomorrow’s Workshop, Confirmed for Sunday’s Workshop, Already Attended, Requested Recording, Declined Both, Wrong Number / Ineligible, Voicemail / No Answer.", 
            "type": "string"
        },
        {
            "name": "call_summary", 
            "prompt": "Write a concise call summary, strictly under 120 words, for a human agent to review. The summary must include: 1. The reason they couldn’t attend. 2. What they were hoping to gain. 3. How Rohan responded. 4. The agreed next step.", 
            "type": "string"
        },
        {
            "name": "lead_stage", 
            "prompt": "Based on the call transcript, classify the lead into ONLY ONE of the following stages: Appointment_Booked/Call_Scheduled (Customer explicitly agreed to a call with a Senior Counsellor), Call Again Later (Customer requested a callback or was busy), In Pipeline (Customer is hesitant but agreed to receive more info like a video or case study), Closed Not Interested (Customer explicitly stated they are not interested and to not call back), DNP (Do Not Pursue - Lead is invalid, a wrong number, or abusive), Promised To Pay (Only if the customer has explicitly agreed to make a payment, unlikely for this AI's role).", 
            "type": "string"
        },
        {
            "name": "customer_goal", 
            "prompt": "Identify and extract the participant’s primary goal or motivation for registering for the workshop. List them as a concise, comma-separated string. Examples: Learn AI tools for productivity, Career growth, Explore AI basics, Upskill for future jobs.", 
            "type": "string"
        },
        {
            "name": "objections", 
            "prompt": "Identify all objections or concerns raised by the customer during the call. List them as a concise, comma-separated string. Examples: Financial cost, Time commitment, Relevance to my field, Already have a similar course, Needs to discuss with family.", 
            "type": "string"
        },
        {
            "name": "next_step", 
            "prompt": "Summarize the single clear next action agreed upon at the end of the call in one short sentence. Examples: Customer will join live on Sept 21 at 11 AM, Sending workshop recording via WhatsApp, No further follow-up needed.", 
            "type": "string"
        },
        {
            "name": "rapport_hooks", 
            "prompt": "Extract any personal or professional details mentioned that a human agent could use to build rapport on future outreach. List them as a comma-separated string. Examples: preparing for MBA entrance, works in IT, based in Bangalore, new parent.", 
            "type": "string"
        },
        {
            "name": "call_sentiment", 
            "prompt": "Analyze the overall tone and mood of the participant throughout the call. Classify as Positive (engaged, appreciative), Neutral (polite but reserved), or Negative (irritated, dismissive). Select only one.", 
            "type": "string"
        },
        {
            "name": "ai_performance_score", 
            "prompt": "Rate the AI agent’s performance on a scale of 1 to 10 based on the following rubric: Adherence to Conversation Flow (3 pts), Tone & Empathy (3 pts), Handling Barriers Smoothly (2 pts), Securing a Clear Next Step (2 pts). Provide only the final numeric score.", 
            "type": "integer" # Note: I've set this to integer as it makes sense for a score.
        },
        {
            "name": "talk_to_listen_ratio", 
            "prompt": "Analyze the call audio and calculate Rohan’s speaking time versus the participant’s. Express this as a decimal (e.g., 0.4 means Rohan spoke for 40% of the call).", 
            "type": "float" # Note: I've set this to float for the decimal.
        }
    ]

if 'activity_event_code' not in st.session_state:
    st.session_state.activity_event_code = 227 # Replace with your actual code if different

if 'activity_json_template' not in st.session_state:
    # Pre-configured JSON template based on your provided schema
    st.session_state.activity_json_template = json.dumps([
      {
        "SchemaName": "mx_Custom_2",
        "Value": "{{call_outcome}}"
      },
      {
        "SchemaName": "mx_Custom_4",
        "Value": "",
        "Fields": [
          {
            "SchemaName": "mx_CustomObject_121",
            "Value": "{{call_summary}}"
          }
        ]
      },
      {
        "SchemaName": "mx_Custom_3",
        "Value": "{{recordingUrl}}" # Placeholder from original CSV
      },
      {
        "SchemaName": "mx_Custom_1",
        "Value": "",
        "Fields": [
          {
            "SchemaName": "mx_CustomObject_121",
            "Value": "{{transcript}}" # Placeholder from original CSV
          }
        ]
      },
      {
        "SchemaName": "Status",
        "Value": "Active" # Hardcoded value
      },
      {
        "SchemaName": "mx_Custom_5",
        "Value": "{{lead_stage}}"
      },
      {
        "SchemaName": "mx_Custom_6",
        "Value": "{{customer_goal}}"
      },
      {
        "SchemaName": "mx_Custom_7",
        "Value": "{{objections}}"
      },
      {
        "SchemaName": "mx_Custom_8",
        "Value": "{{next_step}}"
      },
      {
        "SchemaName": "mx_Custom_9",
        "Value": "{{rapport_hooks}}"
      },
      {
        "SchemaName": "mx_Custom_10",
        "Value": "{{call_sentiment}}"
      },
      {
        "SchemaName": "mx_Custom_11",
        "Value": "{{ai_performance_score}}"
      },
      {
        "SchemaName": "mx_Custom_12",
        "Value": "{{talk_to_listen_ratio}}"
      },
      {
        "SchemaName": "mx_Custom_13",
        "Value": "Answered" # Hardcoded value
      },
      {
        "SchemaName": "mx_Custom_14",
        "Value": "Tool Test" # Hardcoded value
      }
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