import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

REQUIRED_KEYS = [
    "dataset_purpose", "sample_event", "data_location", "dataset_name",
    "pii_fields", "dedup_key", "timestamp_key", "storage_option"
]

import re

def escape_json_string(raw_json: str) -> str:
    """Ensure sample_event or any JSON value can be safely embedded as a string."""
    return json.dumps(json.loads(raw_json))  # double encode

def extract_json(text):
    try:
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start != -1 and json_end != -1:
            json_text = text[json_start:json_end]
            return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"[extract_json] JSON decode error: {e}")
        try:
            import demjson3
            print("[extract_json] Attempting auto-fix using demjson3...")
            json_text = text[json_start:json_end]
            fixed_json = demjson3.decode(json_text)
            fixed_json["_note"] = "⚠️ Auto-fixed invalid JSON from user input."
            return fixed_json
        except Exception as fix_error:
            print(f"[extract_json] Auto-fix failed: {fix_error}")
    return {}

def safe_context_for_prompt(ctx):
    """Ensure context is safe to embed inside prompt"""
    safe = {}
    for k, v in ctx.items():
        if k == "sample_event" and isinstance(v, str):
            try:
                safe[k] = escape_json_string(v)
            except:
                safe[k] = v
        elif k != "history":
            safe[k] = v
    return safe

def normalize_context(ctx):
    if "sample_event" in ctx and isinstance(ctx["sample_event"], str):
        try:
            ctx["sample_event"] = json.loads(ctx["sample_event"])
            ctx["_note"] = "⚠️ Auto-fixed stringified sample_event into a proper JSON object."
        except json.JSONDecodeError:
            pass  # already malformed
    return ctx


async def get_ai_response_stream(user_input, context, websocket: WebSocket):
    try:
        conversation_history = context.get("history", [])
        conversation_history.append({"role": "user", "content": user_input})

        existing_context = context.copy()
        #relevant_context = {k: v for k, v in existing_context.items() if k not in ["history"] and v not in [None, "", []]}
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
        
        5. **Dataset Name Suggestions**
           - If `dataset_name` not in context:
             - Generate **three relevant dataset names** using the dataset purpose and fields from the sample.
             - Ask the user to pick one or modify

        4. **Sample Data**
           - Only if purpose and data location are available.
           - If `sample_event` not in context:
             - Ask:
               _"Can you provide a sample JSON event or schema from your dataset?"_
             - When storing in context, always stringify and escape:
               ```json
               "sample_event": "{{\\"field\\":\\"value\\"}}"
               ```
             - Never display raw JSON in the message.

        5. **Analyze Sample: PII + Dedup Key + Timestamp Key**
           - If any of `pii_fields`, `dedup_key`, or `timestamp_key` are missing:
             - Analyze the `sample_event` and say:
               _"Based on your sample:\n\n• Potential PII fields: `<pii_fields>`\n  → For each, how should I treat them? (Mask, Encrypt, or None)\n\n• Suggested deduplication key: `<dedup_key>` → Does this work?\n\n• Suggested timestamp field: `<timestamp_key>` → Use this as event time?"_
             - Ask for confirmation or updates.

        6. **Dynamic Modifications**
           - If user asks to change or update any field, acknowledge and update context.
           - Examples: "Change dataset name", "Update dedup key", "Modify PII rules", etc.

        7. **Final Confirmation**
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

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": True
        }

        print(f"[get_ai_response] Sending prompt to Ollama (stream)...")
        collected_output = ""

        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", OLLAMA_URL, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            stream_json = json.loads(line)
                            response_text = stream_json.get("response", "")
                            collected_output += response_text
                            print(collected_output)
                        except json.JSONDecodeError:
                            print(f"[get_ai_response_stream] Skipping malformed line: {line}")

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

        if all(context.get(k) for k in REQUIRED_KEYS):
            await websocket.send_text(json.dumps({
                "message": "All steps complete! Here's your full configuration.",
                "context": context
            }))
        else:
            await websocket.send_text(json.dumps({
                "message": json_response.get("message"),
                "delta": delta
            }))

    except httpx.TimeoutException:
        print("[get_ai_response] Request to Ollama timed out.")
        await websocket.send_text(json.dumps({"error": "Request to Ollama timed out."}))
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
