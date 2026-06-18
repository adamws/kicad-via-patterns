import ctypes
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator, Optional, Tuple, Union

import kipy
import kipy.errors
import pytest
from kipy.board import Board
from kipy.project_types import NetClass
from PIL import ImageGrab
from pyvirtualdisplay.smartdisplay import DisplayTimeoutError, SmartDisplay

if sys.platform == "win32":
    from ctypes.wintypes import DWORD, HWND, RECT

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


@pytest.fixture(autouse=True, scope="function")
def prepare_report_dir(tmpdir) -> None:
    os.mkdir(f"{tmpdir}/report")


def kicad_cli() -> str:
    if sys.platform == "darwin":
        return "/opt/homebrew/bin/kicad-cli"
    return "kicad-cli"


RENDER_LAYERS = "F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts,F.Mask,B.Mask"


def generate_render(
    board_path: Union[str, os.PathLike],
    *,
    destination_dir: Union[str, os.PathLike] = "",
) -> None:
    """Render a saved board's copper/silkscreen/mask/edge layers to a single
    SVG (via `kicad-cli`, headless, no live KiCad instance required) so it
    can be attached to the pytest-html report by `pytest_runtest_makereport`.
    """
    board_path = Path(board_path)
    board_name = board_path.stem
    if destination_dir == "":
        destination_dir = board_path.parent
    destination_dir = Path(destination_dir) / "report"
    assert destination_dir.is_dir()

    output_path = destination_dir / f"{board_name}-layers.svg"
    subprocess.run(
        [
            kicad_cli(),
            "pcb",
            "export",
            "svg",
            "--output",
            str(output_path),
            "--layers",
            RENDER_LAYERS,
            "--page-size-mode",
            "2",  # board area only, no page frame/title block
            "--mode-single",
            "--theme",
            "unittest",
            str(board_path),
        ],
        check=True,
    )


@pytest.fixture
def render(board: Board, tmpdir):
    """Save the live board's current state and render it into the per-test
    report directory, so the html report shows what the plugin produced.
    """

    def _render(name: str = "board") -> None:
        board_path = Path(tmpdir) / f"{name}.kicad_pcb"
        board.save_as(str(board_path), overwrite=True, include_project=False)
        generate_render(board_path, destination_dir=tmpdir)

    return _render


@pytest.fixture
def default_netclass(board: Board) -> NetClass:
    """The live board's "Default" netclass (real KiCad values, not a mock)."""
    for nc in board.get_project().get_net_classes():
        if nc.name == "Default":
            return nc
    raise AssertionError("Board has no 'Default' netclass")


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
        if is_xvfb_available():
            return LinuxVirtualScreenManager()
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


# --- Live KiCad IPC API instance -------------------------------------------
#
# The IPC API has no headless mode: the only way to use it is to launch the
# pcbnew GUI (under a virtual display in CI) with the API server enabled and
# connect to it over the IPC socket with kipy. See:
#   https://adamws.github.io/using-the-new-kicad-ipc-api-in-a-ci-environment/


def _kicad_settings_version() -> str:
    """KiCad's settings dir is versioned by major.minor (e.g. "9.0", "10.0").

    Honour an explicit KICAD_VERSION override (e.g. set per CI matrix entry),
    otherwise derive it from `kicad-cli version`.
    """
    if version := os.environ.get("KICAD_VERSION"):
        return version
    try:
        out = subprocess.check_output(["kicad-cli", "version"], text=True).strip()
        major, minor, *_ = out.split(".")
        return f"{major}.{minor}"
    except (OSError, subprocess.SubprocessError, ValueError):
        return "9.0"


def _kicad_config_dir() -> Path:
    if config_home := os.environ.get("KICAD_CONFIG_HOME"):
        base = Path(config_home)
    else:
        base = Path.home() / ".config" / "kicad"
    return base / _kicad_settings_version()


