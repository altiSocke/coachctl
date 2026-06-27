"""Deterministic plan engine tools — preview and apply structured plan templates.

These expose the reconcile-based workout engine to the coach agent:

* ``preview_plan`` — expand a named plan template over N weeks and show what would
  change against the real calendar (create / update / match / skip), WITHOUT
  writing. Reconcile rules: existing names are preserved on update, strength is
  never touched, races block their day, ambiguous same-day endurance is skipped,
  rest-day creates are suppressed unless requested.
* ``apply_plan`` — apply the previewed plan, sandbox-validated first (apply +
  re-preview + bake in a throwaway DB copy must converge) before any write to the
  live database.

``seed`` convention: ``-1`` (default) means fully deterministic — base variant,
no duration jitter, no PRNG. Any value ``>= 0`` selects a reproducible seeded
variation (quality-session rotation + ±5min jitter on easy/long runs).
"""

from __future__ import annotations


def _seed_arg(seed: int) -> int | None:
    """Map the MCP-friendly ``seed`` sentinel (-1) to ``None`` (deterministic)."""
    return None if seed is None or seed < 0 else seed


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def list_plan_templates() -> str:
        """
        List the available deterministic plan templates and their shape.

        Returns each template's name, number of weeks, and per-week TSS targets.
        Use this before ``preview_plan`` to pick a template name.
        """
        import json

        from ..plan_templates import TEMPLATES

        out = []
        for name, template in sorted(TEMPLATES.items()):
            out.append(
                {
                    "name": name,
                    "weeks": len(template.weeks),
                    "week_target_tss": [w.target_tss for w in template.weeks],
                }
            )
        return json.dumps(out, indent=2)

    @mcp.tool()
    def preview_plan(
        template: str,
        start: str,
        weeks: int,
        seed: int = -1,
        slug_prefix: str = "",
        create_rest_days: bool = False,
    ) -> str:
        """
        Preview an expanded multi-week plan template against the real calendar.

        Reconcile-only (never overwrites non-endurance): existing endurance
        sessions are updated with their NAME PRESERVED (or matched); strength is
        left untouched; races block their date; two endurance sessions on one day
        are skipped as ambiguous; rest-day creates are suppressed unless
        ``create_rest_days`` is true. Writes nothing — review the actions, then
        call ``apply_plan`` with the same arguments to commit.

        Parameters
        ----------
        template : plan template name (see ``list_plan_templates``).
        start : plan start date YYYY-MM-DD (use a Monday).
        weeks : number of weeks to expand (1..template length).
        seed : -1 = deterministic (default); >= 0 = reproducible variation.
        slug_prefix : optional generated-event slug prefix (default 'plan').
        create_rest_days : create explicit rest-day rows instead of suppressing.
        """
        from ..db import init_db
        from ..workout_preview import format_preview_text, preview_plan_from_db

        init_db()
        result = preview_plan_from_db(
            template_name=template,
            start_date=start,
            weeks=weeks,
            seed=_seed_arg(seed),
            slug_prefix=slug_prefix or None,
            create_rest_days=create_rest_days,
        )
        if result.error:
            return f"Error: {result.error}"
        return format_preview_text(
            race_name=result.race_name,
            window_start=result.window_start,
            window_end=result.window_end,
            previews=result.previews,
            summary=result.summary,
        )

    @mcp.tool()
    def apply_plan(
        template: str,
        start: str,
        weeks: int,
        seed: int = -1,
        slug_prefix: str = "",
        create_rest_days: bool = False,
        allow_skips: bool = False,
    ) -> str:
        """
        Apply an expanded plan template to the calendar, sandbox-validated.

        SAFETY: the plan is first applied in a throwaway copy of the database;
        the copy is re-previewed (must converge to no further create/update) and
        baked, and only then are the same changes written to the live database.
        Reconcile rules match ``preview_plan`` (names/strength preserved, races
        blocked, rests suppressed). Skips are rejected unless ``allow_skips`` is
        true. ALWAYS run ``preview_plan`` with the same arguments first and have
        the athlete confirm before applying.

        Parameters mirror ``preview_plan`` plus ``allow_skips`` (apply the
        non-skipped rows when some days are ambiguous/locked/completed).

        After applying, call ``bake`` to refresh the dashboard.
        """
        from ..db import init_db
        from ..workout_apply import apply_plan_from_db, format_apply_text

        init_db()
        try:
            result = apply_plan_from_db(
                template_name=template,
                start_date=start,
                weeks=weeks,
                seed=_seed_arg(seed),
                slug_prefix=slug_prefix or None,
                allow_skips=allow_skips,
                create_rest_days=create_rest_days,
            )
        except RuntimeError as exc:
            return f"Error: {exc}"
        return format_apply_text(result)
