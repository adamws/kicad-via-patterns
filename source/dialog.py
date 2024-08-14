import os

import pcbnew
import wx

from ._version import __version__


class MainDialog(wx.Dialog):
    def __init__(self: "MainDialog", parent: wx.Frame) -> None:
        super().__init__(parent, -1, "Via Patterns")

        information_section = self.get_information_section()

        buttons = self.CreateButtonSizer(wx.OK)

        header = wx.BoxSizer(wx.HORIZONTAL)
        header.Add(information_section, 3, wx.ALL, 5)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(header, 0, wx.EXPAND | wx.ALL, 5)
        box.Add(buttons, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizerAndFit(box)

    def get_information_section(self) -> wx.BoxSizer:
        source_dir = os.path.dirname(__file__)
        icon_file_name = os.path.join(source_dir, "icon.png")
        icon = wx.Image(icon_file_name, wx.BITMAP_TYPE_ANY)
        icon_bitmap = wx.Bitmap(icon)
        static_icon_bitmap = wx.StaticBitmap(self, wx.ID_ANY, icon_bitmap)

        font = wx.Font(
            12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        name = wx.StaticText(self, -1, "KiCad Plugin Template")
        name.SetFont(font)

        versions = [
            f"pcbnew version: {pcbnew.Version()}",
            f"plugin version: {__version__}",
        ]
        name_box = wx.BoxSizer(wx.HORIZONTAL)
        name_box.Add(static_icon_bitmap, 0, wx.ALL, 5)
        name_box.Add(name, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(name_box, 0, wx.ALL, 5)
        for v in versions:
            text = wx.StaticText(self, -1, v)
            box.Add(text, 0, wx.ALL, 5)

        return box
