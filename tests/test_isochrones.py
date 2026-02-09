import unittest
from unittest.mock import patch, MagicMock
import datetime
from shapely.geometry import Polygon, MultiPolygon
import shapely.errors
import geopandas as gpd
from isochrones.isochrones import (
    filter_small_polygons,
    make_non_overlapping,
    calculate_isochrones,
)


class TestFilterSmallPolygons(unittest.TestCase):
    def setUp(self):
        # Create helper geometries
        # Area = 0.01
        self.small_poly = Polygon([(0, 0), (0, 0.1), (0.1, 0.1), (0.1, 0), (0, 0)])
        # Area = 100
        self.large_poly = Polygon([(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)])
        self.threshold = 1.0

    def test_multipolygons_filtering(self):
        """MultiPolygons with small polygons are correctly filtered."""
        # Create MultiPolygon with one large and one small polygon
        geom = MultiPolygon([self.large_poly, self.small_poly])
        result = filter_small_polygons(geom, self.threshold)

        # Should return a MultiPolygon with only the large polygon
        self.assertIsInstance(result, MultiPolygon)
        if isinstance(result, MultiPolygon):
            self.assertEqual(len(result.geoms), 1)
            self.assertEqual(result.geoms[0], self.large_poly)

    def test_all_polygons_filtered(self):
        """All polygons being filtered out results in an empty Polygon."""
        # Create MultiPolygon with two small polygons
        geom = MultiPolygon([self.small_poly, self.small_poly])
        result = filter_small_polygons(geom, self.threshold)

        # Should return an empty Polygon
        self.assertIsInstance(result, Polygon)
        self.assertTrue(result.is_empty)

    def test_single_multipolygon_not_filtered(self):
        """Single-polygon MultiPolygons are not filtered."""
        # Even though it's small, it's the only one, so it should stay
        geom = MultiPolygon([self.small_poly])
        result = filter_small_polygons(geom, self.threshold)

        self.assertEqual(geom, result)

    def test_regular_polygon_unchanged(self):
        """Regular Polygons pass through unchanged."""
        # Regular polygons are returned as-is, regardless of size
        result = filter_small_polygons(self.small_poly, self.threshold)
        self.assertEqual(self.small_poly, result)

    def test_none_input(self):
        """None input results in an empty Polygon."""
        result = filter_small_polygons(None, self.threshold)
        self.assertIsInstance(result, Polygon)
        self.assertTrue(result.is_empty)


