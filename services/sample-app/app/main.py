from fastapi import FastAPI
from app.orders import router as orders_router

app = FastAPI(title="sample-app")
app.include_router(orders_router)


@app.get("/health")
def health():
    return {"status": "ok"}
