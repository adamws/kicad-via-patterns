import json
import logging
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from pprint import pformat
from typing import List, Union, cast

import pcbnew
import pytest

from via_patterns import (
    Direction,
    Pattern,
    add_via_pattern,
)

from .conftest import KICAD_VERSION, generate_render

logger = logging.getLogger(__name__)


def _add_track(
    board, start: pcbnew.VECTOR2I, end: pcbnew.VECTOR2I, layer, *, width: int = 250000
):
    track = pcbnew.PCB_TRACK(board)
    track.SetWidth(width)
    track.SetLayer(layer)
    track.SetStart(start)
    track.SetEnd(end)
    board.Add(track)
    return track


def _add_via(
    board: pcbnew.BOARD,
    width: float,
    drill: float,
    netname: str,
    position: pcbnew.VECTOR2I,
) -> pcbnew.PCB_VIA:
    via = pcbnew.PCB_VIA(board)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetStart(position)
    via.SetWidth(pcbnew.FromMM(width))
    via.SetDrill(pcbnew.FromMM(drill))
    via.SetTopLayer(pcbnew.F_Cu)
    via.SetBottomLayer(pcbnew.B_Cu)
    board.Add(via)
    via.SetNet(board.FindNet(netname))
    return via


@pytest.fixture()
def board_path(tmpdir) -> str:
    return f"{tmpdir}/test.kicad_pcb"


@pytest.fixture()
def work_board(board_path):
    @contextmanager
    def _isolation(number_of_nets: int = 0):
        board = pcbnew.CreateEmptyBoard()

        default_netclass = board.GetAllNetClasses()["Default"]
        logger.debug(
            f"Default netclass clearance: {default_netclass.GetClearance()}, "
            f"track width: {default_netclass.GetTrackWidth()}"
        )

        def _add_net(name: str) -> pcbnew.NETINFO_ITEM:
            net = pcbnew.NETINFO_ITEM(board, name)
            board.Add(net)
            return net

        for i in range(1, number_of_nets + 1):
            net = _add_net(f"Net{i}")
            # add dummy tracks to avoid orphaned net removal on board save
            t = _add_track(
                board,
                pcbnew.VECTOR2I_MM(0, i + 10),
                pcbnew.VECTOR2I_MM(5, i + 10),
                pcbnew.F_Cu,
            )
            t.SetNet(net)

        nets = board.GetNetsByNetcode()
        for code, net in nets.items():
            netname = net.GetNetname()
            netclass = net.GetNetClassName()
            logger.debug(f"Net '{netname}' code: '{code}' class: '{netclass}'")

        # must save and reload, otherwise netclass clearance settings would not
        # propagate (desing rules are handled in kicad proj file)
        board.Save(board_path)
        board = pcbnew.LoadBoard(board_path)

        yield board

        board.Save(board_path)

    yield _isolation


def assert_via_nets(
    items: List[pcbnew.PCB_VIA],
    net: Union[str, int],
) -> None:
    assert items[0].GetNetname() == net if isinstance(net, str) else f"Net{net}"
    for i in range(1, len(items)):
        assert items[i].GetNetCode() == 0


def assert_drc(tmpdir, board_path: Union[str, os.PathLike], log: bool = True) -> None:
    board_path = Path(board_path)
    board_name = board_path.stem

    drc_path = tmpdir / f"report/{board_name}-drc.json"
    subprocess.run(
        f"kicad-cli pcb drc --output {drc_path} --format json {board_path}",
        shell=True,
        check=False,
    )

    drc = json.load(drc_path)
    if log:
        logger.debug(f"All DRC: {pformat(drc)}")
    filtered_drc = [
        v
        for v in drc["violations"]
        if v["type"] not in ["track_dangling", "invalid_outline"]
    ]
    if log:
        logger.debug(f"Filtered DRC {pformat(filtered_drc)}")
    assert len(filtered_drc) == 0


