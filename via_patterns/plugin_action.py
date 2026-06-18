from __future__ import annotations

import logging
import os
import sys
from typing import List, Optional, cast

import kipy
import wx
from kipy.board import Board
from kipy.board_types import Via
from kipy.kicad import KiCadVersion
from kipy.util.units import from_mm, to_mm

from .dialog import MainDialog, RotateDialog, SelectViaDialog, WindowState
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


class PluginAction:
    def initialize(self) -> None:
        # Under the IPC API the plugin runs as its own standalone process
        # (launched via entrypoint.py), not inside pcbnew's process, so
        # there is no wx.App yet - wx.GetActiveWindow() requires one to
        # exist, and dialogs need one to run their event loop.
        if wx.GetApp() is None:
            self._app = wx.App()
        self.window = wx.GetActiveWindow()
        self.plugin_path = os.path.dirname(__file__)
        setup_logging(self.plugin_path)

        self.kicad = kipy.KiCad()

    def get_kicad_version(self) -> KiCadVersion:
        version = self.kicad.get_version()
        logger.info(f"Plugin executed with KiCad version: {version}")
        logger.info(f"Plugin executed with python version: {repr(sys.version)}")
        return version

    def get_selected_via(self, board: Board) -> Optional[Via]:
        selected_items = board.get_selection()
        selected_vias = [i for i in selected_items if isinstance(i, Via)]
        if len(selected_vias) == 1:
            return cast(Via, selected_vias[0])
        return None

    def wait_for_via_selection(self, board: Board) -> Optional[Via]:
        """Show a "select a via" prompt and poll the live selection until
        the user picks exactly one, closing the prompt automatically."""
        picked: List[Optional[Via]] = [None]

        def check_selection() -> bool:
            picked[0] = self.get_selected_via(board)
            return picked[0] is not None

        dlg = SelectViaDialog(self.window, check_selection)
        result = dlg.ShowModal()
        dlg.Destroy()

        return picked[0] if result == wx.ID_OK else None

    def run(self) -> None:
        self.initialize()

        _ = self.get_kicad_version()
        board = self.kicad.get_board()

        selected_via = self.get_selected_via(board)
        if selected_via is None:
            selected_via = self.wait_for_via_selection(board)

        if selected_via is None:
            # user cancelled the "select a via" prompt
            logging.shutdown()
            return

        via_netclass = get_netclass(board, selected_via)
        track_width = via_netclass.track_width
        logger.debug(f"via_netclass: '{via_netclass.name}', track_width: {track_width}")

        state = WindowState(
            track_width=f"{to_mm(track_width):.4f}",
            units_label="mm",
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
                track_width=from_mm(float(dlg.get_track_width())),
                inherit_net=dlg.assign_nets(),
                extra_space=from_mm(float(dlg.get_extra_space())),
            )

        dlg.Destroy()

        if added_vias:

            def rotate_callback(_, direction: RotateDirection) -> None:
                rotate_via_pattern(board, added_vias, direction)

            dlg = RotateDialog(self.window, rotate_callback)
            dlg.ShowModal()
            dlg.Destroy()

        logging.shutdown()
