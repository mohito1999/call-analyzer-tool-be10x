# services/llm_service.py

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from the .env file in the root directory
load_dotenv()

# Retrieve the API key from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def extract_from_transcript(transcript: str, schema: list, model: str = "openai/gpt-4o-mini"):
    """
    Analyzes a transcript using an LLM via OpenRouter to extract structured data.

    This function constructs a single prompt to the LLM, asking it to return a JSON
    object with all the requested fields, making it efficient.

    Args:
        transcript (str): The call transcript text to analyze.
        schema (list): A list of dictionaries defining the data to extract.
                       Each dict should have 'name' and 'prompt' keys.
                       Example: [{'name': 'sentiment', 'prompt': 'Rate the sentiment'}]
        model (str): The OpenRouter model identifier to use for the analysis.

    Returns:
        dict: A dictionary containing the extracted data, or None if an error occurs.
    """
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY is not set.")
        return None

    # 1. Construct the detailed prompt for the LLM
    prompt_instructions = "\n".join(
        [f"- For the field '{item['name']}', follow this instruction: {item['prompt']}" for item in schema]
    )
    
    # This creates a JSON "template" to show the model what to output
    json_template = ", ".join([f'"{item["name"]}": "..."' for item in schema])

    system_prompt = (
        "You are an expert AI assistant for call analysis. Your task is to analyze the "
        "provided call transcript and extract specific information based on the instructions. "
        "You must respond ONLY with a single, valid JSON object. Do not include any "
        "introductory text, explanations, or markdown formatting like ```json."
    )

    user_prompt = f"""
        Here is the call transcript:
        --- TRANSCRIPT START ---
        {transcript}
        --- TRANSCRIPT END ---

        Please analyze the transcript and extract the following information:
        {prompt_instructions}

        Your response must be a single JSON object with the following structure:
        {{ {json_template} }}
    """

    # 2. Make the API call to OpenRouter
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"} # Force JSON output
            }
        )

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # 3. Parse the response
        response_data = response.json()
        message_content = response_data['choices'][0]['message']['content']
        
        # The content itself should be a JSON string, so we parse it again
        extracted_data = json.loads(message_content)
        return extracted_data

    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenRouter API: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Error parsing LLM response: {e}")
        print(f"Raw response content: {response.text if 'response' in locals() else 'No response object'}")
        return None


# This block allows us to test the service directly
if __name__ == "__main__":
    print("--- Running llm_service.py test ---")

    # Example data
    test_transcript = "Customer: Hi, I'm really happy with the service, it's amazing. I'd like to book a session for next Tuesday. Operator: Great, I can help with that."
    test_schema = [
        {
            "name": "customer_sentiment",
            "prompt": "Analyze the customer's sentiment. Choose from: positive, neutral, negative."
        },
        {
            "name": "lead_stage",
            "prompt": "Assign a lead stage. Choose from: session booked, information gathering, not interested."
        }
    ]

    # Call the function
    result = extract_from_transcript(test_transcript, test_schema)

    if result:
        print("\nSuccessfully extracted data:")
        print(result)
        # Expected output: {'customer_sentiment': 'positive', 'lead_stage': 'session booked'}
    else:
        print("\nFailed to extract data.")
    
    print("\n--- Test complete ---")