import json
import urllib.request
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Config (Manually mirroring logic to ensure isolation)
ENDPOINT = os.getenv("AZURE_OPENAI_CHAT_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
API_KEY = os.getenv("AZURE_OPENAI_CHAT_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_CHAT_API_VERSION", "2024-02-15-preview")
MODEL_ID = os.getenv("DOCQA_MODEL_ID", "gpt-5-nano")

print(f"Testing Endpoint: {ENDPOINT}")
print(f"Deployment: {MODEL_ID}")
print(f"Version: {API_VERSION}")

def test_chat():
    url = f"{ENDPOINT.rstrip('/')}/openai/deployments/{MODEL_ID}/chat/completions?api-version={API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY,
    }
    
    # 1. Standard Payload (What we use now)
    payload_standard = {
        "messages": [
            {"role": "user", "content": "Say 'Test Passed'"}
        ],
        "max_completion_tokens": 5,
    }

    try:
        print("\n--- Attempt 1: Standard Payload ---")
        req = urllib.request.Request(
            url,
            data=json.dumps(payload_standard).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
            print("SUCCESS:", data["choices"][0]["message"]["content"])
    except urllib.error.HTTPError as e:
        print(f"FAILED: {e.code} - {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_chat()
