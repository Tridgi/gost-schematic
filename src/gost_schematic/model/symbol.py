"""Versioned graphic symbol definition, not an electrical component instance."""
from dataclasses import dataclass
from enum import Enum

from gost_schematic.core.geometry import (
    Box,
    Primitive,
    enclosing_box,
    primitive_bounds,
    primitive_stroked_bounds,
)
from gost_schematic.model.annotations import AnnotationSlot
from gost_schematic.model.pins import GraphicPin


class SymbolStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


@dataclass(frozen=True, slots=True)
class SymbolDefinition:
    identifier: str
    revision: int
    graphics: tuple[Primitive, ...]
    pins: tuple[GraphicPin, ...]
    body_keepout: Box
    line_width_um: int
    status: SymbolStatus = SymbolStatus.DRAFT
    standard_refs: tuple[str, ...] = ()
    annotation_slots: tuple[AnnotationSlot, ...] = ()
    constant_annotations: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.identifier.strip() or type(self.revision) is not int or self.revision < 1:
            raise ValueError("Symbol ID must be non-empty and revision positive")
        if not self.graphics or not self.pins:
            raise ValueError("Symbol requires both graphical primitives and pins")
        if type(self.line_width_um) is not int or self.line_width_um <= 0:
            raise ValueError("Line width must be positive micrometres")
        keys = [slot.key for slot in self.annotation_slots]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate annotation slot key")
        literals = [key for key, _ in self.constant_annotations]
        if len(literals) != len(set(literals)) or any(key not in keys for key in literals):
            raise ValueError("Constant annotation needs a unique, declared slot key")
        if any(not text for _, text in self.constant_annotations):
            raise ValueError("Constant annotation text must not be empty")
        numbers = [pin.number for pin in self.pins]
        positions = [pin.at for pin in self.pins]
        if len(numbers) != len(set(numbers)) or len(positions) != len(set(positions)):
            raise ValueError("Duplicate graphic pin number or connector coordinate")
        if any(self.body_keepout.contains_interior(pin.at) for pin in self.pins):
            raise ValueError("Connector is trapped inside the body keepout")

    @property
    def bounds(self) -> Box:
        boxes = tuple(primitive_bounds(shape) for shape in self.graphics)
        boxes += (self.body_keepout,)
        for pin in self.pins:
            p = pin.at
            boxes += (Box(p.x, p.y, p.x + 1, p.y + 1),)
        return enclosing_box(boxes)

    @property
    def stroked_bounds(self) -> Box:
        """Complete visual extent, including thick ferrite or custom strokes.

        Legacy `bounds` remains the un-stroked layout geometry for backward
        compatibility; consumers checking visual collisions use this property.
        """
        boxes = tuple(
            primitive_stroked_bounds(item, self.line_width_um)
            for item in self.graphics
        )
        boxes += (self.body_keepout,)
        for pin in self.pins:
            p = pin.at
            boxes += (Box(p.x, p.y, p.x + 1, p.y + 1),)
        return enclosing_box(boxes)
