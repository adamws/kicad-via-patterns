from __future__ import annotations

import logging
from enum import Enum
from typing import List, Optional, Union

import pcbnew

logger = logging.getLogger(__name__)
ZERO_POSITION = pcbnew.VECTOR2I(0, 0)


class Pattern(str, Enum):
    PERPENDICULAR = "Perpendicular"

    @classmethod
    def get(cls, name: str) -> Pattern:
        if isinstance(name, str):
            try:
                return Pattern(name.title())
            except ValueError:
                # fallback to error below to use 'name' before converting to titlecase
                pass
        msg = f"'{name}' is not a valid Pattern"
        raise ValueError(msg)


def _default_via(board: pcbnew.BOARD) -> pcbnew.PCB_VIA:
    via = pcbnew.PCB_VIA(board)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(pcbnew.FromMM(0.6))
    via.SetDrill(pcbnew.FromMM(0.3))
    via.SetTopLayer(pcbnew.F_Cu)
    via.SetBottomLayer(pcbnew.B_Cu)
    return via


def add_via_pattern(
    board: pcbnew.BOARD,
    count: int,
    pattern: Pattern,
    *,
    via: Optional[pcbnew.PCB_VIA] = None,
    start_position: pcbnew.VECTOR2I = ZERO_POSITION,
    net: Union[str, int] = 0,
    extra_space: int = 0,
    select: bool = False,
) -> List[pcbnew.PCB_VIA]:
    vias: List[pcbnew.PCB_VIA] = []
    if not via:
        _via = _default_via(board)
        _via.SetStart(start_position)
        if net:
            if isinstance(net, str) and net != "":
                nets = board.GetNetsByName()
                _via.SetNet(nets[net])
            elif isinstance(net, int) and net != 0:
                _via.SetNetCode(net)
            else:
                msg = "The `net` argument must be str or int"
                raise ValueError(msg)
        board.Add(_via)
    else:
        _via = via
        if via.GetParent() != board:
            msg = "The `via` must be element of `board`"
            raise ValueError(msg)

    if pattern != Pattern.PERPENDICULAR:
        msg = "Unsupported pattern"
        raise ValueError(msg)

    vias.append(_via)

    via_width = _via.GetWidth()
    clearance = _via.GetOwnClearance(_via.GetLayer())

    logger.debug(f"via_width: {via_width}, clearance: {clearance}")
    logger.debug(f"extra_space: {extra_space}")
    logger.debug(f"netclass: {_via.GetNetClassName()}")

    move = pcbnew.VECTOR2I(0, 0)
    offset = clearance + via_width + extra_space

    for _ in range(0, count - 1):
        v = _via.Duplicate()
        v.SetNetCode(0)
        move += pcbnew.VECTOR2I(offset, 0)
        v.Move(move)
        if select:
            v.SetSelected()
        board.Add(v)
        vias.append(v)

    return vias
