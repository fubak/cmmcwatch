#!/usr/bin/env python3
"""Tests for main.py helper functions."""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dataclasses import dataclass

import pytest
from main import _to_dict, _to_dict_list


@dataclass
class SampleDataclass:
    """Sample dataclass for testing."""

    name: str
    value: int
    optional: str = None


@dataclass
class NestedDataclass:
    """Nested dataclass for testing."""

    id: str
    data: SampleDataclass


class TestToDict:
    """Test _to_dict helper function."""

    def test_converts_dataclass_to_dict(self):
        """Test that dataclass instances are converted to dicts."""
        sample = SampleDataclass(name="test", value=42)

        result = _to_dict(sample)

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_preserves_dict_input(self):
        """Test that dict input is returned as-is."""
        input_dict = {"name": "test", "value": 42}

        result = _to_dict(input_dict)

        assert result is input_dict
        assert result == {"name": "test", "value": 42}

    def test_handles_none_values(self):
        """Test handling of None values in dataclass."""
        sample = SampleDataclass(name="test", value=42, optional=None)

        result = _to_dict(sample)

        assert result["optional"] is None

    def test_handles_nested_dataclass(self):
        """Test handling of nested dataclasses."""
        inner = SampleDataclass(name="inner", value=10)
        outer = NestedDataclass(id="outer", data=inner)

        result = _to_dict(outer)

        assert isinstance(result, dict)
        assert result["id"] == "outer"
        # Nested dataclass should also be converted
        assert isinstance(result["data"], dict)
        assert result["data"]["name"] == "inner"

    def test_handles_non_dataclass_objects(self):
        """Test handling of non-dataclass objects."""
        # Regular objects without __dataclass_fields__ should be returned as-is
        regular_obj = "just a string"

        result = _to_dict(regular_obj)

        assert result == "just a string"

    def test_handles_int_input(self):
        """Test that integer input is returned as-is."""
        result = _to_dict(42)

        assert result == 42

    def test_handles_list_input(self):
        """Test that list input is returned as-is."""
        input_list = [1, 2, 3]

        result = _to_dict(input_list)

        assert result == [1, 2, 3]


class TestToDictList:
    """Test _to_dict_list helper function."""

    def test_converts_list_of_dataclasses(self):
        """Test converting list of dataclasses to list of dicts."""
        items = [
            SampleDataclass(name="item1", value=1),
            SampleDataclass(name="item2", value=2),
            SampleDataclass(name="item3", value=3),
        ]

        result = _to_dict_list(items)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, dict) for item in result)
        assert result[0]["name"] == "item1"
        assert result[1]["value"] == 2

    def test_preserves_list_of_dicts(self):
        """Test that list of dicts is preserved."""
        items = [{"name": "item1", "value": 1}, {"name": "item2", "value": 2}]

        result = _to_dict_list(items)

        assert result == items

    def test_handles_mixed_list(self):
        """Test handling of mixed list (dataclasses and dicts)."""
        items = [
            SampleDataclass(name="item1", value=1),
            {"name": "item2", "value": 2},
            SampleDataclass(name="item3", value=3),
        ]

        result = _to_dict_list(items)

        assert len(result) == 3
        assert all(isinstance(item, dict) for item in result)
        assert result[0]["name"] == "item1"
        assert result[1]["name"] == "item2"
        assert result[2]["name"] == "item3"

    def test_handles_empty_list(self):
        """Test handling of empty list."""
        result = _to_dict_list([])

        assert result == []

    def test_handles_single_item_list(self):
        """Test handling of single-item list."""
        items = [SampleDataclass(name="only", value=99)]

        result = _to_dict_list(items)

        assert len(result) == 1
        assert result[0]["name"] == "only"

    def test_handles_list_with_none_values(self):
        """Test handling of list with None values in dataclasses."""
        items = [
            SampleDataclass(name="test1", value=1, optional=None),
            SampleDataclass(name="test2", value=2, optional="present"),
        ]

        result = _to_dict_list(items)

        assert result[0]["optional"] is None
        assert result[1]["optional"] == "present"

    def test_handles_nested_dataclasses_in_list(self):
        """Test handling of nested dataclasses in list."""
        inner1 = SampleDataclass(name="inner1", value=1)
        inner2 = SampleDataclass(name="inner2", value=2)

        items = [
            NestedDataclass(id="outer1", data=inner1),
            NestedDataclass(id="outer2", data=inner2),
        ]

        result = _to_dict_list(items)

        assert len(result) == 2
        assert result[0]["id"] == "outer1"
        assert isinstance(result[0]["data"], dict)
        assert result[0]["data"]["name"] == "inner1"

    def test_large_list_performance(self):
        """Test performance with large list."""
        # Create large list of dataclasses
        items = [SampleDataclass(name=f"item{i}", value=i) for i in range(1000)]

        result = _to_dict_list(items)

        assert len(result) == 1000
        assert all(isinstance(item, dict) for item in result)


