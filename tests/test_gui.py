import logging
import os
import re
import subprocess

import pytest
import wx

from via_patterns.dialog import FloatValidator

from .conftest import get_screen_manager

logger = logging.getLogger(__name__)


def run_process(args, package_path):
    env = os.environ.copy()
    return subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        cwd=package_path,
        env=env,
    )


def run_gui_test(tmpdir, screen_manager, window_name, gui_callback) -> None:
    with screen_manager as mgr:
        p = gui_callback()

        is_ok = mgr.screenshot(window_name, f"{tmpdir}/report/screenshot.png")
        try:
            outs, errs = p.communicate("q\n", timeout=1)
        except subprocess.TimeoutExpired:
            logger.error("Process timeout expired")
            p.kill()
            outs, errs = p.communicate()

        logger.info(f"Process stdout: {outs}")
        logger.info(f"Process stderr: {errs}")

        assert outs.endswith("exit ok\n")
        assert errs == ""
        assert is_ok


def test_main_dialog(tmpdir, package_path, package_name, screen_manager) -> None:
    def _callback():
        return run_process(
            ["python3", "-m", f"{package_name}.dialog", "main"],
            package_path,
        )

    run_gui_test(tmpdir, screen_manager, "Via Patterns", _callback)


def test_rotation_dialog(tmpdir, package_path, package_name, screen_manager) -> None:
    def _callback():
        return run_process(
            ["python3", "-m", f"{package_name}.dialog", "rotate"], package_path
        )

    run_gui_test(tmpdir, screen_manager, "Adjust rotation", _callback)


@pytest.fixture(scope="class")
def validator_screen_manager():
    if mgr := get_screen_manager():
        with mgr:
            app = wx.App()
            yield
            app.Destroy()
    else:
        pytest.skip(f"Platform is not supported")


@pytest.mark.usefixtures("validator_screen_manager")
class TestFloatValidator:
    @pytest.fixture
    def text_ctrl(self):
        frame = wx.Frame(None)
        ctrl = wx.TextCtrl(frame, validator=FloatValidator(), name="TestFloat")
        frame.Show()
        yield ctrl
        frame.Destroy()

    @pytest.mark.parametrize(
        "text",
        # fmt: off
        ["123", "1.5", "+1.5", "-1.5", "0.5", ".5", "+.5", "0", "0.0", "+0", " 1.1", "1.1 "]
        # fmt: on
    )
    def test_valid_float(self, text_ctrl, monkeypatch, text):
        call_count = {"count": 0}

        def fake_messagebox(msg, caption, *args, **kwargs):
            call_count["count"] += 1
            return wx.OK

        monkeypatch.setattr(wx, "MessageBox", fake_messagebox)

        text_ctrl.SetValue(text)
        assert text_ctrl.GetValidator().Validate(text_ctrl.GetParent() or text_ctrl)
        assert call_count["count"] == 0

    @pytest.mark.parametrize(
        "text",
        # fmt: off
        ["123a", "a123", "0x123", "123-", ".123-", "", "+", "+-1", "1,1"]
        # fmt: on
    )
    def test_invalid_float(self, text_ctrl, monkeypatch, text):
        captured = {}

        def fake_messagebox(msg, caption, *args, **kwargs):
            captured["msg"] = msg
            captured["caption"] = caption
            return wx.OK

        monkeypatch.setattr(wx, "MessageBox", fake_messagebox)

        text_ctrl.SetValue(text)
        assert not text_ctrl.GetValidator().Validate(text_ctrl.GetParent() or text_ctrl)
        assert captured["caption"] == "Error"
        assert re.match(
            r"Invalid 'TestFloat' value: '.*' is not a number!", captured["msg"]
        )
