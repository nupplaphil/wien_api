from queue import Queue
from typing import Dict, Any, Set, List

# In‑Memory Cache der letzten MQTT‑Items (key = ident)
LAST_DATA: Dict[str, Dict[str, Any]] = {}

# Sehr leichte SSE‑Hub Umsetzung
class SSEHub:
    def __init__(self) -> None:
        self._subs: Set[Queue] = set()

    def subscribe(self) -> Queue:
        q: Queue = Queue(maxsize=100)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: Queue) -> None:
        self._subs.discard(q)

    def publish(self, json_str: str) -> None:
        dead: List[Queue] = []
        for q in list(self._subs):
            try:
                q.put_nowait(json_str)
            except Exception:
                try:
                    _ = q.get_nowait()
                    q.put_nowait(json_str)
                except Exception:
                    dead.append(q)
        for q in dead:
            self.unsubscribe(q)

HUB = SSEHub()
