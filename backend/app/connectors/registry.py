"""Registers every available connector with `app.connectors.base` (imported by the worker).

S11 adds Canvas here; S14 adds Gradescope.
"""

from app.connectors.base import register_connector
from app.connectors.canvas import CanvasConnector
from app.connectors.gradescope.connector import GradescopeConnector

register_connector(CanvasConnector())  # base URL read from settings at call time
register_connector(GradescopeConnector())
