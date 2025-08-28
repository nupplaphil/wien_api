import re

_topic_safe_re = re.compile(r"[^A-Za-z0-9_.\-]")

def safe_topic_fragment(s: str | None) -> str:
    """Nur A‑Z a‑z 0‑9 _ . - zulassen – Rest durch '_' ersetzen."""
    return _topic_safe_re.sub("_", (s or "").strip())
