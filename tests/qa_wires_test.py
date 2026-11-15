"""Seeded adversarial tests against REAL installed physical symbols and wire graphs."""

from importlib.resources import files
from pathlib import Path
from random import Random

import pytest

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)


@pytest.fixture(scope="module")
def real_parts():
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    source = {}
    parts = {
        part.identifier: part
        for path in sorted((root / "parts").rglob("*.json"))
        for part in (load_part(path),)
    }
    for path in sorted((root / "symbols").rglob("*.json")):
        sym = load_symbol(path)
        assert sym.identifier in parts, sym.identifier
        source[sym.identifier] = (parts[sym.identifier], sym)
    for path in sorted((root / "inductors").glob("*.json")):
        item = load_inductor(path)
        assert item.symbol.identifier not in source
        source[item.symbol.identifier] = (item.part, item.symbol)
    assert source
    return source


def _place(reference, part, symbol, contact, transform: Transform | None = None):
    tx = transform if transform is not None else Transform()
    pin = next(item for item in symbol.pins if item.number == "1")
    return ComponentInstance(reference, part.identifier, contact - tx.apply(pin.at), tx)


def _run(circuit, segments, parts, symbols, junctions=()):
    return validate_external_wires(
        circuit,
        ExternalWireGraph(tuple(segments), tuple(junctions)),
        parts,
        symbols,
    )


def _codes(diags):
    return {item.code for item in diags}


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_real_catalog_each_pin_identity_has_a_valid_external_wire(
    real_parts, rotation, mirror,
):
    tx = Transform(rotation, mirror)
    for identifier, (part, symbol) in sorted(real_parts.items()):
        start, end = Point(0, 0), Point(120_000, 70_000)
        first = _place("QA1", part, symbol, start, tx)
        second = _place("QA2", part, symbol, end, tx)
        assert first.pin_positions(symbol)["1"] == start, identifier
        assert second.pin_positions(symbol)["1"] == end, identifier
        circuit = Circuit(
            (first, second),
            (Net("LINK", (PinRef("QA1", "1"), PinRef("QA2", "1"))),),
        )
        assert _run(
            circuit, (WireSegment(start, end, "LINK"),),
            {part.identifier: part}, {symbol.identifier: symbol},
        ) == (), (identifier, rotation, mirror)


def _resistor(real_parts):
    return real_parts["resistor.fixed"]


