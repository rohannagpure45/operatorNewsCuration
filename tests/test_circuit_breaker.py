"""Tests for the CircuitBreaker class."""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch

# =============================================================================
# PHASE 1: CRAWL - Circuit Breaker Unit Tests
# =============================================================================


class TestCircuitBreakerBasicState:
    """Tests for basic circuit breaker state transitions."""

    def test_circuit_starts_closed(self):
        """Test that a new circuit breaker starts in closed state."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        assert cb.get_state("test_service") == "closed"

    def test_circuit_opens_after_threshold_failures(self):
        """Test that circuit opens after reaching failure threshold."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        service = "archive_today"
        
        # Record failures up to threshold
        cb.record_failure(service)
        assert cb.get_state(service) == "closed"
        
        cb.record_failure(service)
        assert cb.get_state(service) == "closed"
        
        cb.record_failure(service)
        assert cb.get_state(service) == "open"

    def test_circuit_rejects_calls_when_open(self):
        """Test that open circuit returns False for allow_request."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=60)
        service = "google_cache"
        
        # Open the circuit
        cb.record_failure(service)
        cb.record_failure(service)
        
        assert cb.get_state(service) == "open"
        assert cb.allow_request(service) is False

    def test_circuit_allows_requests_when_closed(self):
        """Test that closed circuit allows requests."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        service = "wayback"
        
        assert cb.allow_request(service) is True

    def test_circuit_half_opens_after_reset_timeout(self):
        """Test that circuit transitions to half-open after reset timeout."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)  # 100ms timeout
        service = "archive_today"
        
        # Open the circuit
        cb.record_failure(service)
        cb.record_failure(service)
        assert cb.get_state(service) == "open"
        
        # Wait for reset timeout
        time.sleep(0.15)
        
        # Should now be half-open and allow one request
        assert cb.allow_request(service) is True
        assert cb.get_state(service) == "half-open"

    def test_circuit_closes_on_success_in_half_open(self):
        """Test that success in half-open state closes the circuit."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)
        service = "archive_today"
        
        # Open the circuit
        cb.record_failure(service)
        cb.record_failure(service)
        
        # Wait for reset timeout to enter half-open
        time.sleep(0.15)
        cb.allow_request(service)  # Transition to half-open
        
        # Record success
        cb.record_success(service)
        
        assert cb.get_state(service) == "closed"

    def test_circuit_reopens_on_failure_in_half_open(self):
        """Test that failure in half-open state reopens the circuit."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)
        service = "archive_today"
        
        # Open the circuit
        cb.record_failure(service)
        cb.record_failure(service)
        
        # Wait for reset timeout to enter half-open
        time.sleep(0.15)
        cb.allow_request(service)  # Transition to half-open
        
        # Record another failure
        cb.record_failure(service)
        
        assert cb.get_state(service) == "open"


class TestCircuitBreakerMultiService:
    """Tests for multi-service circuit breaker behavior."""

    def test_circuit_tracks_separate_state_per_service(self):
        """Test that each service has independent circuit state."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=60)
        
        # Open circuit for service1
        cb.record_failure("service1")
        cb.record_failure("service1")
        
        # service1 should be open, service2 should be closed
        assert cb.get_state("service1") == "open"
        assert cb.get_state("service2") == "closed"
        assert cb.allow_request("service1") is False
        assert cb.allow_request("service2") is True

    def test_reset_clears_all_services(self):
        """Test that reset() clears state for all services."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=60)
        
        # Open circuits for multiple services
        cb.record_failure("service1")
        cb.record_failure("service1")
        cb.record_failure("service2")
        cb.record_failure("service2")
        
        cb.reset()
        
        assert cb.get_state("service1") == "closed"
        assert cb.get_state("service2") == "closed"

    def test_reset_single_service(self):
        """Test that reset(service) only clears that service."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=60)
        
        # Open circuits for both services
        cb.record_failure("service1")
        cb.record_failure("service1")
        cb.record_failure("service2")
        cb.record_failure("service2")
        
        cb.reset("service1")
        
        assert cb.get_state("service1") == "closed"
        assert cb.get_state("service2") == "open"


class TestCircuitBreakerConcurrency:
    """Tests for thread safety of circuit breaker."""

    def test_circuit_state_is_thread_safe(self):
        """Test that concurrent access from multiple threads doesn't corrupt state."""
        import threading
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=100, reset_timeout=60)
        service = "test_service"
        
        def record_failures():
            for _ in range(50):
                cb.record_failure(service)
        
        # Run concurrent failure recordings from real threads
        thread1 = threading.Thread(target=record_failures)
        thread2 = threading.Thread(target=record_failures)
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
        
        # Should have recorded 100 failures and opened the circuit
        assert cb.get_state(service) == "open"
        metrics = cb.get_metrics()
        assert metrics[service]["failures"] >= 100


class TestCircuitBreakerDecorator:
    """Tests for the circuit breaker decorator pattern."""

    @pytest.mark.asyncio
    async def test_decorator_allows_call_when_closed(self):
        """Test that decorated function is called when circuit is closed."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        call_count = 0
        
        async def fetch_from_archive(url):
            nonlocal call_count
            call_count += 1
            return "content"
        
        result = await cb.call("archive", fetch_from_archive, "http://example.com")
        
        assert result == "content"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_raises_when_open(self):
        """Test that decorated function raises CircuitOpenError when open."""
        from src.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=60)
        
        # Open the circuit
        cb.record_failure("archive")
        cb.record_failure("archive")
        
        async def fetch_from_archive(url):
            return "content"
        
        with pytest.raises(CircuitOpenError):
            await cb.call("archive", fetch_from_archive, "http://example.com")

    @pytest.mark.asyncio
    async def test_decorator_records_success_on_return(self):
        """Test that successful call records success."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        
        # Record some failures first
        cb.record_failure("archive")
        cb.record_failure("archive")
        
        async def fetch_from_archive(url):
            return "content"
        
        await cb.call("archive", fetch_from_archive, "http://example.com")
        
        # Failure count should be reset on success
        assert cb._failures.get("archive", 0) == 0

    @pytest.mark.asyncio
    async def test_decorator_records_failure_on_exception(self):
        """Test that exception in call records failure."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        
        async def fetch_from_archive(url):
            raise Exception("Network error")
        
        with pytest.raises(Exception):
            await cb.call("archive", fetch_from_archive, "http://example.com")
        
        assert cb._failures.get("archive", 0) == 1


class TestCircuitBreakerMetrics:
    """Tests for circuit breaker metrics and monitoring."""

    def test_get_metrics_returns_service_stats(self):
        """Test that get_metrics returns failure counts and states."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        
        cb.record_failure("service1")
        cb.record_failure("service1")
        cb.record_failure("service2")
        
        metrics = cb.get_metrics()
        
        assert metrics["service1"]["failures"] == 2
        assert metrics["service1"]["state"] == "closed"
        assert metrics["service2"]["failures"] == 1
        assert metrics["service2"]["state"] == "closed"

    def test_metrics_show_open_state(self):
        """Test that metrics correctly show open state."""
        from src.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=60)
        
        cb.record_failure("service1")
        cb.record_failure("service1")
        
        metrics = cb.get_metrics()
        
        assert metrics["service1"]["state"] == "open"

