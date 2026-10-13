from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Trigger(BaseModel):
    event: str
    received_at: datetime
    event_age_s: int

class Goal(BaseModel):
    id: str
    deadline: datetime

class DialectInfo(BaseModel):
    used: str
    source: str
    conflicts: List[str] = []

class Checks(BaseModel):
    passed: List[str] = []
    failed: List[str] = []

class DecisionOutput(BaseModel):
    """The exact output format required by the evaluator."""
    decision_id: str
    viewer_id: str
    trigger: Trigger
    goal: Optional[Goal] = None
    action: str = Field(..., description="HOME_PAGE, PUSH, WHATSAPP, IN_APP_MESSAGE, or NO_ACTION")
    dialect: Optional[DialectInfo] = None
    content: List[str] = []
    confidence: float
    evidence: List[str] = []
    assumptions: List[str] = []
    checks: Checks
    decided_in_ms: int
    status: str = Field(..., description="PUBLISHED or NO_ACTION")

class ViewerState(BaseModel):
    """Durable state maintained per viewer across triggers."""
    user_id: str
    signup_at: Optional[datetime] = None
    subscription_status: str = "never"
    preferred_dialect: str = "unknown"
    dialect_source: str = "none"
    notifications_opt_in: bool = False
    whatsapp_opt_in: bool = False
    last_message_sent_ist_date: Optional[str] = None
    active_goal_id: Optional[str] = None
    active_goal_deadline: Optional[datetime] = None
    completed_episodes: List[str] = []
    started_plays: List[str] = []