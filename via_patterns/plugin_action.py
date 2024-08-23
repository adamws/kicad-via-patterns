from __future__ import annotations

import logging
import os
from typing import Optional

import pcbnew
import wx

from .dialog import MainDialog
from .via_patterns import Pattern, add_via_pattern

logger = logging.getLogger(__name__)


class PluginAction(pcbnew.ActionPlugin):
    def defaults(self) -> None:
        self.name = "Via Patterns"
        self.category = "Modify PCB"
        self.description = "Add vias using various patterns"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")

    def Initialize(self) -> None:
        version = pcbnew.Version()
        if int(version.split(".")[0]) < 8:
            msg = f"KiCad version {version} is not supported"
            raise Exception(msg)

        # Remove all handlers associated with the root logger object.
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        log_file = "via-patterns.log"

        # set up logger
        logging.basicConfig(
            level=logging.DEBUG,
            filename=log_file,
            filemode="w",
            format="[%(filename)s:%(lineno)d]: %(message)s",
        )

    def Run(self) -> None:
        self.Initialize()

        pcb_frame = next(
            x for x in wx.GetTopLevelWindows() if x.GetName() == "PcbFrame"
        )

        board = pcbnew.GetBoard()

        selection: pcbnew.DRAWINGS = pcbnew.GetCurrentSelection()
        selected_via: Optional[pcbnew.PCB_VIA] = None
        if len(selection) == 1:
            selected_via = next(
                f.Cast() for f in selection if isinstance(f.Cast(), pcbnew.PCB_VIA)
            )
        else:
            msg = f"Must select single element, selected {len(selection)}"
            raise Exception(msg)

        if not selected_via:
            msg = "No via selected"
            raise Exception(msg)

        dlg = MainDialog(pcb_frame)
        if dlg.ShowModal() == wx.ID_OK:
            # for now only number of vias to place
            number_of_vias = dlg.get_number_of_vias()
            add_via_pattern(
                board,
                number_of_vias,
                Pattern.PERPENDICULAR,
                select=True,
                via=selected_via,
            )

        dlg.Destroy()
        logging.shutdown()
