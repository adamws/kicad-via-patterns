import os

import pcbnew
import wx

from .dialog import MainDialog


class PluginAction(pcbnew.ActionPlugin):
    def defaults(self) -> None:
        self.name = "Via Patterns"
        self.category = "Modify PCB"
        self.description = "Add vias using various patterns"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")

    def Run(self) -> None:
        pcb_frame = next(
            x for x in wx.GetTopLevelWindows() if x.GetName() == "PcbFrame"
        )

        dlg = MainDialog(pcb_frame)
        if dlg.ShowModal() == wx.ID_OK:
            # this plugin does nothing usefull yet
            pass

        dlg.Destroy()
