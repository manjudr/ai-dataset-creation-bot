import os
from openai import OpenAI

# Step 1: Initialize OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Step 2: Function to summarize the health message
def generate_summary(message, model="gpt-4"):
    prompt = f"Summarize the following Kubernetes health report into a concise set of key points:\n\n{message}"

    # Request from OpenAI API
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=150
    )
    
    # Check if 'choices' exists and has content
    if 'choices' in response and len(response['choices']) > 0:
        summary = response['choices'][0]['message']['content'].strip()
        print("Generated Summary:", summary)
        return summary
    else:
        print("Error: No valid response from OpenAI.")
        return None
