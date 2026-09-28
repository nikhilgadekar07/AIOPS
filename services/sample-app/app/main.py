from fastapi import FastAPI

app = FastAPI(title="sample-app")

@app.get("/health")
def health():
    return {"status": "ok"}