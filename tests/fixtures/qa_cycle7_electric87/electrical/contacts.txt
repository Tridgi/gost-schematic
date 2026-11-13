"""Normalized physical contact identities, separate from graphic labels.

Unrelated contacts can share printed text, but never become the same physical
terminal without an explicit and separately validated electrical transaction.
"""
from dataclasses import dataclass
from enum import Enum

from gost_schematic.model.pins import ElectricalType


class ContactRole(str, Enum):
    GENERAL = "general"
    BJT_BASE = "bjt_base"
    BJT_COLLECTOR = "bjt_collector"
    BJT_EMITTER = "bjt_emitter"
    FET_GATE = "fet_gate"
    FET_DRAIN = "fet_drain"
    FET_SOURCE = "fet_source"
    FET_SUBSTRATE = "fet_substrate"
    POT_END_A = "pot_end_a"
    POT_END_B = "pot_end_b"
    POT_WIPER = "pot_wiper"
    FUSE_END = "fuse_end"
    CONNECTOR_CONTACT = "connector_contact"


@dataclass(frozen=True, slots=True)
class ContactSpec:
    number: str
    role: ContactRole
    function: str
    electrical_type: ElectricalType = ElectricalType.PASSIVE
    label: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.number, str) or not self.number.strip():
            raise ValueError("Physical contact number must be nonblank")
        if self.number != self.number.strip():
            raise ValueError("Physical contact numbers must be canonical")
        if not isinstance(self.role, ContactRole):
            raise TypeError("Physical contact role must be ContactRole")
        if not isinstance(self.function, str) or not self.function.strip():
            raise ValueError("Physical contact function is required")
        if not isinstance(self.electrical_type, ElectricalType):
            raise TypeError("Contact electrical type must be ElectricalType")
        if not isinstance(self.label, str):
            raise TypeError("Graphical label must be text")


@dataclass(frozen=True, slots=True)
class ContactInventory:
    contacts: tuple[ContactSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.contacts, tuple) or not self.contacts:
            raise ValueError("Physical inventory requires at least one terminal")
        if not all(isinstance(item, ContactSpec) for item in self.contacts):
            raise TypeError("Inventory expects ContactSpec")
        numbers = tuple(item.number for item in self.contacts)
        if len(numbers) != len(set(numbers)):
            raise ValueError("Duplicate physical contact numbers")

    def require_roles(self, roles: tuple[ContactRole, ...]) -> None:
        if not isinstance(roles, tuple) or len(roles) != len(set(roles)):
            raise ValueError("Required contact roles must be unique")
        selected: list[str] = []
        for role in roles:
            if not isinstance(role, ContactRole):
                raise TypeError("Expected ContactRole")
            candidates = [item.number for item in self.contacts if item.role is role]
            if len(candidates) != 1:
                raise ValueError(f"Expected exactly one physical {role.value} contact")
            selected.extend(candidates)
        if len(selected) != len(set(selected)):
            raise ValueError("Two distinct roles resolve to one physical pin")
