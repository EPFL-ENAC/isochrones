import unittest
from shapely.geometry import Polygon, MultiPolygon
from isochrones.isochrones import filter_small_polygons


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


if __name__ == "__main__":
    unittest.main()
