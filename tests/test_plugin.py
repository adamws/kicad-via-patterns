import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pcbnew
import pytest

from via_patterns.plugin_action import get_kicad_version, setup_logging

logger = logging.getLogger(__name__)


def test_if_plugin_loads() -> None:
    dirname = Path(os.path.realpath(__file__)).parents[1]
    pcbnew.LoadPluginModule(dirname, "via_patterns", "")
    not_loaded = pcbnew.GetUnLoadableWizards()
    assert not_loaded == "", pcbnew.GetWizardsBackTrace()


def test_setup_logging(tmpdir: Path) -> None:
    setup_logging(str(tmpdir))
    assert Path(f"{tmpdir}/plugin.log").exists()


def test_get_kicad_version() -> None:
    assert get_kicad_version()[0] in ["7", "8"]


@patch("pcbnew.Version")
def test_get_kicad_version_unsupported(mock_pcbnew_version: MagicMock) -> None:
    mock_pcbnew_version.return_value = "6.0.11"
    with pytest.raises(Exception, match="KiCad version 6.0.11 is not supported"):
        get_kicad_version()
