"""Unit tests for transit route filtering functions.

This test suite uses synthetic mock data to test the transit route filtering logic
without requiring external PBF files or data extraction. Tests run quickly (<1 second)
and provide comprehensive coverage of edge cases.
"""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from isochrones import filter_routes_by_isochrone, filter_routes_by_proximity
from isochrones.pois import count_route_stops_in_isochrones


# ============================================================================
# Mock Data Fixtures
# ============================================================================


@pytest.fixture
def mock_transit_stops():
    """
    Create mock transit stops for testing.

    Returns 10 stops with a mix of transit modes:
    - Stops 1-3: Inside small test area (bus stops)
    - Stops 4-6: Inside small test area (train stops)
    - Stops 7-8: Inside small test area (tram stops)
    - Stops 9-10: Outside test area (bus stops)
    """
    stops = gpd.GeoDataFrame(
        {
            "osm_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "route_ids": [
                [101, 102],  # Stop 1: routes 101, 102 (bus)
                [101],  # Stop 2: route 101 (bus)
                [102],  # Stop 3: route 102 (bus)
                [103],  # Stop 4: route 103 (train)
                [103],  # Stop 5: route 103 (train)
                [104],  # Stop 6: route 104 (train)
                [105],  # Stop 7: route 105 (tram)
                [105, 106],  # Stop 8: routes 105, 106 (tram)
                [107],  # Stop 9: route 107 (bus, outside)
                [107],  # Stop 10: route 107 (bus, outside)
            ],
            "transit_mode": [
                "bus",
                "bus",
                "bus",
                "train",
                "train",
                "train",
                "tram",
                "tram",
                "bus",
                "bus",
            ],
            "geometry": [
                Point(6.140, 46.200),  # Inside small area
                Point(6.141, 46.201),  # Inside small area
                Point(6.142, 46.202),  # Inside small area
                Point(6.143, 46.203),  # Inside small area
                Point(6.144, 46.204),  # Inside small area
                Point(6.145, 46.205),  # Inside small area
                Point(6.146, 46.206),  # Inside small area
                Point(6.147, 46.207),  # Inside small area
                Point(6.200, 46.250),  # Outside small area
                Point(6.201, 46.251),  # Outside small area
            ],
        },
        crs="EPSG:4326",
    )
    return stops


@pytest.fixture
def mock_transit_routes():
    """
    Create mock transit routes for testing (ungrouped).

    Returns 7 routes:
    - Route 101: bus with 2 stops inside (stops 1, 2)
    - Route 102: bus with 2 stops inside (stops 1, 3)
    - Route 103: train with 2 stops inside (stops 4, 5)
    - Route 104: train with 1 stop inside (stop 6)
    - Route 105: tram with 2 stops inside (stops 7, 8)
    - Route 106: tram with 1 stop inside (stop 8)
    - Route 107: bus with 0 stops inside (stops 9, 10 outside)
    """
    routes = gpd.GeoDataFrame(
        {
            "osm_id": [101, 102, 103, 104, 105, 106, 107],
            "route": ["bus", "bus", "train", "train", "tram", "tram", "bus"],
            "ref": ["1", "2", "T1", "T2", "12", "15", "99"],
            "network": ["TPG"] * 7,
            "from": ["Station A"] * 7,
            "to": ["Station B"] * 7,
            "geometry": [
                LineString([(6.140, 46.200), (6.141, 46.201)]),  # Route 101
                LineString([(6.140, 46.200), (6.142, 46.202)]),  # Route 102
                LineString([(6.143, 46.203), (6.144, 46.204)]),  # Route 103
                LineString([(6.145, 46.205), (6.200, 46.250)]),  # Route 104
                LineString([(6.146, 46.206), (6.147, 46.207)]),  # Route 105
                LineString([(6.147, 46.207), (6.200, 46.250)]),  # Route 106
                LineString([(6.200, 46.250), (6.201, 46.251)]),  # Route 107
            ],
        },
        crs="EPSG:4326",
    )
    return routes


