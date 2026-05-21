from pydantic import BaseModel


class ScrapingJobMessage(BaseModel):
    job_id: str
    protocol_id: str
    stakeholder_id: str


class AiExtractionJobMessage(BaseModel):
    job_id: str
    protocol_id: str
    stakeholder_id: str
    content_id: str


class AiExtractionResultMessage(BaseModel):
    job_id: str
    protocol_id: str
    stakeholder_id: str
    found: bool
    protocol_number: str | None = None
    external_status: str | None = None
    external_situation: str | None = None
    last_movement_date: str | None = None
    observation: str | None = None
    confidence: float = 0.0
    error: dict | None = None


class FailedJobMessage(BaseModel):
    job_id: str
    protocol_id: str
    stage: str  # scraping | cleaning | ai_extraction | api_delivery
    error_type: str
    error_message: str
