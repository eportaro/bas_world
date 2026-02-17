"""
Tests for the inventory search tool.
Validates structured filtering, edge cases, and data integrity.
"""

import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.data_loader import load_inventory, get_vehicle_by_id, get_unique_values
from app.schemas.schemas import SearchFilters
from app.tools.search_inventory import search_inventory_direct


class TestDataLoader:
    """Tests for CSV loading and normalization."""

    def setup_method(self):
        load_inventory()

    def test_inventory_loads(self):
        from app.services.data_loader import get_dataframe
        df = get_dataframe()
        assert len(df) > 600, "Should load 600+ vehicles"
        assert "vehicle_id" in df.columns

    def test_gearbox_normalized(self):
        from app.services.data_loader import get_dataframe
        df = get_dataframe()
        gearbox_values = df["gearbox"].dropna().unique()
        # Should be English values, not Dutch
        assert "AUTOMAAT" not in gearbox_values
        assert "automatic" in gearbox_values

    def test_vehicle_by_id(self):
        vehicle = get_vehicle_by_id(271313)
        assert vehicle is not None
        assert vehicle.brand == "DAF"
        assert vehicle.power == 475

    def test_vehicle_not_found(self):
        vehicle = get_vehicle_by_id(999999)
        assert vehicle is None

    def test_unique_brands(self):
        brands = get_unique_values("brand")
        assert "DAF" in brands
        assert "SCANIA" in brands
        assert "MERCEDES" in brands


class TestSearchInventory:
    """Tests for the structured search tool."""

    def setup_method(self):
        load_inventory()

    def test_filter_by_brand(self):
        filters = SearchFilters(brand="DAF", limit=100)
        results = search_inventory_direct(filters)
        assert len(results) > 0
        assert all(v.brand == "DAF" for v in results)

    def test_filter_by_configuration(self):
        filters = SearchFilters(configuration="4X2", limit=100)
        results = search_inventory_direct(filters)
        assert len(results) > 0
        assert all(v.configuration == "4X2" for v in results)

    def test_filter_by_euro(self):
        filters = SearchFilters(euro=6, limit=100)
        results = search_inventory_direct(filters)
        assert len(results) > 0
        assert all(v.euro == 6 for v in results)

    def test_filter_by_price_range(self):
        filters = SearchFilters(min_price=20000, max_price=50000, limit=100)
        results = search_inventory_direct(filters)
        assert len(results) > 0
        for v in results:
            assert v.internet_price >= 20000
            assert v.internet_price <= 50000

    def test_filter_by_power(self):
        filters = SearchFilters(min_power=450, limit=100)
        results = search_inventory_direct(filters)
        assert len(results) > 0
        assert all(v.power >= 450 for v in results)

    def test_filter_by_gearbox(self):
        filters = SearchFilters(gearbox="automatic", limit=100)
        results = search_inventory_direct(filters)
        assert len(results) > 0
        assert all(v.gearbox == "automatic" for v in results)

    def test_combined_filters(self):
        """Scenario B: 4x2, Euro 6, automatic, >= 450 HP, < 50k"""
        filters = SearchFilters(
            configuration="4X2",
            euro=6,
            gearbox="automatic",
            min_power=450,
            max_price=50000,
            limit=10,
        )
        results = search_inventory_direct(filters)
        assert len(results) > 0
        for v in results:
            assert v.configuration == "4X2"
            assert v.euro == 6
            assert v.gearbox == "automatic"
            assert v.power >= 450
            assert v.internet_price <= 50000

    def test_no_results(self):
        """Edge case: impossible filters."""
        filters = SearchFilters(brand="TESLA", limit=10)
        results = search_inventory_direct(filters)
        assert len(results) == 0

    def test_limit_respected(self):
        filters = SearchFilters(limit=5)
        results = search_inventory_direct(filters)
        assert len(results) <= 5

    def test_returned_vehicles_exist(self):
        """Grounding check: all returned vehicle IDs must exist in the CSV."""
        filters = SearchFilters(brand="SCANIA", limit=20)
        results = search_inventory_direct(filters)
        from app.services.data_loader import get_dataframe
        df = get_dataframe()
        all_ids = set(df["vehicle_id"].tolist())
        for v in results:
            assert v.vehicle_id in all_ids, f"Vehicle {v.vehicle_id} not in inventory!"

    def test_damaged_excluded_by_default(self):
        """Damaged vehicles should be excluded by default."""
        filters = SearchFilters(limit=200)
        results = search_inventory_direct(filters)
        damaged = [v for v in results if v.is_damaged]
        assert len(damaged) == 0, "Damaged vehicles should be excluded by default"


class TestSearchTool:
    """Test the LangChain tool interface."""

    def setup_method(self):
        load_inventory()

    def test_tool_json_interface(self):
        from app.tools.search_inventory import search_inventory
        result = search_inventory.invoke('{"brand": "VOLVO", "limit": 3}')
        data = json.loads(result)
        assert "count" in data
        assert "vehicles" in data
        assert data["count"] <= 3

    def test_tool_invalid_json(self):
        from app.tools.search_inventory import search_inventory
        result = search_inventory.invoke("not valid json")
        data = json.loads(result)
        assert "error" in data

    def test_compare_tool(self):
        from app.tools.search_inventory import compare_vehicles
        # Get two real vehicle IDs
        filters = SearchFilters(brand="DAF", limit=2)
        results = search_inventory_direct(filters)
        if len(results) >= 2:
            ids = [results[0].vehicle_id, results[1].vehicle_id]
            result = compare_vehicles.invoke({"vehicle_ids": ids})
            data = json.loads(result)
            assert "vehicle_count" in data
            assert data["vehicle_count"] == 2


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
