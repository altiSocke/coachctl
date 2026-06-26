"""
Signal bot — sends the next day's training plan to a phone via signal-cli-rest-api.

Environment variables (loaded from <DATA_ROOT>/.env):
    SIGNAL_API_URL      Base URL of the signal-cli-rest-api instance
                        e.g. http://localhost:9922
    SIGNAL_NUMBER       The Signal number registered with signal-cli-rest-api
                        e.g. +41791234567
    SIGNAL_RECIPIENT    Phone number to send to (can be the same as SIGNAL_NUMBER
                        if you are sending to yourself)

Usage via CLI:
    uv run coachctl signal daily-plan              # send tomorrow's plan
    uv run coachctl signal daily-plan --date 2026-06-20  # preview any date
    uv run coachctl signal daily-plan --dry-run    # print without sending
    uv run coachctl signal check                   # test API connectivity
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from . import paths
from .config import load_athlete
from .db import get_conn
from .events import Event, get_calendar

_MAX_MSG_CHARS = 3_500
_SENT_LOG = "signal_last_sent.txt"

# ── Config ────────────────────────────────────────────────────────────────────


def get_signal_config() -> dict[str, str]:
    """
    Read Signal env vars.  Raises RuntimeError with a clear message if any
    required variable is missing or empty.
    """
    required = ("SIGNAL_API_URL", "SIGNAL_NUMBER", "SIGNAL_RECIPIENT")
    missing: list[str] = []
    cfg: dict[str, str] = {}
    for var in required:
        val = os.environ.get(var, "").strip()
        if not val:
            missing.append(var)
        else:
            cfg[var] = val
    if missing:
        raise RuntimeError(
            f"Signal bot not configured. Missing env vars: {', '.join(missing)}\n"
            "Add them to <DATA_ROOT>/.env — see .env.example for the template."
        )
    return cfg


# ── Formatting helpers ────────────────────────────────────────────────────────


def _detect_dominant_sport(events: list[Event]) -> str:
    """Return 'run', 'ride', or 'all' based on planned sessions."""
    _run_kws = ("run", "trail", "jog")
    _ride_kws = ("ride", "cycling", "spin", "bike", "velo")

    def _text(e: Event) -> str:
        return (e.name + " " + (e.summary or "")).lower()

    run_count = sum(
        1
        for e in events
        if e.kind in ("training", "untracked") and any(kw in _text(e) for kw in _run_kws)
    )
    ride_count = sum(
        1
        for e in events
        if e.kind in ("training", "untracked") and any(kw in _text(e) for kw in _ride_kws)
    )
    if run_count > 0 and ride_count == 0:
        return "run"
    if ride_count > 0 and run_count == 0:
        return "ride"
    return "all"


def _tsb_label(tsb: float) -> str:
    if tsb >= 15:
        return "fresh"
    if tsb >= 5:
        return "recovering"
    if tsb >= -10:
        return "mid-block fatigue — normal"
    if tsb >= -20:
        return "fatigued — keep intensity controlled"
    return "very fatigued — reduce load"


def _sport_icon(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("run", "trail", "jog")):
        return "Running"
    if any(k in t for k in ("ride", "cycling", "spin", "bike", "velo")):
        return "Cycling"
    if any(k in t for k in ("strength", "gym", "yoga", "drill")):
        return "Strength"
    return "Session"


def _format_training_event(event: Event) -> str:
    """Format a single training or untracked event for a Signal message."""
    icon = _sport_icon(event.name + " " + (event.summary or ""))
    lines: list[str] = [f"[{icon}] {event.name}", "-" * 38]

    if event.duration_min:
        lines.append(f"Duration:  {event.duration_min} min")

    if event.summary:
        lines.append(f"Details:   {event.summary.strip()}")

    if event.notes:
        lines.append(f"Notes:     {event.notes.strip()}")

    if event.estimated_tss:
        lines.append(f"Est. TSS:  {event.estimated_tss:.0f}")

    return "\n".join(lines)


def _format_race_event(event: Event) -> str:
    """Condensed race-day brief extracted from race card payload."""
    p = event.payload or {}
    goal = p.get("goal", {})
    pacing = p.get("pacing", [])
    nutrition = p.get("nutrition", {})
    course = p.get("course", {})
    principles = p.get("key_principles", [])

    priority = p.get("priority", "")
    distance = course.get("distance_km", "")
    elev = course.get("elevation_gain_m", "")

    lines: list[str] = []
    header = f"[RACE] {event.name}"
    if priority:
        header += f" [{priority}]"
    lines.append(header)
    lines.append("=" * 38)

    meta: list[str] = []
    if distance:
        meta.append(f"{distance} km")
    if elev:
        meta.append(f"+/-{elev} m")
    if event.start_time:
        meta.append(f"Start {event.start_time}")
    if meta:
        lines.append("  ".join(meta))

    # Goals
    a = goal.get("a_goal") or goal.get("a") or ""
    b = goal.get("b_goal") or goal.get("b") or ""
    c = goal.get("c_goal") or goal.get("c") or ""
    if any([a, b, c]):
        lines.append("")
        lines.append("GOAL:")
        for label, text in (("A", a), ("B", b), ("C", c)):
            if text:
                lines.append(f"  {label}) {text}")

    # Pacing — max 5 segments
    if pacing:
        lines.append("")
        lines.append("PACING:")
        for seg in pacing[:5]:
            km = seg.get("km", "")
            name = seg.get("segment", "")
            target = seg.get("target", "")
            cue = seg.get("cue", "")
            seg_line = f"  km {km}  {name}"
            if target:
                seg_line += f"\n    -> {target}"
            lines.append(seg_line)
            if cue:
                short = cue[:80] + ("..." if len(cue) > 80 else "")
                lines.append(f"    {short}")

    # Nutrition — pre + during (max 3 items)
    during = nutrition.get("during", [])
    pre = nutrition.get("pre_race", [])
    if pre or during:
        lines.append("")
        lines.append("NUTRITION:")
        for item in pre[:1]:
            lines.append(f"  {item.get('time', '')}: {item.get('action', '')}")
        for item in during[:3]:
            km_t = item.get("time_or_km", "")
            action = item.get("action", "")
            lines.append(f"  {km_t}: {action}")

    # Key principles — max 3
    if principles:
        lines.append("")
        lines.append("KEY PRINCIPLES:")
        for p_item in principles[:3]:
            lines.append(f"  * {p_item}")

    return "\n".join(lines)


def format_daily_plan(
    target_date: str,
    events: list[Event],
    athlete_profile: dict[str, Any],
    fitness_by_sport: dict[str, dict[str, float]],
    dashboard_url: str = "",
) -> str:
    """
    Build the complete Signal message for target_date.

    Parameters
    ----------
    target_date     : ISO YYYY-MM-DD — the date being described
    events          : calendar events for that date; must be pre-filtered
                      (no cancelled, no kind='activity')
    athlete_profile : dict from load_athlete()
    fitness_by_sport: {'all': {'ctl': ..., 'atl': ..., 'tsb': ...}, ...}
    dashboard_url   : optional URL appended to the message footer

    The message is hard-capped at _MAX_MSG_CHARS with a truncation trailer.
    """
    from datetime import datetime

    dt = datetime.strptime(target_date, "%Y-%m-%d")
    day_label = f"{dt:%a} {dt.day} {dt:%b}"  # "Mon 15 Jun"; portable across Windows/POSIX.

    # Week number from first training event payload
    week_num: int | None = None
    for e in events:
        wn = (e.payload or {}).get("week_number")
        if wn:
            week_num = int(wn)
            break
    week_str = f" — Week {week_num}" if week_num else ""

    # Dominant sport -> which fitness row to show
    sport = _detect_dominant_sport(events)
    fit = fitness_by_sport.get(sport) or fitness_by_sport.get("all") or {}
    ctl = fit.get("ctl", 0.0)
    atl = fit.get("atl", 0.0)
    tsb = fit.get("tsb", 0.0)

    # Split races from training
    race_events = [e for e in events if e.kind == "race"]
    training_events = [e for e in events if e.kind in ("training", "untracked")]
    is_race_day = bool(race_events)

    # Header
    header = f"=== {day_label}{week_str}"
    if is_race_day:
        header += " — RACE DAY"
    header += " ==="

    lines: list[str] = [header, ""]
    lines.append(f"CTL {ctl:.1f} · ATL {atl:.1f} · TSB {tsb:+.1f}  ({_tsb_label(tsb)})")

    if training_events:
        total_tss = sum(e.estimated_tss or 0.0 for e in training_events)
        if total_tss > 0:
            lines.append(f"Est. load: ~{total_tss:.0f} TSS")

    lines.append("")

    if not events:
        lines.append("Rest day. No training scheduled.")
    else:
        for e in race_events:
            lines.append(_format_race_event(e))
            lines.append("")
        for e in training_events:
            lines.append(_format_training_event(e))
            lines.append("")

    if dashboard_url:
        lines.append(f"Dashboard: {dashboard_url}")

    msg = "\n".join(lines).rstrip()

    if len(msg) > _MAX_MSG_CHARS:
        trailer = "\n...(truncated — full plan on dashboard)"
        msg = msg[: _MAX_MSG_CHARS - len(trailer)] + trailer

    return msg


# ── Transport ─────────────────────────────────────────────────────────────────


def send_signal_message(
    api_url: str,
    number: str,
    recipient: str,
    message: str,
    timeout: float = 15.0,
) -> None:
    """
    POST message to signal-cli-rest-api /v2/send.

    Raises
    ------
    httpx.HTTPError on network failure.
    RuntimeError on non-2xx response.
    """
    url = api_url.rstrip("/") + "/v2/send"
    payload: dict[str, Any] = {
        "message": message,
        "number": number,
        "recipients": [recipient],
    }
    resp = httpx.post(url, json=payload, timeout=timeout)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"signal-cli-rest-api returned HTTP {resp.status_code}: {resp.text[:200]}"
        )


def check_connectivity(api_url: str, timeout: float = 5.0) -> tuple[bool, str]:
    """
    Test connectivity to signal-cli-rest-api /v1/about.

    Returns
    -------
    (ok: bool, message: str)
    """
    url = api_url.rstrip("/") + "/v1/about"
    try:
        resp = httpx.get(url, timeout=timeout)
        if resp.status_code == 200:
            return True, f"Connected to {api_url} — signal-cli-rest-api is running."
        return False, f"HTTP {resp.status_code} from {url}: {resp.text[:100]}"
    except httpx.ConnectError:
        return False, f"Cannot connect to {api_url}. Is the Docker container running?"
    except Exception as exc:  # noqa: BLE001
        return False, f"Error: {exc}"


# ── Duplicate-send guard ──────────────────────────────────────────────────────


def _sent_log_path(data_root: Path) -> Path:
    return data_root / "data" / _SENT_LOG


def last_sent_date(data_root: Path) -> str | None:
    """Return the last target date that was sent, or None."""
    p = _sent_log_path(data_root)
    if p.exists():
        return p.read_text("utf-8").strip() or None
    return None


def mark_sent(data_root: Path, target_date: str) -> None:
    """Record target_date as sent."""
    p = _sent_log_path(data_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(target_date, encoding="utf-8")


# ── Orchestrator ──────────────────────────────────────────────────────────────


def send_tomorrows_plan(
    data_root: Path | None = None,
    target_date: str = "",
    force: bool = False,
    dashboard_url: str = "",
) -> str:
    """
    Query the calendar for target_date (default: tomorrow), format the plan,
    and send it via Signal.

    Returns a status string suitable for CLI output.
    Raises RuntimeError / httpx.HTTPError on send failure (so cron can detect it).
    """
    from dotenv import load_dotenv

    dr = data_root or paths.data_root()

    # Load env vars from personal .env (no-op if file missing)
    env_file = dr / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    cfg = get_signal_config()

    tomorrow = target_date or (date.today() + timedelta(days=1)).isoformat()

    # Duplicate-send guard
    if not force:
        last = last_sent_date(dr)
        if last == tomorrow:
            return f"Already sent plan for {tomorrow}. Use --force to resend."

    # Calendar for target date — filter cancelled events and completed activities
    all_events = get_calendar(tomorrow, tomorrow)
    events = [e for e in all_events if e.status != "cancelled" and e.kind != "activity"]

    athlete = load_athlete()

    # Fitness snapshot keyed by sport_category
    fitness_by_sport: dict[str, dict[str, float]] = {}
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT sport_category, ctl, atl, tsb
            FROM fitness
            WHERE date = (SELECT MAX(date) FROM fitness)
            """,
        ).fetchall()
        for row in rows:
            fitness_by_sport[row["sport_category"]] = {
                "ctl": float(row["ctl"] or 0.0),
                "atl": float(row["atl"] or 0.0),
                "tsb": float(row["tsb"] or 0.0),
            }

    msg = format_daily_plan(
        target_date=tomorrow,
        events=events,
        athlete_profile=athlete,
        fitness_by_sport=fitness_by_sport,
        dashboard_url=dashboard_url,
    )

    send_signal_message(
        api_url=cfg["SIGNAL_API_URL"],
        number=cfg["SIGNAL_NUMBER"],
        recipient=cfg["SIGNAL_RECIPIENT"],
        message=msg,
    )

    mark_sent(dr, tomorrow)
    return f"Plan for {tomorrow} sent to {cfg['SIGNAL_RECIPIENT']} ({len(msg)} chars)."
