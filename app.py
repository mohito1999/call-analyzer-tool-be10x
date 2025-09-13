# app.py
import streamlit as st
import pandas as pd
import json
from services.llm_service import extract_from_transcript
from services.leadsquared_service import update_lead_by_phone # <-- IMPORT THE LSQ SERVICE
import io

# --- Page Configuration ---
st.set_page_config(
    page_title="Call Log Analyzer & CRM Updater",
    page_icon="📞",
    layout="wide"
)

# --- App Title ---
st.title("📞 Call Log Analyzer & CRM Updater")

# --- Session State Initialization ---
if 'extraction_schema' not in st.session_state:
    st.session_state.extraction_schema = [
        {"name": "customer_sentiment", "prompt": "Analyze transcript and return customer sentiment. Pick only from: positive, neutral, negative.", "type": "string"},
        {"name": "lead_stage", "prompt": "Assign a lead stage. Choose from: in-pipeline, closed, session booked, not interested.", "type": "string"}
    ]
if 'lsq_mapping' not in st.session_state:
    st.session_state.lsq_mapping = [{"source_field": "customer_sentiment", "lsq_field": "mx_Custom_1"}]
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'processed_df' not in st.session_state:
    st.session_state.processed_df = None
if 'error_log' not in st.session_state:
    st.session_state.error_log = []

# --- Main App Logic ---
if not st.session_state.processing_complete:
    st.write("Upload a CSV of call logs, define what to extract, and update your CRM.")
    
    # --- UI LAYOUT FOR SETUP ---
    col1, col2 = st.columns(2)

    with col1:
        st.header("1. Upload Call Logs")
        uploaded_file = st.file_uploader("Upload a CSV file with call transcripts.", type=['csv'])
        
        st.subheader("Specify Key Columns")
        st.info("Tell the app which columns in your CSV contain the transcript and phone number.")
        phone_column = st.text_input("Column name for Phone Number", "PhoneNumber")
        transcript_column = st.text_input("Column name for Transcript", "Transcript")
        
        if uploaded_file:
            st.session_state.uploaded_file = uploaded_file
            try:
                df_preview = pd.read_csv(uploaded_file, nrows=5)
                st.success("File uploaded! Here's a preview:")
                st.dataframe(df_preview, use_container_width=True)
                uploaded_file.seek(0)
            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
                st.session_state.uploaded_file = None

    with col2:
        st.header("2. Configure Extraction & CRM Mapping")

        with st.expander("Define Data to Extract", expanded=True):
            for i, item in enumerate(st.session_state.extraction_schema):
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

        with st.expander("Map Fields to Leadsquared", expanded=True):
            st.info("Map source fields to Leadsquared's 'Schema Name'.")
            for i, item in enumerate(st.session_state.lsq_mapping):
                row_col1, row_col2 = st.columns([10, 1])
                with row_col1:
                    st.text_input("Source Field Name", value=item["source_field"], key=f"source_{i}")
                    st.text_input("Leadsquared Field Name", value=item["lsq_field"], key=f"lsq_{i}")
                    st.markdown("---")
                with row_col2:
                     if st.button("❌", key=f"del_map_{i}", help="Delete mapping"):
                        st.session_state.lsq_mapping.pop(i)
                        st.rerun()

            if st.button("Add Mapping Field"):
                st.session_state.lsq_mapping.append({"source_field": "", "lsq_field": ""})
                st.rerun()
    
    st.header("3. Start Processing")
    process_button_disabled = st.session_state.uploaded_file is None
    if st.button("Process Call Logs", type="primary", disabled=process_button_disabled, use_container_width=True):
        with st.spinner('Processing calls... This may take a few minutes.'):
            # 1. Update schema from UI
            current_schema = []
            for i in range(len(st.session_state.extraction_schema)):
                current_schema.append({
                    "name": st.session_state[f"name_{i}"],
                    "prompt": st.session_state[f"prompt_{i}"],
                    "type": st.session_state[f"type_{i}"]
                })
            st.session_state.extraction_schema = current_schema

            # 2. Update mapping from UI
            current_mapping = []
            for i in range(len(st.session_state.lsq_mapping)):
                current_mapping.append({
                    "source_field": st.session_state[f"source_{i}"],
                    "lsq_field": st.session_state[f"lsq_{i}"]
                })
            st.session_state.lsq_mapping = current_mapping

            # 3. Load the full CSV
            try:
                df = pd.read_csv(st.session_state.uploaded_file)
                st.session_state.phone_column = phone_column # Store for later use
                if phone_column not in df.columns or transcript_column not in df.columns:
                    st.error(f"Error: The specified columns '{phone_column}' or '{transcript_column}' were not found in the CSV. Please check the column names.")
                    st.stop()
            except Exception as e:
                st.error(f"Failed to load the full CSV file. Error: {e}")
                st.stop()

            # 4. Process each row
            new_columns = {item['name']: [] for item in current_schema}
            error_log = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for index, row in df.iterrows():
                transcript = str(row.get(transcript_column, ""))
                if not transcript.strip():
                    for item in current_schema: new_columns[item['name']].append(None)
                    continue

                extracted_data = extract_from_transcript(transcript, current_schema)
                if extracted_data:
                    for item in current_schema:
                        field_name = item['name']
                        value = extracted_data.get(field_name)
                        if value is not None:
                            try:
                                if item['type'] == 'integer':
                                    clean_value = ''.join(filter(str.isdigit, str(value)))
                                    value = int(clean_value) if clean_value else None
                                elif item['type'] == 'float':
                                    clean_value = ''.join(filter(lambda c: c.isdigit() or c == '.', str(value)))
                                    value = float(clean_value) if clean_value else None
                            except (ValueError, TypeError):
                                error_log.append(f"Row {index+2}: Could not convert '{value}' to '{item['type']}' for '{field_name}'.")
                                value = None
                        new_columns[field_name].append(value)
                else:
                    error_log.append(f"Row {index+2}: Failed to get LLM response for transcript.")
                    for item in current_schema: new_columns[item['name']].append(None)
                
                progress_percentage = (index + 1) / len(df)
                progress_bar.progress(progress_percentage)
                status_text.text(f"Processing row {index + 1} of {len(df)}")
            
            for col_name, data in new_columns.items():
                df[col_name] = data
            
            st.session_state.processed_df = df
            st.session_state.error_log = error_log
            st.session_state.processing_complete = True
            st.rerun()

