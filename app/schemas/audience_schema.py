from pydantic import BaseModel


class AudienceRequest(BaseModel):
    prompt: str


class AudienceResponse(BaseModel):
    segment_name: str
    customer_count: int