@pytest.mark.parametrize("number_of_vias", [3, 6])
@pytest.mark.parametrize(
    "pattern", [Pattern.PERPENDICULAR, Pattern.DIAGONAL, Pattern.STAGGER]
)
@pytest.mark.parametrize("via", [None, (0.8, 0.4)])
@pytest.mark.parametrize("track_width", [0, 0.65])  # 0 means deafult (0.2)
@pytest.mark.parametrize("direction", [Direction.HORIZONTAL, Direction.VERTICAL])
def test_via_pattern(
    number_of_vias, pattern, via, track_width, direction, board_path, work_board, tmpdir
) -> None:
    net = "Net1"
    track_width = cast(int, pcbnew.FromMM(track_width))
    with work_board(number_of_vias) as board:
        if via:
            via = _add_via(board, via[0], via[1], net, pcbnew.VECTOR2I(0, 0))
        vias = add_via_pattern(
            board,
            number_of_vias,
            pattern,
            via=via,
            net=net,
            track_width=track_width,
            direction=direction,
        )
        assert len(vias) == number_of_vias
        assert_via_nets(vias, net)

    # add tracks to created vias in separate board which will be used
    # for DRC checks and extra render for html report
    vias = []
    board_with_tracks = pcbnew.LoadBoard(board_path)

    items = board_with_tracks.AllConnectedItems()
    if direction == Direction.HORIZONTAL:
        items = sorted(items, key=lambda i: [i.GetX(), i.GetY()])
    else:
        items = sorted(items, key=lambda i: [i.GetY(), i.GetX()])
    for item in items:
        if item.Type() != pcbnew.PCB_VIA_T:
            # remove temporary tracks
            board_with_tracks.RemoveNative(item)
        else:
            vias.append(item)

    assert len(vias) == number_of_vias
    track_directions = {
        Direction.HORIZONTAL: [(0, 1), (0, -1)],
        Direction.VERTICAL: [(1, 0), (-1, 0)],
    }
    for i, v in enumerate(vias):
        start = v.GetPosition()
        netname = f"Net{i+1}"
        logger.debug(f"Setting net: {netname}")
        v.SetNet(board.FindNet(netname))
        for layer, directions in [
            (pcbnew.F_Cu, track_directions[direction][0]),
            (pcbnew.B_Cu, track_directions[direction][1]),
        ]:
            _add_track(
                board_with_tracks,
                start,
                start + pcbnew.VECTOR2I_MM(*directions),
                layer,
                width=track_width if track_width else 200000,
            )

    board_with_tracks_path = Path(board_path).with_name("test1.kicad_pcb")
    board_with_tracks.Save(board_with_tracks_path)
    generate_render(board_with_tracks_path)
    if KICAD_VERSION >= (8, 0, 0):
        # `kicad-cli pcb drc` not available in kicad 7 - using python API for this sometimes crashes,
        # see https://gitlab.com/kicad/code/kicad/-/issues/17504
        assert_drc(tmpdir, board_with_tracks_path)

        # to check if pattern is efficient, move second via (with tracks) towards
        # first one by some predefined step to see if DRC clearance violation starts to be detected
        board_with_vias_moved = pcbnew.LoadBoard(board_with_tracks_path)
        for t in board_with_vias_moved.TracksInNet(2):
            if direction == Direction.HORIZONTAL:
                t.Move(pcbnew.VECTOR2I_MM(-0.001, 0))
            else:
                t.Move(pcbnew.VECTOR2I_MM(0, -0.001))
        board_with_vias_moved_path = Path(board_path).with_name("test2.kicad_pcb")
        board_with_vias_moved.Save(board_with_vias_moved_path)
        with pytest.raises(AssertionError):
            assert_drc(tmpdir, board_with_vias_moved_path, log=False)


def test_via_pattern_wrong_net_type(work_board) -> None:
    with work_board() as board:
        with pytest.raises(TypeError, match="The `net` argument must be str or int"):
            add_via_pattern(board, 5, Pattern.PERPENDICULAR, net=("Net1",))  # type: ignore


def test_via_pattern_unsupported_pattern_type(work_board) -> None:
    with work_board() as board:
        with pytest.raises(ValueError, match="Unsupported pattern"):
            add_via_pattern(board, 5, "SOME_PATTERN")


def test_via_pattern_unsupported_direction(work_board) -> None:
    with work_board() as board:
        with pytest.raises(ValueError, match="Unsupported direction"):
            add_via_pattern(board, 5, Pattern.DIAGONAL, direction="NO_SUCH_DIRECTION")  # type: ignore


def test_via_pattern_negative_extra_space(work_board) -> None:
    with work_board() as board:
        with pytest.raises(
            ValueError, match="The `extra_space` argument must be greater or equal 0"
        ):
            add_via_pattern(board, 5, Pattern.PERPENDICULAR, extra_space=-10)


def test_via_pattern_negative_track_width(work_board) -> None:
    with work_board() as board:
        with pytest.raises(
            ValueError, match="The `track_width` argument must be greater or equal 0"
        ):
            add_via_pattern(board, 5, Pattern.PERPENDICULAR, track_width=-10)


@pytest.mark.parametrize(
    "params", [("diagonal", Pattern.DIAGONAL), ("StaGGEr", Pattern.STAGGER)]
)
def test_pattern_enum_from_string(params) -> None:
    string, expected = params
    assert Pattern.get(string) == expected


def test_pattern_enum_from_illegal_string() -> None:
    with pytest.raises(ValueError, match=r"'.*' is not a valid Pattern"):
        _ = Pattern.get("NO_SUCH_PATTERN")
