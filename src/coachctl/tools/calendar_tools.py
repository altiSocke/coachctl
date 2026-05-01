"""Google Calendar integration tools."""

from __future__ import annotations


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def calendar_auth() -> str:
        """
        Trigger Google OAuth2 consent flow for Calendar access.
        Opens browser for authorization. Stores refresh token in .env.
        Requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.
        """
        from ..calendar import do_google_auth

        token = do_google_auth()
        if token:
            return "Google Calendar authorized successfully. Refresh token saved to .env."
        return "Authorization failed — no refresh token received."

    @mcp.tool()
    def calendar_sync(horizon_days: int = 7) -> str:
        """
        Push training sessions to Google Calendar.
        - Races/events from athlete.yaml are ALWAYS pushed regardless of horizon.
        - Training sessions are pushed for the next N days.
        - Use horizon_days=0 for races only, or 999 for full plan.
        """
        from ..calendar import sync_calendar

        result = sync_calendar(horizon_days)
        if "error" in result:
            return result["error"]
        return (
            f"Calendar sync complete: "
            f"{result['created']} created, {result['updated']} updated, "
            f"{result['skipped']} unchanged. "
            f"Total events considered: {result['total_pushed']}."
        )

    @mcp.tool()
    def calendar_clear() -> str:
        """
        Remove all agent-created events from Google Calendar.
        Deletes events tracked in the calendar_events DB table.
        """
        from ..calendar import clear_calendar

        result = clear_calendar()
        return f"Cleared {result['deleted']} events from Google Calendar."
