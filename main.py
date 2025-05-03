import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Load model configuration
with open("config.json", "r") as config_file:
    CONFIG = json.load(config_file)

# Get the default model
DEFAULT_MODEL = next((model for model in CONFIG["models"] if model.get("default")), None)
if not DEFAULT_MODEL:
    raise ValueError("No default model found in the configuration.")

REQUIRED_KEYS = [
    "dataset_purpose", "sample_event", "data_location", "dataset_name",
    "pii_fields", "dedup_key", "timestamp_key", "storage_option"
]

def get_model_details(model_id=None):
    """Retrieve model details by ID or return the default model."""
    if model_id:
        return next((model for model in CONFIG["models"] if model["model_id"] == model_id), DEFAULT_MODEL)
    return DEFAULT_MODEL

def safe_context_for_prompt(context):
    """
    Sanitize and filter the context to include only relevant fields for the prompt.
    """
    # Remove sensitive or unnecessary fields from the context
    sanitized_context = {key: value for key, value in context.items() if key in REQUIRED_KEYS and value}
    return sanitized_context

def extract_json(text):
    """
    Extract JSON object from a string.
    This function assumes the JSON object is enclosed in curly braces.
    """
    import re
    try:
        # Use regex to find the first JSON object in the text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"[extract_json] JSON decode error: {e}")
    return {}

def normalize_context(context):
    """
    Normalize the context by ensuring all required keys are present and have default values if missing.
    """
    for key in REQUIRED_KEYS:
        if key not in context:
            context[key] = None
    return context

