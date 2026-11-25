"""Experimental isolated CAD-v2 data contract. No changes to existing engine modules.

Requires jsonschema 4.26+ (MIT) for Draft 2020-12 structural validation.
Cross-ref / net semantics are NOT and cannot be assured by JSON Schema alone.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[3] / 'contracts' / 'project-v2.schema.json'
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
CHECKER = Draft202012Validator(SCHEMA)
FORMAT = 'gscad-project'
V2 = 2
SOURCE_SHA = 'e695c415fdced164b0e0c39c5249d030795a0aa6'
FROZEN_MEMBERSHIP_HASH = 'df0b305173f1f1851d6f39d41294eac8bb75e5a6cc0fdc44686ca79fc8d7bb3e'
FROZEN_PART_HASH = '40187cfdec48caad8aae0f9e6412b4b47d192459f7a8bbf9919fb815604673a7'
MAX_BYTES = 5_000_000


class ContractError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f'{code}: {detail}')


def _duplicates_error(pairs: list[tuple[str, Any]]) -> dict:
    value = {}
    for key, val in pairs:
        if key in value:
            raise ContractError('JSON_DUPLICATE_KEY', key)
        value[key] = val
    return value


def _reject_float(value: str):
    raise ContractError('JSON_NON_INTEGER', f'Number {value} forbidden in document')


def strict_loads(blob: bytes | str) -> dict:
    if isinstance(blob, str):
        blob = blob.encode('utf-8')
    if len(blob) > MAX_BYTES:
        raise ContractError('FILE_TOO_LARGE', str(len(blob)))
    try:
        value = json.loads(blob.decode('utf-8'), object_pairs_hook=_duplicates_error,
                           parse_float=_reject_float, parse_constant=_reject_float)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError('JSON_INVALID', str(exc)) from exc
    if type(value) is not dict:
        raise ContractError('SCHEMA_INVALID', 'Top-level object required')
    return value


def _unique(items: list[str], label: str) -> None:
    if len(items) != len(set(items)):
        raise ContractError('DUPLICATE_ID', label)


def _map(items: list[dict], label: str) -> dict[str, dict]:
    keys = [item['id'] for item in items]
    _unique(keys, label)
    return {item['id']: item for item in items}


def pin_world(instance: dict, local: list[int]) -> tuple[int, int]:
    x, y = local
    if instance['mirror_x']:
        x = -x
    rotation = instance['rotation_deg']
    if rotation == 90:
        x, y = -y, x
    elif rotation == 180:
        x, y = -x, -y
    elif rotation == 270:
        x, y = y, -x
    return instance['origin_um'][0] + x, instance['origin_um'][1] + y


def _on_segment(p: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> bool:
    return ((b[0]-a[0])*(p[1]-a[1]) == (b[1]-a[1])*(p[0]-a[0])
            and min(a[0],b[0]) <= p[0] <= max(a[0],b[0])
            and min(a[1],b[1]) <= p[1] <= max(a[1],b[1]))



def route_is_complete(project: dict, net: dict) -> bool:
    """Only authored connectivity joins paths. Coincident free ends and bare X/T do not.

    Segment interior touches are conductive only at an explicit named junction;
    an invisible splice joins exactly two explicitly anchored wire endpoints.
    """
    members = {(m['component_id'], m['physical_pin_number']) for m in net['members']}
    if len(members) < 2:
        return True
    parent: dict[str, str] = {}
    physical: dict[tuple[str, str], list[str]] = {}
    splices: dict[tuple[str, str], list[str]] = {}
    segments: list[tuple[str, tuple[int, int], tuple[int, int], str]] = []

    def root(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        a, b = root(a), root(b)
        if a != b:
            parent[b] = a

    for sheet in project['sheets']:
        sid = sheet['id']
        for wire in sheet['wires']:
            if wire['net_id'] != net['id']:
                continue
            vertices = wire['vertices']
            for i, vertex in enumerate(vertices):
                node = sid + ':' + wire['id'] + ':' + vertex['id']
                parent[node] = node
                anchor = vertex['anchor']
                if anchor['kind'] == 'pin':
                    key = anchor['component_id'], anchor['physical_pin_number']
                    physical.setdefault(key, []).append(node)
                elif anchor['kind'] == 'splice':
                    splices.setdefault((sid, anchor['splice_id']), []).append(node)
                if i:
                    prev = sid + ':' + wire['id'] + ':' + vertices[i-1]['id']
                    union(prev, node)
                    segments.append((sid, tuple(vertices[i-1]['at_um']),
                                     tuple(vertex['at_um']), node))
    # A physical pin identity is a single contact. A splice is authored and
    # never merges a coincident but unrelated dangling free endpoint.
    for groups in (physical, splices):
        for nodes in groups.values():
            for node in nodes[1:]:
                union(nodes[0], node)
    for sheet in project['sheets']:
        for junction in sheet['junctions']:
            if junction['net_id'] != net['id']:
                continue
            p = tuple(junction['at_um'])
            touching = [node for sid, a, b, node in segments
                        if sid == sheet['id'] and _on_segment(p, a, b)]
            for node in touching[1:]:
                union(touching[0], node)
    if not members <= set(physical):
        return False
    return len({root(physical[key][0]) for key in members}) == 1


def _semantic(project: dict) -> None:
    parts = _map(project['part_definitions'], 'part definitions')
    symbols = _map(project['symbol_definitions'], 'symbols')
    components = _map(project['components'], 'components')
    nets = _map(project['nets'], 'nets')
    sheets = _map(project['sheets'], 'sheets')
    _unique([c['refdes'] for c in components.values()], 'refdes')
    _unique([c['source_refdes'] for c in components.values()], 'source_refdes')
    _unique([n['name'] for n in nets.values()], 'net names')
    _unique([s['index'] for s in sheets.values()], 'sheet indexes')
    if not sheets:
        raise ContractError('SHEET_REQUIRED', 'At least one sheet required')
    for part in parts.values():
        _unique([p['number'] for p in part['physical_pins']], part['id']+' physical numbers')
        _unique(part['symbol_ids'],part['id']+' symbol list')
        for symbol_id in part['symbol_ids']:
            if symbol_id not in symbols or symbols[symbol_id]['part_id'] != part['id']:
                raise ContractError('PART_SYMBOL_MISMATCH', part['id'])
    for sym in symbols.values():
        # Circle = center and cardinal rim point; semicircle = start, apex, end.
        # All values remain integer µm, and D4 transforms preserve this contract.
        for g in sym['graphics']:
            pts = g['points_um']
            if g['kind'] == 'circle':
                a, b = pts
                dx, dy = b[0]-a[0], b[1]-a[1]
                if (dx == 0) == (dy == 0):
                    raise ContractError('INVALID_CURVE', sym['id'])
                r = abs(dx)+abs(dy)
                if any(abs(v)+r > 1_000_000_000 for v in a):
                    raise ContractError('INVALID_CURVE', sym['id'])
            elif g['kind'] == 'semicircle':
                a, m, b = pts
                if (a[0]+b[0]) % 2 or (a[1]+b[1]) % 2:
                    raise ContractError('INVALID_CURVE', sym['id'])
                x,y = (a[0]+b[0])//2,(a[1]+b[1])//2
                dx,dy = a[0]-x,a[1]-y
                ux,uy = m[0]-x,m[1]-y
                r = abs(dx)+abs(dy)
                if (dx == 0) == (dy == 0) or dx*ux+dy*uy != 0 or abs(ux)+abs(uy) != r:
                    raise ContractError('INVALID_CURVE', sym['id'])
                if abs(x)+r > 1_000_000_000 or abs(y)+r > 1_000_000_000:
                    raise ContractError('INVALID_CURVE', sym['id'])
        part = parts.get(sym['part_id'])
        if not part or sym['id'] not in part['symbol_ids']:
            raise ContractError('PART_SYMBOL_MISMATCH', sym['id'])
        known = {p['number'] for p in part['physical_pins']}
        pin_numbers = [p['physical_pin_number'] for p in sym['pins']]
        _unique(pin_numbers, sym['id']+' graphic pins')
        if not set(pin_numbers) <= known:
            raise ContractError('SYMBOL_UNKNOWN_PIN', sym['id'])
        _unique([tuple(p['at_um']) for p in sym['pins']],sym['id']+' pin coordinates')
    for comp in components.values():
        if comp['part_id'] not in parts:
            raise ContractError('UNKNOWN_PART',comp['id'])
    for net in nets.values():
        _unique([(p['component_id'],p['physical_pin_number']) for p in net['members']],
                net['name']+' members')
    owners: dict[tuple[str, str], str] = {}
    for net in nets.values():
        for pref in net['members']:
            cid, pn = pref['component_id'], pref['physical_pin_number']
            if cid not in components:
                raise ContractError('UNKNOWN_PHYSICAL_COMPONENT', cid)
            part = parts[components[cid]['part_id']]
            if pn not in {p['number'] for p in part['physical_pins']}:
                raise ContractError('INVALID_PINREF', components[cid]['refdes']+'.'+pn)
            key = cid, pn
            if key in owners and owners[key] != net['id']:
                raise ContractError('PIN_MULTI_NET', components[cid]['refdes']+'.'+pn)
            owners[key] = net['id']

    # A component has one physical PinRef inventory even if depicted via multiple units/sheets.
    locations: dict[tuple[str,str], tuple[str,tuple[int,int]]] = {}
    global_ids: set[str] = set()
    for sheet in sheets.values():
        # Geometry is sheet-local; identical coordinates on different sheets never touch.
        segments: list[tuple[str, str, tuple[int,int], tuple[int,int], str]] = []
        layer_map = _map(sheet['layers'], sheet['id']+' layers')
        instances = _map(sheet['instances'],sheet['id']+' instances')
        wires = _map(sheet['wires'],sheet['id']+' wires')
        junctions = _map(sheet['junctions'], sheet['id']+' junctions')
        splices = _map(sheet['splices'], sheet['id']+' splices')
        used_free_ids: set[str] = set()
        used_splices: dict[str, list[tuple[str, tuple[int,int]]]] = {}
        used_junctions: set[str] = set()
        for collection in ('layers','instances','wires','junctions','splices','texts','labels','graphics'):
            for item in sheet[collection]:
                if item['id'] in global_ids:
                    raise ContractError('DUPLICATE_ID', item['id']+' global')
                global_ids.add(item['id'])
                if (collection not in ('layers', 'instances')
                        and item['layer_id'] not in layer_map):
                    raise ContractError('UNKNOWN_LAYER',item['id'])
        for inst in instances.values():
            if inst['layer_id'] not in layer_map:
                raise ContractError('UNKNOWN_LAYER', inst['id'])
            comp = components.get(inst['component_id'])
            sym = symbols.get(inst['symbol_id'])
            if comp is None or sym is None or sym['part_id'] != comp['part_id']:
                raise ContractError('PART_SYMBOL_MISMATCH', inst['id'])
            for pin in sym['pins']:
                key = (comp['id'], pin['physical_pin_number'])
                if key in locations:
                    raise ContractError('DUPLICATE_PIN_PLACEMENT',str(key))
                point = pin_world(inst,pin['at_um'])
                if any(abs(coordinate) > 1_000_000_000 for coordinate in point):
                    raise ContractError('PIN_WORLD_OUT_OF_BOUNDS', str(key))
                locations[key] = (sheet['id'], point)
        for label in sheet['labels']:
            if (label['role']=='visual' and label['net_id'] is not None) or (
                label['role']=='net_annotation' and label['net_id'] not in nets):
                raise ContractError('LABEL_BINDING_INVALID', label['id'])
        for wire in wires.values():
            if wire['net_id'] not in nets:
                raise ContractError('UNKNOWN_NET', wire['id'])
            vertices = wire['vertices']
            vmap = {v['id']:v for v in vertices}
            _unique([v['id'] for v in vertices],wire['id']+' vertices')
            _unique([s['id'] for s in wire['segments']],wire['id']+' segments')
            if len(wire['segments']) != len(vertices)-1:
                raise ContractError('POLYLINE_BROKEN', wire['id']+' segment count')
            for i,segment in enumerate(wire['segments']):
                if (segment['from_vertex_id']!=vertices[i]['id'] or
                    segment['to_vertex_id']!=vertices[i+1]['id']):
                    raise ContractError('POLYLINE_BROKEN',wire['id']+' segment order')
                a = tuple(vmap[segment['from_vertex_id']]['at_um'])
                b = tuple(vmap[segment['to_vertex_id']]['at_um'])
                if a == b or (a[0]!=b[0] and a[1]!=b[1]):
                    raise ContractError('SEGMENT_NOT_ORTHOGONAL', wire['id']+'/'+segment['id'])
                segments.append((wire['net_id'], wire['id'], a, b, segment['id']))
            for idx, vertex in enumerate(vertices):
                ep = vertex['anchor']
                p = tuple(vertex['at_um'])
                if ep['kind'] in ('pin','free','splice','junction') and idx not in (0,len(vertices)-1):
                    raise ContractError('ENDPOINT_INTERIOR_INVALID',wire['id'])
                if ep['kind'] == 'bend' and idx in (0,len(vertices)-1):
                    raise ContractError('ENDPOINT_TERMINAL_INVALID',wire['id'])
                if ep['kind']=='pin':
                    key = ep['component_id'],ep['physical_pin_number']
                    if owners.get(key)!=wire['net_id']:
                        raise ContractError('PIN_WRONG_NET',wire['id']+'/'+str(key))
                    if locations.get(key)!=(sheet['id'],p):
                        raise ContractError('PIN_ANCHOR_MISMATCH',wire['id']+'/'+str(key))
                elif ep['kind']=='free':
                    fid = ep['free_id']
                    if fid in used_free_ids or fid in global_ids:
                        raise ContractError('DUPLICATE_FREE_ID', fid)
                    used_free_ids.add(fid)
                    global_ids.add(fid)
                elif ep['kind']=='splice':
                    sp = splices.get(ep['splice_id'])
                    if sp is None or sp['net_id'] != wire['net_id'] or tuple(sp['at_um']) != p:
                        raise ContractError('SPLICE_ENDPOINT_MISMATCH', wire['id'])
                    used_splices.setdefault(sp['id'], []).append((wire['id'], p))
                elif ep['kind']=='junction':
                    used_junctions.add(ep['junction_id'])
                    j = junctions.get(ep['junction_id'])
                    if j is None or j['net_id']!=wire['net_id'] or tuple(j['at_um'])!=p:
                        raise ContractError('JUNCTION_ENDPOINT_MISMATCH',wire['id'])
        # Splice is a hidden, precisely degree-2 contact joining two distinct
        # terminal wires. Unlike a Junction it cannot be used for a three-way T.
        for sp in splices.values():
            if sp['net_id'] not in nets:
                raise ContractError('UNKNOWN_NET', sp['id'])
            hits = [seg for seg in segments if _on_segment(tuple(sp['at_um']), seg[2], seg[3])]
            if any(seg[0] != sp['net_id'] for seg in hits):
                raise ContractError('SPLICE_CROSSES_FOREIGN_NET', sp['id'])
            refs = used_splices.get(sp['id'], [])
            if len(refs) != 2 or len({ref[0] for ref in refs}) != 2:
                raise ContractError('SPLICE_DEGREE_INVALID', sp['id'])
            # No unbound segment may touch this hidden contact. Every stroke
            # through the splice must belong to precisely those two wire ends.
            if len(hits) != 2 or {seg[1] for seg in hits} != {ref[0] for ref in refs}:
                raise ContractError('SPLICE_UNAUTHORIZED_CONTACT', sp['id'])
        # Reject false junctions, including those touching a different Net's ink.
        for j in junctions.values():
            if j['net_id'] not in nets:
                raise ContractError('UNKNOWN_NET',j['id'])
            p = tuple(j['at_um'])
            hits = [s for s in segments if _on_segment(p,s[2],s[3])]
            foreign = [s for s in hits if s[0] != j['net_id']]
            own = [s for s in hits if s[0] == j['net_id']]
            if foreign:
                raise ContractError('JUNCTION_CROSSES_FOREIGN_NET',j['id'])
            if len(own)<2 or (len({s[1] for s in own})<2 and len(own)<3):
                raise ContractError('FALSE_JUNCTION',j['id'])
    # Wires cannot claim physical pin if the relevant graphical pin has not been placed.
    for net in nets.values():
        if net['route_status'] == 'verified':
            # The live wire engine emits this review flag after an approved
            # provisional move/rotation. Preserve it in JSON but never infer
            # print-ready routing before clearance/ERC gates have re-run.
            if any(w.get('needs_routing_review', False)
                   for sheet in sheets.values() for w in sheet['wires']
                   if w['net_id'] == net['id']):
                raise ContractError('ROUTE_REVIEW_REQUIRED',net['name'])
            if not route_is_complete(project,net):
                raise ContractError('ROUTE_INCOMPLETE',net['name'])
    source = project['provenance']
    counts = source['expected_counts']
    actual = {'components':len(components),'nets':len(nets),
              'memberships':sum(len(n['members']) for n in nets.values()),
              'da1_pins':sum(len(parts[c['part_id']]['physical_pins']) for c in components.values()
                              if c['source_refdes']=='DA1'),
              'b_graphics':sum(1 for s in sheets.values() for g in s['graphics']
                                if g['kind']=='source_b_continuation')}
    if actual!=counts:
        raise ContractError('SOURCE_COUNT_MISMATCH',f'expected {counts}, got {actual}')
    if source['status']=='source_traced_unapproved' and source['source_sha']==SOURCE_SHA:
        if counts!={'components':23,'nets':15,'memberships':62,'da1_pins':16,'b_graphics':2}:
            raise ContractError('FROZEN_COUNT_MISMATCH',str(counts))
        pkey=sorted((c['source_refdes'],c['part_id']) for c in components.values())
        nkey=sorted((n['name'],sorted((components[x['component_id']]['source_refdes'],x['physical_pin_number'])
                    for x in n['members'])) for n in nets.values())
        def sha(x):return hashlib.sha256(_canonical(x)).hexdigest()
        if sha(pkey)!=FROZEN_PART_HASH or sha(nkey)!=FROZEN_MEMBERSHIP_HASH:
            raise ContractError('SOURCE_TOPOLOGY_DRIFT','Frozen E695 inventory/physical PinRefs changed')


def validate(document: dict) -> dict:
    if type(document) is not dict or document.get('format_version')!=V2:
        raise ContractError('VERSION_UNSUPPORTED',str(document.get('format_version')) if isinstance(document,dict) else 'invalid root')
    errs = sorted(CHECKER.iter_errors(document),key=lambda e: (list(map(str,e.path)),e.message))
    if errs:
        e = errs[0]
        raise ContractError('SCHEMA_INVALID',f'{"/".join(map(str,e.path))}: {e.message}')
    project=document['project']
    _semantic(project)
    if document['workspace']['active_sheet_id'] not in {s['id'] for s in project['sheets']}:
        raise ContractError('WORKSPACE_UNKNOWN_SHEET',document['workspace']['active_sheet_id'])
    return document


def migrate(document: dict) -> dict:
    """Only known 1->2 migration; future versions fail closed, never silently coercing pins."""
    if document.get('format')!=FORMAT:
        raise ContractError('FORMAT_UNSUPPORTED',str(document.get('format')))
    if document.get('format_version')==2:
        return validate(copy.deepcopy(document))
    if document.get('format_version')!=1:
        raise ContractError('VERSION_UNSUPPORTED',str(document.get('format_version')))
    if set(document)!={'format','format_version','project'}:
        raise ContractError('MIGRATION_REQUIRES_EXACT_V1','unknown v1 fields')
    old=copy.deepcopy(document)
    old['format_version']=2
    # v1 experimental wire vertices used endpoint and omitted explicit free IDs.
    # v2 does not infer connectivity from coincident free endpoints during upgrade.
    for sheet in old['project']['sheets']:
        if 'splices' in sheet:
            raise ContractError('MIGRATION_REQUIRES_EXACT_V1', 'Unexpected v1 splices')
        sheet['splices'] = []
        for wire in sheet['wires']:
            for index, vertex in enumerate(wire['vertices']):
                if 'anchor' in vertex or 'endpoint' not in vertex:
                    raise ContractError('MIGRATION_REQUIRES_EXACT_V1', 'Malformed v1 vertex')
                anchor = vertex.pop('endpoint')
                if anchor['kind'] == 'free':
                    if set(anchor) != {'kind'}:
                        raise ContractError('MIGRATION_REQUIRES_EXACT_V1', 'Malformed v1 free')
                    anchor['free_id'] = wire['id'] + ':free:' + str(index)
                vertex['anchor'] = anchor
    sid=old['project']['sheets'][0]['id']
    old['workspace']={'active_sheet_id':sid,'camera_center_um':[0,0],
                      'zoom_milli':1000,'selected_ids':[],
                      'panels_px':{'left':280,'right':320,'bottom':160}}
    return validate(old)


def _canonical(value: Any) -> bytes:
    """Integer-only JCS-compatible subset; keys in schema are ASCII identifiers."""
    return json.dumps(value,ensure_ascii=False,sort_keys=True,
                      separators=(',',':'),allow_nan=False).encode('utf-8')


def source_inventory_hash(project: dict) -> str:
    """Content address immutable declared source topology, distinct from route digest."""
    components = {c['id']: c for c in project['components']}
    record = {
        'source_sha': project['provenance']['source_sha'],
        'components': sorted((cid, c['source_refdes'], c['part_id'])
                             for cid, c in components.items()),
        # Freezing only component IDs / Net memberships is insufficient:
        # a writer could silently retype a physical pin, move its library-local
        # contact 1µm or relabel a part without changing the old source hash.
        # Lock the physical catalogue inventory and pin anchors as well.
        'physical_parts': sorted((p['id'], p['reference_prefix'],
                                  sorted(p['symbol_ids']),
                                  sorted((pin['number'], pin['name'],
                                          pin['electrical_type'])
                                         for pin in p['physical_pins']))
                                 for p in project['part_definitions']),
        'graphic_pin_bindings': sorted((s['id'], s['part_id'], s['revision'],
                                        sorted((pin['physical_pin_number'],
                                                pin['side'], pin['at_um'])
                                               for pin in s['pins']))
                                       for s in project['symbol_definitions']),
        'nets': sorted((net['id'], net['name'], sorted(
            (m['component_id'], m['physical_pin_number']) for m in net['members']))
            for net in project['nets']),
    }
    return hashlib.sha256(b'GSCAD_SOURCE_V2\x00' + _canonical(record)).hexdigest()


def digest(document: dict) -> str:
    validate(document)
    return hashlib.sha256(b'GSCAD_PROJECT_V2\x00'+_canonical(document['project'])).hexdigest()


def serialize(document: dict) -> bytes:
    validate(document)
    # Pretty but deterministic file; hash uses compact sorted canonical *project* data.
    return (json.dumps(document,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')


def atomic_save(path: Path, document: dict, *, simulated_error: bool = False) -> str:
    """Safe replace in same filesystem; controlled failure before replace leaves old bytes intact."""
    blob=serialize(document)
    folder=Path(path).parent
    folder.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='wb',prefix='.gscad-',suffix='.tmp',
                                         dir=folder,delete=False) as file:
            temp=Path(file.name)
            file.write(blob)
            file.flush()
            os.fsync(file.fileno())
        if simulated_error:
            raise OSError('simulated write failure before atomic rename')
        os.replace(temp,path)
        temp=None
        if os.name!='nt':
            fd=os.open(folder,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return digest(document)


class History:
    """MVP transaction snapshots for undo/redo; future journal stores typed command deltas.

    Changes are validated as a whole, so part motion plus attached wire motion
    must arrive in the same transaction. This class is in-memory and not autosave.
    """
    def __init__(self,document:dict):
        self.current=validate(copy.deepcopy(document))
        self.undo: list[dict]=[]
        self.redo: list[dict]=[]
    def apply(self, candidate:dict) -> None:
        validate(candidate)
        self.undo.append(copy.deepcopy(self.current))
        self.current=copy.deepcopy(candidate)
        self.redo.clear()
    def commit_cas(self, candidate: dict, *, expected_sha256: str,
                   expected_generation: int, generation: int,
                   source_topology_hash: str) -> tuple[str, int]:
        """Atomic in-memory snapshot replacement with explicit source and revision guard.

        The command layer (#123) must prepare the candidate; the project model
        validates the complete resulting graph before updating state. An OS
        durable journal and an IPC generation allocator belong to MASTER/desktop.
        """
        if expected_generation != generation or expected_sha256 != digest(self.current):
            raise ContractError('REVISION_CONFLICT', 'Stale project revision')
        if source_topology_hash != source_inventory_hash(self.current['project']):
            raise ContractError('SOURCE_TOPOLOGY_CONFLICT', 'Stale source declaration')
        validated = validate(copy.deepcopy(candidate))
        if source_inventory_hash(validated['project']) != source_topology_hash:
            raise ContractError('SOURCE_TOPOLOGY_DRIFT', 'Cannot edit source pins via move/wire command')
        self.apply(validated)
        return digest(self.current), generation + 1

    def revert(self) -> None:
        if not self.undo:raise ContractError('UNDO_EMPTY','')
        self.redo.append(self.current)
        self.current=self.undo.pop()
    def replay(self) -> None:
        if not self.redo:raise ContractError('REDO_EMPTY','')
        self.undo.append(self.current)
        self.current=self.redo.pop()


def write_autosave(path: Path, document: dict, *, base_sha256: str) -> str:
    """Sidecar autosave, separate from manually saved document and scoped to base hash.

    Autosave must not silently overwrite a manual save of a different revision.
    """
    if len(base_sha256)!=64 or any(c not in '0123456789abcdef' for c in base_sha256):
        raise ContractError('AUTOSAVE_BASE_INVALID',base_sha256)
    digest_candidate=digest(document)
    record={'kind':'gscad-autosave-v1','base_sha256':base_sha256,
            'candidate_sha256':digest_candidate,'document':document}
    atomic_blob=(json.dumps(record,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    folder=Path(path).parent
    folder.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='wb',prefix='.gscad-autosave-',
                                         suffix='.tmp',dir=folder,delete=False) as handle:
            temp=Path(handle.name)
            handle.write(atomic_blob)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp,path)
        temp=None
    finally:
        if temp is not None:temp.unlink(missing_ok=True)
    return digest_candidate


def recover_autosave(path: Path, *, base_document:dict) -> dict | None:
    """Recover only validated autosave created from current disk base revision."""
    base=digest(base_document)
    if not Path(path).is_file():return None
    record=strict_loads(Path(path).read_bytes())
    if set(record)!={'kind','base_sha256','candidate_sha256','document'} or record['kind']!='gscad-autosave-v1':
        raise ContractError('AUTOSAVE_INVALID','Malformed autosave envelope')
    if record['base_sha256']!=base:
        raise ContractError('AUTOSAVE_BASE_CONFLICT','Saved file changed since autosave')
    validate(record['document'])
    if digest(record['document'])!=record['candidate_sha256']:
        raise ContractError('AUTOSAVE_CORRUPT','Autosave payload checksum mismatch')
    return record['document']
