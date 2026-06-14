from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.analytics_schema import AnalyticsResponse
from app.services.analytics_service import AnalyticsService
from app.routes.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics Dashboard"]
)

@router.get("/stats", response_model=AnalyticsResponse)
def get_analytics_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = AnalyticsService()
    stats = service.get_analytics(db, current_user.id)
    return stats