def wait_for_kicad(kicad: kipy.KiCad, timeout: float, interval: float = 1.0) -> None:
    """Poll kicad.ping() until it succeeds."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            kicad.ping()
            return
        except (kipy.errors.ApiError, kipy.errors.ConnectionError):
            pass
        time.sleep(interval)
    raise TimeoutError(f"KiCad did not respond within {timeout} seconds.")


def _setup_kicad_config(config_dir: Path) -> dict:
    """Enable the IPC API server, stub library tables and set the
    do-not-show-again prompts so KiCad's first-run setup wizard never
    triggers (see startwizard.cpp: it only runs if a provider reports it
    needs input). Also installs the "unittest" color theme used for report
    renders, so plots are reproducible regardless of the host's KiCad
    settings. Returns a record of what was changed so it can be reverted."""
    config_dir.mkdir(parents=True, exist_ok=True)

    common_path = config_dir / "kicad_common.json"
    original_common = common_path.read_text() if common_path.is_file() else None

    settings = json.loads(original_common) if original_common else {}
    settings.setdefault("api", {})
    settings["api"]["enable_server"] = True
    settings["api"]["interpreter_path"] = ""
    settings.setdefault("do_not_show_again", {})
    settings["do_not_show_again"]["update_check_prompt"] = True
    settings["do_not_show_again"]["data_collection_prompt"] = True
    common_path.write_text(json.dumps(settings, indent=2))

    created_tables = []
    for table in ("fp-lib-table", "sym-lib-table", "design-block-lib-table"):
        table_path = config_dir / table
        if not table_path.is_file():
            table_path.write_text(f"({table.replace('-', '_')})")
            created_tables.append(table_path)

    theme_path = config_dir / "colors" / "unittest.json"
    created_theme = None
    if not theme_path.is_file():
        theme_path.parent.mkdir(parents=True, exist_ok=True)
        test_dir = Path(__file__).parent
        shutil.copy(test_dir / "colors" / "unittest.json", theme_path)
        created_theme = theme_path

    return {
        "common_path": common_path,
        "original_common": original_common,
        "created_tables": created_tables,
        "created_theme": created_theme,
    }


def _restore_kicad_config(record: dict) -> None:
    common_path: Path = record["common_path"]
    original_common: Optional[str] = record["original_common"]
    if original_common is None:
        common_path.unlink(missing_ok=True)
    else:
        common_path.write_text(original_common)
    for table_path in record["created_tables"]:
        table_path.unlink(missing_ok=True)
    if created_theme := record.get("created_theme"):
        created_theme.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def kicad() -> Iterator[kipy.KiCad]:
    """Launch a real KiCad (pcbnew) instance with the IPC API enabled and
    yield a connected kipy.KiCad client.

    Tests must exercise the plugin against a live board, not a mock.
    """
    if sys.platform != "linux":
        pytest.skip(f"Live KiCad fixture only supported on linux, not {sys.platform}")
    if shutil.which("pcbnew") is None:
        pytest.skip("'pcbnew' executable not found on PATH")
    if not is_xvfb_available():
        pytest.skip("Xvfb is required to launch the pcbnew GUI")

    config_record = _setup_kicad_config(_kicad_config_dir())

    display = SmartDisplay(backend="xvfb", size=(1024, 768))
    display.start()  # sets DISPLAY in os.environ for the child process

    process = subprocess.Popen(["pcbnew"], env=os.environ.copy())
    try:
        kicad = kipy.KiCad()
        wait_for_kicad(kicad, timeout=60, interval=0.5)
        logger.info("Connected to KiCad %s", kicad.get_version())
        yield kicad
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        display.stop()
        _restore_kicad_config(config_record)


@pytest.fixture
def board(kicad: kipy.KiCad) -> Board:
    """The active board of the live KiCad instance, cleared for each test."""
    board = kicad.get_board()
    stale = board.get_vias() + board.get_tracks()
    if stale:
        board.remove_items(stale)
    return board
