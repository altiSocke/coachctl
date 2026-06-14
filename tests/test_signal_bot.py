"""
Tests for src/coachctl/signal_bot.py

Coverage targets:
- get_signal_config: missing vars, all present
- _detect_dominant_sport: run, ride, mixed, empty
- _tsb_label: all bands
- _sport_icon: run, ride, strength, unknown
- _format_training_event: with/without optional fields
- _format_race_event: full race card, minimal payload
- format_daily_plan: training day, rest day, race day, truncation, week number
- send_signal_message: success, HTTP error, network error
- check_connectivity: success, HTTP error, connect error
- last_sent_date / mark_sent: round-trip
- send_tomorrows_plan: happy path, duplicate guard, force flag
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coachctl.events import Event
from coachctl.signal_bot import (
    _detect_dominant_sport,
    _format_race_event,
    _format_training_event,
    _sport_icon,
    _tsb_label,
    check_connectivity,
    format_daily_plan,
    get_signal_config,
    last_sent_date,
    mark_sent,
    send_signal_message,
    send_tomorrows_plan,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _training(
    name: str = "60min easy Z2 run",
    summary: str = "Easy Z2 run, HR <155",
    duration_min: int = 60,
    tss: float = 50.0,
    week_num: int = 9,
    notes: str = "",
    status: str = "planned",
    kind: str = "training",
) -> Event:
    return Event(
        slug=f"test-{name[:10].replace(' ', '-')}",
        kind=kind,
        date="2026-06-15",
        name=name,
        summary=summary,
        duration_min=duration_min,
        estimated_tss=tss,
        status=status,
        notes=notes,
        payload={"week_number": week_num},
    )


def _ride(name: str = "90min Z2 ride") -> Event:
    return Event(
        slug="test-ride",
        kind="training",
        date="2026-06-16",
        name=name,
        summary="Z2 ride 154-210W",
        duration_min=90,
        estimated_tss=65.0,
        status="planned",
        payload={"week_number": 9},
    )


def _race(name: str = "Bernina Ultraks Steinbock") -> Event:
    return Event(
        slug="2026-07-04-steinbock",
        kind="race",
        date="2026-07-04",
        name=name,
        start_time="09:30",
        status="planned",
        payload={
            "priority": "B",
            "course": {"distance_km": 16.3, "elevation_gain_m": 880},
            "goal": {
                "a_goal": "2:05-2:10",
                "b_goal": "2:10-2:25",
                "c_goal": "sub-2:35",
            },
            "pacing": [
                {
                    "km": "0-0.7",
                    "segment": "Opening climb",
                    "target": "RPE 5-6, HR <154",
                    "cue": "Let idiots sprint. First 5 min must feel embarrassingly easy.",
                }
            ],
            "nutrition": {
                "pre_race": [{"time": "T-15", "action": "1 gel + 200ml water"}],
                "during": [{"time_or_km": "km 4.5-5.0", "action": "Take 1 gel (40g)"}],
            },
            "key_principles": [
                "Start boring.",
                "Hike early, hike proudly.",
                "Eat before empty.",
            ],
        },
    )


_FITNESS = {
    "all": {"ctl": 41.8, "atl": 48.7, "tsb": -6.9},
    "run": {"ctl": 22.0, "atl": 25.0, "tsb": -3.0},
    "ride": {"ctl": 20.0, "atl": 24.0, "tsb": -4.0},
}

_PROFILE = {"ftp": 280, "rftp": 270, "threshold_hr": 178}


# ── get_signal_config ─────────────────────────────────────────────────────────


class TestGetSignalConfig:
    def test_all_present(self, monkeypatch):
        monkeypatch.setenv("SIGNAL_API_URL", "http://localhost:9922")
        monkeypatch.setenv("SIGNAL_NUMBER", "+41700000000")
        monkeypatch.setenv("SIGNAL_RECIPIENT", "+41700000001")
        cfg = get_signal_config()
        assert cfg["SIGNAL_API_URL"] == "http://localhost:9922"
        assert cfg["SIGNAL_NUMBER"] == "+41700000000"
        assert cfg["SIGNAL_RECIPIENT"] == "+41700000001"

    def test_missing_all(self, monkeypatch):
        for v in ("SIGNAL_API_URL", "SIGNAL_NUMBER", "SIGNAL_RECIPIENT"):
            monkeypatch.delenv(v, raising=False)
        with pytest.raises(RuntimeError, match="Missing env vars"):
            get_signal_config()

    def test_missing_one(self, monkeypatch):
        monkeypatch.setenv("SIGNAL_API_URL", "http://localhost:9922")
        monkeypatch.setenv("SIGNAL_NUMBER", "+41700000000")
        monkeypatch.delenv("SIGNAL_RECIPIENT", raising=False)
        with pytest.raises(RuntimeError, match="SIGNAL_RECIPIENT"):
            get_signal_config()


# ── _detect_dominant_sport ────────────────────────────────────────────────────


class TestDetectDominantSport:
    def test_run_only(self):
        events = [_training("60min easy Z2 run")]
        assert _detect_dominant_sport(events) == "run"

    def test_ride_only(self):
        events = [_ride()]
        assert _detect_dominant_sport(events) == "ride"

    def test_trail_run(self):
        events = [_training("90min trail run")]
        assert _detect_dominant_sport(events) == "run"

    def test_mixed(self):
        events = [_training("60min run"), _ride()]
        assert _detect_dominant_sport(events) == "all"

    def test_empty(self):
        assert _detect_dominant_sport([]) == "all"

    def test_race_ignored(self):
        # race kind should not contribute to sport detection
        events = [_race()]
        assert _detect_dominant_sport(events) == "all"


# ── _tsb_label ────────────────────────────────────────────────────────────────


class TestTsbLabel:
    @pytest.mark.parametrize(
        "tsb, expected",
        [
            (20.0, "fresh"),
            (15.0, "fresh"),
            (10.0, "recovering"),
            (5.0, "recovering"),
            (0.0, "mid-block fatigue — normal"),
            (-9.9, "mid-block fatigue — normal"),
            (-10.0, "mid-block fatigue — normal"),
            (-11.0, "fatigued — keep intensity controlled"),
            (-20.0, "fatigued — keep intensity controlled"),
            (-21.0, "very fatigued — reduce load"),
        ],
    )
    def test_bands(self, tsb, expected):
        assert _tsb_label(tsb) == expected


# ── _sport_icon ───────────────────────────────────────────────────────────────


class TestSportIcon:
    def test_run(self):
        assert _sport_icon("60min trail run") == "Running"

    def test_ride(self):
        assert _sport_icon("90min Z2 ride") == "Cycling"

    def test_strength(self):
        assert _sport_icon("strength S5 DR prehab") == "Strength"

    def test_unknown(self):
        assert _sport_icon("something else") == "Session"


# ── _format_training_event ────────────────────────────────────────────────────


class TestFormatTrainingEvent:
    def test_basic(self):
        e = _training()
        out = _format_training_event(e)
        assert "60min easy Z2 run" in out
        assert "60 min" in out
        assert "50" in out  # TSS

    def test_no_tss(self):
        e = _training(tss=0.0)
        out = _format_training_event(e)
        assert "TSS" not in out

    def test_with_notes(self):
        e = _training(notes="Stop if hamstring warning.")
        out = _format_training_event(e)
        assert "Stop if hamstring" in out

    def test_ride_icon(self):
        e = _ride()
        out = _format_training_event(e)
        assert "Cycling" in out

    def test_no_summary(self):
        e = Event(
            slug="no-summary",
            kind="training",
            date="2026-06-15",
            name="Easy run",
            summary=None,
            status="planned",
            payload={},
        )
        out = _format_training_event(e)
        assert "Easy run" in out


# ── _format_race_event ────────────────────────────────────────────────────────


class TestFormatRaceEvent:
    def test_full_race_card(self):
        e = _race()
        out = _format_race_event(e)
        assert "Bernina Ultraks Steinbock" in out
        assert "[B]" in out
        assert "2:05-2:10" in out  # A goal
        assert "km 0-0.7" in out  # pacing segment
        assert "NUTRITION" in out
        assert "Start boring" in out  # key principles

    def test_minimal_payload(self):
        e = Event(
            slug="minimal-race",
            kind="race",
            date="2026-07-04",
            name="Test Race",
            status="planned",
            payload={},
        )
        out = _format_race_event(e)
        assert "Test Race" in out

    def test_priority_shown(self):
        e = _race()
        out = _format_race_event(e)
        assert "[B]" in out

    def test_pacing_truncated_to_five(self):
        e = _race()
        e.payload["pacing"] = [
            {"km": str(i), "segment": f"seg{i}", "target": "RPE 6", "cue": "cue"} for i in range(10)
        ]
        out = _format_race_event(e)
        # Only first 5 segments
        assert "seg4" in out
        assert "seg5" not in out


# ── format_daily_plan ─────────────────────────────────────────────────────────


class TestFormatDailyPlan:
    def test_training_day(self):
        events = [_training()]
        msg = format_daily_plan("2026-06-15", events, _PROFILE, _FITNESS)
        assert "Mon 15 Jun" in msg
        assert "CTL 22.0" in msg  # run sport detected, run CTL used
        assert "60min easy Z2 run" in msg
        assert "Week 9" in msg

    def test_rest_day(self):
        msg = format_daily_plan("2026-06-22", [], _PROFILE, _FITNESS)
        assert "Rest day" in msg
        assert "No training scheduled" in msg

    def test_race_day(self):
        events = [_race()]
        msg = format_daily_plan("2026-07-04", events, _PROFILE, _FITNESS)
        assert "RACE DAY" in msg
        assert "Bernina Ultraks Steinbock" in msg

    def test_week_number_in_header(self):
        events = [_training(week_num=11)]
        msg = format_daily_plan("2026-06-29", events, _PROFILE, _FITNESS)
        assert "Week 11" in msg

    def test_no_week_number(self):
        e = Event(
            slug="no-week",
            kind="training",
            date="2026-06-15",
            name="Easy run",
            status="planned",
            payload={},  # no week_number key
        )
        msg = format_daily_plan("2026-06-15", [e], _PROFILE, _FITNESS)
        assert "Week" not in msg

    def test_cancelled_events_not_in_events_list(self):
        # format_daily_plan receives pre-filtered events; cancelled events
        # are excluded by the caller (send_tomorrows_plan).
        # This test verifies the formatter doesn't re-add them.
        events = [_training(status="cancelled")]
        # Cancelled event passed in — formatter renders what it gets
        msg = format_daily_plan("2026-06-15", events, _PROFILE, _FITNESS)
        assert "60min easy Z2 run" in msg  # renderer is stateless

    def test_message_truncated_at_max(self):
        # Build a big summary to trigger truncation
        big = "x" * 200
        events = [_training(summary=big) for _ in range(30)]
        msg = format_daily_plan("2026-06-15", events, _PROFILE, _FITNESS)
        assert len(msg) <= 3_500
        assert "truncated" in msg

    def test_dashboard_url_appended(self):
        msg = format_daily_plan(
            "2026-06-15", [], _PROFILE, _FITNESS, dashboard_url="https://example.com"
        )
        assert "https://example.com" in msg

    def test_total_tss_shown(self):
        events = [_training(tss=60.0), _ride()]
        msg = format_daily_plan("2026-06-15", events, _PROFILE, _FITNESS)
        assert "125" in msg  # 60 + 65

    def test_fitness_fallback_to_all(self):
        # Only 'all' available — should not crash
        fitness = {"all": {"ctl": 40.0, "atl": 44.0, "tsb": -4.0}}
        events = [_training()]
        msg = format_daily_plan("2026-06-15", events, _PROFILE, fitness)
        assert "CTL 40.0" in msg

    def test_empty_fitness(self):
        msg = format_daily_plan("2026-06-15", [], _PROFILE, {})
        assert "CTL 0.0" in msg  # graceful fallback

    def test_ride_uses_ride_fitness(self):
        events = [_ride()]
        msg = format_daily_plan("2026-06-16", events, _PROFILE, _FITNESS)
        assert "CTL 20.0" in msg  # ride CTL


# ── send_signal_message ───────────────────────────────────────────────────────


class TestSendSignalMessage:
    def test_success_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("coachctl.signal_bot.httpx.post", return_value=mock_resp) as mock_post:
            send_signal_message("http://localhost:9922", "+41000000000", "+41000000001", "hello")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["message"] == "hello"
        assert call_kwargs[1]["json"]["number"] == "+41000000000"
        assert call_kwargs[1]["json"]["recipients"] == ["+41000000001"]

    def test_success_201(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        with patch("coachctl.signal_bot.httpx.post", return_value=mock_resp):
            send_signal_message("http://localhost:9922", "+41000000000", "+41000000001", "hi")

    def test_http_error_raises(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"
        with patch("coachctl.signal_bot.httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="HTTP 400"):
                send_signal_message("http://localhost:9922", "+41000000000", "+41000000001", "x")

    def test_network_error_propagates(self):
        import httpx as _httpx

        with patch("coachctl.signal_bot.httpx.post", side_effect=_httpx.ConnectError("refused")):
            with pytest.raises(_httpx.ConnectError):
                send_signal_message("http://localhost:9922", "+41000000000", "+41000000001", "x")

    def test_url_constructed_correctly(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("coachctl.signal_bot.httpx.post", return_value=mock_resp) as mock_post:
            send_signal_message("http://localhost:9922/", "+410", "+411", "m")
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:9922/v2/send"


# ── check_connectivity ────────────────────────────────────────────────────────


class TestCheckConnectivity:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("coachctl.signal_bot.httpx.get", return_value=mock_resp):
            ok, msg = check_connectivity("http://localhost:9922")
        assert ok is True
        assert "running" in msg

    def test_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "service unavailable"
        with patch("coachctl.signal_bot.httpx.get", return_value=mock_resp):
            ok, msg = check_connectivity("http://localhost:9922")
        assert ok is False
        assert "503" in msg

    def test_connect_error(self):
        import httpx as _httpx

        with patch("coachctl.signal_bot.httpx.get", side_effect=_httpx.ConnectError("refused")):
            ok, msg = check_connectivity("http://localhost:9922")
        assert ok is False
        assert "Cannot connect" in msg

    def test_generic_exception(self):
        with patch("coachctl.signal_bot.httpx.get", side_effect=ValueError("boom")):
            ok, msg = check_connectivity("http://localhost:9922")
        assert ok is False
        assert "Error" in msg


# ── last_sent_date / mark_sent ────────────────────────────────────────────────


class TestSentLog:
    def test_no_log_file(self, tmp_path):
        assert last_sent_date(tmp_path) is None

    def test_round_trip(self, tmp_path):
        (tmp_path / "data").mkdir()
        mark_sent(tmp_path, "2026-06-15")
        assert last_sent_date(tmp_path) == "2026-06-15"

    def test_creates_data_dir(self, tmp_path):
        # data/ does not exist yet
        mark_sent(tmp_path, "2026-06-20")
        assert (tmp_path / "data" / "signal_last_sent.txt").exists()

    def test_overwrite(self, tmp_path):
        (tmp_path / "data").mkdir()
        mark_sent(tmp_path, "2026-06-15")
        mark_sent(tmp_path, "2026-06-16")
        assert last_sent_date(tmp_path) == "2026-06-16"

    def test_empty_file_returns_none(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "signal_last_sent.txt").write_text("", encoding="utf-8")
        assert last_sent_date(tmp_path) == None


# ── send_tomorrows_plan (orchestrator) ────────────────────────────────────────


class TestSendTomorrowsPlan:
    """Test the orchestrator with all external calls mocked."""

    def _setup(self, monkeypatch, tmp_path: Path) -> None:
        import coachctl.signal_bot as bot

        monkeypatch.setenv("SIGNAL_API_URL", "http://localhost:9922")
        monkeypatch.setenv("SIGNAL_NUMBER", "+41700000000")
        monkeypatch.setenv("SIGNAL_RECIPIENT", "+41700000001")
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)

        # Patch calendar
        monkeypatch.setattr(
            bot,
            "get_calendar",
            lambda start, end: [_training()],
        )
        # Patch athlete profile
        monkeypatch.setattr(bot, "load_athlete", lambda: _PROFILE)
        # Patch DB fitness query
        monkeypatch.setattr(
            bot,
            "get_conn",
            self._mock_get_conn(),
        )

    @staticmethod
    def _mock_get_conn():
        """Return a context-manager factory that yields a mock conn with fitness rows."""
        from contextlib import contextmanager
        import sqlite3

        @contextmanager
        def _get_conn():
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            conn.execute(
                "CREATE TABLE fitness (date TEXT, sport_category TEXT, ctl REAL, atl REAL, tsb REAL)"
            )
            conn.execute("INSERT INTO fitness VALUES ('2026-06-14', 'all', 41.8, 48.7, -6.9)")
            conn.execute("INSERT INTO fitness VALUES ('2026-06-14', 'run', 22.0, 25.0, -3.0)")
            conn.commit()
            yield conn
            conn.close()

        return _get_conn

    def test_happy_path(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        sent = []
        monkeypatch.setattr(
            "coachctl.signal_bot.send_signal_message",
            lambda api_url, number, recipient, message: sent.append(message),
        )
        result = send_tomorrows_plan(
            data_root=tmp_path,
            target_date="2026-06-15",
            force=True,
        )
        assert "sent" in result.lower()
        assert len(sent) == 1
        assert "60min easy Z2 run" in sent[0]

    def test_duplicate_guard_blocks_resend(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "coachctl.signal_bot.send_signal_message",
            lambda **kw: None,
        )
        mark_sent(tmp_path, "2026-06-15")
        result = send_tomorrows_plan(
            data_root=tmp_path,
            target_date="2026-06-15",
            force=False,
        )
        assert "Already sent" in result

    def test_force_overrides_guard(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        sent = []
        monkeypatch.setattr(
            "coachctl.signal_bot.send_signal_message",
            lambda api_url, number, recipient, message: sent.append(message),
        )
        mark_sent(tmp_path, "2026-06-15")
        result = send_tomorrows_plan(
            data_root=tmp_path,
            target_date="2026-06-15",
            force=True,
        )
        assert "sent" in result.lower()
        assert len(sent) == 1

    def test_mark_sent_written_after_success(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "coachctl.signal_bot.send_signal_message",
            lambda api_url, number, recipient, message: None,
        )
        send_tomorrows_plan(
            data_root=tmp_path,
            target_date="2026-06-20",
            force=True,
        )
        assert last_sent_date(tmp_path) == "2026-06-20"

    def test_cancelled_events_excluded(self, monkeypatch, tmp_path):
        """Cancelled events must not appear in the formatted message."""
        import coachctl.signal_bot as bot

        self._setup(monkeypatch, tmp_path)

        cancelled = Event(
            slug="cancelled-session",
            kind="training",
            date="2026-06-15",
            name="Cancelled hard intervals",
            status="cancelled",
            payload={},
        )
        active = _training(name="Easy Z2 run")
        monkeypatch.setattr(
            bot,
            "get_calendar",
            lambda start, end: [cancelled, active],
        )
        sent = []
        monkeypatch.setattr(
            "coachctl.signal_bot.send_signal_message",
            lambda api_url, number, recipient, message: sent.append(message),
        )
        send_tomorrows_plan(data_root=tmp_path, target_date="2026-06-15", force=True)
        assert "Cancelled hard intervals" not in sent[0]
        assert "Easy Z2 run" in sent[0]

    def test_missing_config_raises(self, monkeypatch, tmp_path):
        for v in ("SIGNAL_API_URL", "SIGNAL_NUMBER", "SIGNAL_RECIPIENT"):
            monkeypatch.delenv(v, raising=False)
        with pytest.raises(RuntimeError, match="Missing env vars"):
            send_tomorrows_plan(data_root=tmp_path, target_date="2026-06-15", force=True)

    def test_dashboard_url_in_message(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        sent = []
        monkeypatch.setattr(
            "coachctl.signal_bot.send_signal_message",
            lambda api_url, number, recipient, message: sent.append(message),
        )
        send_tomorrows_plan(
            data_root=tmp_path,
            target_date="2026-06-15",
            force=True,
            dashboard_url="https://myboard.vercel.app",
        )
        assert "https://myboard.vercel.app" in sent[0]
