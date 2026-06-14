from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.customer import Customer
from app.models.campaign import Campaign
from app.models.event import Event

class AnalyticsService:
    def get_analytics(self, db: Session, user_id: int):
        """
        Gathers general dashboard analytics metrics by aggregating customer, campaign, and event logs.
        """
        total_customers = db.query(func.count(Customer.id)).filter(Customer.user_id == user_id).scalar() or 0
        total_campaigns = db.query(func.count(Campaign.id)).filter(Campaign.user_id == user_id).scalar() or 0
        
        sent = db.query(func.count(Event.id)).join(Campaign).filter(Campaign.user_id == user_id, Event.event_type == "sent").scalar() or 0
        delivered = db.query(func.count(Event.id)).join(Campaign).filter(Campaign.user_id == user_id, Event.event_type == "delivered").scalar() or 0
        opened = db.query(func.count(Event.id)).join(Campaign).filter(Campaign.user_id == user_id, Event.event_type == "opened").scalar() or 0
        clicked = db.query(func.count(Event.id)).join(Campaign).filter(Campaign.user_id == user_id, Event.event_type == "clicked").scalar() or 0
        purchased = db.query(func.count(Event.id)).join(Campaign).filter(Campaign.user_id == user_id, Event.event_type == "purchased").scalar() or 0
        
        revenue = db.query(func.sum(Campaign.revenue)).filter(Campaign.user_id == user_id).scalar() or 0.0

        # Calculations
        open_rate = (opened / delivered * 100.0) if delivered > 0 else 0.0
        ctr = (clicked / opened * 100.0) if opened > 0 else 0.0
        conversion_rate = (purchased / clicked * 100.0) if clicked > 0 else 0.0
        
        # Spend estimation: ₹0.50 per sent outreach message
        spend = sent * 0.50
        campaign_roi = ((float(revenue) - spend) / spend * 100.0) if spend > 0.0 else 0.0

        return {
            "total_customers": total_customers,
            "total_campaigns": total_campaigns,
            "messages_sent": sent,
            "delivered": delivered,
            "opened": opened,
            "clicked": clicked,
            "purchased": purchased,
            "revenue_generated": float(revenue),
            "open_rate": round(open_rate, 2),
            "ctr": round(ctr, 2),
            "conversion_rate": round(conversion_rate, 2),
            "campaign_roi": round(campaign_roi, 2)
        }
