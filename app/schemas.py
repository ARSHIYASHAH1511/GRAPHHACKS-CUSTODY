from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class RunDemoRequest(BaseModel):
    mode: str = Field(..., description="off | naive | custody")
    scenario_id: str = Field("scenario_001", description="Scenario to run")


class EvaluationResult(BaseModel):
    mode: str
    claim_id: str
    decision: str
    reason_code: str
    evidence: List[str] = []
    provenance: List[Dict[str, Any]] = []
    explanation: str
    session_id: str
    decision_id: str


class DemoResult(BaseModel):
    scenario_id: str
    mode: str
    researcher_session: str
    assistant_session: str
    research_observations: List[Dict[str, Any]]
    evaluations: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    graph: str


class ResetResponse(BaseModel):
    status: str
    message: str


class ObservationRequest(BaseModel):
    agent_id: str
    session_id: str
    claim: Dict[str, Any]
    source_id: str


class ProvenanceResponse(BaseModel):
    claim_id: str
    provenance: List[Dict[str, Any]]
