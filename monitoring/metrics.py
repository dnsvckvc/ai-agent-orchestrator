"""
Metrics Collection and Monitoring
Prometheus-compatible metrics for production monitoring
"""

import time
from typing import Dict, Any, List
from collections import defaultdict, deque
import threading
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Container for metric data"""
    name: str
    type: str  # counter, gauge, histogram
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """
    Collects and exposes metrics for monitoring
    Thread-safe implementation for concurrent access
    """

    def __init__(self, max_histogram_samples: int = 1000):
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_histogram_samples))
        self._start_time = time.time()

        # Initialize standard metrics
        self._initialize_metrics()

    def _initialize_metrics(self):
        """Initialize standard metrics"""
        self._counters["tasks_submitted"] = 0
        self._counters["tasks_completed"] = 0
        self._counters["tasks_failed"] = 0
        self._counters["tasks_cancelled"] = 0
        self._counters["tasks_retried"] = 0
        self._counters["tasks_running"] = 0
        self._counters["tasks_under_500ms"] = 0

    def increment(self, metric_name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment a counter metric"""
        with self._lock:
            key = self._make_key(metric_name, labels)
            self._counters[key] += value
            logger.debug(f"Incremented {key} by {value} (now {self._counters[key]})")

    def decrement(self, metric_name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Decrement a counter metric"""
        self.increment(metric_name, -value, labels)

    def set_gauge(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric to a specific value"""
        with self._lock:
            key = self._make_key(metric_name, labels)
            self._gauges[key] = value
            logger.debug(f"Set gauge {key} to {value}")

    def record(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Record a value in histogram (for percentiles, averages, etc.)"""
        with self._lock:
            key = self._make_key(metric_name, labels)
            self._histograms[key].append({
                "value": value,
                "timestamp": time.time()
            })

    def get_counter(self, metric_name: str, labels: Dict[str, str] = None) -> float:
        """Get current value of a counter"""
        with self._lock:
            key = self._make_key(metric_name, labels)
            return self._counters.get(key, 0.0)

    def get_gauge(self, metric_name: str, labels: Dict[str, str] = None) -> float:
        """Get current value of a gauge"""
        with self._lock:
            key = self._make_key(metric_name, labels)
            return self._gauges.get(key, 0.0)

    def get_histogram_stats(self, metric_name: str, labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get statistics from histogram (mean, p50, p95, p99)"""
        with self._lock:
            key = self._make_key(metric_name, labels)
            samples = self._histograms.get(key, deque())

            if not samples:
                return {
                    "count": 0,
                    "mean": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                    "min": 0.0,
                    "max": 0.0
                }

            values = sorted([s["value"] for s in samples])
            count = len(values)

            return {
                "count": count,
                "mean": sum(values) / count,
                "p50": self._percentile(values, 50),
                "p95": self._percentile(values, 95),
                "p99": self._percentile(values, 99),
                "min": values[0],
                "max": values[-1]
            }

    def _percentile(self, sorted_values: List[float], percentile: int) -> float:
        """Calculate percentile from sorted values"""
        if not sorted_values:
            return 0.0

        index = int((percentile / 100.0) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]

    def _make_key(self, metric_name: str, labels: Dict[str, str] = None) -> str:
        """Create metric key with labels"""
        if not labels:
            return metric_name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{metric_name}{{{label_str}}}"

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics for export"""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: self.get_histogram_stats(name.split("{")[0])
                    for name in self._histograms.keys()
                },
                "uptime_seconds": time.time() - self._start_time
            }

    def get_task_metrics(self) -> Dict[str, Any]:
        """Get task-specific metrics for monitoring"""
        with self._lock:
            total_submitted = self._counters.get("tasks_submitted", 0)
            total_completed = self._counters.get("tasks_completed", 0)
            total_failed = self._counters.get("tasks_failed", 0)
            total_cancelled = self._counters.get("tasks_cancelled", 0)
            under_500ms = self._counters.get("tasks_under_500ms", 0)

            # Calculate success rate
            total_terminal = total_completed + total_failed + total_cancelled
            success_rate = (total_completed / total_terminal * 100) if total_terminal > 0 else 0.0

            # Calculate error rate
            error_rate = (total_failed / total_terminal * 100) if total_terminal > 0 else 0.0

            # Get latency stats
            latency_stats = self.get_histogram_stats("task_execution_time_ms")

            return {
                "tasks_submitted": total_submitted,
                "tasks_completed": total_completed,
                "tasks_failed": total_failed,
                "tasks_cancelled": total_cancelled,
                "tasks_under_500ms": under_500ms,
                "success_rate_percent": success_rate,
                "error_rate_percent": error_rate,
                "latency_ms": latency_stats,
                "uptime_seconds": time.time() - self._start_time
            }

    def export_prometheus_format(self) -> str:
        """
        Export metrics in Prometheus text format
        For production integration with Prometheus
        """
        lines = []

        # Export counters
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        # Export gauges
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        # Export histogram summaries
        for name in self._histograms.keys():
            metric_name = name.split("{")[0]
            stats = self.get_histogram_stats(metric_name)

            lines.append(f"# TYPE {metric_name} summary")
            lines.append(f"{metric_name}{{quantile=\"0.5\"}} {stats['p50']}")
            lines.append(f"{metric_name}{{quantile=\"0.95\"}} {stats['p95']}")
            lines.append(f"{metric_name}{{quantile=\"0.99\"}} {stats['p99']}")
            lines.append(f"{metric_name}_count {stats['count']}")

        return "\n".join(lines)

    def check_sla_compliance(self) -> Dict[str, bool]:
        """
        Check if system meets SLA requirements
        Returns compliance status for each SLA metric
        """
        metrics = self.get_task_metrics()
        latency_stats = metrics["latency_ms"]

        sla_checks = {
            "latency_p95_under_500ms": latency_stats["p95"] < 500,
            "error_rate_under_1_percent": metrics["error_rate_percent"] < 1.0,
            "success_rate_above_99_percent": metrics["success_rate_percent"] >= 99.0,
        }

        return sla_checks

    def reset(self):
        """Reset all metrics (useful for testing)"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._start_time = time.time()
            self._initialize_metrics()
            logger.info("Metrics reset")


class PerformanceMonitor:
    """Context manager for measuring execution time"""

    def __init__(self, metrics_collector: MetricsCollector, metric_name: str,
                 labels: Dict[str, str] = None):
        self.metrics = metrics_collector
        self.metric_name = metric_name
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        self.metrics.record(self.metric_name, duration_ms, self.labels)
        return False
