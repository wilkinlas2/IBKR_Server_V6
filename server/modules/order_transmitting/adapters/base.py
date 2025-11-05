from __future__ import annotations
from typing import Protocol, Any, Tuple

class TransmitAdapter(Protocol):
    def send(self, order: dict) -> Tuple[bool, dict[str, Any]]:
        """
        Verzendt order naar broker.
        Return: (ok, result)
          ok=True: result bevat minstens {"status": "queued"|"filled", ...}
          ok=False: result bevat {"status":"error","error":"..."}
        """
        ...