@pytest.fixture
def mock_transit_routes_grouped():
    """
    Create mock transit routes grouped by route_master.

    Returns 3 route masters:
    - Master 201: Contains variants [101, 102] (bus routes)
    - Master 202: Contains variants [103, 104] (train routes)
    - Master 203: Contains variants [105, 106] (tram routes)
    """
    routes = gpd.GeoDataFrame(
        {
            "osm_id": [201, 202, 203],
            "route": ["bus", "train", "tram"],
            "ref": ["1", "T1", "12"],
            "network": ["TPG"] * 3,
            "from": ["Station A"] * 3,
            "to": ["Station B"] * 3,
            "variant_route_ids": [
                [101, 102],  # Master 201 contains routes 101, 102
                [103, 104],  # Master 202 contains routes 103, 104
                [105, 106],  # Master 203 contains routes 105, 106
            ],
            "geometry": [
                LineString([(6.140, 46.200), (6.142, 46.202)]),  # Master 201
                LineString([(6.143, 46.203), (6.200, 46.250)]),  # Master 202
                LineString([(6.146, 46.206), (6.200, 46.250)]),  # Master 203
            ],
        },
        crs="EPSG:4326",
    )
    return routes


@pytest.fixture
def mock_isochrone_small():
    """
    Create a small isochrone covering stops 1-8 (inside area).

    This isochrone covers:
    - Bus stops: 1, 2, 3 (routes 101, 102)
    - Train stops: 4, 5, 6 (routes 103, 104)
    - Tram stops: 7, 8 (routes 105, 106)
    """
    polygon = Polygon(
        [
            (6.139, 46.199),
            (6.148, 46.199),
            (6.148, 46.208),
            (6.139, 46.208),
            (6.139, 46.199),
        ]
    )
    isochrone = gpd.GeoDataFrame({"time": [600]}, geometry=[polygon], crs="EPSG:4326")
    return isochrone


@pytest.fixture
def mock_isochrone_large():
    """
    Create a large isochrone covering all stops (1-10).

    This covers all routes including those outside the small area.
    """
    polygon = Polygon(
        [
            (6.135, 46.195),
            (6.205, 46.195),
            (6.205, 46.255),
            (6.135, 46.255),
            (6.135, 46.195),
        ]
    )
    isochrone = gpd.GeoDataFrame({"time": [900]}, geometry=[polygon], crs="EPSG:4326")
    return isochrone


@pytest.fixture
def mock_isochrone_empty():
    """
    Create an isochrone that covers no stops.

    This is useful for testing edge cases where no routes should be found.
    """
    polygon = Polygon(
        [
            (7.000, 47.000),
            (7.010, 47.000),
            (7.010, 47.010),
            (7.000, 47.010),
            (7.000, 47.000),
        ]
    )
    isochrone = gpd.GeoDataFrame({"time": [300]}, geometry=[polygon], crs="EPSG:4326")
    return isochrone


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_filter_routes_basic(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """Test basic route filtering with small isochrone."""
    routes, stops = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
    )

    # Check result types
    assert isinstance(routes, gpd.GeoDataFrame)
    assert isinstance(stops, gpd.GeoDataFrame)

    # Check that we got results
    assert len(routes) > 0, "Should find some routes in isochrone"
    assert len(stops) > 0, "Should find some stops in isochrone"

    # Check that filtered routes are subset of input
    assert len(routes) <= len(mock_transit_routes)

    # Verify stops are within isochrone
    assert all(
        stop_id in [1, 2, 3, 4, 5, 6, 7, 8] for stop_id in stops["osm_id"].tolist()
    )

    print(f"✓ test_filter_routes_basic: Found {len(routes)} routes, {len(stops)} stops")


def test_filter_routes_min_stops_threshold(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """Test filtering with different min_stops_bus_tram thresholds."""
    # Filter with min_stops = 1 (lenient)
    routes_lenient, _ = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
        min_stops_bus_tram=1,
    )

    # Filter with min_stops = 3 (strict)
    routes_strict, _ = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
        min_stops_bus_tram=3,
    )

    # Strict filter should return fewer or equal routes
    assert len(routes_strict) <= len(routes_lenient), (
        "Stricter filter should return fewer or equal routes"
    )

    # Lenient should include routes with just 1 stop
    assert len(routes_lenient) >= 4, "Lenient filter should find at least 4 routes"

    # Strict should exclude routes with only 1-2 stops (except trains)
    # Routes 101, 102 have 2 stops each, routes 105, 106 have 2 and 1 stops
    # Only routes with >=3 stops or trains should pass
    assert len(routes_strict) <= len(routes_lenient)

    print(
        f"✓ test_filter_routes_min_stops_threshold: Lenient={len(routes_lenient)}, "
        f"Strict={len(routes_strict)} routes"
    )


