"""Conservative native Type A text ink measurement and release coverage.

A printed text baseline or nominal size is NOT glyph ink. Actual ink bounds
must come from the pinned physical renderer. Producer claims must subsequently
be independently compared with raster output before full-sheet certification.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from xml.etree import ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"


@dataclass(frozen=True)
class InkBox:
    """Stroke-inclusive integer-micrometre bounding rectangle."""

    left: int
    top: int
    right: int
    bottom: int

    @classmethod
    def read(cls, raw: str) -> InkBox:
        fields = raw.split(",")
        if len(fields) != 4 or any(not f or f.strip() != f for f in fields):
            raise ValueError("LABEL_INK_BBOX_MALFORMED")
        try:
            box = cls(*(int(x) for x in fields))
        except ValueError as exc:
            raise ValueError("LABEL_INK_BBOX_MALFORMED") from exc
        if box.left >= box.right or box.top >= box.bottom:
            raise ValueError("LABEL_INK_BBOX_DEGENERATE")
        return box

    def distance_um(self, other: InkBox) -> int:
        dx = max(0, self.left-other.right, other.left-self.right)
        dy = max(0, self.top-other.bottom, other.top-self.bottom)
        return round(math.hypot(dx, dy))

    def editorial_frame_intrusion_um(self) -> int:
        return max(0, 10000-self.left, 10000-self.top,
                   self.right-410000, self.bottom-287000)


def _wire_box(wire: dict) -> InkBox:
    x, y, xx, yy = wire["coords"]
    width = wire["stroke"]
    if width < 200 or width > 1000 or ((x == xx) == (y == yy)):
        raise ValueError("LABEL_NATIVE_WIRE_INVALID")
    return InkBox(min(x, xx)-width//2, min(y, yy)-width//2,
                  max(x, xx)+(width+1)//2, max(y, yy)+(width+1)//2)


def _text_identity(text: ET.Element) -> str:
    owner, key = text.get("data-owner"), text.get("data-key")
    if not owner or key not in {"refdes", "value"}:
        raise ValueError("LABEL_SOURCE_IDENTITY_INVALID")
    return f"{owner}:{key}"


def _text_baseline(text: ET.Element) -> tuple[int, int]:
    if (text.get("font-family") != "OpenGOST type A"
            or text.get("data-font-sha256") != FONT_SHA
            or text.get("font-style") != "normal"
            or text.get("fill") != "#000000"
            or text.get("stroke") != "none"
            or text.get("transform") is not None
            or not (text.text and text.text.strip())):
        raise ValueError("LABEL_TRUE_TYPE_A_FONT_PROVENANCE_DRIFT")
    try:
        x, y, size = (float(text.get(k, ""))
                      for k in ("x", "y", "font-size"))
    except (ValueError, TypeError) as exc:
        raise ValueError("LABEL_UNMEASURABLE_BASELINE") from exc
    if not all(map(math.isfinite, (x, y, size))) or size != 5.48:
        raise ValueError("LABEL_TRUE_TYPE_A_SIZE_DRIFT")
    return round(x*1000), round(y*1000)


def audit_type_a_annotations(
    root: ET.Element,
    wires: list[dict],
    symbols: dict[str, tuple[int, int, int, int]],
) -> dict:
    """Inspect 39 real owner annotations; don't manufacture missing ink.

    data-ink-um is a producer supplied stroke-inclusive outline measurement,
    never independent raster attestation. Its absence keeps release blocked.
    A >=1mm label-to-wire/symbol rule here is a PROJECT review constraint,
    not a blanket ГОСТ 2.701 requirement.
    """
    labels = root.findall(f".//{NS}text[@data-layer='annotations']")
    if (len(labels) != 39 or len(symbols) != 23
            or root.get("width") != "420mm"
            or root.get("height") != "297mm"):
        raise ValueError("LABEL_REAL_A3_39_TEXT_23_SYMBOLS_REQUIRED")
    identities = [_text_identity(t) for t in labels]
    if len(set(identities)) != len(labels):
        raise ValueError("LABEL_OWNER_KIND_DUPLICATED")
    wire_boxes = [(str(w["index"]), _wire_box(w)) for w in wires]
    symbol_boxes = [(k, InkBox(*v)) for k, v in symbols.items()]
    measured: list[dict] = []
    unmeasured: list[dict] = []
    frame: list[dict] = []
    hazards: list[dict] = []
    observed = {"label_wire": 0, "label_foreign_symbol": 0}
    minima: dict[str, int | None] = {
        "label_wire": None, "label_foreign_symbol": None,
    }
    for tag, identity in zip(labels, identities, strict=True):
        x, y = _text_baseline(tag)
        raw = tag.get("data-ink-um")
        if raw is None:
            unmeasured.append({"identity": identity, "text": tag.text,
                               "baseline_um": [x, y],
                               "reason": "NO_PHYSICAL_GLYPH_INK_AABB"})
            continue
        if (tag.get("data-ink-method") != "signed-native-type-a-outline-v1"
                or tag.get("data-ink-font-sha256") != FONT_SHA):
            raise ValueError("LABEL_MEASUREMENT_PROVENANCE_UNSIGNED")
        box = InkBox.read(raw)
        if not (box.left-1000 <= x <= box.right+1000
                and y-10960 <= box.top < box.bottom <= y+5480):
            raise ValueError("LABEL_BBOX_INCONSISTENT_WITH_BASELINE")
        measured.append({"identity": identity, "text": tag.text,
                         "bbox_um": [box.left, box.top, box.right, box.bottom],
                         "scope": "OWNER_OUTLINE_NOT_INDEPENDENT_RASTER"})
        intrusion = box.editorial_frame_intrusion_um()
        if intrusion:
            frame.append({"identity": identity, "intrusion_um": intrusion,
                          "rule": "PROJECT_EDITORIAL_10MM_NOT_GOST_FRAME"})
        categories = (
            ("label_wire", wire_boxes),
            ("label_foreign_symbol", [
                (ref, target) for ref, target in symbol_boxes
                if ref != tag.get("data-owner")
            ]),
        )
        for kind, others in categories:
            for other_id, target in others:
                gap = box.distance_um(target)
                observed[kind] += 1
                minima[kind] = (
                    gap if minima[kind] is None else min(minima[kind], gap)
                )
                if gap < 1000:
                    hazards.append({"label": identity, "kind": kind,
                                    "other": other_id, "gap_um": gap,
                                    "rule": "PROJECT_1MM_REVIEW_ONLY"})
    return {
        "schema": "ESKD_C16_NATIVE_LABEL_INK_V1",
        "font_sha256": FONT_SHA,
        "source_annotation_count": 39,
        "producer_measured_count": len(measured),
        "unmeasured_count": len(unmeasured),
        "unmeasured_annotations": unmeasured,
        "measured_annotations": measured,
        "measured_pair_count": observed,
        "minimum_ink_box_gap_um": minima,
        "project_editorial_10mm_frame_intrusions": frame,
        "project_1mm_label_collisions": hazards,
        "independent_raster_outlines": "BLOCKED_NOT_CORRELATED",
        "formal_gost_frame_and_title": "BLOCKED_SEPARATE_NORMATIVE_CHECK",
        "full_label_ink_verdict": (
            "BLOCKED_39_LABEL_BBOX_COVERAGE_INCOMPLETE"
            if unmeasured else "BLOCKED_ALL_BOXES_NEED_INDEPENDENT_RASTER"
        ),
    }
