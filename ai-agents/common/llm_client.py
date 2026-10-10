import json
import os

import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20"))


def generate(prompt: str, system: str = "", json_mode: bool = False) -> str:
    body = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": 512,
        },
    }
    if json_mode:
        body["format"] = "json"

    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=body, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()["response"]
    except (requests.RequestException, ValueError, KeyError):
        if json_mode:
            return "{}"
        return ""


def generate_json(prompt: str, system: str = "") -> dict:
    try:
        raw_text = generate(prompt, system=system, json_mode=True)
        return json.loads(raw_text)
    except (TypeError, ValueError):
        return {}


def embed(text: str) -> list[float]:
    body = {"model": "nomic-embed-text", "prompt": text}
    try:
        response = requests.post(f"{OLLAMA_URL}/api/embeddings", json=body, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()["embedding"]
    except (requests.RequestException, ValueError, KeyError):
        return []


if __name__ == "__main__":
    vector = embed("Allow users to cancel a pending order")
    print("Length:", len(vector))
    print("First 5 numbers:", vector[:5])