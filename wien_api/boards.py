# wien_api/boards.py
import re, time
from typing import Any, Dict, List
from .state import LAST_DATA

_BOARDS: Dict[str, Any] = {}

def set_boards(boards: Dict[str, Any]) -> None:
    global _BOARDS
    _BOARDS = boards or {}

def _match_line(line: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    if rule.get("name") and (line.get("name") or "").strip() != rule["name"]:
        return False
    rgx = rule.get("towards_regex")
    if rgx:
        tw = (line.get("towards") or "").strip()
        try:
            if not re.search(rgx, tw, flags=re.IGNORECASE):
                return False
        except re.error:
            return False
    return True

def _dedupe_and_limit(deps: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for d in deps or []:
        if not isinstance(d, dict): continue
        cd = d.get("countdown")
        if not isinstance(cd, (int, float)): continue
        key = f"{d.get('timeReal') or ''}|{d.get('timePlanned') or ''}|{cd}"
        if key in seen: continue
        seen.add(key); out.append(d)
    out.sort(key=lambda x: x.get("countdown", 1e9))
    return out[:limit] if (limit and limit > 0) else out

def _minutes_text(items: List[Dict[str, Any]], sep: str = " / ") -> str:
    parts: List[str] = []
    for d in items:
        cd = d.get("countdown")
        if isinstance(cd, float) and cd.is_integer():
            parts.append(str(int(cd)))
        else:
            parts.append(str(cd))
    return sep.join(parts)

def build_board(board_id: str) -> Dict[str, Any]:
    spec = _BOARDS.get(board_id)
    if not spec:
        return {"id": board_id, "title": board_id, "generatedAt": int(time.time()), "items": [], "max_departures": 0}

    default_limit = int(spec.get("max_departures") or 0)
    out_items: List[Dict[str, Any]] = []
    now = int(time.time())

    for item in LAST_DATA.values():
        for mon in item.get("items", []) or []:
            stop = (mon.get("stop") or {})
            title = (stop.get("title") or "").strip()
            plat = stop.get("platform") or None

            for r in spec.get("rules", []):
                if r.get("stop") and r["stop"].strip() != title:
                    continue
                if "platform" in r and (r["platform"] or None) != plat:
                    continue

                rule_limit = int(r.get("max_departures") or 0) or default_limit
                lines_ok = []
                for ln in mon.get("lines", []) or []:
                    if r.get("lines") and not any(_match_line(ln, lr) for lr in r["lines"]):
                        continue
                    ln2 = dict(ln)
                    ln2["departures"] = _dedupe_and_limit(ln.get("departures") or [], rule_limit)
                    ln2["countdown_text"] = _minutes_text(ln2.get("departures") or [])
                    lines_ok.append(ln2)

                if lines_ok:
                    out_items.append({
                        "municipality": stop.get("municipality", ""),
                        "platform": plat,
                        "title": stop.get("title", ""),
                        "rbl": stop.get("rbl", 0),
                        "lines": lines_ok,
                        "trafficInfoCategories": mon.get("trafficInfoCategories", []),
                        "trafficInfos": mon.get("trafficInfos", {})
                    })

    return {
        "id": board_id,
        "title": spec.get("title") or board_id,
        "generatedAt": now,
        "max_departures": default_limit,
        "items": out_items
    }

