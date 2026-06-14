from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.customer import Customer
from app.models.campaign import Campaign
from app.models.order import Order
from app.services.groq_service import GroqService

class CopilotService:
    def __init__(self):
        self.groq_service = GroqService()

    def query_copilot(self, db: Session, query: str, user_id: int) -> str:
        """
        Gathers database metrics and prompts Gemini with context to respond to strategy queries.
        """
        total_customers = db.query(func.count(Customer.id)).filter(Customer.user_id == user_id).scalar() or 0
        total_campaigns = db.query(func.count(Campaign.id)).filter(Campaign.user_id == user_id).scalar() or 0
        total_revenue = db.query(func.sum(Campaign.revenue)).filter(Campaign.user_id == user_id).scalar() or 0.0
        
        # Segment counts
        segments = db.query(Customer.segment, func.count(Customer.id)).filter(Customer.user_id == user_id).group_by(Customer.segment).all()
        segment_summary = ", ".join([f"{seg or 'Unknown'}: {count}" for seg, count in segments])

        # Orders stats
        total_orders = db.query(func.count(Order.id)).join(Customer).filter(Customer.user_id == user_id).scalar() or 0
        avg_spend = db.query(func.avg(Customer.total_spend)).filter(Customer.user_id == user_id).scalar() or 0.0

        db_context = (
            f"CRM Stats Summary:\n"
            f"- Total customers: {total_customers}\n"
            f"- Customers by segment: {segment_summary}\n"
            f"- Total campaigns run: {total_campaigns}\n"
            f"- Total campaign revenue: ₹{float(total_revenue):,.2f}\n"
            f"- Total orders: {total_orders}\n"
            f"- Average customer lifetime spend: ₹{float(avg_spend):,.2f}\n"
        )

        formatting_instructions = (
            "\n\n==================================================\n"
            "FORMATTING REQUIREMENT:\n"
            "If the user is simply greeting you (e.g., 'hello', 'hi') or making small talk, respond naturally and politely as a helpful AI assistant.\n\n"
            "However, if the user asks for insights, analysis, data, or CRM strategy, you MUST format your response professionally as a Senior CRM Growth Consultant. "
            "Use headings, clear bullet points, markdown tables, and action sections. "
            "Do NOT write large, verbose paragraphs. Structure the response using this format:\n\n"
            "📊 Current Situation\n"
            "(Bullet points summarizing the current metrics, trends, or issues)\n\n"
            "👥 Segment Analysis\n"
            "| Segment | Count | Priority/Opportunity |\n"
            "| :--- | :--- | :--- |\n"
            "(Include a markdown table representing relevant customer segment data or comparison)\n\n"
            "🚀 Recommended Actions\n"
            "(Bulleted list of highly actionable, step-by-step outreach strategies or campaign advice)\n\n"
            "📈 Expected Impact\n"
            "(Bulleted expected outcomes, conversion lifts, e.g. '+14.2% expected conversion lift')\n\n"
            "Keep the language clear, executive, and highly structured."
        )
        db_context += formatting_instructions

        return self.groq_service.copilot_query(query, db_context, db=db, user_id=user_id)
