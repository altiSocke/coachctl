"""Sync tools: pull activities from Strava, list/inspect routes."""

from __future__ import annotations

import json
import logging

from ..db import get_conn
from ..sync import fetch_athlete_routes, fetch_route, fetch_route_streams, get_strava_access_token
from ..metrics import format_pace

logger = logging.getLogger(__name__)


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def sync_activities(full: bool = False) -> str:
        """
        Pull latest activities from Strava into the local database.
        Set full=True to re-sync all history instead of incremental.
        """
        from ..sync import sync

        try:
            sync(full=full)
            with get_conn() as conn:
                count = conn.execute("SELECT COUNT(*) as c FROM activities").fetchone()["c"]
            return f"Sync complete. Total activities in database: {count}"
        except Exception as e:
            logger.exception("sync_activities failed")
            return "Sync failed — check server logs for details."

    @mcp.tool()
    def list_routes() -> str:
        """
        List all saved routes for the authenticated athlete.
        Returns route ID, name, distance, elevation gain, and type.
        Use the route ID with get_route_detail to get full elevation profile.
        """
        try:
            access_token = get_strava_access_token()
            routes = fetch_athlete_routes(access_token)
            if not routes:
                return "No saved routes found."

            results = []
            for r in routes:
                results.append(
                    {
                        "id": r["id"],
                        "name": r.get("name", "Unnamed"),
                        "distance_km": round(r.get("distance", 0) / 1000, 1),
                        "elevation_gain_m": round(r.get("elevation_gain", 0), 0),
                        "type": r.get("type"),  # 1=ride, 2=run
                        "sub_type": r.get("sub_type"),  # 1=road, 2=mtb, 3=cx, 4=trail, 5=mixed
                        "starred": r.get("starred", False),
                        "estimated_moving_time_min": round(
                            r.get("estimated_moving_time", 0) / 60, 0
                        ),
                    }
                )
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.exception("list_routes failed")
            return "Failed to fetch routes — check server logs for details."

    @mcp.tool()
    def get_route_detail(route_id: int) -> str:
        """
        Get detailed route info and elevation/distance streams for race preparation.
        Returns: route metadata, elevation profile with gradient analysis,
        km-by-km breakdown, and key climbing segments.
        """
        import bisect

        try:
            access_token = get_strava_access_token()
            route = fetch_route(access_token, route_id)
            streams = fetch_route_streams(access_token, route_id)

            result: dict = {
                "name": route.get("name", "Unnamed"),
                "distance_km": round(route.get("distance", 0) / 1000, 2),
                "elevation_gain_m": round(route.get("elevation_gain", 0), 0),
                "type": {1: "ride", 2: "run", 3: "run", 5: "run"}.get(route.get("type"), "unknown"),
                "sub_type": {1: "road", 2: "mtb", 3: "cx", 4: "trail", 5: "mixed"}.get(
                    route.get("sub_type"), "unknown"
                ),
                "estimated_moving_time_min": round(route.get("estimated_moving_time", 0) / 60, 0),
            }

            if not streams:
                result["note"] = "No stream data available for this route."
                return json.dumps(result, indent=2)

            alt_data = streams.get("altitude", {}).get("data", [])
            dist_data = streams.get("distance", {}).get("data", [])

            if not alt_data or not dist_data:
                result["note"] = "Streams available but no altitude/distance data."
                return json.dumps(result, indent=2)

            alt = alt_data
            dist = dist_data

            result["elevation_profile"] = {
                "start_m": round(alt[0], 0),
                "max_m": round(max(alt), 0),
                "min_m": round(min(alt), 0),
                "end_m": round(alt[-1], 0),
                "total_ascent_m": round(
                    sum(max(0, alt[i + 1] - alt[i]) for i in range(len(alt) - 1)), 0
                ),
                "total_descent_m": round(
                    sum(max(0, alt[i] - alt[i + 1]) for i in range(len(alt) - 1)), 0
                ),
            }

            km_splits = []
            for km in range(int(dist[-1] // 1000)):
                start_m = km * 1000
                end_m = (km + 1) * 1000
                si = bisect.bisect_left(dist, start_m)
                ei = bisect.bisect_left(dist, end_m)
                if ei <= si or ei >= len(alt):
                    continue
                seg_alt = alt[si:ei]
                elev_change = seg_alt[-1] - seg_alt[0]
                ascent = sum(max(0, seg_alt[j + 1] - seg_alt[j]) for j in range(len(seg_alt) - 1))
                descent = sum(max(0, seg_alt[j] - seg_alt[j + 1]) for j in range(len(seg_alt) - 1))
                km_splits.append(
                    {
                        "km": km + 1,
                        "elevation_change_m": round(elev_change, 0),
                        "ascent_m": round(ascent, 0),
                        "descent_m": round(descent, 0),
                        "avg_gradient_pct": round(elev_change / 1000 * 100, 1),
                        "altitude_at_end_m": round(alt[ei], 0),
                    }
                )
            result["km_splits"] = km_splits

            climbs = []
            i = 0
            while i < len(alt) - 1:
                if alt[i + 1] > alt[i]:
                    climb_start = i
                    while i < len(alt) - 1 and alt[i + 1] >= alt[i] - 2:
                        i += 1
                    gain = alt[i] - alt[climb_start]
                    if gain > 50:
                        climb_dist = dist[i] - dist[climb_start]
                        avg_grad = gain / climb_dist * 100 if climb_dist > 0 else 0
                        climbs.append(
                            {
                                "start_km": round(dist[climb_start] / 1000, 2),
                                "end_km": round(dist[i] / 1000, 2),
                                "gain_m": round(gain, 0),
                                "distance_m": round(climb_dist, 0),
                                "avg_gradient_pct": round(avg_grad, 1),
                                "max_altitude_m": round(alt[i], 0),
                            }
                        )
                i += 1
            result["major_climbs"] = climbs

            return json.dumps(result, indent=2)
        except Exception as e:
            logger.exception("get_route_detail failed for route_id=%s", route_id)
            return "Failed to fetch route detail — check server logs for details."
