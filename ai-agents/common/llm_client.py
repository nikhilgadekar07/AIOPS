import json
import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.1:8b"


def generate(prompt: str, system: str = "") -> str:
    body = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
    }
    response = requests.post(f"{OLLAMA_URL}/api/generate", json=body, timeout=300)
    response.raise_for_status()
    return response.json()["response"]


if __name__ == "__main__":
    print(generate("Reply with exactly the word: ready"))