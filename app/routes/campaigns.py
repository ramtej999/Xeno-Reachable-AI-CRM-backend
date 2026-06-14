from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.campaign import Campaign
from app.models.customer import Customer
from app.models.event import Event
from app.schemas.campaign_schema import (
    CampaignCreate, CampaignResponse, CampaignGenerateRequest, CampaignGenerateResponse
)
from app.services.campaign_service import CampaignService
from app.routes.auth import get_current_user
from app.models.user import User
from typing import List

router = APIRouter(
    prefix="/campaigns",
    tags=["Campaign Studio"]
)

from pydantic import BaseModel
from datetime import datetime

class CampaignScheduleRequest(BaseModel):
    scheduled_time: datetime

from sqlalchemy import func

@router.get("/", response_model=List[CampaignResponse])
def get_campaigns(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    campaigns = db.query(Campaign).filter(Campaign.user_id == current_user.id).order_by(Campaign.id.desc()).all()
    for c in campaigns:
        sent_count = db.query(Event).filter(Event.campaign_id == c.id, Event.event_type == "sent").count()
        delivered_count = db.query(Event).filter(Event.campaign_id == c.id, Event.event_type == "delivered").count()
        opened_count = db.query(Event).filter(Event.campaign_id == c.id, Event.event_type == "opened").count()
        clicked_count = db.query(Event).filter(Event.campaign_id == c.id, Event.event_type == "clicked").count()
        purchased_count = db.query(Event).filter(Event.campaign_id == c.id, Event.event_type == "purchased").count()
        c.failed = db.query(Event).filter(Event.campaign_id == c.id, Event.event_type == "failed").count()

        # Enforce metrics consistency via temporary safety guards
        c.purchased = purchased_count
        c.clicked = max(clicked_count, c.purchased)
        c.opened = max(opened_count, c.clicked)
        c.delivered = max(delivered_count, c.opened)
        c.sent = max(sent_count, c.delivered)
        
        # Dynamically calculate attributed revenue from the events table
        revenue_sum = db.query(func.sum(Event.revenue)).filter(Event.campaign_id == c.id, Event.event_type == "purchased").scalar()
        c.revenue = float(revenue_sum) if revenue_sum is not None else 0.0
    return campaigns

@router.post("/generate")
def generate_campaign(
    payload: CampaignGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CampaignService()
    # Find base audience size of the target segment for the current user
    if payload.segment:
        audience_size = db.query(Customer).filter(
            Customer.user_id == current_user.id,
            Customer.segment.ilike(f"%{payload.segment}%")
        ).count()
    else:
        audience_size = db.query(Customer).filter(Customer.user_id == current_user.id).count()
    
    campaign, copy = service.generate_and_save_campaign(
        db,
        payload.goal,
        audience_size,
        payload.segment,
        payload.channel,
        current_user.id
    )
    return {
        "campaign": CampaignResponse.model_validate(campaign),
        "copy": copy
    }

@router.post("/{id}/send")
def send_campaign(
    id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaign = db.query(Campaign).filter(Campaign.id == id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Determine target segment and filter only current user's customers belonging to the segment (no guessing!)
    if campaign.target_segment:
        customers = db.query(Customer).filter(
            Customer.user_id == current_user.id,
            Customer.segment == campaign.target_segment
        ).all()
    else:
        customers = db.query(Customer).filter(
            Customer.user_id == current_user.id
        ).all()

    if not customers:
        raise HTTPException(status_code=400, detail="No target customers found for this campaign segment")

    # Run sending asynchronously in a background task
    campaign_service = CampaignService()
    customer_ids = [c.id for c in customers]
    background_tasks.add_task(
        campaign_service.send_campaign_to_channel_service,
        campaign.id,
        customer_ids
    )

    return {
        "status": "success",
        "message": f"Campaign sending initiated for {len(customers)} recipients."
    }

@router.post("/{id}/schedule")
def schedule_campaign(
    id: int,
    payload: CampaignScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaign = db.query(Campaign).filter(Campaign.id == id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "Scheduled"
    campaign.scheduled_time = payload.scheduled_time
    db.commit()
    return {"status": "success", "message": f"Campaign scheduled for {payload.scheduled_time}"}

@router.post("/{id}/cancel")
def cancel_campaign(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaign = db.query(Campaign).filter(Campaign.id == id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != "Scheduled":
        raise HTTPException(status_code=400, detail="Only scheduled campaigns can be cancelled.")
    campaign.status = "Cancelled"
    campaign.scheduled_time = None
    campaign.launch_time = None
    db.commit()
    return {"status": "success", "message": "Campaign schedule cancelled."}

@router.get("/{id}/performance")
def get_campaign_performance(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaign = db.query(Campaign).filter(Campaign.id == id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Query all events for this campaign
    events = db.query(Event).filter(Event.campaign_id == id).all()

    # Group events by customer_id
    from collections import defaultdict
    customer_events = defaultdict(list)
    for e in events:
        customer_events[e.customer_id].append(e.event_type)

    customer_ids = list(customer_events.keys())
    customers = db.query(Customer).filter(Customer.id.in_(customer_ids)).all() if customer_ids else []

    records = []
    for c in customers:
        types = customer_events[c.id]
        status = "Sent"
        if "purchased" in types:
            status = "Purchased"
        elif "clicked" in types:
            status = "Clicked"
        elif "opened" in types:
            status = "Opened"
        elif "delivered" in types:
            status = "Delivered"
        elif "failed" in types:
            status = "Failed"

        records.append({
            "customer_name": c.name,
            "customer_id": c.id,
            "status": status,
            "sent": "sent" in types,
            "delivered": "delivered" in types,
            "opened": "opened" in types,
            "clicked": "clicked" in types,
            "purchased": "purchased" in types,
            "failed": "failed" in types
        })

    return {
        "campaign_id": id,
        "campaign_name": campaign.campaign_name,
        "performance": records
    }