"""
priority_engine.py – Weighted priority scoring for pothole repairs.

Priority Score = (severity_weight × normalized_severity)
              + (traffic_weight  × normalized_traffic)
Result: 0–100 float, higher = more urgent.
"""

DEFAULT_TRAFFIC = 5000
MAX_SEVERITY = 10
MIN_SEVERITY = 1


class PriorityEngine:
    def __init__(self, severity_weight=0.5, traffic_weight=0.5):
        if abs(severity_weight + traffic_weight - 1.0) > 1e-9:
            raise ValueError("Weights must sum to 1.0")
        self.severity_weight = severity_weight
        self.traffic_weight = traffic_weight

    def normalize_severity(self, severity: int) -> float:
        severity = max(MIN_SEVERITY, min(MAX_SEVERITY, int(severity)))
        return ((severity - MIN_SEVERITY) / (MAX_SEVERITY - MIN_SEVERITY)) * 100

    def normalize_traffic(self, traffic: int, max_traffic: int) -> float:
        if max_traffic <= 0:
            return 0.0
        return (min(traffic, max_traffic) / max_traffic) * 100

    def calculate_score(self, severity: int, traffic: int, max_traffic: int) -> float:
        ns = self.normalize_severity(severity)
        nt = self.normalize_traffic(traffic, max(1, max_traffic))
        return round(self.severity_weight * ns + self.traffic_weight * nt, 2)

    def get_label(self, score: float) -> str:
        if score >= 75: return "Critical"
        if score >= 50: return "High"
        if score >= 25: return "Medium"
        return "Low"

    def get_label_color(self, score: float) -> str:
        """Return hex color for priority label."""
        if score >= 75: return "#dc3545"
        if score >= 50: return "#fd7e14"
        if score >= 25: return "#ffc107"
        return "#28a745"


default_engine = PriorityEngine()
