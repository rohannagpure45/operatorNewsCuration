"""Circuit breaker pattern implementation for fault tolerance."""

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and request is rejected."""

    def __init__(self, service: str, message: str = "Circuit breaker is open"):
        self.service = service
        super().__init__(f"{message} for service: {service}")


class CircuitBreaker:
    """
    Circuit breaker for managing fault tolerance in fallback services.
    
    States:
    - closed: Normal operation, requests allowed
    - open: Too many failures, requests rejected immediately
    - half-open: Testing if service recovered, allow one request
    
    Usage:
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        
        # Check if request is allowed
        if cb.allow_request("archive_today"):
            try:
                result = await fetch_from_archive(url)
                cb.record_success("archive_today")
            except Exception:
                cb.record_failure("archive_today")
        
        # Or use the call wrapper
        result = await cb.call("archive_today", fetch_from_archive, url)
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: float = 60.0,
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit.
            reset_timeout: Seconds to wait before trying again (half-open).
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        
        # State tracking per service
        self._failures: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._state: Dict[str, str] = {}  # "closed", "open", "half-open"
        
        # Thread safety
        self._lock = threading.Lock()

    def get_state(self, service: str) -> str:
        """Get the current state of a service's circuit."""
        with self._lock:
            return self._get_state_internal(service)

    def _get_state_internal(self, service: str) -> str:
        """Internal state getter without lock (caller must hold lock)."""
        current_state = self._state.get(service, "closed")
        
        # Check if open circuit should transition to half-open
        if current_state == "open":
            last_failure = self._last_failure_time.get(service, 0)
            if time.time() - last_failure >= self.reset_timeout:
                return "half-open"
        
        return current_state

    def allow_request(self, service: str) -> bool:
        """
        Check if a request should be allowed for this service.
        
        Returns True if the request should proceed, False if it should be
        rejected (circuit is open).
        """
        with self._lock:
            state = self._get_state_internal(service)
            
            if state == "closed":
                return True
            
            if state == "half-open":
                # Allow one test request, transition to half-open
                self._state[service] = "half-open"
                return True
            
            # state == "open"
            return False

    def record_failure(self, service: str) -> None:
        """Record a failure for a service."""
        with self._lock:
            current_failures = self._failures.get(service, 0) + 1
            self._failures[service] = current_failures
            self._last_failure_time[service] = time.time()
            
            current_state = self._get_state_internal(service)
            
            # If in half-open and failed, go back to open
            if current_state == "half-open":
                self._state[service] = "open"
                logger.warning(f"Circuit breaker: {service} failed in half-open, reopening")
            
            # If threshold reached, open the circuit
            elif current_failures >= self.failure_threshold:
                self._state[service] = "open"
                logger.warning(
                    f"Circuit breaker: {service} opened after {current_failures} failures"
                )

    def record_success(self, service: str) -> None:
        """Record a success for a service."""
        with self._lock:
            current_state = self._get_state_internal(service)
            
            # Reset on success
            self._failures[service] = 0
            self._state[service] = "closed"
            
            if current_state == "half-open":
                logger.info(f"Circuit breaker: {service} closed after successful test")

    def reset(self, service: Optional[str] = None) -> None:
        """
        Reset the circuit breaker state.
        
        Args:
            service: If provided, reset only this service. Otherwise reset all.
        """
        with self._lock:
            if service:
                self._failures.pop(service, None)
                self._last_failure_time.pop(service, None)
                self._state.pop(service, None)
            else:
                self._failures.clear()
                self._last_failure_time.clear()
                self._state.clear()

    async def call(
        self,
        service: str,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            service: The service identifier.
            func: The async function to call.
            *args: Arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.
            
        Returns:
            The result of the function.
            
        Raises:
            CircuitOpenError: If the circuit is open.
            Exception: Any exception raised by the function.
        """
        if not self.allow_request(service):
            raise CircuitOpenError(service)
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self.record_success(service)
            return result
        
        except Exception:
            self.record_failure(service)
            raise

    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for all tracked services.
        
        Returns:
            Dict mapping service names to their metrics (failures, state).
        """
        with self._lock:
            metrics = {}
            
            # Get all known services
            all_services = set(self._failures.keys()) | set(self._state.keys())
            
            for service in all_services:
                metrics[service] = {
                    "failures": self._failures.get(service, 0),
                    "state": self._get_state_internal(service),
                    "last_failure": self._last_failure_time.get(service),
                }
            
            return metrics


# Global circuit breaker instance for fallback services
_fallback_circuit_breaker: Optional[CircuitBreaker] = None


def get_fallback_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker for fallback services."""
    global _fallback_circuit_breaker
    if _fallback_circuit_breaker is None:
        _fallback_circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            reset_timeout=60.0,
        )
    return _fallback_circuit_breaker

