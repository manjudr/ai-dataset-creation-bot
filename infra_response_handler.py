import asyncio
import json
from kubectl_ai import query_kubectl_ai

async def query_kubectl_ai_async(user_input: str, websocket, context):
    try:
        response = await asyncio.to_thread(query_kubectl_ai, user_input)
        await websocket.send_text(
            json.dumps({"type": "infra", "output": response})
        )
        context["history"].append({"user": user_input, "ai": response})
    except Exception as e:
        await websocket.send_text(json.dumps({"error": str(e)}))