def test_filter_routes_empty_inputs():
    """Test that empty inputs are handled gracefully."""
    # Create empty GeoDataFrames
    empty_routes = gpd.GeoDataFrame(
        columns=["osm_id", "route", "geometry"], crs="EPSG:4326"
    )
    empty_stops = gpd.GeoDataFrame(columns=["osm_id", "geometry"], crs="EPSG:4326")

    # Create a sample isochrone
    polygon = Polygon([(6.14, 46.20), (6.15, 46.20), (6.15, 46.21), (6.14, 46.21)])
    isochrone = gpd.GeoDataFrame({"time": [600]}, geometry=[polygon], crs="EPSG:4326")

    # Should not raise an error
    routes, stops = filter_routes_by_isochrone(empty_routes, empty_stops, isochrone)

    # Check result
    assert isinstance(routes, gpd.GeoDataFrame)
    assert isinstance(stops, gpd.GeoDataFrame)
    assert routes.empty
    assert stops.empty

    print("✓ test_filter_routes_empty_inputs: Empty inputs handled correctly")


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_filter_routes_train_vs_bus_logic(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """
    Test that trains need only 1 stop while bus/tram need min_stops_bus_tram.

    With min_stops_bus_tram=2:
    - Route 104 (train) with 1 stop should be included
    - Route 106 (tram) with 1 stop should be excluded
    """
    routes, _ = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
        min_stops_bus_tram=2,
    )

    route_ids = routes["osm_id"].tolist()

    # Train route 104 with 1 stop should be included
    assert 104 in route_ids, "Train with 1 stop should be included"

    # Tram route 106 with 1 stop should be excluded (needs 2 stops)
    assert 106 not in route_ids, "Tram with 1 stop should be excluded with min=2"

    # Train route 103 with 2 stops should be included
    assert 103 in route_ids, "Train with 2 stops should be included"

    print("✓ test_filter_routes_train_vs_bus_logic: Train/bus logic verified")


def test_filter_routes_grouped_by_route_master(
    mock_transit_routes_grouped, mock_transit_stops, mock_isochrone_small
):
    """Test filtering with routes grouped by route_master.

    When routes are grouped by route_master, the function should:
    1. Filter route_masters based on whether any variant routes have stops in the isochrone
    2. Return stops that belong to any of the variant routes in the filtered route_masters
    """
    routes, stops = filter_routes_by_isochrone(
        mock_transit_routes_grouped,
        mock_transit_stops,
        mock_isochrone_small,
    )

    # Check that we got route masters
    assert len(routes) > 0, "Should find route masters in isochrone"

    # Verify result has variant_route_ids column
    assert "variant_route_ids" in routes.columns

    # Check that route masters are included if any variant is in isochrone
    # Master 201 (bus routes 101, 102) should be included (both have 2 stops)
    # Master 202 (train routes 103, 104) should be included (trains need 1 stop)
    # Master 203 (tram routes 105, 106) should be included (105 has 2 stops)
    assert len(routes) >= 2, "Should find at least 2 route masters"

    # Verify that stops are correctly filtered based on variant route IDs
    # Stops should include those belonging to routes 101-106 (variants of included masters)
    assert len(stops) > 0, "Should find stops belonging to variant routes"

    # Verify specific stops are included:
    # - Stops 1-3 belong to routes 101, 102 (variants of master 201)
    # - Stops 4-6 belong to routes 103, 104 (variants of master 202)
    # - Stops 7-8 belong to routes 105, 106 (variants of master 203)
    stop_ids = set(stops["osm_id"].tolist())
    expected_stops = {1, 2, 3, 4, 5, 6, 7, 8}  # All stops inside the isochrone
    assert stop_ids == expected_stops, (
        f"Expected stops {expected_stops}, got {stop_ids}"
    )

    print(
        f"✓ test_filter_routes_grouped_by_route_master: Found {len(routes)} "
        f"route masters, {len(stops)} stops"
    )