class TestHelperFunctionsIntegration:
    """Integration tests for helper functions."""

    def test_round_trip_conversion(self):
        """Test converting dataclass to dict and back."""
        original = SampleDataclass(name="test", value=42, optional="data")

        as_dict = _to_dict(original)

        # Create new instance from dict
        reconstructed = SampleDataclass(**as_dict)

        assert reconstructed.name == original.name
        assert reconstructed.value == original.value
        assert reconstructed.optional == original.optional

    def test_list_round_trip(self):
        """Test converting list of dataclasses to dicts and back."""
        original_list = [
            SampleDataclass(name="a", value=1),
            SampleDataclass(name="b", value=2),
        ]

        dict_list = _to_dict_list(original_list)

        # Reconstruct from dicts
        reconstructed = [SampleDataclass(**d) for d in dict_list]

        assert len(reconstructed) == len(original_list)
        assert reconstructed[0].name == original_list[0].name
        assert reconstructed[1].value == original_list[1].value

    def test_idempotency_of_to_dict(self):
        """Test that calling _to_dict on a dict is idempotent."""
        original_dict = {"name": "test", "value": 42}

        result1 = _to_dict(original_dict)
        result2 = _to_dict(result1)

        assert result1 == result2 == original_dict

    def test_idempotency_of_to_dict_list(self):
        """Test that calling _to_dict_list on list of dicts is idempotent."""
        original_list = [{"name": "a", "value": 1}, {"name": "b", "value": 2}]

        result1 = _to_dict_list(original_list)
        result2 = _to_dict_list(result1)

        assert result1 == result2 == original_list


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_to_dict_with_custom_object(self):
        """Test _to_dict with custom object (non-dataclass)."""

        class CustomObject:
            def __init__(self, value):
                self.value = value

        obj = CustomObject(42)

        # Should return object as-is since it's not a dataclass
        result = _to_dict(obj)

        assert result is obj

    def test_to_dict_list_with_none_in_list(self):
        """Test _to_dict_list with None values in list."""
        items = [SampleDataclass(name="valid", value=1), None, {"key": "value"}]

        result = _to_dict_list(items)

        # Should handle None by returning it as-is
        assert len(result) == 3
        assert isinstance(result[0], dict)
        assert result[1] is None
        assert result[2] == {"key": "value"}

    def test_to_dict_with_special_types(self):
        """Test _to_dict with special Python types."""

        @dataclass
        class SpecialTypes:
            path: Path
            timestamp: str

        obj = SpecialTypes(path=Path("/tmp/test"), timestamp="2024-01-01")

        result = _to_dict(obj)

        # Path objects should be converted by asdict
        assert isinstance(result, dict)
        assert "path" in result
        assert "timestamp" in result

    def test_empty_dataclass(self):
        """Test with empty dataclass."""

        @dataclass
        class EmptyDataclass:
            pass

        obj = EmptyDataclass()

        result = _to_dict(obj)

        assert result == {}

    def test_dataclass_with_default_factory(self):
        """Test dataclass with default_factory."""
        from dataclasses import field

        @dataclass
        class WithFactory:
            items: list = field(default_factory=list)

        obj = WithFactory()
        obj.items.append("test")

        result = _to_dict(obj)

        assert result["items"] == ["test"]

    def test_to_dict_list_preserves_order(self):
        """Test that _to_dict_list preserves order of items."""
        items = [SampleDataclass(name=f"item_{i}", value=i) for i in range(10, 0, -1)]

        result = _to_dict_list(items)

        # Order should be preserved
        for i, item in enumerate(result):
            assert item["value"] == 10 - i


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
