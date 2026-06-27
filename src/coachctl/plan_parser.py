"""
Parse a training plan markdown file into structured data.

Used by both the site generator and the calendar integration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class Session:
    day_label: str  # e.g. "Mon Apr 20"
    date: str | None  # ISO date YYYY-MM-DD if parseable
    name: str  # e.g. "Aerobic run + strides + Core"
    details: str  # full details text
    completed: bool = False


@dataclass
class Week:
    number: int
    title: str  # e.g. "Recovery → Base Entry"
    target_tss: int | None = None
    phase: str = ""
    sessions: list[Session] = field(default_factory=list)
    all_completed: bool = False


@dataclass
class Plan:
    title: str
    athlete_info: str
    period: str
    event: str
    weeks: list[Week] = field(default_factory=list)


def _parse_date(day_label: str, year: str | None = None) -> str | None:
    """Try to extract YYYY-MM-DD from a day label like 'Mon Apr 20' or 'Sat/Sun Sep 6'."""
    if year is None:
        year = str(date.today().year)
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})", day_label)
    if m:
        try:
            parsed = datetime.strptime(f"{m.group(1)} {m.group(2).zfill(2)} {year}", "%b %d %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _extract_year_from_period(period: str) -> str | None:
    """Extract a 4-digit year from a period string like 'Apr 2026 – Aug 2026'."""
    m = re.search(r"\b(20\d{2})\b", period)
    return m.group(1) if m else None


def parse_plan(markdown: str) -> Plan:
    """Parse a training plan markdown string into a Plan dataclass."""
    lines = markdown.split("\n")

    # Extract header info
    title = ""
    athlete_info = ""
    period = ""
    event = ""

    for line in lines[:10]:
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("**Athlete:**"):
            athlete_info = line.replace("**Athlete:**", "").strip()
        elif line.startswith("**Period:**"):
            period = line.replace("**Period:**", "").strip()
        elif line.startswith("**A-Event:**"):
            event = line.replace("**A-Event:**", "").strip()

    plan = Plan(
        title=title,
        athlete_info=athlete_info,
        period=period,
        event=event,
    )

    # Infer year from period string, fall back to current year
    plan_year = _extract_year_from_period(period)

    # Parse weeks
    current_phase = ""
    current_week: Week | None = None

    # Match phase headers
    phase_re = re.compile(r"^## (PHASE \d+.*)")
    # Match week headers like "### Week 1 (Apr 18–24) — Recovery → Base Entry | Target TSS: ~180"
    week_re = re.compile(
        r"^### Week (\d+)\s*\(([^)]+)\)\s*[—–-]\s*(.+?)(?:\s*\|\s*Target TSS:\s*~?(\d+))?(?:\s*\|[^|]*)?\s*$"
    )
    # Match table rows: | Day | Session | Details |
    row_re = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")

    for line in lines:
        # Phase header
        pm = phase_re.match(line)
        if pm:
            current_phase = pm.group(1).strip()
            continue

        # Week header
        wm = week_re.match(line)
        if wm:
            if current_week:
                plan.weeks.append(current_week)
            current_week = Week(
                number=int(wm.group(1)),
                title=wm.group(3).strip(),
                target_tss=int(wm.group(4)) if wm.group(4) else None,
                phase=current_phase,
            )
            continue

        # Table row (skip header/separator rows)
        rm = row_re.match(line)
        if rm and current_week is not None:
            day_label = rm.group(1).strip()
            session_name = rm.group(2).strip()
            details = rm.group(3).strip()

            # Skip table header rows
            if day_label.lower() in ("day", "-----", "---") or session_name.lower() == "session":
                continue
            if set(day_label) <= {"-", " "}:
                continue
            # Skip phase-end summary rows and any row without a parseable date
            # (e.g. "End Phase 1 (May 15) | 40–44 | 0 to +5 | ...").
            if _parse_date(day_label, plan_year) is None:
                continue

            # Check if completed (✅ in the line)
            completed = "✅" in line

            # Clean up markdown bold/emoji from session name
            clean_name = re.sub(r"[*🏔️🏁🏋️]", "", session_name).strip()

            session = Session(
                day_label=day_label,
                date=_parse_date(day_label, plan_year),
                name=clean_name,
                details=details,
                completed=completed,
            )
            current_week.sessions.append(session)

    # Append last week
    if current_week:
        plan.weeks.append(current_week)

    return plan


# Ordered from most to least specific so "vo2max" matches before "moderate" etc.
_INTENSITY_KEYWORDS: list[tuple[str, str]] = [
    ("anaerobic", "anaerobic"),
    ("vo2max", "vo2max"),
    ("vo2", "vo2max"),
    ("threshold", "threshold"),
    ("tempo", "tempo"),
    ("moderate", "moderate"),
    ("z3", "moderate"),
    ("recovery", "recovery"),
    ("z1", "recovery"),
    ("easy", "easy"),
    ("z2", "easy"),
]


def parse_session_duration_intensity(details: str) -> tuple[float | None, str | None]:
    """Extract (duration_min, intensity_label) from a session details string.

    Returns ``(None, None)`` for any field that cannot be determined.

    Examples
    --------
    >>> parse_session_duration_intensity("60 min easy Z2 run")
    (60.0, 'easy')
    >>> parse_session_duration_intensity("45 min threshold intervals + cool-down")
    (45.0, 'threshold')
    >>> parse_session_duration_intensity("Rest")
    (None, None)
    """
    text = details.lower()

    # Duration: first integer followed by "min" or "minutes"
    dur_match = re.search(r"(\d+(?:\.\d+)?)\s*min(?:utes?)?", text)
    duration_min: float | None = float(dur_match.group(1)) if dur_match else None

    # Intensity: first keyword match in priority order
    intensity: str | None = None
    for keyword, label in _INTENSITY_KEYWORDS:
        if keyword in text:
            intensity = label
            break

    return duration_min, intensity


# Sport detection keywords, matched as WHOLE WORDS (so "strides" does not match
# "ride", "running" does match "run" via the stem list). Cycling terms win over
# generic ones only when a real cycling word is present. Anything unmatched
# defaults to "run" (the conservative, higher-IF table).
_RIDE_KEYWORDS = ("ride", "rides", "bike", "biking", "cycling", "spin", "trainer", "zwift", "gravel", "mtb")
_RUN_KEYWORDS = ("run", "runs", "running", "jog", "jogging", "fartlek", "strides", "shakeout")
_STRENGTH_KEYWORDS = ("strength", "gym", "lifting", "weights", "core")


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    """True if any of ``words`` appears as a whole word in ``text``."""
    import re

    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def detect_session_sport(text: str) -> str:
    """Infer a coarse sport label from a session's name/details text.

    Returns one of ``"ride"``, ``"run"``, ``"strength"`` or ``"rest"``. Used to
    pick the correct intensity→IF table for planned-TSS estimation. Matching is
    whole-word (so "strides" is not read as "ride"). Defaults to ``"run"`` when
    no cycling/strength/rest signal is present, since running is the more
    conservative (higher-IF) assumption.

    For mixed sessions that name both sports (e.g. "Z2 ride + run off the bike"),
    the cycling label wins — the dominant block in such combos is the ride.

    NOTE: this is a *last-resort* heuristic for free-text planned sessions. When
    a structured sport (deterministic-engine payload) or an authoritative Strava
    ``sport_type`` (a linked completed activity) is available, prefer those via
    :func:`resolve_sport`.
    """
    t = (text or "").lower()
    if not t.strip():
        return "rest"
    has_ride = _has_word(t, _RIDE_KEYWORDS)
    has_run = _has_word(t, _RUN_KEYWORDS)
    if "rest" in t and not has_ride and not has_run:
        return "rest"
    if has_ride:
        return "ride"
    if has_run:
        return "run"
    if _has_word(t, _STRENGTH_KEYWORDS):
        return "strength"
    return "run"


# Strava sport_type → coarse sport label. Authoritative when a completed
# activity is linked to a planned event.
_STRAVA_RIDE = {"ride", "virtualride", "gravelride", "mountainbikeride", "ebikeride", "road bike"}
_STRAVA_RUN = {"run", "running", "trailrun", "virtualrun"}
_STRAVA_STRENGTH = {"weighttraining", "workout", "crossfit"}


def normalize_strava_sport(sport_type: str) -> str | None:
    """Map a Strava ``sport_type`` to ``ride``/``run``/``strength`` (or None).

    Returns ``None`` for sports that don't map to the run/ride IF model (swim,
    ski, hike, etc.), so callers can fall back to other signals.
    """
    key = (sport_type or "").lower().strip()
    if key in _STRAVA_RIDE:
        return "ride"
    if key in _STRAVA_RUN:
        return "run"
    if key in _STRAVA_STRENGTH:
        return "strength"
    return None


def resolve_sport(
    *,
    strava_sport_type: str | None = None,
    structured_sport: str | None = None,
    text: str | None = None,
) -> str:
    """Resolve the best sport label from the available signals, best-first.

    Priority:
      1. ``strava_sport_type`` — authoritative (a linked completed activity).
      2. ``structured_sport`` — deterministic-engine payload ``workout.sport``.
      3. ``text`` — free-text keyword heuristic (``detect_session_sport``).

    Only signals that resolve to a known run/ride/strength label are used;
    otherwise the next signal is tried. Falls back to the text heuristic (which
    itself defaults to ``"run"``).
    """
    if strava_sport_type:
        mapped = normalize_strava_sport(strava_sport_type)
        if mapped is not None:
            return mapped
    if structured_sport:
        s = structured_sport.lower().strip()
        if s in {"ride", "run", "strength"}:
            return s
        # structured sport may be a Strava-style or trail label
        mapped = normalize_strava_sport(s)
        if mapped is not None:
            return mapped
        if s in {"trail_run", "trailrun"}:
            return "run"
    return detect_session_sport(text or "")


def parse_plan_file(path: Path) -> Plan:
    """Parse a plan from a file path."""
    return parse_plan(path.read_text(encoding="utf-8"))


def get_latest_plan_path() -> Path | None:
    """Find the most recently dated plan file in the profile's plans dir.

    Files are expected to be named with a YYYY-MM-DD prefix (e.g. 2026-04-18-plan.md).
    Falls back to mtime if no date prefix is found.
    """
    from .paths import plans_dir

    def _sort_key(p: Path):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", p.name)
        return m.group(1) if m else p.stat().st_mtime

    plans = sorted(plans_dir().glob("*.md"), key=_sort_key, reverse=True)
    return plans[0] if plans else None
