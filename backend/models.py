from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

Category = Literal['unknown', 'cyber_fraud', 'suspicious_content', 'broker', 'demat', 'unauthorized_trade', 'payout', 'kyc', 'transmission', 'mutual_fund', 'listed_company']
Language = Literal['en', 'hi', 'bn', 'ta', 'te', 'mr']

class Facts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Category = 'unknown'
    description: str = Field(default='', max_length=12000)
    entity_name: str | None = Field(default=None, max_length=200)
    amount: float | None = Field(default=None, ge=0, le=1e12)
    incident_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=80)
    transaction_reference: str | None = Field(default=None, max_length=100)
    recipient: str | None = Field(default=None, max_length=200)
    money_transferred: bool | None = None
    entity_contacted: bool = False
    entity_complaint_reference: str | None = Field(default=None, max_length=100)
    holding_type: Literal['demat', 'physical', 'unknown'] = 'unknown'
    desired_resolution: str | None = Field(default=None, max_length=1000)

class Extraction(BaseModel):
    facts: Facts
    normalized_text: str
    reply: str
    out_of_scope: bool

class NewCase(BaseModel):
    language: Language = 'en'
    ai_consent: bool = False
    preferred_channel: Literal['in_app', 'sms_demo', 'whatsapp_demo'] = 'in_app'

class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=12000)

class ConfirmFacts(BaseModel):
    facts: Facts
    revision: int

class Submission(BaseModel):
    approved: bool
    revision: int
    idempotency_key: str = Field(min_length=8, max_length=100)

class Acknowledgement(BaseModel):
    portal: Literal['entity', 'SCORES', 'NCRP', 'offline', 'review_1', 'review_2']
    reference_number: str = Field(min_length=3, max_length=100)
    occurred_at: datetime
    confirmed: bool

class ResponseIn(BaseModel):
    text: str = Field(min_length=10, max_length=16000)
    received_at: datetime
    source: Literal['entity', 'SCORES_ENTITY_ATR', 'SCORES_REVIEW_1_ATR']

class Decision(BaseModel):
    satisfied: bool

class FraudResult(BaseModel):
    risk_score: float = Field(ge=0, le=1)
    category: str = Field(max_length=150)
    signals: list[str] = Field(max_length=30)

class Preferences(BaseModel):
    language: Language
    ai_consent: bool
    preferred_channel: Literal['in_app', 'sms_demo', 'whatsapp_demo']
