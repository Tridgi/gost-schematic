"""Contract integration regressions for accepted ui/contracts/manual-wire-v2.md."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from contract import ContractError, digest, migrate, route_is_complete, validate
from contract import strict_loads

FIX = Path(__file__).resolve().parents[4] / 'fixtures'


def toy():
    return strict_loads((FIX / 'toy-v2.gscad.json').read_bytes())


def split_horizontal_endpoints(doc):
    """Split a verified net into two wires touching visually, but not electrically."""
    sh = doc['project']['sheets'][0]
    wire = sh['wires'][0]
    original = copy.deepcopy(wire)
    split = [40000, 30000]
    first = copy.deepcopy(original)
    first['id'] = 'wire-first'
    first['vertices'] = [copy.deepcopy(original['vertices'][0]),
                         {'id': 'wire-first-end', 'at_um': split,
                          'anchor': {'kind': 'free', 'free_id': 'first-free'}}]
    first['segments'] = [{'id': 'first-seg',
                          'from_vertex_id': first['vertices'][0]['id'],
                          'to_vertex_id': first['vertices'][1]['id']}]
    second = copy.deepcopy(original)
    second['id'] = 'wire-second'
    second['vertices'] = [
        {'id': 'wire-second-start', 'at_um': split,
         'anchor': {'kind': 'free', 'free_id': 'second-free'}},
        copy.deepcopy(original['vertices'][-1])]
    second['segments'] = [{'id': 'second-seg',
                           'from_vertex_id': second['vertices'][0]['id'],
                           'to_vertex_id': second['vertices'][1]['id']}]
    sh['wires'][0:1] = [first, second]
    return first, second


def test_same_net_free_ends_coincident_unjoined():
    doc = toy()
    first, second = split_horizontal_endpoints(doc)
    net = doc['project']['nets'][0]
    assert first['vertices'][-1]['at_um'] == second['vertices'][0]['at_um']
    assert not route_is_complete(doc['project'], net)
    with pytest.raises(ContractError, match='ROUTE_INCOMPLETE'):
        validate(doc)
    net['route_status'] = 'partial'
    validate(doc)


def test_splice_two_wire_ends_joins_without_visible_dot():
    doc = toy()
    first, second = split_horizontal_endpoints(doc)
    sh = doc['project']['sheets'][0]
    for v in (first['vertices'][-1], second['vertices'][0]):
        v['anchor'] = {'kind': 'splice', 'splice_id': 'splice-1'}
    sh['splices'].append({'id':'splice-1','net_id':first['net_id'],
                           'at_um':[40000,30000],'layer_id':'layer-electric'})
    assert sh['junctions'] == []
    validate(doc)
    assert route_is_complete(doc['project'],doc['project']['nets'][0])
    assert digest(doc) == digest(strict_loads(__import__('contract').serialize(doc)))


def test_splice_foreign_net_touch_rejected():
    doc = toy()
    first, second = split_horizontal_endpoints(doc)
    sh=doc['project']['sheets'][0]
    for v in (first['vertices'][-1],second['vertices'][0]):
        v['anchor']={'kind':'splice','splice_id':'splice-1'}
    sh['splices'].append({'id':'splice-1','net_id':first['net_id'],
                           'at_um':[50000,30000],'layer_id':'layer-electric'})
    with pytest.raises(ContractError,match='SPLICE_ENDPOINT_MISMATCH'):
        validate(doc)


def test_splice_three_terminal_forbidden():
    doc=toy()
    first,second=split_horizontal_endpoints(doc)
    sh=doc['project']['sheets'][0]
    for v in (first['vertices'][-1],second['vertices'][0]):
        v['anchor']={'kind':'splice','splice_id':'splice-1'}
    sh['splices'].append({'id':'splice-1','net_id':first['net_id'],
                         'at_um':[40000,30000],'layer_id':'layer-electric'})
    extra=copy.deepcopy(first)
    extra['id']='third-wire'
    extra['vertices'][0]['id']='third-pin'
    extra['vertices'][0]['at_um']=[40000,25000]
    extra['vertices'][0]['anchor']={'kind':'free','free_id':'third-free'}
    extra['vertices'][1]['id']='third-splice'
    extra['segments'][0]['id']='third-segment'
    extra['segments'][0]['from_vertex_id']='third-pin'
    extra['segments'][0]['to_vertex_id']='third-splice'
    sh['wires'].append(extra)
    with pytest.raises(ContractError,match='SPLICE_DEGREE_INVALID'):
        validate(doc)


def test_duplicate_free_id_is_not_valid_anchor_identity():
    doc=toy()
    first,second=split_horizontal_endpoints(doc)
    second['vertices'][0]['anchor']['free_id']=first['vertices'][-1]['anchor']['free_id']
    doc['project']['nets'][0]['route_status']='partial'
    with pytest.raises(ContractError,match='DUPLICATE_FREE_ID'):
        validate(doc)


def test_same_net_unmarked_x_keeps_two_islands_unconnected():
    doc=toy()
    project=doc['project']
    first,second=project['nets']
    first['members'].extend(copy.deepcopy(second['members']))
    del project['nets'][1]
    project['sheets'][0]['wires'][1]['net_id']=first['id']
    project['provenance']['expected_counts']['nets']=1
    assert route_is_complete(project,first) is False
    with pytest.raises(ContractError,match='ROUTE_INCOMPLETE'):
        validate(doc)
    first['route_status']='partial'
    validate(doc)
    project['sheets'][0]['junctions'].append({'id':'junction-X','net_id':first['id'],
         'at_um':[50000,30000],'layer_id':'layer-electric'})
    first['route_status']='verified'
    validate(doc)
    assert route_is_complete(project,first)


def test_v1_migration_keeps_1um_and_named_free_id():
    v1=strict_loads((FIX/'toy-v1.gscad.json').read_bytes())
    v2=migrate(v1)
    assert v2==toy()
    assert v2['project']['sheets'][0]['splices']==[]


def test_unknown_future_version_or_old_v2_wire_fail_closed():
    doc=toy()
    doc['project']['sheets'][0]['wires'][0]['vertices'][0]['endpoint'] = \
        doc['project']['sheets'][0]['wires'][0]['vertices'][0].pop('anchor')
    with pytest.raises(ContractError,match='SCHEMA_INVALID'):
        validate(doc)
    doc=toy()
    doc['format_version']=3
    with pytest.raises(ContractError,match='VERSION_UNSUPPORTED'):
        validate(doc)


def test_snapshot_cas_rejects_stale_source_and_preserves_original():
    from contract import History, source_inventory_hash
    history=History(toy())
    base=digest(history.current)
    source=source_inventory_hash(history.current['project'])
    candidate=copy.deepcopy(history.current)
    candidate['project']['components'][0]['value']='42k'
    with pytest.raises(ContractError,match='REVISION_CONFLICT'):
        history.commit_cas(candidate, expected_sha256='0'*64,
                           expected_generation=1,generation=1,
                           source_topology_hash=source)
    with pytest.raises(ContractError,match='REVISION_CONFLICT'):
        history.commit_cas(candidate, expected_sha256=base,
                           expected_generation=0,generation=1,
                           source_topology_hash=source)
    with pytest.raises(ContractError,match='SOURCE_TOPOLOGY_CONFLICT'):
        history.commit_cas(candidate, expected_sha256=base,
                           expected_generation=1,generation=1,
                           source_topology_hash='f'*64)
    assert digest(history.current)==base and not history.undo
    new_sha,generation=history.commit_cas(candidate,expected_sha256=base,
                                          expected_generation=1,generation=1,
                                          source_topology_hash=source)
    assert generation==2 and new_sha==digest(candidate)
    assert source_inventory_hash(history.current['project'])==source


def test_snapshot_cas_rejects_forged_source_net_member():
    from contract import History, source_inventory_hash
    history=History(toy())
    candidate=copy.deepcopy(history.current)
    candidate['project']['nets'][0]['name']='FORGED_SOURCE_NET_NAME'
    with pytest.raises(ContractError,match='SOURCE_TOPOLOGY_DRIFT'):
        history.commit_cas(candidate,expected_sha256=digest(history.current),
                           expected_generation=0,generation=0,
                           source_topology_hash=source_inventory_hash(history.current['project']))
    assert history.current==toy()
