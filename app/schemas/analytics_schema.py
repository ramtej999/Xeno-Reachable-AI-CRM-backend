from pydantic import BaseModel


class AnalyticsResponse(BaseModel):
    total_customers: int
    total_campaigns: int
    messages_sent: int
    delivered: int
    opened: int
    clicked: int
    purchased: int
    revenue_generated: float
    open_rate: float
    ctr: float
    conversion_rate: float
    campaign_roi: float