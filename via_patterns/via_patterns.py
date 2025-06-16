from __future__ import annotations

import logging
import math
from enum import Enum, auto
from typing import List, Optional, Union

import kipy
from kipy.board import Board
from kipy.board_types import BoardItem, Net, Via
from kipy.geometry import Angle, Vector2
from kipy.project_types import NetClass
from kipy.proto.board.board_types_pb2 import ViaType
from kipy.util.units import from_mm

logger = logging.getLogger(__name__)
ZERO_POSITION = Vector2.from_xy(0, 0)
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


class Direction(int, Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()


class RotateDirection(int, Enum):
    CLOCKWISE = 1
    COUNTERCLOCKWISE = -1


def _default_via() -> Via:
    via = Via()
    via.type = ViaType.VT_THROUGH
    via.diameter = from_mm(0.6)
    via.drill_diameter = from_mm(0.3)
    #via.SetTopLayer(pcbnew.F_Cu)
    #via.SetBottomLayer(pcbnew.B_Cu)
    #via.SetNetCode(0)
    return via


def get_netclass(board: Board, item) -> NetClass:
    netclasses = board.get_netclass_for_nets(item.net)
    logger.debug(f"{netclasses=}")
    return netclasses[item.net.name]


def add_via_pattern(
    board: Board,
    count: int,
    pattern: Union[Pattern, str],
    *,
    via: Optional[Via] = None,
    start_position: Vector2 = ZERO_POSITION,
    direction: Direction = Direction.HORIZONTAL,
    net: str = "",
    track_width: int = 0,
    extra_space: int = 0,
    select: bool = False,
) -> List[Via]:
    vias: List[Via] = []

    if pattern not in [Pattern.DIAGONAL, Pattern.PERPENDICULAR, Pattern.STAGGER]:
        msg = "Unsupported pattern"
        raise ValueError(msg)

    if direction not in [Direction.HORIZONTAL, Direction.VERTICAL]:
        msg = "Unsupported direction"
        raise ValueError(msg)

    if track_width < 0:
        msg = "The `track_width` argument must be greater or equal 0"
        raise ValueError(msg)

    if extra_space < 0:
        msg = "The `extra_space` argument must be greater or equal 0"
        raise ValueError(msg)

    if not via:
        _via = _default_via()
        _via.position = start_position
        if net:
            if isinstance(net, str) and net != "":
                nets = board.get_nets()
                logger.debug(f"nets: {nets}")
                #_via.SetNet(nets[net])
            else:
                msg = "The `net` argument must be str or int"
                raise TypeError(msg)
        #board.Add(_via)
    else:
        _via = via
        #if via.GetParent().m_Uuid != board.m_Uuid:
        #    msg = "The `via` must be element of `board`"
        #    raise ValueError(msg)

    vias.append(_via)

    via_width = _via.diameter
    via_clearance = _via.GetOwnClearance(_via.GetLayer())

    if track_width == 0 or via_clearance == 0:
        via_netclass = get_netclass(board, _via)
        if track_width == 0:
            track_width = via_netclass.GetTrackWidth()
            logger.debug(
                "The `track_width` argument not specified, using via's "
                f"netclass ({via_netclass.GetName()}) value: {track_width}"
            )
        if via_clearance == 0:
            via_clearance = via_netclass.GetClearance()
            logger.debug(
                "The `via_clearance` not specified, using via's "
                f"netclass ({via_netclass.GetName()}) value: {via_clearance}"
            )

    logger.debug(f"via_width: {via_width}, via_clearance: {via_clearance}")
    logger.debug(f"track_width: {track_width}")
    logger.debug(f"extra_space: {extra_space}")
    #logger.debug(f"netclass: {_via.GetNetClassName()}")

    if pattern in [Pattern.STAGGER, Pattern.DIAGONAL] and track_width > via_width:
        logger.debug(
            f"The '{pattern}' pattern when `track_width` > `via_width` makes no sense, "
            f"replacing with '{Pattern.PERPENDICULAR}' pattern"
        )
        pattern = Pattern.PERPENDICULAR

    move = Vector2.from_xy(0, 0)
    offset_x = 0
    offset_y = 0

    if pattern == Pattern.PERPENDICULAR:
        offset_x = via_clearance + max(via_width, track_width) + extra_space
        offset_y = 0
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

    # used for STAGGER pattern:
    zigzag = [(0.5, 1), (0.5, -1)]

    if direction == Direction.VERTICAL:
        offset_x, offset_y = offset_y, offset_x
        zigzag = [(1, 0.5), (-1, 0.5)]

    logger.debug(f"offsets: x: {offset_x} y: {offset_y}")

    for i in range(0, count - 1):
        v = _via.Duplicate()
        assert v, "Failed to duplicate via item"
        v.SetNetCode(0)
        v.SetIsFree(True)
        if pattern == Pattern.PERPENDICULAR:
            move += Vector2.from_xy(offset_x, offset_y)
        elif pattern == Pattern.DIAGONAL:
            move += Vector2.from_xy(offset_x, offset_y)
        else:  # Pattern.STAGGER
            coeffs = zigzag[i % 2]
            x = int(offset_x * coeffs[0])
            y = int(offset_y * coeffs[1])
            move += Vector2.from_xy(x, y)
        v.Move(move)
        if select:
            v.SetSelected()
        board.Add(v)
        vias.append(v)

    return vias


def rotate_via_pattern(
    vias: List[Via],
    direction: RotateDirection,
    *,
    reference_index: int = 0,
) -> None:
    if direction not in [RotateDirection.CLOCKWISE, RotateDirection.COUNTERCLOCKWISE]:
        msg = "Unsupported direction"
        raise ValueError(msg)

    if reference_index > len(vias) - 1:
        msg = "The `reference_index` argument is out of range"
        raise ValueError(msg)

    reference_position = vias[reference_index].position
    for i, via in enumerate(vias):
        if i == reference_index:
            continue
        #via.Rotate(
        #    reference_position, Angle.from_degrees(direction * -90)
        #)
