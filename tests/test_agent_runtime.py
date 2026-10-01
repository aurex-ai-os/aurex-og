import pytest
from datetime import datetime, timezone
import uuid
import json
from sqlalchemy.orm import Session
from core.database import SessionLocal, engine, Base
from src.agent_runtime.persistence import DbTask, DbAgentRun, AgentPersistence
from src.agent_runtime.models import AgentRunModel, TaskModel, Plan, PlanStep, ArtifactReference
from src.agent_runtime.state_machine import AgentState, StateMachine, InvalidStateTransitionError
from sqlalchemy.orm.exc import StaleDataError

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def db_session(setup_db):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

# STATE MACHINE TESTS
def test_state_machine_valid_transitions():
    assert StateMachine.can_transition(AgentState.CREATED, AgentState.PLANNING)
    StateMachine.validate_transition(AgentState.MODEL_PRODUCED_TOOL, AgentState.WAITING_FOR_APPROVAL)
    StateMachine.validate_transition(AgentState.WAITING_FOR_APPROVAL, AgentState.EXECUTING_TOOL)
    StateMachine.validate_transition(AgentState.EXECUTING_TOOL, AgentState.TOOL_COMPLETED)
    StateMachine.validate_transition(AgentState.TOOL_COMPLETED, AgentState.OBSERVING)
    StateMachine.validate_transition(AgentState.OBSERVING, AgentState.READY)

def test_state_machine_invalid_transitions():
    assert not StateMachine.can_transition(AgentState.COMPLETED, AgentState.EXECUTING_TOOL)
    with pytest.raises(InvalidStateTransitionError):
        StateMachine.validate_transition(AgentState.FAILED, AgentState.READY)

def test_terminal_states_cannot_transition():
    assert len(StateMachine.VALID_TRANSITIONS[AgentState.COMPLETED]) == 0
    assert len(StateMachine.VALID_TRANSITIONS[AgentState.FAILED]) == 0
    assert len(StateMachine.VALID_TRANSITIONS[AgentState.CANCELLED]) == 0

def test_cancellation_from_active_states():
    # Test cancellation from every active state
    for state in StateMachine.VALID_TRANSITIONS:
        if not StateMachine.is_terminal(state):
            assert AgentState.CANCELLED in StateMachine.VALID_TRANSITIONS[state], f"Should be able to cancel from {state}"

def test_approval_rejection_and_pause():
    assert StateMachine.can_transition(AgentState.WAITING_FOR_APPROVAL, AgentState.REPLANNING)
    assert StateMachine.can_transition(AgentState.WAITING_FOR_APPROVAL, AgentState.PAUSED)
    assert StateMachine.can_transition(AgentState.PAUSED, AgentState.WAITING_FOR_APPROVAL)
    assert StateMachine.can_transition(AgentState.PAUSED, AgentState.READY)

def test_verification_failure():
    assert StateMachine.can_transition(AgentState.VERIFYING, AgentState.REPLANNING)

# PERSISTENCE & OWNERSHIP TESTS
def test_persistence_full_lifecycle(db_session: Session):
    task_id = str(uuid.uuid4())
    db_session.add(DbTask(id=task_id, user_id="user1", project_id="proj1", objective="Research"))
    db_session.commit()
    
    run_id = str(uuid.uuid4())
    db_run = DbAgentRun(
        id=run_id,
        session_id="session1",
        user_id="user1",
        project_id="proj1",
        task_id=task_id,
        goal="Find docs",
        status=AgentState.CREATED
    )
    db_session.add(db_run)
    db_session.commit()
    
    loaded_run = db_session.query(DbAgentRun).filter_by(id=run_id).first()
    pydantic_model = AgentPersistence._to_pydantic_run(loaded_run)
    
    # Update various fields
    pydantic_model.status = AgentState.OBSERVING
    pydantic_model.plan = Plan(steps=[PlanStep(step_id="1", description="Read files")])
    pydantic_model.current_step = "1"
    pydantic_model.observations = [{"obs": "found something"}]
    pydantic_model.pending_approval = {"action": "delete_file"}
    pydantic_model.verification_result = {"passed": True}
    
    AgentPersistence._update_db_run(loaded_run, pydantic_model)
    db_session.commit()
    
    # Reload and verify
    reloaded_run = db_session.query(DbAgentRun).filter_by(id=run_id).first()
    assert reloaded_run.status == AgentState.OBSERVING
    assert reloaded_run.plan["steps"][0]["description"] == "Read files"
    assert reloaded_run.current_step == "1"
    assert reloaded_run.observations[0]["obs"] == "found something"
    assert reloaded_run.pending_approval["action"] == "delete_file"
    assert reloaded_run.verification_result["passed"] is True

