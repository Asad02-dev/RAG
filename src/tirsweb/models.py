from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class Address(BaseModel):
    city: str
    state: str
    country: str

class InsuredEntity(BaseModel):
    legal_name: str
    dba_names: List[str] = Field(default_factory=list)
    fein: str
    primary_address: Optional[Address] = None
    employee_count: int = 0
    market_cap_usd: float = 0.0
    industry_naics_sic: str = ""
    sanctions_cleared: bool = False
    legal_standing: str = ""

class BrokerEntity(BaseModel):
    broker_firm: str
    producing_office: str = ""
    broker_contact_name: str = ""
    broker_email: str = ""
    commission_pct: float = 0.0

class Submission(BaseModel):
    tirs_submission_key: str
    status: str = "RECEIVED"
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    line_of_business: str = ""
    total_insurable_value: float = 0.0
    confidence_index: float = 0.0
    is_renewal: bool = False

class ClearanceRecord(BaseModel):
    clearance_id: str
    match_status: str
    match_score: float
    matched_prior_submission_keys: List[str] = Field(default_factory=list)
    conflict_flag: bool = False

class StitchAnalysisWorksheet(BaseModel):
    summary_one_pager: str = ""
    financial_metrics: Dict[str, Any] = Field(default_factory=dict)
    key_benefits_coverages: List[str] = Field(default_factory=list)
    terms_and_conditions: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    loss_history_analysis: Dict[str, Any] = Field(default_factory=dict)
    appetite_alignment_score: float = 0.0

class PolicyLayerQuote(BaseModel):
    layer_id: str
    attachment_point: float = 0.0
    layer_limit: float = 0.0
    deductible: float = 0.0
    gross_premium: float = 0.0
    rate_on_line: float = 0.0
    subjectivities: List[str] = Field(default_factory=list)
    quote_letter_uri: str = ""
    auto_quote_eligible: bool = False
    uw_assist_reasoning: str = ""

class TAActionRecord(BaseModel):
    action_type: str
    executed_by: str
    timestamp: datetime
    tirsweb_ui_receipt: str = ""
    status: str = ""

class FieldProvenanceRecord(BaseModel):
    field_id: str
    field_label: str
    assigned_value: Any
    action_type: str
    confidence_score: float
    rationale_short: str
    source_document: str = ""
    source_content_snippet: str = ""
    timestamp: datetime
