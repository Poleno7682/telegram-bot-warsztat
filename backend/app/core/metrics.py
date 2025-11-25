"""Metrics collection for monitoring application health and performance"""

from typing import Dict, Any
from collections import defaultdict
from datetime import datetime
import asyncio


class MetricsCollector:
    """Simple in-memory metrics collector"""
    
    def __init__(self):
        """Initialize metrics collector"""
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def increment(self, metric_name: str, value: int = 1) -> None:
        """
        Increment a counter metric
        
        Args:
            metric_name: Name of the metric
            value: Value to increment by (default: 1)
        """
        async with self._lock:
            self._counters[metric_name] += value
            self._timestamps[metric_name] = datetime.now()
    
    async def set_gauge(self, metric_name: str, value: float) -> None:
        """
        Set a gauge metric value
        
        Args:
            metric_name: Name of the metric
            value: Gauge value
        """
        async with self._lock:
            self._gauges[metric_name] = value
            self._timestamps[metric_name] = datetime.now()
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics
        
        Returns:
            Dictionary with counters, gauges, and timestamps
        """
        async with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timestamps": {
                    k: v.isoformat() for k, v in self._timestamps.items()
                }
            }
    
    async def get_counter(self, metric_name: str) -> int:
        """
        Get counter value
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Counter value
        """
        async with self._lock:
            return self._counters.get(metric_name, 0)
    
    async def get_gauge(self, metric_name: str) -> float | None:
        """
        Get gauge value
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Gauge value or None if not set
        """
        async with self._lock:
            return self._gauges.get(metric_name)
    
    async def reset(self) -> None:
        """Reset all metrics"""
        async with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timestamps.clear()


# Global singleton instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get singleton metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