class TestMakeNonOverlapping(unittest.TestCase):
    """Test suite for make_non_overlapping function error handling."""

    def setUp(self):
        """Create sample isochrone GeoDataFrames for testing."""
        # Create three nested polygons (concentric squares)
        poly1 = Polygon([(0, 0), (0, 2), (2, 2), (2, 0), (0, 0)])  # Smallest
        poly2 = Polygon([(0, 0), (0, 4), (4, 4), (4, 0), (0, 0)])  # Medium
        poly3 = Polygon([(0, 0), (0, 6), (6, 6), (6, 0), (0, 0)])  # Largest

        self.valid_isochrones = gpd.GeoDataFrame(
            {"time": [300, 600, 900], "geometry": [poly1, poly2, poly3]},
            crs="EPSG:4326",
        )

    def test_successful_non_overlapping(self):
        """Test successful creation of non-overlapping isochrones."""
        result = make_non_overlapping(self.valid_isochrones.copy())

        # Should have same number of rows
        self.assertEqual(len(result), 3)

        # First (smallest) isochrone should remain unchanged
        self.assertTrue(
            result.loc[0, "geometry"].equals(self.valid_isochrones.loc[0, "geometry"])
        )

        # Larger isochrones should be modified (no longer equal to original)
        self.assertFalse(
            result.loc[1, "geometry"].equals(self.valid_isochrones.loc[1, "geometry"])
        )
        self.assertFalse(
            result.loc[2, "geometry"].equals(self.valid_isochrones.loc[2, "geometry"])
        )

    def test_single_isochrone_unchanged(self):
        """Test that single isochrone passes through unchanged."""
        single = self.valid_isochrones.iloc[[0]].copy()
        result = make_non_overlapping(single)

        self.assertEqual(len(result), 1)
        self.assertTrue(result.loc[0, "geometry"].equals(single.loc[0, "geometry"]))

    def test_empty_isochrone_unchanged(self):
        """Test that empty GeoDataFrame passes through unchanged."""
        empty = gpd.GeoDataFrame({"time": [], "geometry": []}, crs="EPSG:4326")
        result = make_non_overlapping(empty)

        self.assertEqual(len(result), 0)

    @patch("isochrones.isochrones.logger")
    def test_level1_geos_exception_recovery(self, mock_logger):
        """Test Level 1 error handling: GEOSException triggers polygon-level recovery."""
        isochrones = self.valid_isochrones.copy()

        # Mock the difference operation to raise GEOSException on first call
        original_difference = Polygon.difference
        call_count = [0]

        def mock_difference(self, other):
            call_count[0] += 1
            if call_count[0] == 1:  # First call (largest isochrone)
                raise shapely.errors.GEOSException("Simulated GEOS error")
            return original_difference(self, other)

        with patch.object(Polygon, "difference", mock_difference):
            result = make_non_overlapping(isochrones)

        # Should complete without raising exception
        self.assertEqual(len(result), 3)

        # Should have logged a warning about the GEOS exception
        self.assertTrue(mock_logger.warning.called)
        warning_call = mock_logger.warning.call_args[0][0]
        self.assertIn("GEOSException", warning_call)
        self.assertIn("polygon-level recovery", warning_call)

    @patch("isochrones.isochrones.logger")
    def test_level2_polygon_recovery_with_multipolygon(self, mock_logger):
        """Test Level 2 recovery: handles MultiPolygon with some failing polygons."""
        # Create isochrones where smaller geometry is a MultiPolygon
        poly1_a = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
        poly1_b = Polygon([(5, 5), (5, 6), (6, 6), (6, 5), (5, 5)])
        multi_poly = MultiPolygon([poly1_a, poly1_b])
        poly2 = Polygon([(0, 0), (0, 4), (4, 4), (4, 0), (0, 0)])

        isochrones = gpd.GeoDataFrame(
            {"time": [300, 600], "geometry": [multi_poly, poly2]},
            crs="EPSG:4326",
        )

        # Mock to fail on first difference, then succeed on polygon-level recovery
        # but fail on one of the individual polygon differences
        call_count = [0]
        original_difference = Polygon.difference

        def mock_difference(self, other):
            call_count[0] += 1
            if call_count[0] == 1:  # First call to difference (Level 1)
                raise shapely.errors.GEOSException("Simulated GEOS error")
            elif call_count[0] == 2:  # First polygon in recovery
                raise Exception("Simulated polygon-level error")
            # Subsequent calls succeed
            return original_difference(self, other)

        with patch.object(Polygon, "difference", mock_difference):
            result = make_non_overlapping(isochrones)

        # Should complete without raising exception
        self.assertEqual(len(result), 2)

        # Should have logged warnings
        self.assertTrue(mock_logger.warning.called)
        # Check for both Level 1 and Level 2 warnings
        all_warnings = [call[0][0] for call in mock_logger.warning.call_args_list]
        self.assertTrue(any("polygon-level recovery" in w for w in all_warnings))
        self.assertTrue(any("Failed to subtract polygon" in w for w in all_warnings))

    @patch("isochrones.isochrones.logger")
    def test_unexpected_geometry_type_handling(self, mock_logger):
        """Test handling of unexpected geometry types during recovery."""
        # Create isochrones with a Point geometry (unexpected in this context)
        from shapely.geometry import Point

        poly1 = Point(1, 1)  # Unexpected type
        poly2 = Polygon([(0, 0), (0, 4), (4, 4), (4, 0), (0, 0)])

        isochrones = gpd.GeoDataFrame(
            {"time": [300, 600], "geometry": [poly1, poly2]},
            crs="EPSG:4326",
        )

        # Mock to fail difference to trigger recovery path
        def mock_difference(self, other):
            raise shapely.errors.GEOSException("Simulated GEOS error")

        with patch.object(Polygon, "difference", mock_difference):
            _ = make_non_overlapping(isochrones)

        # Should have logged a warning about unexpected geometry type
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
        self.assertTrue(
            any("Unexpected smaller geometry type" in w for w in warning_calls),
            f"Expected warning about unexpected geometry type, got: {warning_calls}",
        )