def test_filter_routes_no_matches(
    mock_transit_routes, mock_transit_stops, mock_isochrone_empty
):
    """Test filtering when isochrone contains no stops."""
    routes, stops = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_empty,
    )

    # Should return valid but empty GeoDataFrames
    assert isinstance(routes, gpd.GeoDataFrame)
    assert isinstance(stops, gpd.GeoDataFrame)
    assert len(routes) == 0, "Should find no routes in empty isochrone"
    assert len(stops) == 0, "Should find no stops in empty isochrone"

    print("✓ test_filter_routes_no_matches: Empty isochrone handled correctly")


def test_filter_routes_all_matches(
    mock_transit_routes, mock_transit_stops, mock_isochrone_large
):
    """Test filtering when isochrone contains all stops."""
    routes, stops = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_large,
        min_stops_bus_tram=2,
    )

    # Should find most routes (route 107 has 2 stops, so it should be included too)
    assert len(routes) >= 5, "Should find most routes with min_stops=2"

    # Should find all stops or most stops
    assert len(stops) >= 8, "Should find most stops in large isochrone"

    print(
        f"✓ test_filter_routes_all_matches: Found {len(routes)} routes, "
        f"{len(stops)} stops"
    )


def test_filter_routes_crs_mismatch(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """Test that CRS conversion is handled automatically."""
    # Convert stops and routes to Web Mercator (EPSG:3857)
    stops_3857 = mock_transit_stops.to_crs("EPSG:3857")
    routes_3857 = mock_transit_routes.to_crs("EPSG:3857")

    # Isochrone stays in EPSG:4326
    # Function should handle CRS conversion internally
    routes, stops = filter_routes_by_isochrone(
        routes_3857,
        stops_3857,
        mock_isochrone_small,
    )

    # Should still get valid results despite CRS mismatch
    assert isinstance(routes, gpd.GeoDataFrame)
    assert isinstance(stops, gpd.GeoDataFrame)
    assert len(routes) > 0, "Should find routes despite CRS mismatch"
    assert len(stops) > 0, "Should find stops despite CRS mismatch"

    print("✓ test_filter_routes_crs_mismatch: CRS conversion handled correctly")


# ============================================================================
# Helper Function Tests
# ============================================================================


def test_count_route_stops_basic(mock_transit_stops, mock_isochrone_small):
    """Test the count_route_stops_in_isochrones helper function."""
    counts = count_route_stops_in_isochrones(mock_transit_stops, mock_isochrone_small)

    # Check result type and structure (returns pd.DataFrame, not GeoDataFrame)
    assert isinstance(counts, pd.DataFrame)
    assert "route_ids" in counts.columns
    assert "stop_count" in counts.columns
    assert "transit_mode" in counts.columns

    # Check that we got results
    assert len(counts) > 0, "Should count stops for some routes"

    # Verify specific counts
    # Route 101 should have 2 stops (stops 1, 2)
    route_101 = counts[counts["route_ids"] == 101]
    assert len(route_101) == 1
    assert route_101.iloc[0]["stop_count"] == 2
    assert route_101.iloc[0]["transit_mode"] == "bus"

    # Route 103 should have 2 stops (stops 4, 5)
    route_103 = counts[counts["route_ids"] == 103]
    assert len(route_103) == 1
    assert route_103.iloc[0]["stop_count"] == 2
    assert route_103.iloc[0]["transit_mode"] == "train"

    print(f"✓ test_count_route_stops_basic: Counted stops for {len(counts)} routes")


def test_count_route_stops_edge_cases():
    """Test count_route_stops_in_isochrones with edge cases."""
    # Test 1: Empty inputs
    empty_stops = gpd.GeoDataFrame(
        columns=["osm_id", "route_ids", "transit_mode", "geometry"], crs="EPSG:4326"
    )
    polygon = Polygon([(6.14, 46.20), (6.15, 46.20), (6.15, 46.21), (6.14, 46.21)])
    isochrone = gpd.GeoDataFrame({"time": [600]}, geometry=[polygon], crs="EPSG:4326")

    counts = count_route_stops_in_isochrones(empty_stops, isochrone)
    assert isinstance(counts, pd.DataFrame)
    assert len(counts) == 0

    # Test 2: Missing required columns should raise ValueError
    bad_stops = gpd.GeoDataFrame(
        {"osm_id": [1, 2], "geometry": [Point(6.14, 46.20), Point(6.15, 46.21)]},
        crs="EPSG:4326",
    )

    with pytest.raises(ValueError, match="route_ids"):
        count_route_stops_in_isochrones(bad_stops, isochrone)

    print("✓ test_count_route_stops_edge_cases: Edge cases handled correctly")


# ============================================================================
# Proximity Filtering Tests
# ============================================================================


def test_filter_routes_by_proximity_basic(mock_transit_routes, mock_transit_stops):
    """Test basic proximity filtering with default 500m radius."""
    # Use center point near the mock stops (6.140-6.147, 46.200-46.207)
    routes, stops = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,  # 500m radius
    )

    # Check result types
    assert isinstance(routes, gpd.GeoDataFrame)
    assert isinstance(stops, gpd.GeoDataFrame)

    # Should find some routes
    assert len(routes) > 0, "Should find routes within 500m"
    assert len(stops) > 0, "Should find stops within filtered routes"

    # Results should be subset of input
    assert len(routes) <= len(mock_transit_routes)
    assert len(stops) <= len(mock_transit_stops)

    print(
        f"✓ test_filter_routes_by_proximity_basic: Found {len(routes)} routes, {len(stops)} stops"
    )


