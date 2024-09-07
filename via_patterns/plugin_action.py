from __future__ import annotations

import logging
import os
import sys
from typing import List, cast

import pcbnew
import wx

from .dialog import MainDialog, RotateDialog, WindowState
from .via_patterns import (
    RotateDirection,
    add_via_pattern,
    get_netclass,
    rotate_via_pattern,
)

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


def get_selected_board_items() -> List[pcbnew.BOARD_ITEM]:
    selection: pcbnew.DRAWINGS = pcbnew.GetCurrentSelection()
    return [item.Cast() for item in selection]


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

        selected_items = get_selected_board_items()
        selected_vias = list(
            filter(lambda i: isinstance(i, pcbnew.PCB_VIA), selected_items)
        )

        if len(selected_vias) != 1:
            msg = (
                "Plugin must be run with selection containing exectly one via. "
                f"Current selection contains {len(selected_items)} items "
                f"and {len(selected_vias)} vias. "
                "Please re-run plugin with proper selection."
            )
            raise Exception(msg)

        selected_via = pcbnew.Cast_to_PCB_VIA(selected_vias[0])

        iu_scale = pcbnew.EDA_IU_SCALE(pcbnew.PCB_IU_PER_MM)
        user_units = pcbnew.GetUserUnits()
        units_label: str = pcbnew.GetLabel(user_units)

        via_netclass = get_netclass(board, selected_via)
        track_width = via_netclass.GetTrackWidth()
        logger.debug(
            f"via_netclass: {via_netclass.GetName()} track_width: {track_width}"
        )

        state = WindowState(
            track_width=pcbnew.StringFromValue(iu_scale, user_units, track_width),
            units_label=units_label,
        )

        added_vias = None
        dlg = MainDialog(self.window, state)
        if dlg.ShowModal() == wx.ID_OK:
            added_vias = add_via_pattern(
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

        if added_vias:
            pcbnew.Refresh()

            def rotate_callback(_, direction: RotateDirection) -> None:
                rotate_via_pattern(added_vias, direction)
                pcbnew.Refresh()

            dlg = RotateDialog(self.window, rotate_callback)
            dlg.ShowModal()
            dlg.Destroy()

        logging.shutdown()
