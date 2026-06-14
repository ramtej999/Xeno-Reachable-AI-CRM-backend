# Main FastAPI Application
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.customers import router as customers_router
from app.routes.audience import router as audience_router
from app.routes.campaigns import router as campaigns_router
from app.routes.analytics import router as analytics_router
from app.routes.copilot import router as copilot_router
from app.routes.negotiations import router as negotiations_router
from app.routes.webhook import router as webhook_router
from app.routes.testing import router as testing_router
from app.routes.auth import router as auth_router
from app.database import engine, Base, SessionLocal, get_db
from app.models.campaign import Campaign
from app.models.customer import Customer
from app.models.event import Event
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends
import threading
import time
from datetime import datetime, timezone
from app.services.campaign_service import CampaignService

Base.metadata.create_all(bind=engine)
with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS org VARCHAR(100);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS scheduled_time TIMESTAMP WITH TIME ZONE;"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS target_segment VARCHAR(100);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS launch_time TIMESTAMP WITHOUT TIME ZONE;"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS revenue NUMERIC(10, 2);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS current_offer NUMERIC(10, 2);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS max_discount NUMERIC(10, 2);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS strategy VARCHAR(50);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS groq_api_key_encrypted VARCHAR(255);"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_enabled BOOLEAN DEFAULT TRUE;"))
    except Exception:
        pass
    try:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS ai_usage_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                module VARCHAR(50) NOT NULL,
                endpoint VARCHAR(100) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        '''))
    except Exception:
        pass
    try:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS security_events (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                event_type VARCHAR(50) NOT NULL,
                prompt TEXT,
                module VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        '''))
    except Exception:
        pass

def run_scheduler():
    print("[SCHEDULER START] Background campaign scheduler thread started.", flush=True)
    campaign_service = CampaignService()
    while True:
        try:
            db = SessionLocal()
            now = datetime.now(timezone.utc)
            scheduled_campaigns = db.query(Campaign).filter(
                Campaign.status == "Scheduled",
                Campaign.scheduled_time <= now
            ).with_for_update(skip_locked=True).all()

            for cmp in scheduled_campaigns:
                print(f"[SCHEDULED CAMPAIGN FOUND] campaign_id={cmp.id} ('{cmp.campaign_name}') at {now}", flush=True)
                cmp.status = "Running"
                cmp.launch_time = datetime.utcnow()
                db.commit()

                # Get recipients using the saved target_segment and user_id of the campaign (no guessing!)
                query = db.query(Customer).filter(Customer.user_id == cmp.user_id)
                if cmp.target_segment:
                    query = query.filter(Customer.segment == cmp.target_segment)
                customers = query.all()

                if customers:
                    campaign_service.send_campaign_to_channel_service(cmp.id, [c.id for c in customers])
                    print(f"[CAMPAIGN LAUNCHED] campaign_id={cmp.id} dispatched to {len(customers)} recipients.", flush=True)
                else:
                    print(f"[SCHEDULER WARNING] No recipients found for scheduled campaign_id={cmp.id}. Completing it.", flush=True)
                    cmp.status = "Completed"
                    db.commit()
                    print(f"[CAMPAIGN COMPLETED] Campaign campaign_id={cmp.id} completed with no recipients.", flush=True)
            db.close()
        except Exception as e:
            print(f"[SCHEDULER ERROR] Exception in scheduler thread: {e}", flush=True)
        time.sleep(15)  # check every 15 seconds

app = FastAPI(
    title="Reachable AI CRM",
    version="1.0.0",
    description="AI Native CRM for Xeno Assignment"
)

@app.on_event("startup")
def startup_event():
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()


from fastapi import Request, Response
from app.config import settings

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# React Frontend Access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",")] if settings.CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(customers_router)
app.include_router(audience_router)
app.include_router(campaigns_router)
app.include_router(analytics_router)
app.include_router(copilot_router)
app.include_router(negotiations_router)
app.include_router(webhook_router)
app.include_router(testing_router)
app.include_router(auth_router)

@app.get("/debug/campaign/{campaign_id}/events")
def get_debug_campaign_events(campaign_id: int, db: Session = Depends(get_db)):
    events = db.query(Event).filter(Event.campaign_id == campaign_id).all()
    event_list = []
    for e in events:
        cust = db.query(Customer).filter(Customer.id == e.customer_id).first()
        event_list.append({
            "id": e.id,
            "customer_id": e.customer_id,
            "customer_name": cust.name if cust else "Unknown",
            "event_type": e.event_type,
            "event_time": e.event_time.isoformat() if e.event_time else None
        })
    return {
        "campaign_id": campaign_id,
        "count": len(events),
        "events": event_list
    }

@app.get("/")
def root():
    return {
        "status": "success",
        "message": "Reachable AI CRM Backend Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }