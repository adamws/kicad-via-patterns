from __future__ import annotations

import os
import string
from dataclasses import dataclass
from typing import List

import wx
from wx.lib.embeddedimage import PyEmbeddedImage

from .via_patterns import Pattern, RotateDirection

TEXT_CTRL_EXTRA_SPACE = 25


@dataclass
class WindowState:
    track_width: str = ""
    units_label: str = "mm"


class IntValidator(wx.Validator):
    def __init__(self) -> None:
        wx.Validator.__init__(self)
        self.Bind(wx.EVT_CHAR, self.OnChar)

    def Clone(self) -> IntValidator:
        return IntValidator()

    def Validate(self, _) -> bool:
        text_ctrl = self.GetWindow()
        if not text_ctrl.IsEnabled():
            return True

        text = text_ctrl.GetValue()
        try:
            int(text)
            return True
        except ValueError:
            # this can happen when value is empty,
            # other invalid values should not be allowed by 'OnChar' filtering
            name = text_ctrl.GetName()
            wx.MessageBox(f"Invalid '{name}' value: '{text}' is not a number!", "Error")
            text_ctrl.SetFocus()
            return False

    def TransferToWindow(self) -> bool:
        return True

    def TransferFromWindow(self) -> bool:
        return True

    def OnChar(self, event: wx.KeyEvent) -> None:
        keycode = int(event.GetKeyCode())
        if (
            keycode
            in [
                wx.WXK_BACK,
                wx.WXK_DELETE,
                wx.WXK_LEFT,
                wx.WXK_RIGHT,
                wx.WXK_NUMPAD_LEFT,
                wx.WXK_NUMPAD_RIGHT,
                wx.WXK_TAB,
            ]
            or chr(keycode) in string.digits
        ):
            event.Skip()


class FloatValidator(wx.Validator):
    def __init__(self) -> None:
        wx.Validator.__init__(self)
        self.Bind(wx.EVT_CHAR, self.OnChar)

    def Clone(self) -> FloatValidator:
        return FloatValidator()

    def Validate(self, _) -> bool:
        text_ctrl = self.GetWindow()
        if not text_ctrl.IsEnabled():
            return True

        text = text_ctrl.GetValue()
        try:
            float(text)
            return True
        except ValueError:
            # this can happen when value is empty,
            # other invalid values should not be allowed by 'OnChar' filtering
            name = text_ctrl.GetName()
            wx.MessageBox(f"Invalid '{name}' value: '{text}' is not a number!", "Error")
            text_ctrl.SetFocus()
            return False

    def TransferToWindow(self) -> bool:
        return True

    def TransferFromWindow(self) -> bool:
        return True

    def OnChar(self, event: wx.KeyEvent) -> None:
        text_ctrl = self.GetWindow()
        current_position = text_ctrl.GetInsertionPoint()
        keycode = int(event.GetKeyCode())
        if keycode in [
            wx.WXK_BACK,
            wx.WXK_DELETE,
            wx.WXK_LEFT,
            wx.WXK_RIGHT,
            wx.WXK_NUMPAD_LEFT,
            wx.WXK_NUMPAD_RIGHT,
            wx.WXK_TAB,
        ]:
            event.Skip()
        else:
            text_ctrl = self.GetWindow()
            text = text_ctrl.GetValue()
            key = chr(keycode)
            if (
                # allow only digits
                # or single '-' when as first character
                # or single '.'
                key in string.digits
                or (key == "-" and "-" not in text and current_position == 0)
                or (key == "." and "." not in text)
            ):
                event.Skip()


class LabeledTextCtrl(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        label: str,
        value: str,
        width: int = -1,
        validator: wx.Validator = wx.DefaultValidator,
    ) -> None:
        super().__init__(parent)

        expected_char_width = self.GetTextExtent("x").x
        if width != -1:
            annotation_format_size = wx.Size(
                expected_char_width * width + TEXT_CTRL_EXTRA_SPACE, -1
            )
        else:
            annotation_format_size = wx.Size(-1, -1)

        self.label = wx.StaticText(self, -1, label)
        self.text = wx.TextCtrl(
            self,
            value=value,
            size=annotation_format_size,
            validator=validator,
            name=label.strip(":"),
        )

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.text, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        self.SetSizer(sizer)


