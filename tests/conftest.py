import base64
import glob
import logging
import mimetypes
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple, Union

import pcbnew
import pytest
import svgpathtools

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
