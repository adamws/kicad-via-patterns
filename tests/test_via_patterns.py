import logging
from typing import List

import pytest
from kipy.board_types import Net, Track, Via
from kipy.geometry import Vector2
from kipy.proto.board.board_types_pb2 import BoardLayer
from kipy.util.units import from_mm, to_mm

from via_patterns import (
    Direction,
    Pattern,
    add_via_pattern,
)
from via_patterns.via_patterns import RotateDirection, rotate_via_pattern

logger = logging.getLogger(__name__)


def _make_via(
    board,
    diameter_mm: float = 0.6,
    drill_mm: float = 0.3,
    net_name: str = "",
    x: int = 0,
    y: int = 0,
) -> Via:
    """Create a via and commit it to the live board.

    `add_via_pattern`'s `via` argument is documented to be an existing board
    item (in the real plugin it is always the user's current selection, see
    `plugin_action.py`), so a template built for tests must be committed too
    - otherwise it stays a floating, unrendered object and is silently
    missing from `board.get_vias()` and from report renders.
    """
    from kipy.proto.board.board_types_pb2 import ViaType

    via = Via()
    via.type = ViaType.VT_THROUGH
    via.diameter = from_mm(diameter_mm)
    via.drill_diameter = from_mm(drill_mm)
    via.position = Vector2.from_xy(x, y)
    if net_name:
        net = Net()
        net._proto.name = net_name
        via.net = net

    commit = board.begin_commit()
    created = board.create_items([via])
    board.push_commit(commit, "Add template via")
    return created[0]


def _add_track(
    start: Vector2, end: Vector2, layer: BoardLayer.ValueType, *, width: int
) -> Track:
    track = Track()
    track.start = start
    track.end = end
    track.layer = layer
    track.width = width
    return track


# One short stub per via, on each copper layer, pointing away from the
# pattern's axis - lets the report render show whether the pattern leaves
# enough room to escape-route every via.
STUB_DIRECTIONS = {
    Direction.HORIZONTAL: ((0, 1), (0, -1)),
    Direction.VERTICAL: ((1, 0), (-1, 0)),
}


def add_routing_stubs(board, vias: List[Via], direction: Direction, width: int) -> None:
    stub_length = from_mm(1)
    (dx1, dy1), (dx2, dy2) = STUB_DIRECTIONS[direction]

    stubs = []
    for v in vias:
        start = v.position
        stubs.append(
            _add_track(
                start,
                Vector2.from_xy(
                    start.x + dx1 * stub_length, start.y + dy1 * stub_length
                ),
                BoardLayer.BL_F_Cu,
                width=width,
            )
        )
        stubs.append(
            _add_track(
                start,
                Vector2.from_xy(
                    start.x + dx2 * stub_length, start.y + dy2 * stub_length
                ),
                BoardLayer.BL_B_Cu,
                width=width,
            )
        )

    commit = board.begin_commit()
    board.create_items(stubs)
    board.push_commit(commit, "Add routing stubs for report render")


def assert_via_nets(items: List[Via], inherit_net: bool) -> None:
    """Verify net assignment: first via keeps its net, subsequent vias depend on inherit_net."""
    first_net_name = items[0].net.name
    expected_name = first_net_name if inherit_net else ""
    for i in range(1, len(items)):
        assert items[i].net.name == expected_name


@pytest.mark.parametrize("number_of_vias", [3, 6])
@pytest.mark.parametrize(
    "pattern", [Pattern.PERPENDICULAR, Pattern.DIAGONAL, Pattern.STAGGER]
)
@pytest.mark.parametrize("via_size", [None, (0.8, 0.4)])
@pytest.mark.parametrize("track_width_mm", [0, 0.65])
@pytest.mark.parametrize("direction", [Direction.HORIZONTAL, Direction.VERTICAL])
@pytest.mark.parametrize("inherit_net", [False, True])
def test_via_pattern(
    number_of_vias,
    pattern,
    via_size,
    track_width_mm,
    direction,
    inherit_net,
    board,
    render,
) -> None:
    track_width = from_mm(track_width_mm)

    if via_size:
        template_via = _make_via(board, via_size[0], via_size[1], net_name="Net1")
    else:
        template_via = None

    vias = add_via_pattern(
        board,
        number_of_vias,
        pattern,
        via=template_via,
        net="Net1",
        track_width=track_width,
        direction=direction,
        inherit_net=inherit_net,
    )

    assert len(vias) == number_of_vias
    assert_via_nets(vias, inherit_net)

    # The first via is the template, the rest are the newly created pattern vias
    new_vias = vias[1:]

    if len(new_vias) >= 2:
        # Check that consecutive vias in the pattern have consistent offsets
        positions = [(v.position.x, v.position.y) for v in new_vias]
        logger.debug(f"Via positions (nm): {positions}")
        logger.debug(
            f"Via positions (mm): {[(to_mm(x), to_mm(y)) for x, y in positions]}"
        )

    add_routing_stubs(board, vias, direction, width=track_width or from_mm(0.2))
    render()


def test_via_pattern_correct_count(board) -> None:
    """Verify that exactly count vias are returned."""
    vias = add_via_pattern(board, 5, Pattern.PERPENDICULAR)
    assert len(vias) == 5