else:
    # --- UI FOR REVIEW & PUSH ---
    st.header("Step 4: Review Processed Data")

    if st.session_state.error_log:
        st.warning("Some issues were found during processing:")
        with st.expander("View Error Log"):
            for error in st.session_state.error_log:
                st.write(f"- {error}")

    st.dataframe(st.session_state.processed_df, use_container_width=True)

    @st.cache_data
    def convert_df_to_csv(df):
        return df.to_csv(index=False).encode('utf-8')

    csv_data = convert_df_to_csv(st.session_state.processed_df)
    st.download_button("📥 Download Processed Data as CSV", csv_data, "processed_call_logs.csv", "text/csv")

    st.header("Step 5: Push to Leadsquared")
    st.info("Review the data above. If it looks correct, click the button below to update Leadsquared.")

    # --- FINAL PUSH BUTTON AND LOGIC ---
    if st.button("🚀 Push All Data to Leadsquared", type="primary", use_container_width=True):
        df_to_push = st.session_state.processed_df
        lsq_mapping = st.session_state.lsq_mapping
        phone_col = st.session_state.phone_column
        
        # Check if phone column exists
        if phone_col not in df_to_push.columns:
            st.error(f"The specified phone column '{phone_col}' does not exist in the processed data. Cannot push to Leadsquared.")
            st.stop()

        sync_errors = []
        success_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        with st.spinner("Syncing with Leadsquared..."):
            for index, row in df_to_push.iterrows():
                phone_number = str(row[phone_col]).strip()
                if not phone_number:
                    sync_errors.append(f"Row {index+2}: Missing phone number.")
                    continue

                # Build the payload for this specific lead
                payload = []
                for mapping_item in lsq_mapping:
                    source_field = mapping_item["source_field"]
                    lsq_field = mapping_item["lsq_field"]
                    
                    if source_field in row and pd.notna(row[source_field]):
                        payload.append({
                            "Attribute": lsq_field,
                            "Value": str(row[source_field]) # Ensure value is a string for the API
                        })

                if not payload:
                    sync_errors.append(f"Row {index+2} (Phone: {phone_number}): No data to update after mapping.")
                    continue

                # Call the service
                success, message = update_lead_by_phone(phone_number, payload)

                if success:
                    success_count += 1
                else:
                    sync_errors.append(f"Row {index+2} (Phone: {phone_number}): {message}")
                
                # Update progress
                progress_percentage = (index + 1) / len(df_to_push)
                progress_bar.progress(progress_percentage)
                status_text.text(f"Syncing lead {index + 1} of {len(df_to_push)}")

        # Display final results
        st.header("Sync Complete!")
        st.success(f"✅ Successfully updated {success_count} of {len(df_to_push)} leads.")
        
        if sync_errors:
            st.error(" কিছু ত্রুটি ঘটেছে")
            with st.expander("View Sync Errors"):
                for error in sync_errors:
                    st.write(f"- {error}")

    if st.button("Start Over"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()