def test_filter_routes_by_proximity_radius_threshold(
    mock_transit_routes, mock_transit_stops
):
    """Test different radius thresholds."""
    center_lat, center_lon = 46.2035, 6.1435

    # Small radius - should find fewer routes
    routes_small, _ = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=center_lat,
        center_lon=center_lon,
        radius=100.0,  # 100m
    )

    # Large radius - should find more routes
    routes_large, _ = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=center_lat,
        center_lon=center_lon,
        radius=2000.0,  # 2km
    )

    # Large radius should find more or equal routes
    assert len(routes_large) >= len(routes_small), (
        "Larger radius should find more or equal routes"
    )

    print(
        f"✓ test_filter_routes_by_proximity_radius_threshold: Small={len(routes_small)}, "
        f"Large={len(routes_large)} routes"
    )


def test_filter_routes_by_proximity_min_stops_threshold(
    mock_transit_routes, mock_transit_stops
):
    """Test different min_stops thresholds."""
    center_lat, center_lon = 46.2035, 6.1435

    # Lenient filter (min_stops=1)
    routes_lenient, _ = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=center_lat,
        center_lon=center_lon,
        radius=500.0,
        min_stops=1,
    )

    # Strict filter (min_stops=3)
    routes_strict, _ = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=center_lat,
        center_lon=center_lon,
        radius=500.0,
        min_stops=3,
    )

    # Strict should return fewer or equal routes
    assert len(routes_strict) <= len(routes_lenient), (
        "Stricter min_stops should return fewer or equal routes"
    )

    print(
        f"✓ test_filter_routes_by_proximity_min_stops_threshold: Lenient={len(routes_lenient)}, "
        f"Strict={len(routes_strict)} routes"
    )


def test_filter_routes_by_proximity_empty_inputs():
    """Test that empty inputs are handled gracefully."""
    empty_routes = gpd.GeoDataFrame(
        columns=["osm_id", "route", "geometry"], crs="EPSG:4326"
    )
    empty_stops = gpd.GeoDataFrame(
        columns=["osm_id", "route_ids", "transit_mode", "geometry"], crs="EPSG:4326"
    )

    routes, stops = filter_routes_by_proximity(
        empty_routes,
        empty_stops,
        center_lat=46.2044,
        center_lon=6.1432,
    )

    assert isinstance(routes, gpd.GeoDataFrame)
    assert isinstance(stops, gpd.GeoDataFrame)
    assert routes.empty
    assert stops.empty

    print(
        "✓ test_filter_routes_by_proximity_empty_inputs: Empty inputs handled correctly"
    )


