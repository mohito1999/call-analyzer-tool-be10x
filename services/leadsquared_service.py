# services/leadsquared_service.py

import os
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LEADSQUARED_ACCESS_KEY = os.getenv("LEADSQUARED_ACCESS_KEY")
LEADSQUARED_SECRET_KEY = os.getenv("LEADSQUARED_SECRET_KEY")
LEADSQUARED_HOST = os.getenv("LEADSQUARED_HOST")

def get_lead_by_phone(phone_number: str):
    """
    Retrieves a lead's ProspectID from Leadsquared using their phone number.

    Args:
        phone_number (str): The phone number of the lead to search for.

    Returns:
        tuple: A tuple containing (str, str) for (lead_id, message),
               or (None, str) if not found or an error occurs.
    """
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
    
    # Implement a simple rate limit
    time.sleep(0.2)
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Raise an exception for bad status codes

        response_data = response.json()
        
        # API returns an empty list if no lead is found
        if not response_data:
            message = f"No lead found with phone number: {phone_number}"
            return None, message
        
        # The API returns a list, we'll take the first result
        lead_data = response_data[0]
        lead_id = lead_data.get("ProspectID")

        if lead_id:
            return lead_id, f"Successfully found ProspectID: {lead_id}"
        else:
            return None, "Lead found, but ProspectID was missing in the response."

    except requests.exceptions.RequestException as e:
        message = f"A network error occurred while fetching lead by phone {phone_number}: {e}"
        print(message)
        return None, message
    except Exception as e:
        message = f"An unexpected error occurred while fetching lead by phone {phone_number}: {e}"
        print(message)
        return None, message

def _update_lead_by_id(lead_id: str, payload: list):
    """
    Internal function to update an existing lead in Leadsquared using its ID.
    (This is the original update_lead function, renamed to be 'private')
    """
    url = f"{LEADSQUARED_HOST}/v2/LeadManagement.svc/Lead.Update"
    params = {
        'accessKey': LEADSQUARED_ACCESS_KEY,
        'secretKey': LEADSQUARED_SECRET_KEY,
        'leadId': lead_id
    }
    
    time.sleep(0.2)

    try:
        response = requests.post(url, params=params, json=payload)
        
        if response.status_code != 200:
            message = f"Error: Received HTTP {response.status_code} for lead {lead_id}. Response: {response.text}"
            print(message)
            return False, message

        response_data = response.json()
        if response_data.get("Status") == "Success":
            return True, f"Successfully updated lead {lead_id}."
        else:
            error_message = response_data.get("ExceptionMessage", "Unknown error")
            message = f"Failed to update lead {lead_id}. Reason: {error_message}"
            print(message)
            return False, message

    except requests.exceptions.RequestException as e:
        message = f"A network error occurred while updating lead {lead_id}: {e}"
        print(message)
        return False, message

def update_lead_by_phone(phone_number: str, payload: list):
    """
    Orchestrator function: Fetches a lead by phone number and then updates it.
    This is the main function we will call from our app.
    
    Args:
        phone_number (str): The phone number to look up the lead.
        payload (list): The data to update for the lead.

    Returns:
        tuple: A tuple containing (bool, str) for success status and a message.
    """
    # Step 1: Get the Lead ID
    lead_id, message = get_lead_by_phone(phone_number)
    
    # Step 2: If we didn't find an ID, stop and return the message from the lookup
    if not lead_id:
        return False, message
        
    # Step 3: If we found an ID, proceed with the update
    return _update_lead_by_id(lead_id, payload)


# This block allows us to test the full workflow directly
if __name__ == "__main__":
    print("--- Running leadsquared_service.py test (full workflow) ---")
    
    # --- IMPORTANT ---
    # To run this test, you MUST provide a REAL, VALID Phone Number from your
    # Leadsquared account that exists.
    test_phone_number = "9752887393" # e.g., "9901111111"

    if test_phone_number == "YOUR_REAL_PHONE_NUMBER_HERE":
        print("\nSKIPPING TEST: Please edit leadsquared_service.py and set a valid test_phone_number.")
    else:
        test_payload = [
            {
                "Attribute": "ProspectStage",
                "Value": "In Pipeline"
            },
            {
                "Attribute": "mx_Last_Call_Notes",
                "Value": "API test successful"
            }
        ]

        print(f"\nAttempting to find and update lead with phone: {test_phone_number}")
        success, message = update_lead_by_phone(test_phone_number, test_payload)

        print("\n--- Test Result ---")
        print(f"Success: {success}")
        print(f"Message: {message}")

    print("\n--- Test complete ---")