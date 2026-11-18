import unittest
from pathsnap.visualization.eda import haversine, describe


class EdaTests(unittest.TestCase):
    def test_distance_uses_metres_and_longitude_latitude(self):
        self.assertEqual(haversine((0,0),(0,0)),0)
        self.assertAlmostEqual(haversine((0,0),(1,0)),111195,delta=2)
        self.assertAlmostEqual(haversine((0,60),(1,60)),55597,delta=3)

    def test_quantiles(self):
        self.assertEqual(describe([1,2,3])['median'],2)
        self.assertEqual(describe([]),{})