def test_ownership_isolation(db_session: Session):
    # API layer handles 403s, but we verify fields exist and can be filtered
    task_id = str(uuid.uuid4())
    db_session.add(DbTask(id=task_id, user_id="user_A", project_id="proj_A", objective="test"))
    db_session.commit()
    
    run_id = str(uuid.uuid4())
    db_session.add(DbAgentRun(id=run_id, session_id="sess_A", user_id="user_A", project_id="proj_A", task_id=task_id, goal="test"))
    db_session.commit()
    
    # user B trying to load user A's run would do filter_by(user_id="user_B")
    run_user_b = db_session.query(DbAgentRun).filter_by(id=run_id, user_id="user_B").first()
    assert run_user_b is None
    
    run_user_a = db_session.query(DbAgentRun).filter_by(id=run_id, user_id="user_A").first()
    assert run_user_a is not None

# CONCURRENCY TESTS
def test_concurrent_update_protection(db_session: Session):
    task_id = str(uuid.uuid4())
    db_session.add(DbTask(id=task_id, user_id="u1", objective="concurrency test"))
    db_session.commit()
    
    run_id = str(uuid.uuid4())
    db_session.add(DbAgentRun(id=run_id, session_id="s1", user_id="u1", task_id=task_id, goal="test"))
    db_session.commit()
    
    session1 = SessionLocal()
    session2 = SessionLocal()
    
    run1 = session1.query(DbAgentRun).filter_by(id=run_id).first()
    run2 = session2.query(DbAgentRun).filter_by(id=run_id).first()
    
    run1.status = AgentState.READY
    session1.commit()
    
    run2.status = AgentState.FAILED
    with pytest.raises(StaleDataError):
        session2.commit()
        
    session1.close()
    session2.close()

# SECRET HANDLING TESTS
def test_secret_scrubbing():
    dirty_data = {
        "api_key": "sk-12345", 
        "nested": {"password": "abc", "authorization": "Bearer xyz"},
        "safe_value": "hello",
        "secret_token": "hidden"
    }
    clean_data = AgentPersistence._scrub_secrets(dirty_data)
    assert clean_data["api_key"] == "***SCRUBBED***"
    assert clean_data["nested"]["password"] == "***SCRUBBED***"
    assert clean_data["nested"]["authorization"] == "***SCRUBBED***"
    assert clean_data["secret_token"] == "***SCRUBBED***"
    assert clean_data["safe_value"] == "hello"

def test_secret_scrubbing_in_persistence(db_session: Session):
    task_id = str(uuid.uuid4())
    db_session.add(DbTask(id=task_id, user_id="u1", objective="test"))
    db_session.commit()
    
    run_id = str(uuid.uuid4())
    db_run = DbAgentRun(id=run_id, session_id="s1", user_id="u1", task_id=task_id, goal="test", status=AgentState.CREATED)
    db_session.add(db_run)
    db_session.commit()
    
    loaded = db_session.query(DbAgentRun).filter_by(id=run_id).first()
    model = AgentPersistence._to_pydantic_run(loaded)
    model.current_tool_call = {"tool": "login", "api_key": "my_super_secret"}
    
    AgentPersistence._update_db_run(loaded, model)
    db_session.commit()
    
    reloaded = db_session.query(DbAgentRun).filter_by(id=run_id).first()
    assert reloaded.current_tool_call["tool"] == "login"
    assert reloaded.current_tool_call["api_key"] == "***SCRUBBED***"

# RECOVERY TESTS
def test_recovery_from_paused(db_session: Session):
    task_id = str(uuid.uuid4())
    db_session.add(DbTask(id=task_id, user_id="u1", objective="test"))
    db_session.commit()
    
    run_id = str(uuid.uuid4())
    db_run = DbAgentRun(id=run_id, session_id="s1", user_id="u1", task_id=task_id, goal="test", status=AgentState.PAUSED)
    db_session.add(db_run)
    db_session.commit()
    
    loaded = db_session.query(DbAgentRun).filter_by(id=run_id).first()
    assert loaded.status == AgentState.PAUSED
    assert StateMachine.can_transition(loaded.status, AgentState.READY)
