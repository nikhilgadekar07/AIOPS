from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/orders", tags=["orders"])

ORDERS: dict[int, dict] = {}
next_id = 1
VALID_ORDER_STATUSES = {"pending", "shipped", "delivered", "cancelled"}


class OrderCreate(BaseModel):
    item: str = Field(min_length=1)
    quantity: int = Field(default=1, gt=0)


class OrderUpdate(BaseModel):
    status: str = Field(..., min_length=1)

    @property
    def normalized_status(self) -> str:
        return self.status.strip().lower()


@router.post("", status_code=201)
def create_order(payload: OrderCreate):
    global next_id
    order = {"id": next_id, "item": payload.item,
             "quantity": payload.quantity, "status": "pending"}
    ORDERS[next_id] = order
    next_id += 1
    return order


@router.get("/{order_id}")
def get_order(order_id: int):
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")
    return ORDERS[order_id]


@router.patch("/{order_id}")
def update_order_status(order_id: int, payload: OrderUpdate):
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")

    status = payload.normalized_status
    if status not in VALID_ORDER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. Allowed values: "
                + ", ".join(sorted(VALID_ORDER_STATUSES))
            ),
        )

    ORDERS[order_id]["status"] = status
    return ORDERS[order_id]
