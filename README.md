# Call Log Analyzer & CRM Updater

This is an internal tool designed to automate the process of analyzing call logs, extracting structured data using a Large Language Model (LLM), and syncing this enriched data to the Leadsquared CRM.

The application is built using Python with the Streamlit framework for the user interface, providing a simple, step-by-step workflow for non-technical users.

## Current Features

-   **CSV Upload**: Accepts a CSV file containing call log data, including phone numbers and call transcripts.
-   **Dynamic Extraction Schema**: Users can define a flexible schema of what data points to extract from each call transcript. For each desired field, the user provides a name, a data type (`string`, `integer`, `float`), and a natural language prompt for the LLM.
-   **LLM-Powered Analysis**: Loops through each call log and uses the OpenRouter API to send the transcript and schema to an LLM, which returns structured JSON data.
-   **Type Coercion**: Automatically attempts to convert the LLM's text output into the user-specified data type (e.g., integer, float), logging errors if conversion fails.
-   **Flexible CRM Mapping**: Users can map any column from the original CSV or any new, AI-extracted field to a specific field in Leadsquared.
-   **Human-in-the-Loop Review**: After processing, the application displays a full table of the original data merged with the new AI-extracted data for user review.
-   **CSV Export**: The enriched data table can be downloaded as a new CSV file.
-   **Direct Lead Updates**: Pushes the enriched data to Leadsquared by first looking up a lead by their phone number and then using the `Lead.Update` API to modify the lead's fields directly.
-   **Web Deployment**: Deployed and accessible via Streamlit Community Cloud, with automatic updates on `git push`.

## Tech Stack

-   **Backend & Frontend**: [Streamlit](https://streamlit.io/)
-   **Data Manipulation**: [Pandas](https://pandas.pydata.org/)
-   **LLM Integration**: [OpenRouter API](https://openrouter.ai/)
-   **CRM Integration**: [Leadsquared API](https://www.leadsquared.com/)
-   **Deployment**: Streamlit Community Cloud

## How to Run Locally

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd call-analyzer-tool
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: .\venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create a `.env` file** in the root directory and add your API credentials:
    ```env
    OPENROUTER_API_KEY="YOUR_OPENROUTER_KEY_HERE"
    LEADSQUARED_ACCESS_KEY="YOUR_LSQ_ACCESS_KEY_HERE"
    LEADSQUARED_SECRET_KEY="YOUR_LSQ_SECRET_KEY_HERE"
    LEADSQUARED_HOST="https://api.leadsquared.com"
    ```

5.  **Run the Streamlit app:**
    ```bash
    streamlit run app.py
    ```

## Upcoming Changes & TODO

The current implementation directly updates a lead's fields (`Lead.Update` API). While functional, this overwrites the lead's state and loses the historical context of each individual call.

The next major version will pivot to a more robust, event-based approach by logging each call as a **Custom Activity** on the lead's timeline. This provides a better audit trail for human agents and prevents valuable information from being overwritten.

### **Action Plan:**

1.  **[Admin Task] Create Custom Activity in Leadsquared:**
    *   Define a new "Custom Activity Set" within the Leadsquared admin panel.
    *   **Proposed Name:** `AI Agent Call` or `internal_ai_call_activity`.
    *   This will generate a unique `ActivityEvent` code that we will need for the API call.
    *   Define the custom fields that this activity will accept. These fields will store the AI-enriched data.
    *   **Proposed Fields:**
        *   `call_outcome` (Text)
        *   `call_summary` (Text Area)
        *   `recording_url` (Text/URL)
        *   `transcript_full` (Text Area)
        *   `call_timestamp` (DateTime)
        *   ...any other extracted fields.

2.  **[Development] Update `leadsquared_service.py`:**
    *   Create a new function, `post_activity_on_lead`, that uses the `ProspectActivity.Create` API endpoint.
    *   This function will first look up the lead by phone number to get the `RelatedProspectId`, similar to the current workflow.
    *   It will then construct the payload for the new activity, including the `ActivityEvent` code and the mapped `Fields`.
    *   The existing `update_lead_by_phone` function will be deprecated or removed to align with the new strategy.

3.  **[Development] Update `app.py` UI:**
    *   Change the "Map Fields to Leadsquared" section to "Map Fields to Call Activity".
    *   The UI will prompt the user to enter the `ActivityEvent` code for the newly created custom activity.
    *   The mapping logic will be updated to generate the `Fields` array for the `ProspectActivity.Create` payload instead of the `Lead.Update` payload.

4.  **[Future Consideration] Implement Smart Lead State Updates:**
    *   After the activity-logging system is in place, we may re-introduce the `Lead.Update` functionality as an optional, advanced feature.
    *   This would involve creating a rules engine or a stage hierarchy to prevent the system from overwriting a high-value lead stage (e.g., "Promised to Pay") with a lower-value one (e.g., "Call Back Later"). This would require an additional API call to first *read* the current lead stage before deciding whether to *write* a new one.

    **JSON Schema Sample (Activity Update):**
    ```json
    [
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
        "Value": "{{recordingUrl}}"
    },
    {
        "SchemaName": "mx_Custom_1",
        "Value": "",
        "Fields": [
        {
            "SchemaName": "mx_CustomObject_121",
            "Value": "{{transcript}}"
        }
        ]
    },
    {
        "SchemaName": "Status",
        "Value": "Active"
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
        "Value": "Answered"
    },
    {
        "SchemaName": "mx_Custom_14",
        "Value": "Tool Test"
    },
    ]
    ```