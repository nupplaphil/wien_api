# wien_api/boards.py
from __future__ import annotations
import re, time
from typing import Any, Dict, List, Tuple
from .state import LAST_DATA

_BOARDS: Dict[str, Any] = {}

def set_boards(boards: Dict[str, Any]) -> None:
    """Set/replace board specs (raw dict from config.yaml)."""
    global _BOARDS
    _BOARDS = boards or {}

# ---------- helpers ----------

def _match_line(line: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    """Check if a WL 'line' matches a single line-rule (name, towards_regex)."""
    if not isinstance(line, dict) or not isinstance(rule, dict):
        return False
    want_name = (rule.get("name") or "").strip()
    if want_name and (line.get("name") or "").strip() != want_name:
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
    """Remove duplicates by (timeReal|timePlanned|countdown), sort by countdown, and limit."""
    seen = set()
    out: List[Dict[str, Any]] = []
    for d in deps or []:
        if not isinstance(d, dict):
            continue
        cd = d.get("countdown")
        if not isinstance(cd, (int, float)):
            continue
        key = f"{d.get('timeReal') or ''}|{d.get('timePlanned') or ''}|{cd}"
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    out.sort(key=lambda x: x.get("countdown", 1e9))
    return out[:limit] if (isinstance(limit, int) and limit > 0) else out

def _minutes_text(items: List[Dict[str, Any]], sep: str = " / ") -> str:
    parts: List[str] = []
    for d in items or []:
        cd = d.get("countdown")
        if isinstance(cd, float) and cd.is_integer():
            parts.append(str(int(cd)))
        else:
            parts.append(str(cd))
    return sep.join(parts)

def _line_key(ln: Dict[str, Any], display_title: str | None) -> Tuple[str, str, str]:
    """Stable key to merge the same line across multiple monitors of the same stop/rule."""
    return (
        (ln.get("name") or "").strip(),
        (ln.get("towards") or "").strip(),
        (display_title or "").strip(),
    )

# ---------- main ----------

def build_board(board_id: str) -> Dict[str, Any]:
    """
    Build a curated board based on config:
      boards:
        vz:
          title: "Vorzimmer"
          max_departures: 3
          rules:
            - stop: "Josef-Baumann-Gasse"
              title: "JB (Süd)"
              lines:
                - { name: "25", towards_regex: "Floridsdorf\\s*U", title: "Floridsdorf" }
                - { name: "26", towards_regex: "Hausfeldstraße\\s*U", title: "Hausfeldstraße" }
                - { name: "27", towards_regex: "Strebersdorf\\s*",   title: "Strebersdorf" }
            - stop: "Prandaugasse"
              title: "Prandaugasse (Süd)"
              lines:
                - { name: "25", towards_regex: "Floridsdorf\\s*U", title: "Floridsdorf" }
    Output item fields:
      - name: original stop name
      - title: rule title (display)
      - lines[].title: line display title from rule (if provided)
    """
    spec = _BOARDS.get(board_id)
    now = int(time.time())
    if not spec or not isinstance(spec, dict):
        return {"id": board_id, "title": board_id, "generatedAt": now, "items": [], "max_departures": 0}

    board_title = spec.get("title") or board_id
    default_limit = int(spec.get("max_departures") or 0)
    rules = spec.get("rules") or []

    # Aggregate items per RULE to avoid duplicates when the same stop appears multiple times
    # Key includes: rule_title, stop_name, and optionally platform if rule specifies it.
    items_map: Dict[Tuple[str, str, str | None], Dict[str, Any]] = {}

    for cache_item in (LAST_DATA or {}).values():
        for mon in (cache_item.get("items") or []):
            stop = (mon.get("stop") or {})
            stop_name = (stop.get("title") or "").strip()
            stop_platform = stop.get("platform") or None
            stop_municipality = stop.get("municipality", "")
            stop_rbl = stop.get("rbl", 0)

            for r in rules:
                if not r or not isinstance(r, dict):
                    continue  # tolerate empty entries ('-')
                want_stop = (r.get("stop") or "").strip()
                if want_stop and want_stop != stop_name:
                    continue
                # platform exact match if provided in rule
                rule_platform = r.get("platform") if "platform" in r else None
                if "platform" in r and (rule_platform or None) != stop_platform:
                    continue

                rule_title = r.get("title") or stop_name
                rule_limit = int(r.get("max_departures") or 0) or default_limit
                line_rules = [lr for lr in (r.get("lines") or []) if isinstance(lr, dict)]

                # group key for this rule/stop (include platform if rule specified one)
                key = (rule_title, stop_name, rule_platform if "platform" in r else None)

                # ensure item exists
                if key not in items_map:
                    items_map[key] = {
                        "municipality": stop_municipality,
                        "platform": stop_platform if "platform" in r else stop_platform,  # show actual platform
                        "rbl": stop_rbl,
                        "name": stop_name,         # original stop name
                        "title": rule_title,       # display (from rule)
                        "lines": [],
                        "trafficInfoCategories": mon.get("trafficInfoCategories", []),
                        "trafficInfos": mon.get("trafficInfos", {}),
                        # internal helper: lines map for merging
                        "_lines_map": {}
                    }
                item_ref = items_map[key]

                # Build/merge matching lines
                for ln in (mon.get("lines") or []):
                    # If there are line rules, require at least one match; else accept all
                    if line_rules:
                        matched_lr = None
                        for lr in line_rules:
                            if _match_line(ln, lr):
                                matched_lr = lr
                                break
                        if not matched_lr:
                            continue
                        display_title = (matched_lr.get("title") or "").strip() or None
                    else:
                        matched_lr = None
                        display_title = None

                    # Dedup + limit departures per rule
                    deps = _dedupe_and_limit(ln.get("departures") or [], rule_limit)

                    # Merge lines across multiple monitors for the same rule item
                    lkey = _line_key(ln, display_title)
                    lm: Dict[Tuple[str, str, str], Dict[str, Any]] = item_ref["_lines_map"]  # type: ignore
                    if lkey not in lm:
                        ln2 = {
                            "name": ln.get("name"),
                            "type": ln.get("type"),
                            "towards": ln.get("towards"),
                            "departures": deps,
                            "countdown_text": _minutes_text(deps),
                        }
                        if display_title:
                            ln2["title"] = display_title
                        lm[lkey] = ln2
                    else:
                        # merge departures (union by key, then re-trim)
                        existing = lm[lkey]
                        merged = (existing.get("departures") or []) + deps
                        merged = _dedupe_and_limit(merged, rule_limit)
                        existing["departures"] = merged
                        existing["countdown_text"] = _minutes_text(merged)

                # keep traffic info fresh (last one wins)
                item_ref["trafficInfoCategories"] = mon.get("trafficInfoCategories", [])
                item_ref["trafficInfos"] = mon.get("trafficInfos", {})

    # Materialize items list from items_map
    out_items: List[Dict[str, Any]] = []
    for itm in items_map.values():
        lines = list(itm.pop("_lines_map", {}).values())
        itm["lines"] = lines
        out_items.append(itm)

    return {
        "id": board_id,
        "title": board_title,
        "generatedAt": now,
        "max_departures": default_limit,
        "items": out_items
    }

