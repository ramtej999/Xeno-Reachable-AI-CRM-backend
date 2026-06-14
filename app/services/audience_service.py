from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.customer import Customer
from app.services.groq_service import GroqService
from datetime import date, timedelta

class AudienceService:
    def __init__(self):
        self.groq_service = GroqService()

    def filter_customers_by_prompt(self, db: Session, prompt: str, user_id: int):
        """
        Parses the prompt, applies dynamic SQLAlchemy filters to the Customer model,
        and returns the matching customers along with the parsed filter criteria.
        """
        filters = self.groq_service.parse_audience_query(prompt, db=db, user_id=user_id)
        
        query = select(Customer).where(Customer.user_id == user_id)
        
        # Apply inactive days filter
        if filters.get("inactive_days") is not None:
            cutoff_date = date.today() - timedelta(days=int(filters["inactive_days"]))
            query = query.where(Customer.last_purchase <= cutoff_date)
            
        # Apply min spend filter
        if filters.get("min_spend") is not None:
            query = query.where(Customer.total_spend >= float(filters["min_spend"]))
            
        # Apply customer name filter
        if filters.get("name") is not None:
            query = query.where(
                Customer.name.ilike(f"%{filters['name']}%")
            )

        # Apply city filter
        if filters.get("city") is not None:
            query = query.where(
                Customer.city.ilike(f"%{filters['city']}%")
            )
            
        # Apply segment filter
        if filters.get("segment") is not None:
            query = query.where(
                Customer.segment.ilike(f"%{filters['segment']}%")
            )
            
        results = db.scalars(query).all()
        return results, filters