def test_via_pattern_positions_perpendicular(board, default_netclass) -> None:
    """Verify perpendicular pattern spacing equals via_width + clearance."""
    via_diameter_mm = 0.6

    template = _make_via(board, via_diameter_mm)
    vias = add_via_pattern(
        board,
        3,
        Pattern.PERPENDICULAR,
        via=template,
        direction=Direction.HORIZONTAL,
    )

    assert len(vias) == 3
    new_vias = vias[1:]
    assert len(new_vias) == 2

    # In HORIZONTAL perpendicular, y should be constant and x should increase
    ref_y = template.position.y
    for v in new_vias:
        assert v.position.y == ref_y

    expected_offset = default_netclass.clearance + max(
        from_mm(via_diameter_mm), default_netclass.track_width
    )
    x0 = template.position.x
    assert new_vias[0].position.x == x0 + expected_offset
    assert new_vias[1].position.x == x0 + 2 * expected_offset


def test_via_pattern_square(board, default_netclass) -> None:
    """Square pattern with size=3 should produce 9 vias in a 3x3 grid."""
    template = _make_via(board, 0.6)
    vias = add_via_pattern(
        board,
        3,  # side_length=3 -> 9 total vias
        Pattern.SQUARE,
        via=template,
    )
    assert len(vias) == 9

    new_vias = vias[1:]
    assert len(new_vias) == 8

    offset = default_netclass.clearance + max(
        from_mm(0.6), default_netclass.track_width
    )
    # Check that positions form a 3x3 grid
    positions = sorted(
        [
            (v.position.x - template.position.x, v.position.y - template.position.y)
            for v in new_vias
        ]
    )
    expected = sorted(
        [
            (col * offset, row * offset)
            for row in range(3)
            for col in range(3)
            if not (row == 0 and col == 0)  # skip (0,0) which is the template
        ]
    )
    assert positions == expected


def test_via_pattern_inherit_net(board) -> None:
    """When inherit_net=True, all vias keep the same net as the template."""
    template = _make_via(board, net_name="GND")

    vias = add_via_pattern(
        board, 3, Pattern.PERPENDICULAR, via=template, inherit_net=True
    )
    assert len(vias) == 3

    new_vias = vias[1:]
    for v in new_vias:
        assert v.net.name == "GND"


def test_via_pattern_no_inherit_net(board) -> None:
    """When inherit_net=False, new vias have empty net."""
    template = _make_via(board, net_name="Net1")

    vias = add_via_pattern(
        board, 3, Pattern.PERPENDICULAR, via=template, inherit_net=False
    )
    assert len(vias) == 3

    new_vias = vias[1:]
    for v in new_vias:
        assert v.net.name == ""


def test_pattern_rotation(board, render) -> None:
    """Rotation changes positions of non-reference vias."""
    template = _make_via(board, x=0, y=0)
    vias = add_via_pattern(
        board,
        3,
        Pattern.PERPENDICULAR,
        via=template,
        direction=Direction.HORIZONTAL,
    )
    assert len(vias) == 3

    via_positions_before = [v.position for v in vias]

    rotate_via_pattern(board, vias, RotateDirection.CLOCKWISE)

    # Reference via (index 0) should not have moved
    assert vias[0].position.x == via_positions_before[0].x
    assert vias[0].position.y == via_positions_before[0].y

    # Other vias should have moved
    assert vias[1].position != via_positions_before[1]
    assert vias[2].position != via_positions_before[2]

    # The rotation must be persisted on the live board, not just in memory
    board_positions = {(v.position.x, v.position.y) for v in board.get_vias()}
    for v in vias[1:]:
        assert (v.position.x, v.position.y) in board_positions

    render()


# Argument validation happens before any board interaction, so these need no
# live KiCad instance; the board argument is never dereferenced.


def test_via_pattern_wrong_net_type() -> None:
    with pytest.raises(TypeError, match="The `net` argument must be str"):
        add_via_pattern(None, 5, Pattern.PERPENDICULAR, net=("Net1",))  # type: ignore


def test_via_pattern_unsupported_pattern_type() -> None:
    with pytest.raises(ValueError, match="Unsupported pattern"):
        add_via_pattern(None, 5, "SOME_PATTERN")  # type: ignore


def test_via_pattern_unsupported_direction() -> None:
    with pytest.raises(ValueError, match="Unsupported direction"):
        add_via_pattern(None, 5, Pattern.DIAGONAL, direction="NO_SUCH_DIRECTION")  # type: ignore


def test_via_pattern_negative_extra_space() -> None:
    with pytest.raises(
        ValueError, match="The `extra_space` argument must be greater or equal 0"
    ):
        add_via_pattern(None, 5, Pattern.PERPENDICULAR, extra_space=-10)  # type: ignore


def test_via_pattern_negative_track_width() -> None:
    with pytest.raises(
        ValueError, match="The `track_width` argument must be greater or equal 0"
    ):
        add_via_pattern(None, 5, Pattern.PERPENDICULAR, track_width=-10)  # type: ignore


@pytest.mark.parametrize(
    "params", [("diagonal", Pattern.DIAGONAL), ("StaGGEr", Pattern.STAGGER)]
)
def test_pattern_enum_from_string(params) -> None:
    string, expected = params
    assert Pattern.get(string) == expected


def test_pattern_enum_from_illegal_string() -> None:
    with pytest.raises(ValueError, match=r"'.*' is not a valid Pattern"):
        _ = Pattern.get("NO_SUCH_PATTERN")
