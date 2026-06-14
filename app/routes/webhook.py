from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.event import Event
from app.models.campaign import Campaign
from app.models.customer import Customer
from app.models.order import Order
from datetime import datetime, date, timedelta
from decimal import Decimal
import uuid

router = APIRouter(
    prefix="/webhook",
    tags=["Webhook Callback"]
)

def ensure_preceding_events(campaign_id: int, customer_id: int, event_type: str, event_time: datetime, db: Session):
    hierarchy = ["sent", "delivered", "opened", "clicked", "purchased"]
    if event_type not in hierarchy:
        return
    idx = hierarchy.index(event_type)
    for i in range(idx):
        pre_type = hierarchy[i]
        existing = db.query(Event).filter(
            Event.campaign_id == campaign_id,
            Event.customer_id == customer_id,
            Event.event_type == pre_type
        ).first()
        if not existing:
            pre_time = event_time - timedelta(seconds=(idx - i) * 2)
            db_event = Event(
                customer_id=customer_id,
                campaign_id=campaign_id,
                event_type=pre_type,
                event_time=pre_time
            )
            db.add(db_event)
            print(f"[FUNNEL GUARD] Auto-inserted missing preceding event '{pre_type}' for campaign_id={campaign_id}, customer_id={customer_id}", flush=True)

def handle_webhook_event(payload: dict, db: Session):
    campaign_id = payload.get("campaign_id")
    customer_id = payload.get("customer_id")
    event_type = payload.get("event_type")
    event_time_str = payload.get("event_time")
    metadata = payload.get("metadata") or {}

    try:
        event_time = datetime.fromisoformat(event_time_str)
    except Exception:
        event_time = datetime.utcnow()

    print(f"[WEBHOOK RECEIPT] Received event '{event_type}' for campaign_id={campaign_id}, customer_id={customer_id}", flush=True)

    if event_type == "completed":
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if campaign:
            campaign.status = "Completed"
            db.commit()
            print(f"[CAMPAIGN COMPLETED] Campaign campaign_id={campaign_id} status updated to Completed.", flush=True)
        return {"status": "processed"}

    # 1. Log event in events table
    if customer_id is not None:
        # Enforce event hierarchy consistency
        ensure_preceding_events(campaign_id, customer_id, event_type, event_time, db)

        existing = db.query(Event).filter(
        Event.campaign_id == campaign_id,
        Event.customer_id == customer_id,
        Event.event_type == event_type
        ).first()

        if existing:
            print(
                f"[DUPLICATE EVENT IGNORED] "
                f"campaign={campaign_id} "
                f"customer={customer_id} "
                f"event={event_type}",
                flush=True
            )
            return {"status": "duplicate_ignored"}
        purchase_value = None
        if event_type == "purchased":
            purchase_value = Decimal(str(metadata.get("revenue", 1200.0)))
            print(f"[PURCHASE EVENT] Campaign campaign_id={campaign_id} customer_id={customer_id} purchase value={purchase_value}", flush=True)
        
        db_event = Event(
            customer_id=customer_id,
            campaign_id=campaign_id,
            event_type=event_type,
            event_time=event_time,
            revenue=purchase_value
        )
        db.add(db_event)

    # 2. If purchased, update financial data
    if event_type == "purchased" and customer_id is not None:
        product_name = metadata.get("product_name", "Apparel Item")
        category = metadata.get("category", "Apparel")

        # Update campaign revenue
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if campaign:
            if campaign.revenue is None:
                campaign.revenue = Decimal("0.0")
            campaign.revenue += purchase_value
            print(f"[REVENUE UPDATED] Campaign campaign_id={campaign_id} revenue updated to {campaign.revenue}", flush=True)

        # Update customer stats
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer:
            if customer.total_spend is None:
                customer.total_spend = Decimal("0.0")
            customer.total_spend += purchase_value
            customer.last_purchase = event_time.date()
            print(f"[CUSTOMER SPEND UPDATED] Customer customer_id={customer_id} total_spend updated to {customer.total_spend}", flush=True)

            # Recalculate segment dynamically
            if customer.total_spend > 20000:
                customer.segment = "High Value Customers"
            elif customer.total_spend > 10000:
                customer.segment = "Loyal Customers"
            else:
                customer.segment = "Regular Customers"

        # Record a new transactional Order
        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        db_order = Order(
            customer_id=customer_id,
            order_number=order_number,
            product_name=product_name,
            category=category,
            quantity=1,
            unit_price=purchase_value,
            total_amount=purchase_value,
            order_status="Completed",
            purchase_date=event_time,
            created_at=datetime.utcnow()
        )
        db.add(db_order)

    db.commit()
    return {"status": "processed"}

@router.post("")
@router.post("/")
async def webhook_callback_root(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    return handle_webhook_event(payload, db)

@router.post("/callback")
async def webhook_callback(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    return handle_webhook_event(payload, db)