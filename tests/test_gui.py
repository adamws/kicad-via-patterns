import logging
import os
import re
import subprocess

import pytest
import wx

from via_patterns.dialog import FloatValidator, IntValidator

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
class TestValidators:

    VALID_INTS = [
        "0",
        "42",
        "-42",
        "+42",
        "999999",
    ]
    VALID_FLOATS = [
        "0.0",
        "123.456",
        "-1.23",
        "+0.5",
        ".75",
        "-.999",
        "+.001",
        "1e3",  # scientific notation (supported)
        "-2e-2",
    ]
    INVALID_INPUTS = [
        "abc",  # non-numeric
        "12a",  # mixed
        "++1",  # double sign
        "--1",
        "1..2",  # multiple dots
        "1.2.3",
        "0x123",  # hex-like
        "1e3.5",  # malformed sci notation
        "",  # empty string
        " ",  # whitespace
        ".",  # standalone dot
        "-",  # standalone minus
        "+",  # standalone plus
    ]
    VALID_FLOAT_NOT_INT = [
        "1.0",  # technically a float
        "-1.0",
        "+0.0",
        ".5",
        "-.5",
        "+.5",
    ]

    @pytest.fixture
    def int_ctrl(self):
        frame = wx.Frame(None)
        ctrl = wx.TextCtrl(frame, validator=IntValidator(), name="TestInt")
        frame.Show()
        yield ctrl
        frame.Destroy()

    @pytest.fixture
    def float_ctrl(self):
        frame = wx.Frame(None)
        ctrl = wx.TextCtrl(frame, validator=FloatValidator(), name="TestFloat")
        frame.Show()
        yield ctrl
        frame.Destroy()

    def valid_field(self, ctrl, monkeypatch, text):
        call_count = {"count": 0}

        def fake_messagebox(msg, caption, *args, **kwargs):
            call_count["count"] += 1
            return wx.OK

        monkeypatch.setattr(wx, "MessageBox", fake_messagebox)

        ctrl.SetValue(text)
        assert ctrl.GetValidator().Validate(ctrl.GetParent() or ctrl)
        assert call_count["count"] == 0

    def invalid_field(self, ctrl, monkeypatch, text, expected_err):
        captured = {}

        def fake_messagebox(msg, caption, *args, **kwargs):
            captured["msg"] = msg
            captured["caption"] = caption
            return wx.OK

        monkeypatch.setattr(wx, "MessageBox", fake_messagebox)

        ctrl.SetValue(text)
        assert not ctrl.GetValidator().Validate(ctrl.GetParent() or ctrl)
        assert captured["caption"] == "Error"
        assert re.match(expected_err, captured["msg"])

    @pytest.mark.parametrize("text", VALID_INTS)
    def test_valid_int(self, int_ctrl, monkeypatch, text):
        self.valid_field(int_ctrl, monkeypatch, text)

    @pytest.mark.parametrize("text", INVALID_INPUTS + VALID_FLOAT_NOT_INT)
    def test_invalid_int(self, int_ctrl, monkeypatch, text):
        self.invalid_field(
            int_ctrl,
            monkeypatch,
            text,
            r"Invalid 'TestInt' value: '.*' is not a number!",
        )

    @pytest.mark.parametrize("text", VALID_FLOATS + VALID_INTS)
    def test_valid_float(self, float_ctrl, monkeypatch, text):
        self.valid_field(float_ctrl, monkeypatch, text)

    @pytest.mark.parametrize("text", INVALID_INPUTS)
    def test_invalid_float(self, float_ctrl, monkeypatch, text):
        self.invalid_field(
            float_ctrl,
            monkeypatch,
            text,
            r"Invalid 'TestFloat' value: '.*' is not a number!",
        )
