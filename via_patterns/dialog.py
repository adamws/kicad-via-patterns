from __future__ import annotations

import os
import string

import wx

TEXT_CTRL_EXTRA_SPACE = 25


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

    def Enable(self) -> None:
        self.label.Enable()
        self.text.Enable()

    def Disable(self) -> None:
        self.label.Disable()
        self.text.Disable()

    def Hide(self) -> None:
        self.label.Hide()
        self.text.Hide()


class MainDialog(wx.Dialog):
    def __init__(self: MainDialog, parent: wx.Frame) -> None:
        super().__init__(parent, -1, "Via Patterns")

        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(self.get_main_section(), 0, wx.EXPAND | wx.ALL, 5)
        box.Add(buttons, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizerAndFit(box)

    def get_main_section(self) -> wx.Sizer:
        count = LabeledTextCtrl(
            self,
            "Number of vias:",
            value=str(5),
            width=5,
            validator=IntValidator(),
        )

        box = wx.StaticBox(self, label="Settings")
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(count, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(row1, 0, wx.EXPAND | wx.ALL, 5)

        self.__number_of_vias = count.text

        return sizer

    def get_number_of_vias(self) -> int:
        return int(self.__number_of_vias.GetValue())


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

    print("exit ok")