class LabeledDropdownCtrl(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        label: str,
        choices: List[str] = [],
    ) -> None:
        super().__init__(parent)

        self.label = wx.StaticText(self, -1, label)
        self.dropdown = wx.ComboBox(self, choices=choices, style=wx.CB_DROPDOWN)
        self.dropdown.SetValue(choices[0])

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.dropdown, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        self.SetSizer(sizer)


class MainDialog(wx.Dialog):
    def __init__(
        self: MainDialog, parent: wx.Frame, state: WindowState = WindowState()
    ) -> None:
        super().__init__(parent, -1, "Via Patterns")
        self.initial_track_width = state.track_width
        self.units_label = state.units_label

        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(self.get_main_section(), 0, wx.EXPAND | wx.ALL, 5)
        box.Add(buttons, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizerAndFit(box)

    def get_main_section(self) -> wx.Sizer:
        choices = [
            Pattern.PERPENDICULAR.value,
            Pattern.DIAGONAL.value,
            Pattern.STAGGER.value,
        ]
        pattern_ctrl = LabeledDropdownCtrl(self, "Type:", choices)

        size_ctrl = LabeledTextCtrl(
            self,
            "Size:",
            value=str(5),
            width=5,
            validator=IntValidator(),
        )

        track_width_ctrl = LabeledTextCtrl(
            self,
            "Track width:",
            value=self.initial_track_width,
            validator=FloatValidator(),
        )
        track_width_label = wx.StaticText(self, -1, self.units_label)

        box = wx.StaticBox(self, label="Pattern settings")
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(pattern_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        row1.Add(size_ctrl, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)

        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(track_width_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        row2.Add(track_width_label, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 5)

        sizer.Add(row1, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(row2, 0, wx.EXPAND | wx.ALL, 5)

        self.__number_of_vias = size_ctrl.text
        self.__pattern_type = pattern_ctrl.dropdown
        self.__track_width = track_width_ctrl.text

        return sizer

    def get_number_of_vias(self) -> int:
        return int(self.__number_of_vias.GetValue())

    def get_pattern_type(self) -> Pattern:
        return Pattern(self.__pattern_type.GetValue())

    def get_track_width(self) -> str:
        return self.__track_width.GetValue()


class RotateDialog(wx.Dialog):
    def __init__(self: RotateDialog, parent: wx.Frame, rotate_callback) -> None:
        super().__init__(parent, -1, "Adjust rotation")

        label = wx.StaticText(
            self, -1, "Rotate:"
        )
        # bitmaps obtained with img2py, using KiCad's undo/redo buttons
        rot_left_bitmap = PyEmbeddedImage(
            b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAQAAADZc7J/AAAB8klEQVRIx2NgAIJQiZDbIbdD"
            b"JRjIBSFBIf9D/oeGkG9AKNiAcIRIgECoQahTiH+weZAkAyNJBgTJhDSFnAz5AxKBwtfBc4K9"
            b"GpiIMCBSPGRqyA8krcjwfKgrAQNC6kOegel/ocdD6kM9goyCVUNsQ+JCFoe8gxoy15MdnwEQ"
            b"Z28MMkKX92QPLgx5A5Y9HCiM24D/IV+D43G5MlIkZD9Yzf40VgzJ0BCQVPC/4LOhRaGKuIxI"
            b"Yw1ZDjZiCoZUhCzcl6DAPBtSE6yNzYgEDmD8AMMo2BzTDaLBGSG7Qn4hjAmeg82IUBWwml04"
            b"HBklGBIXuj7kG9iAO9jVBM8Ey2rgSRWx3KEhwROCrLHLBuqDXVhCdrJnYAx5iscTROWczUAD"
            b"blBgQPB8oAHvKHHBXFCSo8SAPUADrpOtvYEp5Dkwse0g335bcDSWkR+Ei8CJWYlM7UGmIX+B"
            b"BuwlU3uAQMhVULkRaoAtm1SH7A81w6c9lDNkL9j/k7AHzieg1I+QRJx+Vw29AM7su7EUKGAF"
            b"MdDidA9mbgeWRm0hn8Haj4fy444gq5AX0NLgakhnSHSIbahlsC+wNNwGyeDATDwtlA1vIIUK"
            b"hXSHfMdRrJ8OcSMuomRCS0OOgiMLBp+FzA72IqJ+QnELT6hWsHuoX6hZqDSJWukOAGS+H1zu"
            b"ajCnAAAAAElFTkSuQmCC"
        ).GetBitmap()
        rot_left_button = wx.BitmapButton(self, bitmap=rot_left_bitmap)
        rot_left_button.Bind(
            wx.EVT_BUTTON,
            lambda event: rotate_callback(event, RotateDirection.COUNTERCLOCKWISE),
        )

        rot_right_bitmap = PyEmbeddedImage(
            b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAQAAADZc7J/AAAB4UlEQVRIx2NgIANEiofcCL4W"
            b"KspALggNCfkPhEGEVTIGSQabh/iHOoUaBAggGRAONiAUj84GplDvkLkhr8EKIfBPyMngxiAZ"
            b"ogwIdg+9gKQVGf4ImRIpjtcAT/aQBVDF74IXhcSF2AarBhmFeoQ0hB4P+QcWfxpah9OAQOGQ"
            b"o2DJ1yEFoWzoskFGIRuh3sFuQBpr6EGw1P5AYZzeiw/5CnUhpgEh08ESy9NYcWmPUAguDDkT"
            b"DPZKaAi6A03BfjwTyok17rVCq0PPIgXnuwhZdPv3gkI5SB6bdmCUIrT+CtkVnBEohu43bbBk"
            b"Pw6f3wfLfgvZEBIXKoRVSUgZSEmwKnYDQmxDJoaGxHLjSXtgD9xiIB+E3AIasIwSAz4APTCB"
            b"EgNAyaOPEgNuAA1YRYkBu4AGXKfEgCpQNIZrkm1AsCo4qVAUCgeABvwMVSG/qDQO+QvMY0cS"
            b"OMj3xjSwN1Y5sOC1yAzo1irsUmzgBP0/5ECQJJ4C5TtQxXsc0gECISfARrwKKcHMOkBP7oQW"
            b"rdE4HejJHjwTmu/fhiwPTQ5xCNUNMg0OCGkOOQ8Vfx5qSSg+PFHKHmT4PbgrSpCY8GQM9Q6e"
            b"E/IcSevfkKOhpZCKhWgArJ+kQ81C/ULcQrXwFiYDCgCpIh3sXAryzgAAAABJRU5ErkJggg=="
        ).GetBitmap()
        rot_right_button = wx.BitmapButton(self, bitmap=rot_right_bitmap)
        rot_right_button.Bind(
            wx.EVT_BUTTON,
            lambda event: rotate_callback(event, RotateDirection.CLOCKWISE),
        )

        buttons = self.CreateButtonSizer(wx.CLOSE)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(label, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        row1.Add(rot_left_button, 0, wx.EXPAND | wx.ALL, 5)
        row1.Add(rot_right_button, 0, wx.EXPAND | wx.ALL, 5)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(row1, 0, wx.EXPAND | wx.ALL, 5)
        box.Add(buttons, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizerAndFit(box)


# used for tests
if __name__ == "__main__":
    import threading

    app = wx.App()
    dlg = MainDialog(None)

    if "PYTEST_CURRENT_TEST" in os.environ:
        print(f"Using {wx.version()}")

        # use stdin for gracefully closing GUI when running
        # from pytest. This is required when measuring
        # coverage and process kill would cause measurement to be lost
        def listen_for_exit() -> None:
            input("Press any key to exit: ")
            dlg.Close()
            wx.Exit()

        input_thread = threading.Thread(target=listen_for_exit)
        input_thread.start()

        dlg.Show()
        app.MainLoop()
    else:
        dlg.ShowModal()
        print(f"number of vias: {dlg.get_number_of_vias()}")
        print(f"pattern: {dlg.get_pattern_type()}")

    print("exit ok")
