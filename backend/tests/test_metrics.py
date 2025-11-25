"""Tests for MetricsCollector"""

import pytest
from app.core.metrics import MetricsCollector


@pytest.mark.asyncio
async def test_increment_counter():
    """Test counter increment"""
    collector = MetricsCollector()
    
    await collector.increment("test.counter")
    await collector.increment("test.counter", 5)
    
    value = await collector.get_counter("test.counter")
    assert value == 6


@pytest.mark.asyncio
async def test_set_gauge():
    """Test gauge setting"""
    collector = MetricsCollector()
    
    await collector.set_gauge("test.gauge", 42.5)
    
    value = await collector.get_gauge("test.gauge")
    assert value == 42.5


@pytest.mark.asyncio
async def test_get_metrics():
    """Test getting all metrics"""
    collector = MetricsCollector()
    
    await collector.increment("counter1")
    await collector.set_gauge("gauge1", 10.0)
    
    metrics = await collector.get_metrics()
    
    assert "counters" in metrics
    assert "gauges" in metrics
    assert "timestamps" in metrics
    assert metrics["counters"]["counter1"] == 1
    assert metrics["gauges"]["gauge1"] == 10.0


@pytest.mark.asyncio
async def test_reset_metrics():
    """Test metrics reset"""
    collector = MetricsCollector()
    
    await collector.increment("test.counter")
    await collector.set_gauge("test.gauge", 10.0)
    
    await collector.reset()
    
    metrics = await collector.get_metrics()
    assert len(metrics["counters"]) == 0
    assert len(metrics["gauges"]) == 0

