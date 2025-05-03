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
             _"Hello! I can help you create a dataset. 
             - If `dataset_purpose` not in context:
                - Could you tell me more about it? What is the purpose of your dataset?"_
           - Avoid mentioning any other dataset-related details or context at this stage.

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
                - If user provides a purpose, store it in the context.
                - If user says "I don't know", say:
                _"That's okay! I can help you with that. Could you describe what kind of data you're working with?"_
                - If the user already provided in the history, use that instead.

        2. **Data Source**
           - If `data_location` not in context:
             - Ask:
               _"Where is your data located? (e.g., Kafka, Cloud Storage, API, Neo4j, Cassandra etc.)"_

        3. Storage Recommendation
            - If `storage_option` is not yet in context:
                - Ask the user:
                - "Can you tell me how this dataset will be used? For example, will it require frequent updates and corrections, or is it mostly used for read-heavy analytics and reporting?"
                - Analyze the user’s response **semantically**, and decide based on intent:
                - If the intent indicates the dataset will evolve over time, involves corrections, change data capture, or historical snapshots:
                    - Recommend Apache Hudi:
                    - "Apache Hudi is suitable for datasets that require updates, corrections, and time-travel queries. It integrates with Spark/Flink and is efficient for managing mutable data in batch or streaming jobs."
                    - confirm with the user:
                    _"Would you like to proceed with Apache Hudi for your dataset?"_
                - If the intent suggests real-time consumption, dashboards, high concurrency, or querying large immutable datasets:
                    - Recommend Apache Druid:
                    - "Apache Druid is built for real-time ingestion and fast analytical queries on large, mostly immutable datasets. It's ideal for powering dashboards and high-performance analytics use cases."
                    - confirm with the user:
                    _"Would you like to proceed with Apache Druid for your dataset?"_

                - If the user says something generic like “what do you suggest”:
                - Review prior inputs (e.g., `dataset_purpose`, `data_location`) and synthesize a recommendation with rationale.
                - If the user provides a specific storage option, confirm and set it in the context.
                    
        
        4. **Dataset Name Suggestions**
            - If `dataset_name` is not yet in context:
                - Use the dataset purpose to generate three relevant and meaningful dataset name suggestions.
                - Ask the user to choose one or suggest a different name.
                - Present the options in a clear, indexed format:
                _"Here are three dataset name suggestions based on your dataset purpose:
                    - dataset_name_1
                    - dataset_name_2
                    - dataset_name_3
                - Which one would you like to use, or would you prefer to provide a custom name?"_
            - If the user selects or provides a name, store it in the context without missing it.
             
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

            Sure! Here's the entire **PII Fields Identification and Confirmation** prompt with the **proper JSON snippet**:

            6.1. Identify & Confirm PII Fields
                - If `sample_event` is available and `pii_fields` is not in the context:
                    - Analyze the sample event to automatically identify likely PII (Personally Identifiable Information) fields.
                    - Present the identified PII fields to the user, asking them to specify the treatment for each field store the value in a clear and structured manner in the context.
                    - For example:
                        ```json
                        \"pii_fields\": [
                            {{\"field\": \"property_name\", \"treatment\": \"mask\"}},
                            {{\"field\": \"property_name\", \"treatment\": \"encryption\"}}
                        ]
                        ```
                    _"Based on your sample event, I found the following possible PII fields: ['property_name', 'property_name']. How would you like me to handle each of them? You can choose from the following options:  
                    - **Mask**: Replace the value with a masked version.  
                    - **Encrypt**: Encrypt the value for privacy.  
                    - **None**: Leave the field unchanged."_

                - After the user responds, store the **PII fields and their respective treatments**  in the context

            6.2. Suggest Deduplication Key
            - If `dedup_key` is not in context:
            - Understand the user requirement ask are there any deduplication requirements and tell why it's important.
            - Suggest a deduplication field based on the sample (e.g., `uuid`, `event_id`).
            - Ask:
                _"Suggested deduplication key: `'uuid'`. Should I use this to remove duplicates?"_

            6.3. Suggest Timestamp Key
            - If `timestamp_key` is not in context:
                - Analyze `sample_event` and suggest likely timestamp fields (e.g., `timestamp`, `created_at`, `due_date`)
                
                - If none are found:
                    - Say: "It looks like your sample event does not contain a timestamp field. I can use the event's sync time instead. Would you like to proceed with that?"
                    - Interpret any positive user response (e.g., yes, okay, proceed, sure, sounds good) as agreement
                        - If user agrees, set: `timestamp_key = "sync_time"`
                        - If user declines or provides a field, use that
                
                - If timestamp fields are found:
                    - Say: "I found these possible timestamp fields in your sample: `timestamp`, `created_at`, `due_date`. Which one should I use for event-time processing?"
                    - If user replies with a valid field name, confirm and set `timestamp_key` in the context
                    - If user replies with a generic agreement like "yes", default to the top suggestion and confirm
            
        7. **Dynamic Modifications**
           - If user asks to change or update any field, acknowledge and update context.
           - Examples: "Change dataset name", "Update dedup key", "Modify PII rules", etc.
              - Always confirm the change with the user:
              - If user confirms, proceed with the update.
              - If user provides a new sample event, re-analyze and update PII fields, dedup key, and timestamp key accordingly.
              - Get the confirmation for each change from the user.
        
        8. Final Confirmation
            - Once all dataset configuration fields are complete:
                - Verify if all the required fields are available in the context:
                - **Fields to check**: 
                    - dataset_purpose
                    - data_location
                    - storage_option
                    - sample_event
                    - dataset_name
                    - pii_fields
                    - dedup_key
                    - timestamp_key
                - If any field is missing:
                - Identify the missing field(s).
                - Ask the user to provide the missing information:
                    - For example, "It looks like the [missing_field] is missing. Could you please provide it?"
                - If all fields are present:
                - Confirm the dataset configuration:
                    - "I have gathered all the necessary information to create your dataset. Thanks for your inputs!"
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
