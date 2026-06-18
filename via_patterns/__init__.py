import logging
from logging import NullHandler

try:
    from ._version import __version__
except ImportError:
    __version__ = "not-found"

__license__ = "MIT"
__version__ = __version__

logging.getLogger(__name__).addHandler(NullHandler())
del NullHandler

from .via_patterns import Direction, Pattern, add_via_pattern