def test_filter_routes_by_proximity_no_matches(mock_transit_routes, mock_transit_stops):
    """Test when no routes are within radius."""
    # Use a center point far from all stops
    routes, stops = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=47.5000,  # Far from test data
        center_lon=7.5000,
        radius=500.0,
    )

    assert isinstance(routes, gpd.GeoDataFrame)
    assert isinstance(stops, gpd.GeoDataFrame)
    assert len(routes) == 0
    assert len(stops) == 0

    print("✓ test_filter_routes_by_proximity_no_matches: No matches handled correctly")


def test_filter_routes_by_proximity_crs_handling(
    mock_transit_routes, mock_transit_stops
):
    """Test that CRS conversion is handled correctly."""
    # Convert to Web Mercator (EPSG:3857)
    routes_3857 = mock_transit_routes.to_crs("EPSG:3857")
    stops_3857 = mock_transit_stops.to_crs("EPSG:3857")

    # Center point is provided in EPSG:4326 (always)
    routes, stops = filter_routes_by_proximity(
        routes_3857,
        stops_3857,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,
    )

    # Results should be in the original input CRS (EPSG:3857)
    assert routes.crs == routes_3857.crs
    assert stops.crs == stops_3857.crs

    # Should still find results despite different input CRS
    assert len(routes) > 0, "Should find routes despite CRS mismatch"

    print(
        "✓ test_filter_routes_by_proximity_crs_handling: CRS conversion handled correctly"
    )


def test_filter_routes_by_proximity_grouped_routes(
    mock_transit_routes_grouped, mock_transit_stops
):
    """Test proximity filtering with grouped routes (route_master)."""
    routes, stops = filter_routes_by_proximity(
        mock_transit_routes_grouped,
        mock_transit_stops,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,
        min_stops=1,
    )

    # Should find route masters
    assert len(routes) > 0, "Should find route masters within radius"

    # Verify variant_route_ids column exists
    assert "variant_route_ids" in routes.columns

    print(
        f"✓ test_filter_routes_by_proximity_grouped_routes: Found {len(routes)} "
        f"route masters (stops={len(stops)})"
    )


def test_filter_routes_by_proximity_all_modes_equal():
    """Test that all transit modes use the same min_stops threshold."""
    # Create stops with different modes at the same location
    stops = gpd.GeoDataFrame(
        {
            "osm_id": [1, 2, 3],
            "route_ids": [[101], [102], [103]],
            "transit_mode": ["train", "bus", "tram"],
            "geometry": [
                Point(6.140, 46.200),
                Point(6.141, 46.201),
                Point(6.142, 46.202),
            ],
        },
        crs="EPSG:4326",
    )

    routes = gpd.GeoDataFrame(
        {
            "osm_id": [101, 102, 103],
            "route": ["train", "bus", "tram"],
            "ref": ["T1", "1", "12"],
            "network": ["TPG"] * 3,
            "from": ["Station A"] * 3,
            "to": ["Station B"] * 3,
            "geometry": [
                LineString([(6.140, 46.200), (6.150, 46.210)]),
                LineString([(6.141, 46.201), (6.151, 46.211)]),
                LineString([(6.142, 46.202), (6.152, 46.212)]),
            ],
        },
        crs="EPSG:4326",
    )

    # Filter with min_stops=1 - should include all routes
    routes_filtered, _ = filter_routes_by_proximity(
        routes,
        stops,
        center_lat=46.2005,
        center_lon=6.1415,
        radius=500.0,
        min_stops=1,
    )

    # All route types should be included (each has 1 stop)
    assert len(routes_filtered) == 3, "All routes should be included with min_stops=1"

    print(
        "✓ test_filter_routes_by_proximity_all_modes_equal: All modes treated equally"
    )


