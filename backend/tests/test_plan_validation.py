"""
Unit tests for PlanExecutionValidator

Tests for PR-1: Catalog + strict plan validation
"""
import pytest
import json
import sys
from pathlib import Path

# Add packages to path
packages_path = Path(__file__).parent.parent.parent.parent / "packages"
if str(packages_path) not in sys.path:
    sys.path.insert(0, str(packages_path))

from thandev_schemas.planning import PlanScanResponse, PlanStep, Timeline
from app.services.ai.plan_validation import PlanExecutionValidator, PlanValidationError


# Test catalog path (relative to backend/)
TEST_CATALOG_PATH = Path(__file__).parent.parent / "services" / "thandev-brain" / "catalog" / "catalog.json"


@pytest.fixture
def validator():
    """Create a PlanExecutionValidator instance"""
    if TEST_CATALOG_PATH.exists():
        return PlanExecutionValidator(catalog_path=TEST_CATALOG_PATH)
    else:
        pytest.skip(f"Catalog file not found at {TEST_CATALOG_PATH}")


@pytest.fixture
def valid_plan():
    """Create a valid plan for testing"""
    return PlanScanResponse(
        plan_id="test-plan-1",
        steps=[
            PlanStep(
                step_id="step1",
                tool_id="nuclei",
                mode_id="basic_web",
                params={"tags": ["cves"], "severity": ["critical", "high"]},
                depends_on=[],
                reason="Initial vulnerability scan",
                estimated_duration_sec=300,
            ),
            PlanStep(
                step_id="step2",
                tool_id="httpx",
                mode_id="low",
                params={},
                depends_on=["step1"],
                reason="HTTP probe after nuclei",
                estimated_duration_sec=60,
            ),
        ],
        timeline=Timeline(
            total_estimated_sec=360,
            phases=[],
        ),
    )


def test_valid_plan_passes(validator, valid_plan):
    """Test that a valid plan passes validation"""
    # Should not raise
    validator.validate_plan(valid_plan, target_type="http")


def test_invalid_tool_id_rejected(validator, valid_plan):
    """Test that invalid tool_id is rejected"""
    invalid_step = PlanStep(
        step_id="step1",
        tool_id="nonexistent_tool",
        mode_id="basic_web",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=300,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[invalid_step],
        timeline=Timeline(total_estimated_sec=300, phases=[]),
    )
    
    with pytest.raises(PlanValidationError, match="Invalid tool_id"):
        validator.validate_plan(plan, target_type="http")


def test_invalid_mode_id_rejected(validator, valid_plan):
    """Test that invalid mode_id is rejected"""
    invalid_step = PlanStep(
        step_id="step1",
        tool_id="nuclei",
        mode_id="nonexistent_mode",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=300,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[invalid_step],
        timeline=Timeline(total_estimated_sec=300, phases=[]),
    )
    
    with pytest.raises(PlanValidationError, match="Invalid mode_id"):
        validator.validate_plan(plan, target_type="http")


def test_extra_params_rejected(validator):
    """Test that extra params (not in schema) are rejected"""
    # Nuclei basic_web mode only allows "tags" and "severity"
    invalid_step = PlanStep(
        step_id="step1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={
            "tags": ["cves"],
            "severity": ["critical"],
            "extra_param": "not_allowed",  # This should be rejected
        },
        depends_on=[],
        reason="Test",
        estimated_duration_sec=300,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[invalid_step],
        timeline=Timeline(total_estimated_sec=300, phases=[]),
    )
    
    with pytest.raises(PlanValidationError, match="Invalid params"):
        validator.validate_plan(plan, target_type="http")


def test_cyclic_depends_on_rejected(validator):
    """Test that cyclic dependencies are rejected"""
    step1 = PlanStep(
        step_id="step1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=["step2"],  # step1 depends on step2
        reason="Test",
        estimated_duration_sec=300,
    )
    step2 = PlanStep(
        step_id="step2",
        tool_id="httpx",
        mode_id="low",
        params={},
        depends_on=["step1"],  # step2 depends on step1 (cycle!)
        reason="Test",
        estimated_duration_sec=60,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[step1, step2],
        timeline=Timeline(total_estimated_sec=360, phases=[]),
    )
    
    with pytest.raises(PlanValidationError, match="Cycle detected"):
        validator.validate_plan(plan, target_type="http")


