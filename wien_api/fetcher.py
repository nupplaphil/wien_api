# wien_api/fetcher.py
import requests
from typing import List, Dict, Any
from .config import WienConf

def build_urls(cfg: WienConf) -> List[str]:
    qs_act = [("activateTrafficInfo", a) for a in (cfg.activate_info or [])]
    urls: List[str] = []
    for sid in cfg.stop_ids or []:
        parts = ["stopId=" + sid] + [f"{k}={v}" for k, v in qs_act] + ["sender=" + cfg.sender]
        urls.append(cfg.base_url + "?" + "&".join(parts))
    for diva in cfg.diva_ids or []:
        parts = ["diva=" + diva] + [f"{k}={v}" for k, v in qs_act] + ["sender=" + cfg.sender]
        urls.append(cfg.base_url + "?" + "&".join(parts))
    return urls

def _headers(cfg: WienConf) -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": cfg.user_agent,
    }

def fetch_all(cfg: WienConf, session: requests.Session) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for url in build_urls(cfg):
        try:
            r = session.get(url, headers=_headers(cfg), timeout=cfg.http_timeout)
            if not r.ok:
                out.append({"query": url, "ok": False, "status": r.status_code, "items": []})
                continue
            payload = r.json() if r.content else {}
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            items = []
            for mon in data.get("monitors", []) or []:
                stop = (mon.get("locationStop", {}) or {}).get("properties", {}) or {}
                lines = []
                for ln in mon.get("lines", []) or []:
                    deps = (ln.get("departures", {}) or {}).get("departure", []) or []
                    lines.append({
                        "name": ln.get("name"),
                        "towards": ln.get("towards"),
                        "type": ln.get("type"),
                        "departures": [{
                            "countdown": d.get("departureTime", {}).get("countdown"),
                            "timePlanned": d.get("departureTime", {}).get("timePlanned"),
                            "timeReal": d.get("departureTime", {}).get("timeReal"),
                        } for d in deps][:8]
                    })
                tinfo = data.get("trafficInfos") or data.get("trafficInfo") or {}
                categories = data.get("trafficInfoCategories", []) or []
                items.append({
                    "stop": {
                        "title": stop.get("title"),
                        "municipality": stop.get("municipality"),
                        "platform": stop.get("platform") or stop.get("gate"),
                        "rbl": (stop.get("attributes", {}) or {}).get("rbl"),
                    },
                    "lines": lines,
                    "trafficInfoCategories": categories,
                    "trafficInfos": tinfo
                })
            out.append({"query": url, "ok": True, "items": items, "raw": None})
        except Exception as e:
            out.append({"query": url, "ok": False, "error": str(e), "items": []})
    return out