class TestCalculateIsochronesErrorHandling(unittest.TestCase):
    """Test suite for calculate_isochrones error handling with overlap parameter."""

    @patch("isochrones.isochrones.requests.get")
    @patch("isochrones.isochrones.get_available_modes")
    @patch("isochrones.isochrones.make_non_overlapping")
    @patch("isochrones.isochrones.logger")
    def test_fallback_to_overlapping_on_geos_exception(
        self, mock_logger, mock_make_non_overlapping, mock_get_modes, mock_requests
    ):
        """Test that calculate_isochrones falls back to overlapping when make_non_overlapping fails."""
        # Setup mocks
        mock_get_modes.return_value = {"WALK": "WALK"}

        # Create mock response with valid GeoJSON
        poly1 = Polygon([(0, 0), (0, 2), (2, 2), (2, 0), (0, 0)])
        poly2 = Polygon([(0, 0), (0, 4), (4, 4), (4, 0), (0, 0)])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {"geometry": poly1.__geo_interface__, "properties": {"time": 300}},
                {"geometry": poly2.__geo_interface__, "properties": {"time": 600}},
            ]
        }
        mock_requests.return_value = mock_response

        # Make make_non_overlapping raise GEOSException
        mock_make_non_overlapping.side_effect = shapely.errors.GEOSException(
            "Simulated geometry error"
        )

        # Call calculate_isochrones with overlap=False
        result = calculate_isochrones(
            lat=46.5,
            lon=6.5,
            cutoffSec=[300, 600],
            date_time=datetime.datetime(2024, 1, 1, 10, 0),
            mode="WALK",
            otp_url="http://example.com",
            overlap=False,  # Request non-overlapping
        )

        # Should return a valid GeoDataFrame (overlapping fallback)
        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertEqual(len(result), 2)

        # Should have called make_non_overlapping
        self.assertTrue(mock_make_non_overlapping.called)

        # Should have logged a warning about falling back
        self.assertTrue(mock_logger.warning.called)
        warning_msg = mock_logger.warning.call_args[0][0]
        self.assertIn("Failed to make isochrones non-overlapping", warning_msg)
        self.assertIn("GEOSException", warning_msg)
        self.assertIn("Returning overlapping isochrones instead", warning_msg)

    @patch("isochrones.isochrones.requests.get")
    @patch("isochrones.isochrones.get_available_modes")
    @patch("isochrones.isochrones.make_non_overlapping")
    def test_successful_non_overlapping_calculation(
        self, mock_make_non_overlapping, mock_get_modes, mock_requests
    ):
        """Test that calculate_isochrones successfully creates non-overlapping isochrones."""
        # Setup mocks
        mock_get_modes.return_value = {"WALK": "WALK"}

        poly1 = Polygon([(0, 0), (0, 2), (2, 2), (2, 0), (0, 0)])
        poly2 = Polygon([(0, 0), (0, 4), (4, 4), (4, 0), (0, 0)])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {"geometry": poly1.__geo_interface__, "properties": {"time": 300}},
                {"geometry": poly2.__geo_interface__, "properties": {"time": 600}},
            ]
        }
        mock_requests.return_value = mock_response

        # Make make_non_overlapping return modified geometries
        def mock_non_overlap(gdf):
            # Simulate successful non-overlapping operation
            gdf_copy = gdf.copy()
            gdf_copy.at[1, "geometry"] = poly2.difference(poly1)
            return gdf_copy

        mock_make_non_overlapping.side_effect = mock_non_overlap

        # Call calculate_isochrones with overlap=False
        result = calculate_isochrones(
            lat=46.5,
            lon=6.5,
            cutoffSec=[300, 600],
            date_time=datetime.datetime(2024, 1, 1, 10, 0),
            mode="WALK",
            otp_url="http://example.com",
            overlap=False,
        )

        # Should return a valid GeoDataFrame
        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertEqual(len(result), 2)

        # Should have called make_non_overlapping
        self.assertTrue(mock_make_non_overlapping.called)

        # The larger geometry should be different (non-overlapping)
        # This verifies make_non_overlapping was applied
        self.assertFalse(result.loc[1, "geometry"].equals(poly2))

    @patch("isochrones.isochrones.requests.get")
    @patch("isochrones.isochrones.get_available_modes")
    def test_overlapping_skips_make_non_overlapping(
        self, mock_get_modes, mock_requests
    ):
        """Test that overlap=True skips make_non_overlapping entirely."""
        # Setup mocks
        mock_get_modes.return_value = {"WALK": "WALK"}

        poly1 = Polygon([(0, 0), (0, 2), (2, 2), (2, 0), (0, 0)])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {"geometry": poly1.__geo_interface__, "properties": {"time": 300}},
            ]
        }
        mock_requests.return_value = mock_response

        # Call with overlap=True (default)
        result = calculate_isochrones(
            lat=46.5,
            lon=6.5,
            cutoffSec=[300],
            date_time=datetime.datetime(2024, 1, 1, 10, 0),
            mode="WALK",
            otp_url="http://example.com",
            overlap=True,
        )

        # Should return valid GeoDataFrame
        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertEqual(len(result), 1)

        # Geometry should be unchanged (original overlapping)
        # (after buffer(0) operation)
        self.assertIsNotNone(result.loc[0, "geometry"])


if __name__ == "__main__":
    unittest.main()
