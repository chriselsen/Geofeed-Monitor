"""Slack alerting for geofeed monitoring."""

import json
import os
from urllib.request import urlopen, Request

# Comprehensive OFAC sanctioned countries (configurable per feed via feed config)
DEFAULT_EMBARGO_COUNTRIES = {"IR", "CU", "KP", "SY"}

# Default thresholds
ACCURACY_DROP_THRESHOLD_PP = 5.0   # percentage point drop triggers alert
ACCURACY_FLOOR_THRESHOLD = 80.0    # absolute floor triggers alert


def _webhook_url(feed_key, alert_type):
    """Resolve webhook URL with fallback chain:
    SLACK_WEBHOOK_<FEED>_<TYPE> -> SLACK_WEBHOOK_<TYPE> -> None
    """
    specific = os.environ.get(f"SLACK_WEBHOOK_{feed_key}_{alert_type}")
    if specific:
        return specific
    return os.environ.get(f"SLACK_WEBHOOK_{alert_type}")


def _post(url, payload):
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        urlopen(req, timeout=10)
    except Exception as e:
        print(f"  Slack webhook failed: {e}")


def _send(feed_key, alert_type, payload):
    url = _webhook_url(feed_key, alert_type)
    if not url:
        return
    _post(url, payload)


def alert_unreachable(feed):
    feed_key = _feed_key(feed)
    _send(feed_key, "UNREACHABLE", {
        "feed": feed["title"],
        "url": feed["url"],
    })


def _feed_key(feed):
    return feed["output"].stem.upper().replace("-", "_")


def _prefixes_str(prefixes):
    return ", ".join(sorted(prefixes))


def check_and_alert(feed, results, stats, prev_state, has_mm=True, has_ip=True, has_i2l=True):
    """Run all alert checks, dispatch webhooks, return new state."""
    feed_key = _feed_key(feed)
    embargo = set(feed.get("embargo_countries", DEFAULT_EMBARGO_COUNTRIES))
    drop_pp = feed.get("accuracy_drop_threshold_pp", ACCURACY_DROP_THRESHOLD_PP)
    floor = feed.get("accuracy_floor_threshold", ACCURACY_FLOOR_THRESHOLD)

    # Build current state
    current_locations = {}
    current_prefixes = set()
    for country_code, display_name, loc_results in results:
        if not loc_results:
            continue
        loc_key = display_name
        prefixes = {r[0] for r in loc_results}
        current_prefixes.update(prefixes)
        from .stats import compute_pct
        country_matches = []
        city_matches = []
        for r in loc_results:
            country_matches += ([r[7]] if has_mm else []) + ([r[10]] if has_ip else []) + ([r[13]] if has_i2l else [])
            city_matches += ([r[8]] if has_mm else []) + ([r[14]] if has_i2l else [])
        country_pct = compute_pct(country_matches)
        city_pct = compute_pct(city_matches)
        current_locations[loc_key] = {
            "country": country_code,
            "prefixes": sorted(prefixes),
            "country_pct": country_pct,
            "city_pct": city_pct,
        }

    prev_locations = prev_state.get("locations", {}) if prev_state else {}
    prev_prefixes = set(prev_state.get("prefixes", [])) if prev_state else set()

    # --- Embargo country ---
    for loc_key, loc in current_locations.items():
        if loc["country"] in embargo:
            _send(feed_key, "EMBARGO", {
                "feed": feed["title"],
                "location": loc_key,
                "country": loc["country"],
                "prefix_count": len(loc["prefixes"]),
                "prefixes": _prefixes_str(loc["prefixes"]),
            })

    # --- New location ---
    for loc_key, loc in current_locations.items():
        if loc_key not in prev_locations:
            _send(feed_key, "NEW_LOCATION", {
                "feed": feed["title"],
                "location": loc_key,
                "country": loc["country"],
                "prefix_count": len(loc["prefixes"]),
                "prefixes": _prefixes_str(loc["prefixes"]),
            })

    # --- Removed location ---
    for loc_key, loc in prev_locations.items():
        if loc_key not in current_locations:
            _send(feed_key, "REMOVED_LOCATION", {
                "feed": feed["title"],
                "location": loc_key,
                "country": loc["country"],
                "prefix_count": len(loc["prefixes"]),
                "prefixes": _prefixes_str(loc["prefixes"]),
            })

    # --- New / removed prefixes within existing locations ---
    for loc_key, loc in current_locations.items():
        if loc_key not in prev_locations:
            continue  # already alerted as new location
        prev_pfx = set(prev_locations[loc_key]["prefixes"])
        curr_pfx = set(loc["prefixes"])
        added = curr_pfx - prev_pfx
        removed = prev_pfx - curr_pfx
        if added:
            _send(feed_key, "NEW_PREFIX", {
                "feed": feed["title"],
                "location": loc_key,
                "country": loc["country"],
                "prefix_count": len(added),
                "prefixes": _prefixes_str(added),
            })
        if removed:
            _send(feed_key, "REMOVED_PREFIX", {
                "feed": feed["title"],
                "location": loc_key,
                "country": loc["country"],
                "prefix_count": len(removed),
                "prefixes": _prefixes_str(removed),
            })

    # --- Accuracy drop ---
    for loc_key, loc in current_locations.items():
        if loc_key not in prev_locations:
            continue
        prev_loc = prev_locations[loc_key]
        for metric in ("country", "city"):
            curr_pct = loc.get(f"{metric}_pct")
            prev_pct = prev_loc.get(f"{metric}_pct")
            if curr_pct is None or prev_pct is None:
                continue
            dropped_pp = prev_pct - curr_pct
            if dropped_pp >= drop_pp or (curr_pct < floor and prev_pct >= floor):
                _send(feed_key, "ACCURACY_DROP", {
                    "feed": feed["title"],
                    "location": loc_key,
                    "metric": metric,
                    "previous_pct": round(prev_pct, 1),
                    "current_pct": round(curr_pct, 1),
                    "drop_pp": round(dropped_pp, 1),
                })

    # --- Prefix no longer routed ---
    # r[16] = routed, r[17] = route_match, r[18] = too_specific
    for _, _, loc_results in results:
        for r in loc_results:
            prefix = r[0]
            routed = r[16]
            too_specific = r[18]
            if too_specific:
                continue
            was_routed = prev_state.get("routed", {}).get(prefix) if prev_state else None
            if was_routed is True and not routed:
                _send(feed_key, "UNROUTED", {
                    "feed": feed["title"],
                    "prefix": prefix,
                    "proto": "IPv6" if r[1] else "IPv4",
                })

    # --- LOCODE violation introduced ---
    for _, _, loc_results in results:
        for r in loc_results:
            prefix = r[0]
            issues = r[15]
            if not issues:
                continue
            prev_issues = prev_state.get("locode_issues", {}).get(prefix, []) if prev_state else []
            if not prev_issues:
                _send(feed_key, "LOCODE", {
                    "feed": feed["title"],
                    "prefix": prefix,
                    "location": f"{r[2]}, {r[3]}, {r[4]}".strip(", "),
                    "issue": issues[0],
                })

    # Build and return new state
    new_state = {
        "locations": current_locations,
        "prefixes": sorted(current_prefixes),
        "routed": {
            r[0]: r[16]
            for _, _, loc_results in results
            for r in loc_results
            if not r[18]
        },
        "locode_issues": {
            r[0]: list(r[15])
            for _, _, loc_results in results
            for r in loc_results
            if r[15]
        },
    }
    return new_state
