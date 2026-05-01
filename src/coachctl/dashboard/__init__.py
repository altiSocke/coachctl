"""
Dashboard FastAPI factory.

Personal repos consume this via a 5-line ``deploy/web.py``::

    from pathlib import Path
    from coachctl.dashboard import create_app
    app = create_app(Path(__file__).parent.parent / "dist" / "data.json")
"""

from .server import create_app

__all__ = ["create_app"]
