from __future__ import annotations

import logging
import os
import sys
from typing import Optional, cast

import pcbnew
import wx

from .dialog import MainDialog, WindowState
from .via_patterns import add_via_pattern

logger = logging.getLogger(__name__)


def setup_logging(destination: str) -> None:
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # set up logger
    logging.basicConfig(
        level=logging.DEBUG,
        filename=f"{destination}/plugin.log",
        filemode="w",
        format="%(asctime)s %(name)s %(lineno)d: %(message)s",
        datefmt="%H:%M:%S",
    )


def get_kicad_version() -> str:
    version = pcbnew.Version()
    if int(version.split(".")[0]) < 7:
        msg = f"KiCad version {version} is not supported"
        raise Exception(msg)
    logger.info(f"Plugin executed with KiCad version: {version}")
    logger.info(f"Plugin executed with python version: {repr(sys.version)}")
    return version


class PluginAction(pcbnew.ActionPlugin):
    def defaults(self) -> None:
        self.name = "Via Patterns"
        self.category = "Modify PCB"
        self.description = "Add vias using various patterns"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")

    def Initialize(self) -> None:
        self.window = wx.GetActiveWindow()
        self.plugin_path = os.path.dirname(__file__)
        setup_logging(self.plugin_path)

        _ = get_kicad_version()

    def Run(self) -> None:
        self.Initialize()

        board = pcbnew.GetBoard()

        selection: pcbnew.DRAWINGS = pcbnew.GetCurrentSelection()
        selected_via: Optional[pcbnew.PCB_VIA] = None
        if len(selection) == 1:
            selected_via = next(
                (f.Cast() for f in selection if isinstance(f.Cast(), pcbnew.PCB_VIA)),
                None,
            )
        else:
            msg = f"Must select single via element, selected {len(selection)} elements"
            raise Exception(msg)

        if not selected_via:
            msg = "No via selected"
            raise Exception(msg)

        iu_scale = pcbnew.EDA_IU_SCALE(pcbnew.PCB_IU_PER_MM)
        user_units = pcbnew.GetUserUnits()
        units_label: str = pcbnew.GetLabel(user_units)

        default_netclass = board.GetAllNetClasses()["Default"]
        track_width = default_netclass.GetTrackWidth()

        state = WindowState(
            track_width=pcbnew.StringFromValue(iu_scale, user_units, track_width),
            units_label=units_label,
        )

        dlg = MainDialog(self.window, state)
        if dlg.ShowModal() == wx.ID_OK:
            add_via_pattern(
                board,
                dlg.get_number_of_vias(),
                dlg.get_pattern_type(),
                select=True,
                via=selected_via,
                track_width=cast(
                    int,
                    pcbnew.ValueFromString(iu_scale, user_units, dlg.get_track_width()),
                ),
            )

        dlg.Destroy()
        logging.shutdown()