def _chain(size, part, symbol):
    assert size >= 4
    step, high = 4000, -12000
    end_x = (size - 2) * step
    first = _place("R1", part, symbol, Point(0, 0), Transform(180))
    second = _place("R2", part, symbol, Point(end_x, 0), Transform(0))
    circuit = Circuit(
        (first, second),
        (Net("SIG", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    segments = [WireSegment(Point(0, 0), Point(0, high), "SIG")]
    for i in range(size - 2):
        segments.append(
            WireSegment(Point(i * step, high), Point((i + 1) * step, high), "SIG")
        )
    segments.append(WireSegment(Point(end_x, high), Point(end_x, 0), "SIG"))
    assert len(segments) == size
    return circuit, segments


@pytest.mark.parametrize("size", [10, 50, 200])
def test_seeded_long_wire_chains_are_connected_independent_of_input_order(
    real_parts, size,
):
    part, symbol = _resistor(real_parts)
    circuit, segments = _chain(size, part, symbol)
    parts, symbols = {part.identifier: part}, {symbol.identifier: symbol}
    original = tuple(segments)
    assert _run(circuit, original, parts, symbols) == ()
    random = Random(360600 + size)
    random.shuffle(segments)
    assert _run(circuit, segments, parts, symbols) == ()
    assert set(segments) == set(original)
    assert _run(circuit, original, parts, symbols) == ()


@pytest.mark.parametrize("size", [10, 50, 200])
def test_one_um_break_stays_disconnected_even_in_a_large_real_catalog_graph(
    real_parts, size,
):
    part, symbol = _resistor(real_parts)
    circuit, segments = _chain(size, part, symbol)
    index = size // 2
    removed = segments[index]
    segments[index] = WireSegment(
        Point(removed.start.x + 1, removed.start.y), removed.end, removed.net_name
    )
    diagnostics = _run(
        circuit, segments, {part.identifier: part}, {symbol.identifier: symbol}
    )
    assert {"WIRE_NET_DISCONNECTED", "WIRE_DANGLING_END"} <= _codes(diagnostics)
    assert "WIRE_NET_SHORT" not in _codes(diagnostics)


def test_seeded_real_resistor_x_crossings_do_not_connect_without_a_junction(real_parts):
    part, symbol = _resistor(real_parts)
    rng = Random(36_024)
    parts, symbols = {part.identifier: part}, {symbol.identifier: symbol}
    for _ in range(32):
        cx = rng.randrange(-700, 701) * 1000
        cy = rng.randrange(-700, 701) * 1000
        crossing = Point(cx, cy)
        left, right = Point(cx - 30_000, cy), Point(cx + 30_000, cy)
        top, bottom = Point(cx, cy - 30_000), Point(cx, cy + 30_000)
        # Each resistor's non-contacted second pin faces AWAY from this route.
        components = (
            _place("R1", part, symbol, left, Transform(180)),
            _place("R2", part, symbol, right, Transform(0)),
            _place("R3", part, symbol, top, Transform(270)),
            _place("R4", part, symbol, bottom, Transform(90)),
        )
        circuit = Circuit(components, (
            Net("H", (PinRef("R1", "1"), PinRef("R2", "1"))),
            Net("V", (PinRef("R3", "1"), PinRef("R4", "1"))),
        ))
        wires = (WireSegment(left, right, "H"), WireSegment(top, bottom, "V"))
        assert _run(circuit, wires, parts, symbols) == ()
        with_junction = _run(circuit, wires, parts, symbols, (crossing,))
        assert "WIRE_NET_SHORT" in _codes(with_junction)
        assert with_junction == _run(circuit, wires, parts, symbols, (crossing,))


def test_invalid_point_and_wire_values_fail_early(real_parts):
    with pytest.raises(TypeError):
        Point(0.0, 0)
    with pytest.raises(TypeError):
        Point(True, 0)
    with pytest.raises(ValueError, match="Zero-length"):
        WireSegment(Point(0, 0), Point(0, 0), "X")
    with pytest.raises(ValueError, match="net_name"):
        WireSegment(Point(0, 0), Point(1, 0), " ")
    with pytest.raises(ValueError, match="Duplicate junction"):
        ExternalWireGraph((), (Point(0, 0), Point(0, 0)))


def test_unassigned_physical_pin_never_disappears_into_a_valid_net(real_parts):
    part, symbol = _resistor(real_parts)
    pin1 = Point(0, 0)
    pin2 = next(item.at for item in symbol.pins if item.number == "2")
    pin1_source = next(item.at for item in symbol.pins if item.number == "1")
    delta = pin2 - pin1_source
    first = _place("R1", part, symbol, pin1)
    second = _place("R2", part, symbol, delta + Point(30_000, 0))
    circuit = Circuit(
        (first, second),
        (Net("SIG", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    # Intentionally drag the route across R1.2: this is not a valid two-pin connection.
    wire = WireSegment(pin1, second.pin_positions(symbol)["1"], "SIG")
    diagnostics = _run(
        circuit, (wire,), {part.identifier: part}, {symbol.identifier: symbol}
    )
    assert _codes(diagnostics) == {"WIRE_PIN_CONTACT_UNDECLARED"}
    assert all(item.severity.value == "error" for item in diagnostics)
    # A crossing without an explicit junction must never create a hidden net tie.
    assert "WIRE_NET_SHORT" not in _codes(diagnostics)


def _compose_d4(outer: Transform, inner: Transform) -> Transform:
    """Compose two genuine D4 symbol transforms without changing model APIs."""
    basis = (Point(1, 0), Point(0, 1))
    for mirror in (False, True):
        for angle in (0, 90, 180, 270):
            candidate = Transform(angle, mirror)
            if all(
                candidate.apply(v) == outer.apply(inner.apply(v)) for v in basis
            ):
                return candidate
    raise AssertionError("No D4 composition exists")


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize(
    "near_miss_um",
    [
        pytest.param(
            0,
            marks=pytest.mark.xfail(
                reason="Issue #54: foreign-net interior contact masked by A attachment",
                strict=True,
            ),
        ),
        1,
    ],
)
def test_foreign_net_interior_hits_preassigned_real_pin_without_false_short(
    real_parts, rotation, mirror, reverse, near_miss_um,
):
    """Issue #54: A terminates at R1.1 while B crosses its physical coordinate.

    Four actual fixed-resistor passports are arranged so neither net crosses
    another pin or a stray conductor. Away from all pins, X without junction
    is non-conductive; at a real pin, there MUST be an explicit error even if
    that pin is already attached to its legitimate network.
    """
    part, symbol = _resistor(real_parts)
    global_tx = Transform(rotation, mirror)
    point = global_tx.apply
    offset = point(Point(near_miss_um, 0))
    positions = {
        "R1": point(Point(0, 0)),
        "R2": point(Point(-20_000, 0)),
        "R3": point(Point(0, -10_000)) + offset,
        "R4": point(Point(0, 10_000)) + offset,
    }
    txs = {
        "R1": global_tx,
        "R2": _compose_d4(global_tx, Transform(180)),
        "R3": _compose_d4(global_tx, Transform(270)),
        "R4": _compose_d4(global_tx, Transform(90)),
    }
    instances = tuple(
        _place(ref, part, symbol, positions[ref], txs[ref])
        for ref in ("R1", "R2", "R3", "R4")
    )
    for item in instances:
        assert item.pin_positions(symbol)["1"] == positions[item.reference]
    circuit = Circuit(
        instances,
        (
            Net("A", (PinRef("R1", "1"), PinRef("R2", "1"))),
            Net("B", (PinRef("R3", "1"), PinRef("R4", "1"))),
        ),
    )
    # A's ENDPOINT is the already-net-owned R1.1. B's INTERIOR crosses
    # that exact point for 0um; at 1um, B becomes an ordinary unmarked X.
    a = WireSegment(positions["R2"], positions["R1"], "A")
    b = WireSegment(positions["R3"], positions["R4"], "B")
    if reverse:
        a = WireSegment(a.end, a.start, "A")
        b = WireSegment(b.end, b.start, "B")
    diagnostics = _run(
        circuit, (a, b), {part.identifier: part}, {symbol.identifier: symbol},
    )
    codes = _codes(diagnostics)
    assert "WIRE_NET_SHORT" not in codes  # Never silently create a junction.
    assert "WIRE_PIN_NET_MISMATCH" not in codes
    if near_miss_um:
        assert diagnostics == (), diagnostics
    else:
        assert codes == {"WIRE_PIN_CONTACT_UNDECLARED"}, diagnostics
        assert all(d.severity.value == "error" for d in diagnostics)
        assert any(d.subject == "R1" for d in diagnostics)
