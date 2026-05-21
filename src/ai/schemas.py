from pydantic import BaseModel, Field


class OrderStatus(BaseModel):
    sequence: int | None = None
    description: str | None = None
    status: str | None = None
    observation: str | None = None


class ExtractionResult(BaseModel):
    found: bool
    protocol_number: str | None = None
    cnpj: str | None = None
    external_status: str | None = None
    external_situation: str | None = None
    last_movement_date: str | None = None
    observation: str | None = None
    agency: str | None = None
    oficio: str | None = None
    orders: list[OrderStatus] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    error: dict | None = None
