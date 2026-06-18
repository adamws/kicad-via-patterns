import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from via_patterns.plugin_action import setup_logging

logger = logging.getLogger(__name__)


def test_setup_logging(tmpdir: Path) -> None:
    setup_logging(str(tmpdir))
    assert Path(f"{tmpdir}/plugin.log").exists()
