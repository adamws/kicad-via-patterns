import logging
import math
from contextlib import contextmanager

import pcbnew
import pytest

from via_patterns.via_patterns import SQRT2, Pattern, add_via_pattern

from .conftest import generate_render

logger = logging.getLogger(__name__)


def _add_track(board, start: pcbnew.VECTOR2I, end: pcbnew.VECTOR2I, layer):
    track = pcbnew.PCB_TRACK(board)
    track.SetWidth(pcbnew.FromMM(0.25))
    track.SetLayer(layer)
    track.SetStart(start)
    track.SetEnd(end)
    board.Add(track)
    return track


@pytest.fixture()
def board_path(tmpdir) -> str:
    return f"{tmpdir}/test.kicad_pcb"


@pytest.fixture()
def work_board(board_path):
    @contextmanager
    def _isolation():
        board = pcbnew.CreateEmptyBoard()

        default_netclass = board.GetAllNetClasses()["Default"]
        logger.debug(f"Default netclass clearance: {default_netclass.GetClearance()}")

        def _add_net(name: str) -> pcbnew.NETINFO_ITEM:
            net = pcbnew.NETINFO_ITEM(board, name)
            board.Add(net)
            return net

        for i in range(1, 6):
            net = _add_net(f"Net{i}")
            # add dummy tracks to avoid orphaned net removal on board save
            t = _add_track(
                board, pcbnew.VECTOR2I_MM(0, i), pcbnew.VECTOR2I_MM(5, i), pcbnew.F_Cu
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

        # remove temporary tracks
        for t in board.GetTracks():
            if t.Type() != pcbnew.PCB_VIA_T:
                board.RemoveNative(t)

        board.Save(board_path)
        generate_render(board_path)

    yield _isolation


@pytest.mark.parametrize("number_of_vias", [1, 2, 5, 10])
@pytest.mark.parametrize("pattern", [Pattern.PERPENDICULAR, Pattern.DIAGONAL])
@pytest.mark.parametrize("start_position", [(0, 0), (2, 3)])
@pytest.mark.parametrize("net", ["Net1", 2])
@pytest.mark.parametrize("extra_space", [0, pcbnew.FromMM(1)])
def test_via_pattern(
    number_of_vias, pattern, start_position, net, extra_space, board_path, work_board
) -> None:
    start_position = pcbnew.VECTOR2I_MM(*start_position)
    with work_board() as board:
        vias = add_via_pattern(
            board,
            number_of_vias,
            pattern,
            start_position=start_position,
            net=net,
            extra_space=extra_space,
        )
    board = pcbnew.LoadBoard(board_path)
    assert len(vias) == number_of_vias
    items = board.AllConnectedItems()
    items = sorted(items, key=lambda i: [i.GetX(), i.GetY()])
    assert len(items) == number_of_vias

    for i in range(0, number_of_vias):
        # default clearance should be 0.2mm and via radius 0.3mm
        actual = items[i].GetPosition()
        if pattern == Pattern.PERPENDICULAR:
            expected = (
                start_position
                + pcbnew.VECTOR2I(800000 * i, 0)
                + pcbnew.VECTOR2I(extra_space * i, 0)
            )
        else:
            xy = math.ceil((800000 + extra_space) / SQRT2) * i
            expected = start_position + pcbnew.VECTOR2I(xy, xy)
        assert actual == expected
    assert items[0].GetNetname() == net if isinstance(net, str) else f"Net{net}"
    for i in range(1, number_of_vias):
        assert items[i].GetNetCode() == 0


def test_via_pattern_wrong_net_type(work_board) -> None:
    with work_board() as board:
        with pytest.raises(TypeError, match="The `net` argument must be str or int"):
            add_via_pattern(board, 5, Pattern.PERPENDICULAR, net=("Net1",))  # type: ignore


def test_via_pattern_unsupported_pattern_type(work_board) -> None:
    with work_board() as board:
        with pytest.raises(ValueError, match="Unsupported pattern"):
            add_via_pattern(board, 5, "SOME_PATTERN")


def test_via_pattern_negative_extra_space(work_board) -> None:
    with work_board() as board:
        with pytest.raises(
            ValueError, match="The `extra_space` argument must be greater than 0"
        ):
            add_via_pattern(board, 5, Pattern.PERPENDICULAR, extra_space=-10)
