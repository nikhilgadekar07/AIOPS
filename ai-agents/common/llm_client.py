import json
import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.1:8b"


def generate(prompt: str, system: str = "", json_mode: bool = False) -> str:
    body = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
    }
    if json_mode:
        body["format"] = "json"

    response = requests.post(f"{OLLAMA_URL}/api/generate", json=body, timeout=300)
    response.raise_for_status()
    return response.json()["response"]


def generate_json(prompt: str, system: str = "") -> dict:
    raw_text = generate(prompt, system=system, json_mode=True)
    return json.loads(raw_text)


if __name__ == "__main__":
    print(generate("Reply with exactly the word: ready"))

    print("\n--- generate_json test ---")
    result = generate_json("List two colors as JSON with a key called colors.")
    print(result)
    print(type(result))