def test_filter_routes_by_proximity_returns_all_stops(
    mock_transit_routes, mock_transit_stops
):
    """Test that returned stops include ALL stops from filtered routes, not just those in radius."""
    # Filter with a specific location
    routes, stops = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=46.200,
        center_lon=6.140,
        radius=300.0,  # Small radius
        min_stops=1,
    )

    # If we found routes, verify that ALL stops from those routes are returned
    if len(routes) > 0:
        route_ids = set(routes["osm_id"])

        # Get all stops that reference these routes
        expected_stops = mock_transit_stops[
            mock_transit_stops["route_ids"].apply(
                lambda rids: any(rid in route_ids for rid in rids)
            )
        ]

        # The returned stops should match all stops from filtered routes
        # (not just stops within the radius)
        assert len(stops) == len(expected_stops), (
            "Should return ALL stops from filtered routes, not just those in radius"
        )

    print(
        "✓ test_filter_routes_by_proximity_returns_all_stops: All route stops returned"
    )


def test_filter_routes_by_proximity_with_isochrone(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """Test proximity filtering with isochrone pre-clipping optimization."""
    routes, stops = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,
        isochrone=mock_isochrone_small,
    )

    # Should find routes within the isochrone
    assert len(routes) > 0, "Should find routes with isochrone"
    assert len(stops) > 0, "Should find stops with isochrone"

    # Results should be same or subset of without isochrone
    # (because isochrone pre-filters the dataset)

    print(
        f"✓ test_filter_routes_by_proximity_with_isochrone: Found {len(routes)} routes, "
        f"{len(stops)} stops with isochrone"
    )


def test_filter_routes_by_proximity_isochrone_empty():
    """Test that empty results are returned when isochrone doesn't overlap stops."""
    # Create stops far from isochrone
    stops = gpd.GeoDataFrame(
        {
            "osm_id": [1, 2],
            "route_ids": [[101], [101]],
            "transit_mode": ["bus", "bus"],
            "geometry": [
                Point(7.0, 47.0),  # Far from isochrone
                Point(7.1, 47.1),
            ],
        },
        crs="EPSG:4326",
    )

    routes = gpd.GeoDataFrame(
        {
            "osm_id": [101],
            "route": ["bus"],
            "ref": ["1"],
            "network": ["TPG"],
            "from": ["A"],
            "to": ["B"],
            "geometry": [LineString([(7.0, 47.0), (7.1, 47.1)])],
        },
        crs="EPSG:4326",
    )

    # Isochrone in Geneva (far from stops)
    isochrone = gpd.GeoDataFrame(
        {
            "time": [600],
            "geometry": [
                Polygon(
                    [
                        (6.139, 46.199),
                        (6.148, 46.199),
                        (6.148, 46.208),
                        (6.139, 46.208),
                        (6.139, 46.199),
                    ]
                )
            ],
        },
        crs="EPSG:4326",
    )

    # Filter with isochrone that doesn't overlap
    filtered_routes, filtered_stops = filter_routes_by_proximity(
        routes,
        stops,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,
        isochrone=isochrone,
    )

    # Should return empty results (no stops in isochrone)
    assert len(filtered_routes) == 0, (
        "Should return no routes when isochrone doesn't overlap"
    )
    assert len(filtered_stops) == 0, (
        "Should return no stops when isochrone doesn't overlap"
    )

    print("✓ test_filter_routes_by_proximity_isochrone_empty: Empty isochrone handled")


def test_filter_routes_by_proximity_isochrone_crs_mismatch(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """Test isochrone clipping with CRS mismatch."""
    # Convert stops to EPSG:3857
    stops_3857 = mock_transit_stops.to_crs("EPSG:3857")

    # Isochrone stays in EPSG:4326
    routes, stops = filter_routes_by_proximity(
        mock_transit_routes,
        stops_3857,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,
        isochrone=mock_isochrone_small,
    )

    # Should handle CRS mismatch gracefully
    assert routes.crs == mock_transit_routes.crs, "Routes should be in original CRS"
    assert stops.crs == stops_3857.crs, "Stops should be in original CRS"
    assert len(routes) > 0, "Should find routes despite CRS mismatch"

    print(
        "✓ test_filter_routes_by_proximity_isochrone_crs_mismatch: CRS mismatch handled"
    )


def test_filter_routes_by_proximity_none_isochrone(
    mock_transit_routes, mock_transit_stops
):
    """Test that isochrone=None works (backward compatibility)."""
    routes, stops = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=46.2035,
        center_lon=6.1435,
        isochrone=None,  # Explicit None
    )

    # Should work without isochrone
    assert len(routes) > 0, "Should work with isochrone=None"
    assert len(stops) > 0, "Should work with isochrone=None"

    print(
        "✓ test_filter_routes_by_proximity_none_isochrone: Backward compatibility maintained"
    )


