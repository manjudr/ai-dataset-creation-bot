# from openai import OpenAI
# import pandas as pd
# import requests
# import json
# import os

# # Initialize OpenAI client
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# PROMETHEUS_URL = "http://localhost:9090/api/v1/query"

# # Load and format the metrics knowledge base
# def load_knowledge_base(csv_path):
#     df = pd.read_csv(csv_path, on_bad_lines='skip')
#     knowledge_base_text = "\n".join(
#         f"Metric: {row['metric_name']}\nDescription: {row['description']}\nExample: {row['example_usage']}"
#         for _, row in df.iterrows()
#     )
#     return knowledge_base_text

# # Use GPT to generate the PromQL query
# def generate_prometheus_query(user_query, model="gpt-4"):
#     # Load available metrics
#     df = pd.read_csv("metrics.csv")
#     available_metrics = df['metric_name'].tolist()
#     available_metrics_text = "\n".join(available_metrics)

#     knowledge_base_text = load_knowledge_base("metrics.csv")

#     messages = [
#         {"role": "system", "content": "You are a helpful assistant that converts natural language queries into Prometheus PromQL queries."},
#         {"role": "user", "content": f"""
# The following are Prometheus metrics available in the system:

# {available_metrics_text}

# Descriptions of these metrics:

# {knowledge_base_text}

# User Query: {user_query}

# Your task:
# - Only use metrics listed above.
# - Do NOT invent or assume metrics that are not listed.
# - Use PromQL syntax correctly.
# - Return ONLY a valid PromQL query. Do NOT return explanations, comments, or extra text.
# """}
#     ]

#     response = client.chat.completions.create(
#         model=model,
#         messages=messages,
#         temperature=0.2,
#         max_tokens=100
#     )

#     return response.choices[0].message.content.strip()


# # Query Prometheus using the generated PromQL
# def query_prometheus(promql_query):
#     response = requests.get(PROMETHEUS_URL, params={'query': promql_query})
#     response.raise_for_status()
#     data = response.json()
#     return data['data']['result']

# # Summarize the result using OpenAI
# def summarize_result(user_query, promql_query, result, model="gpt-4"):
#     result_text = json.dumps(result, indent=2)
#     messages = [
#         {"role": "system", "content": "You are a helpful assistant that explains Prometheus query results in natural language."},
#         {"role": "user", "content": f"""
# User Query: {user_query}
# PromQL Query: {promql_query}

# Query Result:
# {result_text}

# Summarize the result for the user in plain English.
# """}
#     ]

#     response = client.chat.completions.create(
#         model=model,
#         messages=messages,
#         temperature=0.4,
#         max_tokens=200
#     )

#     return response.choices[0].message.content.strip()


import os
import re
import json
import requests
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PROMETHEUS_BASE_URL = "http://localhost:9090/api/v1"

# Load metrics CSV and prepare context
def load_metrics_context(csv_path="metrics.csv"):
    df = pd.read_csv(csv_path, on_bad_lines='skip')
    available_metrics = df['metric_name'].tolist()
    available_metrics_text = "\n".join(available_metrics)

    if 'type' in df.columns:
        knowledge_base_text = "\n\n".join(
            f"Metric: {row['metric_name']}\nDescription: {row['description']}\nType: {row['type']}\nExample: {row['example_usage']}"
            for _, row in df.iterrows()
        )
    else:
        knowledge_base_text = "\n\n".join(
            f"Metric: {row['metric_name']}\nDescription: {row['description']}\nExample: {row['example_usage']}"
            for _, row in df.iterrows()
        )

    return available_metrics_text, knowledge_base_text

# Generate PromQL query from natural language
def generate_prometheus_query(user_query, model="gpt-4"):
    available_metrics_text, knowledge_base_text = load_metrics_context()

    prompt = f"""
You are a Prometheus PromQL expert. Your task is to translate natural language monitoring questions into valid PromQL queries.

You are given:
- A list of valid metric names
- A knowledge base with descriptions and example usages
- Rules about PromQL syntax

Only use the metrics provided. Do NOT invent metric names.

## PromQL Rules (must follow):
- For counters over time (e.g., *_total), use: increase(metric[duration])
- Never use [duration] after an aggregation like sum() — this is invalid
- To aggregate a counter over time, use: sum(increase(metric[duration]))
- To get current values (instant vector), use: sum(metric) or metric
- Do NOT return explanations or comments — return only the PromQL query

## Example PromQL Queries:
Q: How many failed API calls in the last hour?
→ sum(increase(api_calls_failed_total[1h]))

Q: What is the current memory usage?
→ sum(node_memory_Active_bytes)

User Query: {user_query}

Available Metrics:
{available_metrics_text}

Metric Descriptions:
{knowledge_base_text}

Return ONLY the valid PromQL query.
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=150,
    )

    return response.choices[0].message.content.strip()

# Check if query uses range selector
def is_valid_promql(query):
    # Invalid if there's a range selector directly after an aggregation function, like sum(...) [24h]
    invalid_pattern = r'(sum|avg|max|min|count|count_values|stddev|stdvar|topk|bottomk)\([^\)]+\)\[\d+[smhd]\]'
    if re.search(invalid_pattern, query):
        return False
    return True

# Query Prometheus with appropriate API endpoint
def query_prometheus(promql_query):
    uses_range = bool(re.search(r'\[\d+[smhd]\]', promql_query))

    if uses_range:
        end = datetime.utcnow()
        start = end - timedelta(days=1)
        step = "60s"

        response = requests.get(
            f"{PROMETHEUS_BASE_URL}/query_range",
            params={
                'query': promql_query,
                'start': start.isoformat() + "Z",
                'end': end.isoformat() + "Z",
                'step': step
            }
        )
    else:
        response = requests.get(
            f"{PROMETHEUS_BASE_URL}/query",
            params={'query': promql_query}
        )

    response.raise_for_status()
    return response.json()['data']['result']

# Summarize results using OpenAI
def summarize_result(user_query, promql_query, result, model="gpt-4"):
    result_text = json.dumps(result, indent=2)
    messages = [
        {"role": "system", "content": "You are a helpful assistant that explains Prometheus query results in plain English."},
        {"role": "user", "content": f"""
User Query: {user_query}
PromQL Query: {promql_query}

Query Result:
{result_text}

Summarize the result in simple terms.
"""}
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()

# Run the full pipeline
def run_query_pipeline(user_query):
    print("🔍 User Query:", user_query)
    try:
        promql_query = generate_prometheus_query(user_query)
        print("📦 Generated PromQL:", promql_query)

        # Ensure generate_prometheus_query does not return None or empty string
        if not promql_query:
            print("❌ Failed to generate a PromQL query.")
            return

        if not is_valid_promql(promql_query):
            print("❌ Invalid PromQL query generated.")
            return

        result = query_prometheus(promql_query)
        print("✅ Query Success. Raw Result:", result)

        summary = summarize_result(user_query, promql_query, result)
        print("📝 Summary:\n", summary)
    except Exception as e:
        print("❌ Error in query pipeline:", e)

# Uncomment to run interactively
# if __name__ == "__main__":
#     user_query_input = input("Enter a natural language query: ")
#     run_query_pipeline(user_query_input)