async def get_ai_response_stream(user_input, context, websocket: WebSocket, model_id=None):
    try:
        model_details = get_model_details(model_id)
        model_name = model_details["model_name"]
        api_key = model_details["api_key"]
        model_provider = model_details["model_provider"]
        api_url = model_details.get("api_url")
        if not api_url:
            raise ValueError(f"API URL is missing for the model: {model_name}")

        conversation_history = context.get("history", [])
        conversation_history.append({"role": "user", "content": user_input})

        existing_context = context.copy()
        relevant_context = safe_context_for_prompt(existing_context)
        full_prompt = f"""
        You are a smart and interactive AI assistant designed to help users create datasets step by step. Your job is to guide users clearly and conversationally, without repeating questions for fields already completed in the context. Allow users to review, confirm, or modify any part of the configuration along the way.

        ---

        ## **Behavior Rules:**

        1. **Greetings**
           - If user greets you, say:
             _"Hello! I can help you create a dataset. What is the purpose of your dataset?"_
           - Do not mention any other dataset-related context yet.

        2. **Unrelated Queries**
           - If user asks something off-topic, reply:
             _"I'm here to help with dataset creation. Could you tell me what kind of dataset you're working on?"_

        ---

        ## **Dataset Configuration Flow (Strict Order, No Repetition)**

        1. **Dataset Purpose**
           - If `dataset_purpose` not in context:
             - Try to infer from input.
             - Otherwise, ask:
               _"What is the purpose of this dataset?"_

        2. **Data Source**
           - If `data_location` not in context:
             - Ask:
               _"Where is your data located? (e.g., Kafka, file system, API, etc.)"_

        3. **Storage Recommendation**
           - If `storage_option` not in context:
             - Ask:
               _"Will your dataset require update support? (Yes/No)"_
             - Recommend:
               - **Apache Hudi** if updates are needed.
               - **Apache Druid** otherwise.
        
        4. **Dataset Name Suggestions**
           - If `dataset_name` not in context:
             - Generate **three relevant dataset names** using the dataset purpose and fields from the sample.
             - Ask the user to pick one or modify

        5. **Sample Data**
           - Only if purpose and data location are available.
           - If `sample_event` not in context:
             - Ask:
               _"Can you provide a sample JSON event or schema from your dataset?"_
             - When storing in context, always stringify and escape:
               ```json
               "sample_event": "{{\\"field\\":\\"value\\"}}"
               ```
             - Never display raw JSON in the message.

        6. Analyze Sample (PII, Deduplication, Timestamp)

        6.1. Identify & Confirm PII Fields
        - If `sample_event` is available and `pii_fields` is not in context:
        - Analyze the sample to extract likely PII fields.
        - Ask:
            _"Based on your sample, I found possible PII fields: `['email', 'phone', 'user_id']`. For each, how should I treat them? (Mask, Encrypt, or None)"_

        6.2. Suggest Deduplication Key
        - If `dedup_key` is not in context:
        - Suggest a deduplication field based on the sample (e.g., `uuid`, `event_id`).
        - Ask:
            _"Suggested deduplication key: `'uuid'`. Should I use this to remove duplicates?"_

        6.3. Suggest Timestamp Key
        - If `timestamp_key` is not in context:
        - Suggest a timestamp field (e.g., `timestamp`, `created_at`) based on the sample.
        - Ask:
            _"Suggested timestamp field: `'timestamp'`. Should I use this for event-time processing?"_


        7. **Dynamic Modifications**
           - If user asks to change or update any field, acknowledge and update context.
           - Examples: "Change dataset name", "Update dedup key", "Modify PII rules", etc.

        8. **Final Confirmation**
           - Once all fields are complete:
             - Present full summary and ask:
               _"Here’s the complete dataset configuration. Would you like to confirm or make changes?"_

        ---

        ### **Current Context (skip completed fields):**
        {json.dumps(relevant_context, indent=2)}

        ### **User Input:**
        "{user_input}"

        ### **Expected JSON Response Format:**
        ```json
        {{
          "message": "Conversational response guiding the user through the next step or confirming modifications.",
          "context": {{
            "dataset_purpose": "...",
            "data_location": "...",
            "storage_option": "...",
            "sample_event": "...",
            "dataset_name": "...",
            "pii_fields": [...],
            "dedup_key": "...",
            "timestamp_key": "..."
          }}
        }}

        """


        prompt = """
        You are a dataset configuration assistant. Your goal is to interactively collect the following fields from the user in a specific order, and guide them through the configuration process.

        Your task is to extract and build a structured JSON object in this format:

        {
        "message": "Conversational response guiding the user through the next step or confirming modifications.",
        "context": {
            "dataset_purpose": "string",
            "sample_event": "JSON object",
            "data_location": "kafka/file/api/db",
            "dataset_name": "string",
            "pii_fields": [{"field_name": "string", "pii_type": "mask/encryption"}],
            "dedup_key": "string",
            "timestamp_key": "string",
            "storage_option": "druid/hudi/db"
        }
        }

        You must follow this exact flow:
        1. Start by greeting the user and ask: **“What do you want me to do?”**
        2. Use their response to infer the **dataset_purpose**.
        3. Ask for the **data_location** — Kafka, File, API, or DB.
        4. Suggest a **dataset_name** using the purpose or structure and ask the user to confirm or modify.
        5. Ask for the **storage_option** — Druid, Hudi, or DB.
        6. Ask for a **sample_event** (JSON).
        7. Once the event is shared:
        - Analyze and suggest possible **PII fields** (e.g., name, email, phone, etc.). Ask how each should be handled — mask/encryption/ignore.
        - Suggest a **deduplication key** (e.g., `message_id`, `id`, `uuid`) and ask for confirmation.
        - Suggest a **timestamp key** (e.g., `ts`, `timestamp`, `event_time`) and ask for confirmation.
        
        8. At every step, include both:
        - A conversational `"message"` that guides the user.
        - A `"context"` object that accumulates and reflects all collected or inferred fields so far.
        9. Once all fields are collected, respond only with the final JSON object.

        Important rules:
        - Never skip steps.
        - Never ask for multiple fields at once.
        - Always wait for the user’s confirmation before proceeding.
        - If the user greets you, respond accordingly and begin the flow.
        - If the user changes a previous input or gives a new sample, update the `context` accordingly.
        - Always return a single JSON object with a `message` and full `context`.

        Begin with:
        {
        "message": "Hi! What do you want me to do?",
        "context": {}
        }
        """



        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": full_prompt},
                *[{"role": "assistant", "content": msg["content"]} for msg in conversation_history if msg["role"] == "assistant"],
                {"role": "user", "content": user_input}
            ],
            "stream": True
        }

        headers = {}
        if model_provider == "OpenAI" and api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        print(f"[get_ai_response] Sending prompt to {model_provider} ({model_name})...")

        collected_output = ""

        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", api_url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            # Check if the line starts with 'data: '
                            if line.startswith("data: "):
                                line_content = line[len("data: "):].strip()
                                if line_content == "[DONE]":
                                    break

                                stream_json = json.loads(line_content)
                                response_text = stream_json.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if response_text.strip():
                                    collected_output += response_text
                                    print(collected_output)
                                else:
                                    print(f"[get_ai_response_stream] Skipping empty or incomplete delta: {line}")
                            else:
                                print(f"[get_ai_response_stream] Skipping non-data line: {line}")
                        except json.JSONDecodeError:
                            print(f"[get_ai_response_stream] Skipping malformed line: {line}")
                        except (KeyError, IndexError) as e:
                            print(f"[get_ai_response_stream] Malformed line structure: {line}, Error: {e}")

        json_response = extract_json(collected_output)
        json_response = normalize_context(json_response)
        if "_note" in json_response:
            json_response["message"] = (
                    "I noticed your input had some formatting issues, so I auto-corrected the JSON for you. "
                    + json_response.get("message", "")
            )

        if not json_response:
            print("[get_ai_response] Failed to parse valid JSON.")
            await websocket.send_text(json.dumps({"error": "AI response could not be parsed."}))
            return

        # Prevent overwriting or re-asking for known values
        new_context = json_response.get("context", {})
        delta = {}
        for key, value in new_context.items():
            if key not in context or context[key] in [None, "", []]:
                context[key] = value
                delta[key] = value

        context["history"] = conversation_history

        completed_keys = [k for k in REQUIRED_KEYS if context.get(k)]
        missing_keys = [k for k in REQUIRED_KEYS if not context.get(k)]
        print(f"[context update] Completed keys: {completed_keys}")
        print(f"[context update] Missing keys: {missing_keys}")
        print(f"[context update] Delta: {delta}")
        print(f"[context update] Context: {context}")

        if all(context.get(k) for k in REQUIRED_KEYS):
            await websocket.send_text(json.dumps({
                "message": "All steps complete! Here's your full configuration.",
                "context": context
            }))
        else:
            # Send the refined message to the WebSocket
            await websocket.send_text(json.dumps({
                "message": json_response.get("message"),
                "context": context
            }))

    except httpx.TimeoutException:
        print("[get_ai_response] Request to AI provider timed out.")
        await websocket.send_text(json.dumps({"error": "Request to AI provider timed out."}))
    except Exception as e:
        print(f"[get_ai_response] Exception: {e}")
        await websocket.send_text(json.dumps({"error": str(e)}))

app = FastAPI()
connected_clients = {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients[websocket] = {"history": []}
    print("[websocket] New client connected.")

    try:
        while True:
            data = await websocket.receive_text()
            print(f"[websocket] Received raw data: {repr(data)}")

            try:
                json_data = json.loads(data)
                print(f"[websocket] Parsed JSON: {json_data}")

                user_message = json_data.get("message", "").strip()
                if not user_message:
                    await websocket.send_text(json.dumps({"error": "Empty message received"}))
                    continue

                context = connected_clients.get(websocket, {"history": []})
                await get_ai_response_stream(user_message, context, websocket)
                connected_clients[websocket] = context

            except json.JSONDecodeError as e:
                print(f"[websocket] JSON decode error: {e}")
                await websocket.send_text(json.dumps({"error": "Invalid JSON format"}))

    except WebSocketDisconnect:
        print("[websocket] Client disconnected.")
        connected_clients.pop(websocket, None)
    except Exception as e:
        print(f"[websocket] Unexpected error: {e}")
        await websocket.send_text(json.dumps({"error": "Internal server error"}))

# Simple text added for testing purposes
print("Hello, this is a test message!")
