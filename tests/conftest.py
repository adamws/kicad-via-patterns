import glob
import logging
import os
import subprocess
import sys
import time
import ctypes
from pathlib import Path
from typing import Tuple, Union
from unittest.mock import MagicMock

import pytest
from kipy.board import Board
from kipy.board_types import Net, Via
from kipy.project_types import NetClass
from kipy.util.units import from_mm

if sys.platform == "win32":
    from ctypes.wintypes import DWORD, HWND, RECT

try:
    from PIL import ImageGrab
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    from pyvirtualdisplay.smartdisplay import DisplayTimeoutError, SmartDisplay
    _XVFB_AVAILABLE = True
except ImportError:
    _XVFB_AVAILABLE = False

Numeric = Union[int, float]
Box = Tuple[Numeric, Numeric, Numeric, Numeric]

logger = logging.getLogger(__name__)


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--test-plugin-installation",
        action="store_true",
        help="Run tests using ~/.local/share/kicad/9.0/3rdparty/plugins instance instead of local one",
        default=False,
    )


@pytest.fixture(scope="session")
def package_path(request):
    if request.config.getoption("--test-plugin-installation"):
        home_directory = Path.home()
        return f"{home_directory}/.local/share/kicad/9.0/3rdparty/plugins"
    return Path(os.path.realpath(__file__)).parents[1]


@pytest.fixture(scope="session")
def package_name(request):
    if request.config.getoption("--test-plugin-installation"):
        return "com_github_adamws_kicad-via-patterns"
    return "via_patterns"


@pytest.fixture(autouse=True, scope="function")
def prepare_report_dir(tmpdir) -> None:
    os.mkdir(f"{tmpdir}/report")


@pytest.fixture
def default_netclass() -> NetClass:
    nc = NetClass()
    nc._proto.name = "Default"
    nc.track_width = from_mm(0.25)
    nc.clearance = from_mm(0.2)
    return nc


@pytest.fixture
def mock_board(default_netclass: NetClass) -> MagicMock:
    board = MagicMock(spec=Board)

    # get_netclass_for_nets: return netclass keyed by net name
    def _get_netclass_for_nets(net):
        if hasattr(net, "name"):
            key = net.name
        else:
            key = str(net)
        return {key: default_netclass}

    board.get_netclass_for_nets.side_effect = _get_netclass_for_nets
    board.get_project.return_value.get_net_classes.return_value = [default_netclass]
    board.get_nets.return_value = []

    # create_items returns the passed items unchanged
    def _create_items(items):
        if isinstance(items, Via):
            return [items]
        return list(items)

    board.create_items.side_effect = _create_items
    board.update_items.side_effect = lambda items: list(items) if hasattr(items, "__iter__") else [items]
    board.add_to_selection.return_value = []
    board.begin_commit.return_value = MagicMock()
    board.push_commit.return_value = None

    return board


def to_base64(path):
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def image_to_base64(path):
    import mimetypes
    b64 = to_base64(path)
    mime = mimetypes.guess_type(path)
    return f"data:{mime[0]};base64,{b64}"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    pytest_html = item.config.pluginmanager.getplugin("html")
    assert pytest_html
    outcome = yield
    report = outcome.get_result()
    extras = getattr(report, "extras", [])

    if report.when == "call" and not report.skipped:
        if tmpdir := item.funcargs.get("tmpdir"):
            images = glob.glob(f"{tmpdir}/report/*png") + glob.glob(
                f"{tmpdir}/report/*svg"
            )
            for f in images:
                render = image_to_base64(f)
                extras.append(pytest_html.extras.image(render))
            urls = glob.glob(f"{tmpdir}/report/*url")
            for url in urls:
                with open(url) as f:
                    extras.append(pytest_html.extras.url(f.read()))
        report.extras = extras


class LinuxVirtualScreenManager:
    def __enter__(self):
        self.display = SmartDisplay(backend="xvfb", size=(960, 640))
        self.display.start()
        return self

    def __exit__(self, *exc):
        self.display.stop()
        return False

    def screenshot(self, window_name, path):
        try:
            img = self.display.waitgrab(timeout=5)
            img.save(path)
            return True
        except DisplayTimeoutError as err:
            logger.error(err)
            return False


def find_window(name):
    if sys.platform != "win32":
        return None
    user32 = ctypes.windll.user32
    return user32.FindWindowW(None, name)


def get_window_position(window_handle) -> Union[None, Tuple[int, int, int, int]]:
    if sys.platform != "win32":
        return None
    dwmapi = ctypes.windll.dwmapi
    rect = RECT()
    DMWA_EXTENDED_FRAME_BOUNDS = 9
    dwmapi.DwmGetWindowAttribute(
        HWND(window_handle),
        DWORD(DMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    return (rect.left, rect.top, rect.right, rect.bottom)


class HostScreenManager:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def screenshot(self, window_name, path):
        try:
            time.sleep(1)
            window_handle = find_window(window_name)
            window_rect = get_window_position(window_handle)
            img = ImageGrab.grab()
            if window_rect:
                img_width, img_height = img.size
                x1, y1, x2, y2 = window_rect

                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img_width, x2), min(img_height, y2)

                if x1 < x2 and y1 < y2:
                    img = img.crop((x1, y1, x2, y2))
                else:
                    logger.warning(
                        f"Can't crop image of size {img_width}x{img_height} "
                        f"to rectangle ({x1},{y1},{x2},{y2})"
                    )
            img.save(path)
            return True
        except Exception as err:
            logger.error(err)
            return False


def is_xvfb_available() -> bool:
    try:
        p = subprocess.Popen(
            ["Xvfb", "-help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        _, _ = p.communicate()
        return p.returncode == 0
    except FileNotFoundError:
        logger.warning("Xvfb was not found")
    return False


def get_screen_manager():
    if sys.platform == "linux":
        if _XVFB_AVAILABLE and is_xvfb_available():
            return LinuxVirtualScreenManager()
        elif _PIL_AVAILABLE:
            return HostScreenManager()
        return None
    elif sys.platform == "win32" and _PIL_AVAILABLE:
        return HostScreenManager()
    return None


@pytest.fixture
def screen_manager():
    mgr = get_screen_manager()
    if not mgr:
        pytest.skip(f"Platform '{sys.platform}' is not supported")
    return mgr
