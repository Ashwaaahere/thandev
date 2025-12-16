"""
Tests for plan validation
"""
import pytest
from app.models import PlanStep
from app.planner.plan import _validate_plan, _validate_params, _calculate_timeline
from app.catalog import load_catalog


def test_validate_plan_empty_steps():
    """Test that empty plan raises error"""
    catalog = load_catalog()
    
    with pytest.raises(ValueError, match="at least one step"):
        _validate_plan([], catalog)


def test_validate_plan_invalid_tool():
    """Test that invalid tool raises error"""
    catalog = load_catalog()
    
    invalid_step = PlanStep(
        step_id="step_1",
        tool_id="nonexistent_tool",
        mode_id="some_mode",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    with pytest.raises(ValueError, match="Invalid step"):
        _validate_plan([invalid_step], catalog)


def test_validate_plan_invalid_mode():
    """Test that invalid mode raises error"""
    catalog = load_catalog()
    
    invalid_step = PlanStep(
        step_id="step_1",
        tool_id="nuclei",
        mode_id="nonexistent_mode",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    with pytest.raises(ValueError, match="Invalid step"):
        _validate_plan([invalid_step], catalog)


def test_validate_plan_unknown_dependency():
    """Test that unknown dependency raises error"""
    catalog = load_catalog()
    
    step = PlanStep(
        step_id="step_1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=["unknown_step"],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    with pytest.raises(ValueError, match="depends on unknown step"):
        _validate_plan([step], catalog)


def test_validate_plan_cyclic_dependency():
    """Test that cyclic dependency raises error"""
    catalog = load_catalog()
    
    step1 = PlanStep(
        step_id="step_1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=["step_2"],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    step2 = PlanStep(
        step_id="step_2",
        tool_id="nmap",
        mode_id="top_ports",
        params={},
        depends_on=["step_1"],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    with pytest.raises(ValueError, match="Cycle detected"):
        _validate_plan([step1, step2], catalog)


def test_validate_plan_valid():
    """Test that valid plan passes validation"""
    catalog = load_catalog()
    
    step1 = PlanStep(
        step_id="step_1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    step2 = PlanStep(
        step_id="step_2",
        tool_id="nmap",
        mode_id="top_ports",
        params={},
        depends_on=["step_1"],
        reason="Test",
        estimated_duration_sec=200,
    )
    
    # Should not raise
    _validate_plan([step1, step2], catalog)


def test_validate_params_valid():
    """Test that valid params pass validation"""
    params_schema = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "additionalProperties": False
    }
    
    params = {"tags": ["cves", "xss"]}
    
    # Should not raise
    _validate_params(params, params_schema)


def test_validate_params_invalid_type():
    """Test that invalid param type raises error"""
    params_schema = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "additionalProperties": False
    }
    
    params = {"tags": "not_an_array"}
    
    with pytest.raises(ValueError, match="validation failed"):
        _validate_params(params, params_schema)


def test_validate_params_additional_properties():
    """Test that additional properties are rejected"""
    params_schema = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "additionalProperties": False
    }
    
    params = {"tags": ["cves"], "extra_field": "value"}
    
    with pytest.raises(ValueError, match="validation failed"):
        _validate_params(params, params_schema)


def test_calculate_timeline_parallel():
    """Test timeline calculation for parallel steps"""
    step1 = PlanStep(
        step_id="step_1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    step2 = PlanStep(
        step_id="step_2",
        tool_id="nmap",
        mode_id="top_ports",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=200,
    )
    
    timeline = _calculate_timeline([step1, step2])
    
    assert timeline.total_estimated_sec == 200  # Max of parallel steps
    assert len(timeline.phases) == 1
    assert timeline.phases[0]["parallel"] is True
    assert len(timeline.phases[0]["steps"]) == 2


def test_calculate_timeline_sequential():
    """Test timeline calculation for sequential steps"""
    step1 = PlanStep(
        step_id="step_1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    step2 = PlanStep(
        step_id="step_2",
        tool_id="ffuf",
        mode_id="pro",
        params={},
        depends_on=["step_1"],
        reason="Test",
        estimated_duration_sec=200,
    )
    
    timeline = _calculate_timeline([step1, step2])
    
    assert timeline.total_estimated_sec == 300  # Sum of sequential phases
    assert len(timeline.phases) == 2
    assert timeline.phases[0]["parallel"] is False
    assert timeline.phases[1]["parallel"] is False


def test_calculate_timeline_mixed():
    """Test timeline calculation for mixed parallel/sequential steps"""
    step1 = PlanStep(
        step_id="step_1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=100,
    )
    
    step2 = PlanStep(
        step_id="step_2",
        tool_id="nmap",
        mode_id="top_ports",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=200,
    )
    
    step3 = PlanStep(
        step_id="step_3",
        tool_id="ffuf",
        mode_id="pro",
        params={},
        depends_on=["step_1", "step_2"],
        reason="Test",
        estimated_duration_sec=300,
    )
    
    timeline = _calculate_timeline([step1, step2, step3])
    
    # Phase 1: max(100, 200) = 200
    # Phase 2: 300
    # Total: 200 + 300 = 500
    assert timeline.total_estimated_sec == 500
    assert len(timeline.phases) == 2
    assert timeline.phases[0]["parallel"] is True
    assert timeline.phases[1]["parallel"] is False




