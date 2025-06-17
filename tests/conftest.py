import base64
import ctypes
import glob
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple, Union

import pcbnew
import pytest
import svgpathtools
from PIL import ImageGrab
from pyvirtualdisplay.smartdisplay import DisplayTimeoutError, SmartDisplay

if sys.platform == "win32":
    from ctypes.wintypes import DWORD, HWND, RECT

Numeric = Union[int, float]
Box = Tuple[Numeric, Numeric, Numeric, Numeric]


version_match = re.search(r"(\d+)\.(\d+)\.(\d+)", pcbnew.Version())
KICAD_VERSION = tuple(map(int, version_match.groups())) if version_match else ()
logger = logging.getLogger(__name__)


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--test-plugin-installation",
        action="store_true",
        help="Run tests using ~/.local/share/kicad/8.0/3rdparty/plugins instance instead of local one",
        default=False,
    )


@pytest.fixture(scope="session")
def package_path(request):
    if request.config.getoption("--test-plugin-installation"):
        home_directory = Path.home()
        return f"{home_directory}/.local/share/kicad/8.0/3rdparty/plugins"
    return Path(os.path.realpath(__file__)).parents[1]


@pytest.fixture(scope="session")
def package_name(request):
    if request.config.getoption("--test-plugin-installation"):
        return "com_github_adamws_kicad-via-patterns"
    return "via_patterns"


@pytest.fixture(autouse=True, scope="session")
def prepare_ci_machine() -> None:
    # when running on CircleCI's Windows machine, there is annoying
    # notification po-up opened which may obstruct tested plugin window
    # when GUI testing. When running on Windows and CI, simulate single
    # 'ESC' press to close notification. Do this once before testing starts.
    if "CIRCLECI" in os.environ and sys.platform == "win32":
        VK_ESCAPE = 0x1B
        KEYEVENTF_EXTENDEDKEY = 0x0001
        KEYEVENTF_KEYUP = 0x0002
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_EXTENDEDKEY, 0)
        time.sleep(0.1)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


def prepare_kicad_config() -> None:
    test_dir = Path(__file__).parent
    config_path = pcbnew.SETTINGS_MANAGER.GetUserSettingsPath()
    logger.debug(config_path)
    colors_path = f"{config_path}/colors"
    os.makedirs(colors_path, exist_ok=True)
    shutil.copy(f"{test_dir}/colors/unittest.json", colors_path)


@pytest.fixture(autouse=True, scope="function")
def prepare_report_dir(tmpdir) -> None:
    os.mkdir(f"{tmpdir}/report")


def kicad_cli() -> str:
    if sys.platform == "darwin":
        return "/opt/homebrew/bin/kicad-cli"
    return "kicad-cli"


def merge_bbox(left: Box, right: Box) -> Box:
    """
    Merge bounding boxes in format (xmin, xmax, ymin, ymax)
    """
    return tuple([f(l, r) for l, r, f in zip(left, right, [min, max, min, max])])


def shrink_svg(svg: ET.ElementTree, margin: int = 0) -> None:
    """
    Shrink the SVG canvas to the size of the drawing.
    """
    root = svg.getroot()
    paths = svgpathtools.document.flattened_paths(root)

    if len(paths) == 0:
        return
    bbox = paths[0].bbox()
    for x in paths:
        bbox = merge_bbox(bbox, x.bbox())
    bbox = list(bbox)
    bbox[0] -= int(margin)
    bbox[1] += int(margin)
    bbox[2] -= int(margin)
    bbox[3] += int(margin)

    root.set(
        "viewBox",
        f"{bbox[0]} {bbox[2]} {bbox[1] - bbox[0]} {bbox[3] - bbox[2]}",
    )

    root.set("width", f"{float(bbox[1] - bbox[0])}cm")
    root.set("height", f"{float(bbox[3] - bbox[2])}cm")


def generate_render(
    pcb_path: Union[str, os.PathLike],
    *,
    destination_dir: Union[str, os.PathLike] = "",
) -> None:
    prepare_kicad_config()
    pcb_path = Path(pcb_path)
    pcb_name = pcb_path.stem
    board = pcbnew.LoadBoard(str(pcb_path))
    if destination_dir == "":
        destination_dir = pcb_path.parent

    destination_dir = Path(destination_dir) / "report"
    assert destination_dir.is_dir()

    plot_layers = [
        pcbnew.B_Cu,
        pcbnew.F_Cu,
        pcbnew.B_SilkS,
        pcbnew.F_SilkS,
        pcbnew.Edge_Cuts,
        pcbnew.B_Mask,
        pcbnew.F_Mask,
    ]
    plot_control = pcbnew.PLOT_CONTROLLER(board)
    plot_options = plot_control.GetPlotOptions()
    plot_options.SetOutputDirectory(destination_dir)
    plot_options.SetColorSettings(
        pcbnew.GetSettingsManager().GetColorSettings("unittest")
    )
    plot_options.SetPlotFrameRef(False)
    plot_options.SetSketchPadLineWidth(pcbnew.FromMM(0.35))
    plot_options.SetScale(1)
    plot_options.SetAutoScale(False)
    plot_options.SetMirror(False)
    plot_options.SetUseGerberAttributes(False)
    plot_options.SetUseAuxOrigin(True)
    plot_options.SetNegative(False)
    plot_options.SetPlotReference(True)
    plot_options.SetPlotValue(True)
    if KICAD_VERSION < (9, 0, 1):
        plot_options.SetPlotInvisibleText(False)
    plot_options.SetDrillMarksType(pcbnew.DRILL_MARKS_NO_DRILL_SHAPE)
    plot_options.SetSvgPrecision(aPrecision=1)

    plot_control.OpenPlotfile("layers", pcbnew.PLOT_FORMAT_SVG)
    for layer_id in plot_layers:
        plot_control.SetLayer(layer_id)
        plot_control.SetColorMode(True)
        plot_control.PlotLayer()
    plot_control.ClosePlot()

    filepath = destination_dir / f"{pcb_name}-layers.svg"
    tree = ET.parse(filepath)
    shrink_svg(tree, margin=1)
    os.remove(filepath)
    tree.write(filepath)


def to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def image_to_base64(path):
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
    # based on https://stackoverflow.com/a/67137723
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

                # Clamp coordinates within image bounds
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


def is_xvfb_avaiable() -> bool:
    try:
        p = subprocess.Popen(
            ["Xvfb", "-help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        _, _ = p.communicate()
        exit_code = p.returncode
        return exit_code == 0
    except FileNotFoundError:
        logger.warning("Xvfb was not found")
    return False


def get_screen_manager():
    if sys.platform == "linux":
        if is_xvfb_avaiable():
            return LinuxVirtualScreenManager()
        else:
            return HostScreenManager()
    elif sys.platform == "win32":
        return HostScreenManager()
    return None


@pytest.fixture
def screen_manager():
    mgr = get_screen_manager()
    if not mgr:
        pytest.skip(f"Platform '{sys.platform}' is not supported")
    return mgr
