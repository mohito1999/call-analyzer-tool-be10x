# services/leadsquared_service.py

import os
import requests
import time
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

LEADSQUARED_ACCESS_KEY = os.getenv("LEADSQUARED_ACCESS_KEY")
LEADSQUARED_SECRET_KEY = os.getenv("LEADSQUARED_SECRET_KEY")
LEADSQUARED_HOST = os.getenv("LEADSQUARED_HOST")

def get_lead_by_phone(phone_number: str):
    """
    Retrieves a lead's ProspectID from Leadsquared using their phone number.
    (This function remains unchanged as it's still needed)
    """
    # ... (code for this function is unchanged, but included for completeness)
    if not all([LEADSQUARED_ACCESS_KEY, LEADSQUARED_SECRET_KEY, LEADSQUARED_HOST]):
        message = "ERROR: Leadsquared credentials are not fully configured."
        print(message)
        return None, message

    url = f"{LEADSQUARED_HOST}/v2/LeadManagement.svc/RetrieveLeadByPhoneNumber"
    params = {
        'accessKey': LEADSQUARED_ACCESS_KEY,
        'secretKey': LEADSQUARED_SECRET_KEY,
        'phone': phone_number
    }
    
    time.sleep(0.2)
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()

        response_data = response.json()
        
        if not response_data:
            message = f"No lead found with phone number: {phone_number}"
            return None, message
        
        lead_data = response_data[0]
        lead_id = lead_data.get("ProspectID")

        if lead_id:
            return lead_id, f"Successfully found ProspectID: {lead_id}"
        else:
            return None, "Lead found, but ProspectID was missing in the response."

    except requests.exceptions.RequestException as e:
        message = f"Network error while fetching lead by phone {phone_number}: {e}"
        print(message)
        return None, message
    except Exception as e:
        message = f"Unexpected error while fetching lead by phone {phone_number}: {e}"
        print(message)
        return None, message


def post_activity_by_phone(phone_number: str, activity_payload: dict):
    """
    Orchestrator function: Fetches a lead by phone number and then posts a custom activity.
    This is the new primary function for interacting with Leadsquared.
    
    Args:
        phone_number (str): The phone number to look up the lead.
        activity_payload (dict): The dictionary representing the activity JSON body.
                                 This function will add the 'RelatedProspectId'.

    Returns:
        tuple: A tuple containing (bool, str) for success status and a message.
    """
    # Step 1: Get the Lead ID
    lead_id, message = get_lead_by_phone(phone_number)
    
    if not lead_id:
        return False, message # Return the message from the lookup (e.g., "No lead found")
        
    # Step 2: Prepare the final payload
    # Add the retrieved lead ID to the payload
    activity_payload["RelatedProspectId"] = lead_id
    
    # Add the current timestamp as per user request
    activity_payload["ActivityDateTime"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    url = f"{LEADSQUARED_HOST}/v2/ProspectActivity.svc/Create"
    params = {
        'accessKey': LEADSQUARED_ACCESS_KEY,
        'secretKey': LEADSQUARED_SECRET_KEY
    }

    time.sleep(0.2)

    try:
        response = requests.post(url, params=params, json=activity_payload)
        
        if response.status_code != 200:
            message = f"Error: Received HTTP {response.status_code} for lead {lead_id}. Response: {response.text}"
            print(message)
            return False, message

        response_data = response.json()
        if response_data.get("Status") == "Success":
            return True, f"Successfully posted activity on lead with phone {phone_number}."
        else:
            error_message = response_data.get("ExceptionMessage", "Unknown API error")
            message = f"Failed to post activity for phone {phone_number}. Reason: {error_message}"
            print(message)
            return False, message

    except requests.exceptions.RequestException as e:
        message = f"A network error occurred while posting activity for phone {phone_number}: {e}"
        print(message)
        return False, message


# This block allows us to test the new workflow directly
if __name__ == "__main__":
    print("--- Running leadsquared_service.py activity test ---")
    
    test_phone_number = "YOUR_REAL_PHONE_NUMBER_HERE"

    if test_phone_number == "YOUR_REAL_PHONE_NUMBER_HERE":
        print("\nSKIPPING TEST: Please edit this file and set a valid test_phone_number.")
    else:
        # This is the payload our app.py will build.
        # It needs the ActivityEvent code and the Fields array.
        test_activity_payload = {
            "ActivityEvent": 227, # <-- IMPORTANT: Use a REAL ActivityEvent code from your LSQ account
            "Fields": [
                {
                    "SchemaName": "mx_Custom_1", # Use a REAL SchemaName
                    "Value": "Test Outcome from Script"
                },
                {
                    "SchemaName": "mx_Custom_2", # Use a REAL SchemaName
                    "Value": "This is a test note generated by the service test script."
                }
            ]
        }

        print(f"\nAttempting to post activity on lead with phone: {test_phone_number}")
        success, message = post_activity_by_phone(test_phone_number, test_activity_payload)

        print("\n--- Test Result ---")
        print(f"Success: {success}")
        print(f"Message: {message}")

    print("\n--- Test complete ---")