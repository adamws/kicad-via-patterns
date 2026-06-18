from __future__ import annotations

import logging
import math
from enum import Enum, auto
from typing import Dict, List, Optional, Union

from kipy.board import Board
from kipy.board_types import Net, Via
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
    SQUARE = "Square"

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
    return via


def get_netclass(board: Board, item: Via) -> NetClass:
    net = item.net
    if net.name:
        netclasses: Dict[str, NetClass] = board.get_netclass_for_nets(net)
        if net.name in netclasses:
            return netclasses[net.name]
    # fallback: get Default netclass from project
    all_netclasses = board.get_project().get_net_classes()
    for nc in all_netclasses:
        if nc.name == "Default":
            return nc
    return all_netclasses[0]


def _copy_via(source: Via) -> Via:
    # Copy all proto fields (type, padstack, diameter, drill, layers, etc.)
    copy = Via(proto=source._proto)
    # ... except `id`: if `source` is already a board item (e.g. the
    # via passed in by the caller), copying its id would make every
    # duplicate reference the same board item, so `create_items` collapses
    # them into one instead of creating distinct new vias.
    copy._proto.ClearField("id")
    return copy


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
    inherit_net: bool = False,
) -> List[Via]:
    vias: List[Via] = []

    if pattern not in [
        Pattern.DIAGONAL,
        Pattern.PERPENDICULAR,
        Pattern.STAGGER,
        Pattern.SQUARE,
    ]:
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
                matching = [n for n in nets if n.name == net]
                if matching:
                    _via.net = matching[0]
            else:
                msg = "The `net` argument must be str"
                raise TypeError(msg)
        commit = board.begin_commit()
        created = board.create_items([_via])
        board.push_commit(commit, "Add template via")
        _via = created[0]
    else:
        _via = via

    vias.append(_via)

    via_width = _via.diameter
    # clearance always comes from netclass (no GetOwnClearance in IPC API)
    via_clearance = 0

    via_netclass = get_netclass(board, _via)
    if track_width == 0:
        track_width = via_netclass.track_width or 0
        logger.debug(
            "The `track_width` argument not specified, using via's "
            f"netclass ({via_netclass.name}) value: {track_width}"
        )
    via_clearance = via_netclass.clearance or 0
    logger.debug(
        "Using via's " f"netclass ({via_netclass.name}) clearance: {via_clearance}"
    )

    logger.debug(f"via_width: {via_width}, via_clearance: {via_clearance}")
    logger.debug(f"track_width: {track_width}")
    logger.debug(f"extra_space: {extra_space}")

    if pattern in [Pattern.STAGGER, Pattern.DIAGONAL] and track_width > via_width:
        logger.debug(
            f"The '{pattern}' pattern when `track_width` > `via_width` makes no sense, "
            f"replacing with '{Pattern.PERPENDICULAR}' pattern"
        )
        pattern = Pattern.PERPENDICULAR

    side_length = count
    if pattern == Pattern.SQUARE:
        count = side_length * side_length

    offset_x = 0
    offset_y = 0

    if pattern == Pattern.PERPENDICULAR or pattern == Pattern.SQUARE:
        offset_x = via_clearance + max(via_width, track_width) + extra_space
        offset_y = offset_x if pattern == Pattern.SQUARE else 0
    elif pattern == Pattern.DIAGONAL:
        if track_width > 2 * int(
            ((via_width + via_clearance) / SQRT2) - via_clearance - via_width / 2
        ):
            # track too wide to be ignored in DIAGONAL pattern
            offset_x = int(via_width / 2) + via_clearance + int(track_width / 2)
        else:
            logger.debug("Track width small enough to be ignored")
            offset_x = via_clearance + max(via_width, track_width)
            offset_x = int(offset_x / SQRT2)
        offset_x += extra_space
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

    move_x = 0
    move_y = 0
    new_vias: List[Via] = []
    for i in range(0, count - 1):
        v = _copy_via(_via)
        if inherit_net:
            v.net = _via.net
        else:
            v.net = Net()

        if pattern == Pattern.PERPENDICULAR:
            move_x += offset_x
            move_y += offset_y
        elif pattern == Pattern.DIAGONAL:
            move_x += offset_x
            move_y += offset_y
        elif pattern == Pattern.SQUARE:
            k = i + 1
            row = k // side_length
            col = k % side_length
            move_x = col * offset_x
            move_y = row * offset_y
        else:  # Pattern.STAGGER
            coeffs = zigzag[i % 2]
            move_x += int(offset_x * coeffs[0])
            move_y += int(offset_y * coeffs[1])

        v.position = Vector2.from_xy(
            _via.position.x + move_x,
            _via.position.y + move_y,
        )
        new_vias.append(v)

    commit = board.begin_commit()
    created = board.create_items(new_vias)
    board.push_commit(commit, "Add via pattern")
    if select:
        board.add_to_selection(created)
    vias.extend(created)

    return vias


def rotate_via_pattern(
    board: Board,
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
    angle = Angle.from_degrees(direction * -90)
    updated: List[Via] = []
    for i, via in enumerate(vias):
        if i == reference_index:
            continue
        via.position = via.position.rotate(angle, reference_position)
        updated.append(via)

    commit = board.begin_commit()
    board.update_items(updated)
    board.push_commit(commit, "Rotate via pattern")
