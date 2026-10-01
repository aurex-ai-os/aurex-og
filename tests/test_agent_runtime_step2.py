import pytest
import asyncio
from typing import List
from src.agent_runtime.runtime import AgentRuntime
from src.agent_runtime.events import runtime_events, RuntimeEvent
from src.agent_runtime.state_machine import AgentState
from core.database import Base, engine, SessionLocal

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def event_listener():
    events: List[RuntimeEvent] = []
    def handler(e):
        events.append(e)
    runtime_events.add_handler(handler)
    return events

@pytest.mark.asyncio
async def test_runtime_first_increment(setup_db, event_listener):
    # 1. create/run persistence
    run = AgentRuntime.create_run(user_id="u1", session_id="s1", goal="Test goal")
    assert run.goal == "Test goal"
    assert run.status == AgentState.CREATED
    
    # Check events
    assert any(e.event_type == "run.created" and e.run_id == run.run_id for e in event_listener)
    event_listener.clear()
    
    # 2. start_run state transitions and integration
    await AgentRuntime.start_run(run.run_id)
    
    # Reload and verify state is safely stopped at MODEL_PRODUCED_TOOL
    reloaded = AgentRuntime.get_run(run.run_id)
    assert reloaded.status == AgentState.MODEL_PRODUCED_TOOL
    assert reloaded.current_tool_call["tool"] == "search"
    
    # Check event ordering
    event_types = [e.event_type for e in event_listener if e.run_id == run.run_id]
    expected_order = [
        "run.started",
        "run.state_changed", # UNDERSTANDING
        "context.prepared",
        "model.selected",
        "run.state_changed", # PLANNING
        "run.state_changed", # READY
        "run.state_changed", # WAITING_FOR_MODEL
        "model.started",
        "run.state_changed", # MODEL_PRODUCED_TOOL
        "model.completed",
        "tool.pending"
    ]
    # Ensure they appeared in this order
    last_idx = -1
    for ev in expected_order:
        idx = event_types.index(ev, last_idx + 1)
        assert idx > last_idx
        last_idx = idx

@pytest.mark.asyncio
async def test_runtime_cancellation(setup_db):
    run = AgentRuntime.create_run(user_id="u2", session_id="s2", goal="Cancel me")
    assert run.status == AgentState.CREATED
    
    AgentRuntime.cancel_run(run.run_id)
    
    reloaded = AgentRuntime.get_run(run.run_id)
    assert reloaded.status == AgentState.CANCELLED

@pytest.mark.asyncio
async def test_ownership_isolation(setup_db):
    run_a = AgentRuntime.create_run(user_id="userA", session_id="sA", goal="A")
    run_b = AgentRuntime.create_run(user_id="userB", session_id="sB", goal="B")
    
    with SessionLocal() as db:
        from src.agent_runtime.persistence import DbAgentRun
        # Verify completely independent records
        rA = db.query(DbAgentRun).filter_by(id=run_a.run_id).first()
        rB = db.query(DbAgentRun).filter_by(id=run_b.run_id).first()
        assert rA.user_id == "userA"
        assert rB.user_id == "userB"
