import os
import subprocess
import json

def query_kubectl_ai(nl_input: str) -> str:
    try:
        # Log the input received
        print(f"[query_kubectl_ai] Received input: {nl_input}")

        # Check if OPENAI_API_KEY is set
        if not os.getenv("OPENAI_API_KEY"):
            return "[kubectl-ai error] OPENAI_API_KEY environment variable is not set. Please set it and try again."
        # Check if KUBECONFIG is set
        if not os.getenv("KUBECONFIG"):
            return "[kubectl-ai error] KUBECONFIG environment variable is not set. Please set it and try again."
        
        # Read kubeconfig from config.json
        # try:
        #     with open("config.json", "r") as config_file:
        #         config = json.load(config_file)
        #         kubeconfig_path = config.get("kubeconfig")
        #         if kubeconfig_path:
        #             os.environ["KUBECONFIG"] = kubeconfig_path
        #         else:
        #             return "[kubectl-ai error] kubeconfig path is not set in config.json."
        # except (FileNotFoundError, json.JSONDecodeError) as e:
        #     return f"[kubectl-ai error] Failed to read kubeconfig from config.json: {str(e)}"

        # Log the environment and command being executed
        llm_provider = "openai"
        model = "gpt-4.1"
        command = ["kubectl", "ai", "--llm-provider", llm_provider, "--model", model, "--skip-permissions", "--quiet", nl_input]
        print(f"[query_kubectl_ai] Executing command: {' '.join(command)}")
        print(f"[query_kubectl_ai] Environment: KUBECONFIG={os.getenv('KUBECONFIG')}, OPENAI_API_KEY={'set' if os.getenv('OPENAI_API_KEY') else 'not set'}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )

            # Log both stdout and stderr
            print(f"[query_kubectl_ai] stdout: {result.stdout.strip()}")
            print(f"[query_kubectl_ai] stderr: {result.stderr.strip()}")

            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            # Log the error details
            print(f"[query_kubectl_ai] Command failed with stderr: {e.stderr.strip()}")
            return f"[kubectl-ai error] {e.stderr.strip()}"
    except subprocess.CalledProcessError as e:
        return f"[kubectl-ai error] {e.stderr.strip()}"
