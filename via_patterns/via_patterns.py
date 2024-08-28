from __future__ import annotations

import logging
import math
from enum import Enum
from typing import List, Optional, Union

import pcbnew

logger = logging.getLogger(__name__)
ZERO_POSITION = pcbnew.VECTOR2I(0, 0)
SQRT2 = math.sqrt(2)
SQRT3 = math.sqrt(3)


class Pattern(str, Enum):
    PERPENDICULAR = "Perpendicular"
    DIAGONAL = "Diagonal"
    STAGGER = "Stagger"

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
    via.SetNetCode(0)
    return via


def get_netclass(
    board: pcbnew.BOARD, item: pcbnew.BOARD_CONNECTED_ITEM
) -> pcbnew.NETCLASS:
    # workaround, see https://gitlab.com/kicad/code/kicad/-/issues/18609
    netclass_name = item.GetNetClassName()
    if netclass_name == "Default":
        return board.GetAllNetClasses()[netclass_name]
    return board.GetNetClasses()[netclass_name]


def add_via_pattern(
    board: pcbnew.BOARD,
    count: int,
    pattern: Union[Pattern, str],
    *,
    via: Optional[pcbnew.PCB_VIA] = None,
    start_position: pcbnew.VECTOR2I = ZERO_POSITION,
    net: Union[str, int] = 0,
    track_width: int = 0,
    extra_space: int = 0,
    select: bool = False,
) -> List[pcbnew.PCB_VIA]:
    vias: List[pcbnew.PCB_VIA] = []

    if pattern not in [Pattern.DIAGONAL, Pattern.PERPENDICULAR, Pattern.STAGGER]:
        msg = "Unsupported pattern"
        raise ValueError(msg)

    if track_width < 0:
        msg = "The `track_width` argument must be greater or equal 0"
        raise ValueError(msg)

    if extra_space < 0:
        msg = "The `extra_space` argument must be greater or equal 0"
        raise ValueError(msg)

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
                raise TypeError(msg)
        board.Add(_via)
    else:
        _via = via
        if via.GetParent().m_Uuid != board.m_Uuid:
            msg = "The `via` must be element of `board`"
            raise ValueError(msg)

    vias.append(_via)

    via_width = _via.GetWidth()
    via_clearance = _via.GetOwnClearance(_via.GetLayer())

    logger.debug(f"via_width: {via_width}, via_clearance: {via_clearance}")
    if track_width == 0:
        via_netclass = get_netclass(board, _via)
        track_width = via_netclass.GetTrackWidth()
        logger.debug(
            "The `track_width` argument not specified, using via's "
            f"netclass ({via_netclass.GetName()}) value: {track_width}"
        )
    logger.debug(f"track_width: {track_width}")
    logger.debug(f"extra_space: {extra_space}")
    logger.debug(f"netclass: {_via.GetNetClassName()}")

    if pattern in [Pattern.STAGGER, Pattern.DIAGONAL] and track_width > via_width:
        logger.debug(
            f"The '{pattern}' pattern when `track_width` > `via_width` makes no sense, "
            f"replacing with '{Pattern.PERPENDICULAR}' pattern"
        )
        pattern = Pattern.PERPENDICULAR

    move = pcbnew.VECTOR2I(0, 0)
    offset_x = 0
    offset_y = 0

    if pattern == Pattern.PERPENDICULAR:
        offset_x = via_clearance + max(via_width, track_width) + extra_space
    elif pattern == Pattern.DIAGONAL:
        if track_width > 2 * int(
            ((via_width + via_clearance) / SQRT2) - via_clearance - via_width / 2
        ):
            # track too wide to be ignored in DIAGONAL pattern
            offset_x = int(via_width / 2) + via_clearance + int(track_width / 2)
        else:
            logger.debug("Track width small enough to be ignored")
            offset_x = via_clearance + max(via_width, track_width) + extra_space
            offset_x = int(offset_x / SQRT2)
        offset_y = offset_x
    else:  # Pattern.STAGGER
        offset_x = (
            2 * via_clearance + max(via_width, track_width) + track_width + extra_space
        )
        r = via_width // 2
        offset_y = int(
            math.sqrt(
                (3 * r * r)
                + (2 * r * via_clearance)
                - (r * track_width)
                - (via_clearance * track_width)
                - (track_width * track_width) / 4
            )
        )

    logger.debug(f"offsets: x: {offset_x} y: {offset_y}")

    # used for STAGGER pattern:
    zigzag = [(0.5, 1), (0.5, -1)]

    for i in range(0, count - 1):
        v = _via.Duplicate()
        assert v, "Failed to duplicate via item"
        v.SetNetCode(0)
        if pattern == Pattern.PERPENDICULAR:
            move += pcbnew.VECTOR2I(offset_x, 0)
        elif pattern == Pattern.DIAGONAL:
            move += pcbnew.VECTOR2I(offset_x, offset_y)
        else:  # Pattern.STAGGER
            coeffs = zigzag[i % 2]
            x = int(offset_x * coeffs[0])
            y = int(offset_y * coeffs[1])
            move += pcbnew.VECTOR2I(x, y)
        v.Move(move)
        if select:
            v.SetSelected()
        board.Add(v)
        vias.append(v)

    return vias
