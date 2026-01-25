"""Detection metrics collection."""

from prometheus_client import Counter, Histogram, Gauge


# Counters
applications_scored = Counter(
    "fraud_applications_scored_total",
    "Total applications scored",
    ["risk_level"],
)

synthetic_identities_detected = Counter(
    "fraud_synthetic_detected_total",
    "Synthetic identities detected",
    ["risk_level"],
)

bust_outs_predicted = Counter(
    "fraud_bust_outs_predicted_total",
    "Bust-out predictions made",
    ["risk_level"],
)

# Histograms
scoring_latency = Histogram(
    "fraud_scoring_latency_seconds",
    "Time to score an application",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

synthetic_score_distribution = Histogram(
    "fraud_synthetic_score_distribution",
    "Distribution of synthetic scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Gauges
active_cases = Gauge(
    "fraud_active_cases",
    "Number of active investigation cases",
    ["priority"],
)

cluster_count = Gauge(
    "fraud_cluster_count",
    "Number of detected synthetic clusters",
    ["risk_level"],
)


class MetricsCollector:
    """Collects and exposes fraud detection metrics."""

    def record_scoring(self, risk_level: str, latency_seconds: float, score: float):
        """Record a scoring event."""
        applications_scored.labels(risk_level=risk_level).inc()
        scoring_latency.observe(latency_seconds)
        synthetic_score_distribution.observe(score)

    def record_synthetic_detection(self, risk_level: str):
        """Record synthetic identity detection."""
        synthetic_identities_detected.labels(risk_level=risk_level).inc()

    def record_bust_out_prediction(self, risk_level: str):
        """Record bust-out prediction."""
        bust_outs_predicted.labels(risk_level=risk_level).inc()

    def set_active_cases(self, priority: str, count: int):
        """Set active case count."""
        active_cases.labels(priority=priority).set(count)

    def set_cluster_count(self, risk_level: str, count: int):
        """Set cluster count."""
        cluster_count.labels(risk_level=risk_level).set(count)
