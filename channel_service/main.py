from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from channel_service.simulator import run_campaign_simulation

app = FastAPI(
    title="Reachable AI Channel Service Simulator",
    version="1.0.0",
    description="Simulates channels (WhatsApp, Email, SMS) delivery metrics and triggers callbacks."
)

class Recipient(BaseModel):
    customer_id: int
    name: str
    email: str
    phone: str

class SendCampaignRequest(BaseModel):
    campaign_id: int
    campaign_name: str
    channel: str
    recipients: List[Recipient]
    webhook_url: str

@app.post("/send")
def send_campaign(
    payload: SendCampaignRequest,
    background_tasks: BackgroundTasks
):
    """
    Accepts campaign info and initiates non-blocking delivery simulation.
    """
    recipients_list = [
        {
            "customer_id": r.customer_id,
            "name": r.name,
            "email": r.email,
            "phone": r.phone
        }
        for r in payload.recipients
    ]

    background_tasks.add_task(
        run_campaign_simulation,
        webhook_url=payload.webhook_url,
        campaign_id=payload.campaign_id,
        recipients=recipients_list,
        channel=payload.channel
    )

    return {"status": "accepted", "message": f"Outreach simulation queued for {len(recipients_list)} users."}

@app.get("/")
def root():
    return {"status": "running", "service": "Channel Simulator"}
