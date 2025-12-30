"""
Unit tests for ScanLevel enum normalization and serialization

These tests ensure that:
1. normalize_scan_level() correctly normalizes various inputs to lowercase strings
2. scan_level_to_enum() correctly converts strings to ScanLevel enum
3. Pydantic schemas serialize ScanLevel enum by value (not name)
4. SQLAlchemy uses enum values when persisting to database
"""
import pytest
from app.core.scan_utils import normalize_scan_level, scan_level_to_enum
from app.models.scan import ScanLevel
from app.schemas.scan import ScanResponse, ScanJobListItem
from datetime import datetime


class TestNormalizeScanLevel:
    """Test normalize_scan_level() function"""
    
    def test_normalize_lowercase_strings(self):
        """Test that lowercase strings are returned as-is"""
        assert normalize_scan_level("basic") == "basic"
        assert normalize_scan_level("pro") == "pro"
        assert normalize_scan_level("advanced") == "advanced"
    
    def test_normalize_uppercase_strings(self):
        """Test that uppercase strings are normalized to lowercase"""
        assert normalize_scan_level("BASIC") == "basic"
        assert normalize_scan_level("PRO") == "pro"
        assert normalize_scan_level("ADVANCED") == "advanced"
    
    def test_normalize_mixed_case_strings(self):
        """Test that mixed case strings are normalized to lowercase"""
        assert normalize_scan_level("Basic") == "basic"
        assert normalize_scan_level("Pro") == "pro"
        assert normalize_scan_level("Advanced") == "advanced"
        assert normalize_scan_level("BaSiC") == "basic"
    
    def test_normalize_enum_members(self):
        """Test that ScanLevel enum members are normalized to their values"""
        assert normalize_scan_level(ScanLevel.BASIC) == "basic"
        assert normalize_scan_level(ScanLevel.PRO) == "pro"
        assert normalize_scan_level(ScanLevel.ADVANCED) == "advanced"
    
    def test_normalize_enum_string_representation(self):
        """Test that enum string representations like 'ScanLevel.BASIC' are handled"""
        assert normalize_scan_level("ScanLevel.BASIC") == "basic"
        assert normalize_scan_level("ScanLevel.PRO") == "pro"
        assert normalize_scan_level("ScanLevel.ADVANCED") == "advanced"
    
    def test_normalize_whitespace(self):
        """Test that whitespace is stripped"""
        assert normalize_scan_level("  basic  ") == "basic"
        assert normalize_scan_level("  PRO  ") == "pro"
    
    def test_normalize_invalid_values(self):
        """Test that invalid values raise ValueError"""
        with pytest.raises(ValueError, match="Invalid scan_level"):
            normalize_scan_level("invalid")
        
        with pytest.raises(ValueError, match="Invalid scan_level"):
            normalize_scan_level("")
        
        with pytest.raises(ValueError, match="scan_level cannot be None"):
            normalize_scan_level(None)


class TestScanLevelToEnum:
    """Test scan_level_to_enum() function"""
    
    def test_convert_lowercase_strings(self):
        """Test that lowercase strings are converted to enum"""
        assert scan_level_to_enum("basic") == ScanLevel.BASIC
        assert scan_level_to_enum("pro") == ScanLevel.PRO
        assert scan_level_to_enum("advanced") == ScanLevel.ADVANCED
    
    def test_convert_uppercase_strings(self):
        """Test that uppercase strings are normalized and converted"""
        assert scan_level_to_enum("BASIC") == ScanLevel.BASIC
        assert scan_level_to_enum("PRO") == ScanLevel.PRO
        assert scan_level_to_enum("ADVANCED") == ScanLevel.ADVANCED
    
    def test_convert_invalid_values(self):
        """Test that invalid values raise ValueError"""
        with pytest.raises(ValueError):
            scan_level_to_enum("invalid")


class TestPydanticEnumSerialization:
    """Test that Pydantic schemas serialize ScanLevel enum by value"""
    
    def test_scan_response_serializes_enum_by_value(self):
        """Test that ScanResponse serializes scan_level as lowercase string"""
        # Create a mock scan response with ScanLevel enum
        scan_data = {
            "id": "test-id",
            "project_id": "test-project",
            "scan_level": ScanLevel.BASIC,  # Enum member
            "status": "pending",
            "created_at": datetime.now(),
        }
        
        # Create Pydantic model (this will serialize the enum)
        response = ScanResponse(**scan_data)
        
        # Serialize to dict (Pydantic should use enum values)
        serialized = response.model_dump()
        
        # Verify scan_level is serialized as lowercase string (enum value), not enum name
        assert serialized["scan_level"] == "basic"  # Value, not "BASIC" or "ScanLevel.BASIC"
        assert isinstance(serialized["scan_level"], str)
    
    def test_scan_job_list_item_serializes_enum_by_value(self):
        """Test that ScanJobListItem serializes scan_level as lowercase string"""
        item_data = {
            "id": "test-id",
            "project_id": "test-project",
            "scan_level": ScanLevel.PRO,  # Enum member
            "status": "pending",
            "created_at": datetime.now(),
        }
        
        item = ScanJobListItem(**item_data)
        serialized = item.model_dump()
        
        # Verify scan_level is serialized as lowercase string
        assert serialized["scan_level"] == "pro"
        assert isinstance(serialized["scan_level"], str)
    
    def test_all_scan_levels_serialize_correctly(self):
        """Test that all scan levels serialize to their lowercase values"""
        for enum_member in [ScanLevel.BASIC, ScanLevel.PRO, ScanLevel.ADVANCED]:
            scan_data = {
                "id": "test-id",
                "project_id": "test-project",
                "scan_level": enum_member,
                "status": "pending",
                "created_at": datetime.now(),
            }
            
            response = ScanResponse(**scan_data)
            serialized = response.model_dump()
            
            # Verify the serialized value matches the enum value (lowercase)
            assert serialized["scan_level"] == enum_member.value
            assert serialized["scan_level"].islower()


class TestEnumValueConsistency:
    """Test that enum values are consistent and match database expectations"""
    
    def test_enum_values_are_lowercase(self):
        """Test that all ScanLevel enum values are lowercase strings"""
        assert ScanLevel.BASIC.value == "basic"
        assert ScanLevel.PRO.value == "pro"
        assert ScanLevel.ADVANCED.value == "advanced"
        
        # Verify all values are lowercase
        for enum_member in ScanLevel:
            assert enum_member.value.islower(), f"Enum value {enum_member.value} should be lowercase"
    
    def test_enum_values_match_database_enum_type(self):
        """Test that enum values match the expected PostgreSQL enum values"""
        # These should match the values in the 'scanlevel' PostgreSQL enum type
        expected_values = {"basic", "pro", "advanced"}
        actual_values = {member.value for member in ScanLevel}
        
        assert actual_values == expected_values, \
            f"Enum values {actual_values} should match database enum values {expected_values}"

