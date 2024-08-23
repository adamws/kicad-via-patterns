import logging
from contextlib import contextmanager

import pcbnew
import pytest

from via_patterns.via_patterns import Pattern, add_via_pattern

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
def work_board(board_path, tmpdir):
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


def test_via_patterns(board_path, work_board) -> None:
    with work_board() as board:
        vias = add_via_pattern(board, 5, Pattern.PERPENDICULAR, net="Net1")
    board = pcbnew.LoadBoard(board_path)
    assert len(vias) == 5
    assert len(board.AllConnectedItems()) == 5
