from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class TaskLimits(BaseModel):
    max_steps: int = Field(default=30, ge=1)
    timeout_sec: int = Field(default=120, ge=1)


class SuccessCriterion(FlexibleModel):
    type: str


class TaskSpec(BaseModel):
    id: str
    product: str
    instruction: str
    slots: dict[str, Any] = Field(default_factory=dict)
    success_criteria: list[SuccessCriterion] = Field(default_factory=list)
    limits: TaskLimits = Field(default_factory=TaskLimits)
    risk_level: str = "low"


class StepGoal(BaseModel):
    index: int
    description: str
    target: str
    expected: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    step_index: int
    screen_summary: str
    screenshot_path: str | None = None
    ocr_texts: list[dict[str, Any]] = Field(default_factory=list)
    accessibility_candidates: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    type: str
    target: str | None = None
    text: str | None = None
    coordinates: tuple[int, int] | None = None
    mock: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class Verdict(BaseModel):
    status: Literal["pass", "fail", "blocked", "uncertain"]
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    extracted_state: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    timestamp: str
    event_type: str
    step_index: int | None = None
    observation: Observation | None = None
    action: Action | None = None
    verdict: Verdict | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    task_id: str
    run_id: str
    status: Literal["running", "pass", "fail", "blocked", "uncertain"] = "running"
    trace_dir: str
    events: list[TraceEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
