import urllib.request
import urllib.error
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.campaign import Campaign
from app.models.customer import Customer
from app.services.groq_service import GroqService
from app.config import settings
import time


class CampaignService:
    def __init__(self):
        self.groq_service = GroqService()

    def generate_and_save_campaign(self, db: Session, goal: str, audience_size: int, segment: str = None, channel: str = None, user_id: int = None):
        """
        Generates copy details for a campaign, saves it in PostgreSQL database,
        and returns the created campaign database record and content details.
        """
        copy = self.groq_service.generate_campaign(goal, segment, channel, db=db, user_id=user_id)

        # Normalize channel name format for frontend case-sensitivity
        norm_channel = "WhatsApp"
        target_channel = channel or copy.get("recommended_channel")
        if target_channel:
            c_low = target_channel.lower()
            if c_low == "whatsapp":
                norm_channel = "WhatsApp"
            elif c_low == "email":
                norm_channel = "Email"
            elif c_low == "sms":
                norm_channel = "SMS"
            else:
                norm_channel = target_channel.capitalize()

        db_campaign = Campaign(
            campaign_name=copy["campaign_name"],
            channel=norm_channel,
            audience_size=audience_size,
            status="Draft",
            revenue=0.0,
            user_id=user_id,
            target_segment=segment
        )
        db.add(db_campaign)
        db.commit()
        db.refresh(db_campaign)

        return db_campaign, copy

    def send_campaign_to_channel_service(self, campaign_id: int, customer_ids: list[int]):
        """
        Updates the campaign status and dispatches the recipients list to the separate Channel Service.
        Uses a self-managed database session to prevent FastAPI request-scoped session closure inside background tasks.
        Includes wake-up ping and retry logic to handle Render free-tier cold starts.
        """
        print(
            f"[DISPATCH CALLED] campaign_id={campaign_id}",
            flush=True
        )

        from app.database import SessionLocal
        db = SessionLocal()

        try:
            campaign = db.query(Campaign).filter(
                Campaign.id == campaign_id
            ).first()

            if not campaign:
                print(
                    f"[CAMPAIGN DISPATCH ERROR] Campaign with id={campaign_id} not found.",
                    flush=True
                )
                return False

            campaign.status = "Running"
            campaign.launch_time = datetime.utcnow()
            db.commit()

            customers = db.query(Customer).filter(
                Customer.id.in_(customer_ids)
            ).all()

            recipients = []
            for c in customers:
                recipients.append({
                    "customer_id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "phone": c.phone
                })

            print(
                f"[DEBUG] Webhook URL: {settings.CRM_WEBHOOK_URL}",
                flush=True
            )

            payload = {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "channel": campaign.channel,
                "recipients": recipients,
                "webhook_url": settings.CRM_WEBHOOK_URL
            }

            print(
                f"[CAMPAIGN DISPATCH] Initiating dispatch for campaign_id={campaign.id} ('{campaign.campaign_name}') via {campaign.channel} to {len(customers)} recipients...",
                flush=True
            )

            data = json.dumps(payload).encode("utf-8")

            # Wake up Channel Service first (handles Render free-tier cold start)
            try:
                urllib.request.urlopen(
                    settings.CHANNEL_SERVICE_URL,
                    timeout=30
                )
                print(
                    "[WAKEUP] Channel service pinged",
                    flush=True
                )
            except Exception as wakeup_error:
                print(
                    f"[WAKEUP WARNING] {wakeup_error}",
                    flush=True
                )

            # Wait for the service to fully wake up
            time.sleep(5)

            max_retries = 15

            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(
                        f"{settings.CHANNEL_SERVICE_URL}/send",
                        data=data,
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "ReachableAI-CRM/1.0"
                        }
                    )

                    print(
                        f"[DISPATCH ATTEMPT {attempt + 1}/{max_retries}]",
                        flush=True
                    )

                    with urllib.request.urlopen(req, timeout=30) as response:
                        res_data = json.loads(
                            response.read().decode()
                        )

                        print(
                            f"[CHANNEL RESPONSE] {res_data}",
                            flush=True
                        )

                        if res_data.get("status") == "accepted":
                            print(
                                f"[CAMPAIGN DISPATCH] Campaign {campaign.id} successfully queued in Channel Service.",
                                flush=True
                            )
                            return True

                except Exception as retry_error:
                    print(
                        f"[ATTEMPT FAILED] {retry_error}",
                        flush=True
                    )

                    if attempt < max_retries - 1:
                        print(
                            "[RETRYING IN 10 SECONDS]",
                            flush=True
                        )
                        time.sleep(10)
                    else:
                        campaign.status = "Failed"
                        db.commit()

                        print(
                            f"[CAMPAIGN DISPATCH ERROR] Failed to dispatch campaign_id={campaign_id}: {retry_error}",
                            flush=True
                        )
                        return False

        finally:
            db.close()

        return False
