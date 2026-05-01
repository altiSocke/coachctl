"""Module loader for ``uvicorn --reload`` support — exposes a top-level ``app``."""

from .. import paths
from .server import create_app

app = create_app(paths.data_json())
