"""Unit tests for the priority engine."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import unittest
from priority_engine import PriorityEngine, default_engine


class TestPriorityEngine(unittest.TestCase):

    def setUp(self):
        self.engine = PriorityEngine(severity_weight=0.5, traffic_weight=0.5)

    def test_weight_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            PriorityEngine(0.6, 0.6)

    def test_normalize_severity_min(self):
        self.assertAlmostEqual(self.engine.normalize_severity(1), 0.0)

    def test_normalize_severity_max(self):
        self.assertAlmostEqual(self.engine.normalize_severity(10), 100.0)

    def test_normalize_severity_mid(self):
        result = self.engine.normalize_severity(5)
        self.assertGreater(result, 0)
        self.assertLess(result, 100)

    def test_normalize_traffic_zero_max(self):
        self.assertAlmostEqual(self.engine.normalize_traffic(1000, 0), 0.0)

    def test_normalize_traffic_full(self):
        self.assertAlmostEqual(self.engine.normalize_traffic(5000, 5000), 100.0)

    def test_score_range(self):
        score = self.engine.calculate_score(5, 10000, 50000)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_higher_severity_higher_score(self):
        s1 = self.engine.calculate_score(3, 10000, 50000)
        s2 = self.engine.calculate_score(9, 10000, 50000)
        self.assertGreater(s2, s1)

    def test_higher_traffic_higher_score(self):
        s1 = self.engine.calculate_score(5, 5000, 50000)
        s2 = self.engine.calculate_score(5, 40000, 50000)
        self.assertGreater(s2, s1)

    def test_priority_label_critical(self):
        self.assertEqual(self.engine.get_label(80), "Critical")

    def test_priority_label_high(self):
        self.assertEqual(self.engine.get_label(60), "High")

    def test_priority_label_medium(self):
        self.assertEqual(self.engine.get_label(40), "Medium")

    def test_priority_label_low(self):
        self.assertEqual(self.engine.get_label(10), "Low")

    def test_clamping_severity(self):
        # Out-of-range values should be clamped
        s_below = self.engine.normalize_severity(0)
        s_above = self.engine.normalize_severity(11)
        self.assertAlmostEqual(s_below, 0.0)
        self.assertAlmostEqual(s_above, 100.0)

    def test_score_symmetric_weights(self):
        e1 = PriorityEngine(0.5, 0.5)
        e2 = PriorityEngine(0.8, 0.2)
        s1 = e1.calculate_score(10, 50000, 50000)
        s2 = e2.calculate_score(10, 50000, 50000)
        # Both should give 100 when severity and traffic are maxed
        self.assertAlmostEqual(s1, 100.0)
        self.assertAlmostEqual(s2, 100.0)

    def test_default_engine_exists(self):
        self.assertIsNotNone(default_engine)
        self.assertEqual(default_engine.severity_weight, 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