def test_filter_routes_by_proximity_isochrone_grouped_routes(
    mock_transit_routes_grouped, mock_transit_stops, mock_isochrone_small
):
    """Test isochrone optimization with grouped routes (route_master)."""
    routes, stops = filter_routes_by_proximity(
        mock_transit_routes_grouped,
        mock_transit_stops,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,
        min_stops=1,
        isochrone=mock_isochrone_small,
    )

    # Should find route masters
    assert len(routes) > 0, "Should find route masters with isochrone"

    # Verify variant_route_ids column exists
    assert "variant_route_ids" in routes.columns

    print(
        f"✓ test_filter_routes_by_proximity_isochrone_grouped_routes: Found {len(routes)} "
        f"route masters with isochrone"
    )


# ============================================================================
# Geometry Simplification Tests
# ============================================================================


def test_filter_routes_by_isochrone_simplify_none(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """Test that simplify=None (default) doesn't change geometry."""
    routes_no_simplify, _ = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
    )

    routes_explicit_none, _ = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
        simplify=None,
    )

    # Results should be identical
    assert len(routes_no_simplify) == len(routes_explicit_none)

    print("✓ test_filter_routes_by_isochrone_simplify_none: Default behavior preserved")


def test_filter_routes_by_isochrone_simplify_applies(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """Test that simplify parameter simplifies route geometries."""
    routes_original, _ = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
        simplify=None,
    )

    routes_simplified, _ = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
        simplify=0.01,  # Large tolerance for testing
    )

    # Both should return same number of routes
    assert len(routes_original) == len(routes_simplified)

    # Geometry should be simplified (may have fewer coordinates)
    # Note: For simple LineStrings, simplification might not always reduce points,
    # but the operation should complete without error
    assert isinstance(routes_simplified, gpd.GeoDataFrame)
    assert "geometry" in routes_simplified.columns

    print("✓ test_filter_routes_by_isochrone_simplify_applies: Simplification applied")


def test_filter_routes_by_isochrone_simplify_doesnt_affect_stops(
    mock_transit_routes, mock_transit_stops, mock_isochrone_small
):
    """Test that simplify doesn't affect stop geometries."""
    _, stops_original = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
        simplify=None,
    )

    _, stops_with_simplify = filter_routes_by_isochrone(
        mock_transit_routes,
        mock_transit_stops,
        mock_isochrone_small,
        simplify=0.01,
    )

    # Stops should be identical (points don't get simplified)
    assert len(stops_original) == len(stops_with_simplify)

    # Check that geometries are the same
    if len(stops_original) > 0:
        # Use individual comparison for each geometry
        for i in range(len(stops_original)):
            assert stops_original.geometry.iloc[i].equals(
                stops_with_simplify.geometry.iloc[i]
            )

    print(
        "✓ test_filter_routes_by_isochrone_simplify_doesnt_affect_stops: Stops unchanged"
    )


def test_filter_routes_by_proximity_simplify(mock_transit_routes, mock_transit_stops):
    """Test simplify parameter with proximity filtering."""
    routes_original, _ = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,
        simplify=None,
    )

    routes_simplified, _ = filter_routes_by_proximity(
        mock_transit_routes,
        mock_transit_stops,
        center_lat=46.2035,
        center_lon=6.1435,
        radius=500.0,
        simplify=0.01,
    )

    # Should return same number of routes
    assert len(routes_original) == len(routes_simplified)

    # Simplification should complete without error
    assert isinstance(routes_simplified, gpd.GeoDataFrame)

    print(
        "✓ test_filter_routes_by_proximity_simplify: Simplification works with proximity filter"
    )


# ============================================================================
# Main Entry Point
# ============================================================================


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
