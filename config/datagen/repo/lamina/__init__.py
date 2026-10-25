"""lamina: layered configuration files with includes and environment interpolation.

No runtime dependencies. Round-trip safe: ``dumps(loads(text)) == text``.
"""

from lamina.dump import dump, dumps
from lamina.errors import IncludeError, InterpolationError, LaminaError, ParseError
from lamina.loader import load, loads
from lamina.model import Blank, Comment, Document, Entry, Section

__all__ = [
    "Blank",
    "Comment",
    "Document",
    "Entry",
    "IncludeError",
    "InterpolationError",
    "LaminaError",
    "ParseError",
    "Section",
    "dump",
    "dumps",
    "load",
    "loads",
]

__version__ = "0.1.0"
