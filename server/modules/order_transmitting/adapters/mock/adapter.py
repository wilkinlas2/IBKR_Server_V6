from __future__ import annotations
import random

class MockAdapter:
    """Mock: direct queued -> (worker maakt filled)."""
    def send(self, order: dict):
        # We laten de worker het 'filled' zetten (na delay).
        # Hier enkel succesvolle queueing simuleren.
        return True, {"status": "queued", "detail": order, "sim": True}

ADAPTER = MockAdapter()
