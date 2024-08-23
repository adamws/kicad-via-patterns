import logging
import os
import sys
from pathlib import Path

import pcbnew

logger = logging.getLogger(__name__)


def test_if_plugin_loads() -> None:
    version = pcbnew.Version()
    logger.info(f"Plugin executed with KiCad version: {version}")
    logger.info(f"Plugin executed with python version: {sys.version!r}")

    dirname = Path(os.path.realpath(__file__)).parents[1]
    pcbnew.LoadPluginModule(dirname, "via_patterns", "")
    not_loaded = pcbnew.GetUnLoadableWizards()
    assert not_loaded == "", pcbnew.GetWizardsBackTrace()