def test_max_steps_limit(validator):
    """Test that plans exceeding max_steps are rejected"""
    # Create a plan with 51 steps (exceeds default max of 50)
    steps = []
    for i in range(51):
        steps.append(PlanStep(
            step_id=f"step{i}",
            tool_id="nuclei",
            mode_id="basic_web",
            params={},
            depends_on=[],
            reason=f"Step {i}",
            estimated_duration_sec=60,
        ))
    
    plan = PlanScanResponse(
        plan_id="test",
        steps=steps,
        timeline=Timeline(total_estimated_sec=3600, phases=[]),
    )
    
    with pytest.raises(PlanValidationError, match="exceeds maximum"):
        validator.validate_plan(plan, target_type="http", max_steps=50)


def test_max_runtime_limit(validator, valid_plan):
    """Test that plans exceeding max_total_runtime_sec are rejected"""
    # Create a plan with very long estimated runtime
    plan = PlanScanResponse(
        plan_id="test",
        steps=valid_plan.steps,
        timeline=Timeline(
            total_estimated_sec=5000,  # Exceeds default max of 3600
            phases=[],
        ),
    )
    
    with pytest.raises(PlanValidationError, match="exceeds maximum"):
        validator.validate_plan(plan, target_type="http", max_total_runtime_sec=3600)


def test_target_type_validation(validator):
    """Test that target type validation works"""
    # SSLScan only works with https targets
    step = PlanStep(
        step_id="step1",
        tool_id="sslscan",
        mode_id="standard",
        params={},
        depends_on=[],
        reason="Test",
        estimated_duration_sec=300,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[step],
        timeline=Timeline(total_estimated_sec=300, phases=[]),
    )
    
    # Should fail for http target
    with pytest.raises(PlanValidationError, match="does not support target type"):
        validator.validate_plan(plan, target_type="http")
    
    # Should pass for https target
    validator.validate_plan(plan, target_type="https")


def test_valid_params_pass(validator):
    """Test that valid params pass validation"""
    step = PlanStep(
        step_id="step1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={
            "tags": ["cves", "misconfig"],
            "severity": ["critical", "high", "medium"],
        },
        depends_on=[],
        reason="Test",
        estimated_duration_sec=300,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[step],
        timeline=Timeline(total_estimated_sec=300, phases=[]),
    )
    
    # Should not raise
    validator.validate_plan(plan, target_type="http")


def test_invalid_param_type_rejected(validator):
    """Test that invalid param types are rejected"""
    # Severity should be an array, not a string
    step = PlanStep(
        step_id="step1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={
            "tags": ["cves"],
            "severity": "critical",  # Should be array, not string
        },
        depends_on=[],
        reason="Test",
        estimated_duration_sec=300,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[step],
        timeline=Timeline(total_estimated_sec=300, phases=[]),
    )
    
    with pytest.raises(PlanValidationError, match="Invalid params"):
        validator.validate_plan(plan, target_type="http")


def test_dependency_on_nonexistent_step(validator):
    """Test that dependencies on non-existent steps are rejected"""
    step = PlanStep(
        step_id="step1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=["nonexistent_step"],  # This step doesn't exist
        reason="Test",
        estimated_duration_sec=300,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[step],
        timeline=Timeline(total_estimated_sec=300, phases=[]),
    )
    
    with pytest.raises(PlanValidationError, match="non-existent step"):
        validator.validate_plan(plan, target_type="http")


def test_duplicate_step_id_rejected(validator):
    """Test that duplicate step_ids are rejected"""
    step1 = PlanStep(
        step_id="step1",
        tool_id="nuclei",
        mode_id="basic_web",
        params={},
        depends_on=[],
        reason="Test 1",
        estimated_duration_sec=300,
    )
    step2 = PlanStep(
        step_id="step1",  # Duplicate!
        tool_id="httpx",
        mode_id="low",
        params={},
        depends_on=[],
        reason="Test 2",
        estimated_duration_sec=60,
    )
    plan = PlanScanResponse(
        plan_id="test",
        steps=[step1, step2],
        timeline=Timeline(total_estimated_sec=360, phases=[]),
    )
    
    with pytest.raises(PlanValidationError, match="Duplicate step_id"):
        validator.validate_plan(plan, target_type="http")

