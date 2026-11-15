import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from contract import (SCHEMA, ContractError, History, atomic_save, digest,
                      migrate, pin_world, serialize, strict_loads, validate)

ROOT = Path(__file__).resolve().parents[4]
FIX = ROOT / 'fixtures'


def read(path):
    return strict_loads((FIX / path).read_bytes())


def test_schema_self_validates():
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize('path',["minimal-v2.gscad.json","toy-v2.gscad.json","tl494-source-e695-v2.gscad.json","tl494-subset-e695-v2.gscad.json"])
def test_valid_project_and_exact_roundtrip(path):
    doc = read(path)
    assert validate(doc) == doc
    assert strict_loads(serialize(doc)) == doc
    assert digest(strict_loads(serialize(doc))) == digest(doc)


def test_source_locked_identity_and_b_graphics_not_wires():
    doc = validate(read('tl494-source-e695-v2.gscad.json'))
    p = doc['project']
    assert (len(p['components']),len(p['nets']),sum(len(n['members']) for n in p['nets']))==(23,15,62)
    assert len(next(x for x in p['part_definitions'] if x['id']=='reference.tl494cn')['physical_pins'])==16
    assert sum(len(x['wires']) for x in p['sheets']) == 0
    assert sum(g['source_role']=='source_b_continuation' for s in p['sheets'] for g in s['graphics'])==2
    assert set(n['name'] for n in p['nets']) >= {'a_INPUT_PLUS','b_NEGATIVE_OUTPUT','COMMON'}


@pytest.mark.parametrize('name,code',[
    ('fake-da1-pin','INVALID_PINREF'),
    ('false-cross-junction','JUNCTION_CROSSES_FOREIGN_NET'),
    ('part-symbol-mismatch','PART_SYMBOL_MISMATCH'),
    ('source-extra-net','PIN_MULTI_NET'),
    ('pin-offset-1um','PIN_ANCHOR_MISMATCH'),
])
def test_semantically_invalid_mutations(name,code):
    with pytest.raises(ContractError,match=code):
        validate(read('negative/'+name+'.gscad.json'))


def test_source_extra_net_reuses_pin_and_is_rejected():
    x=read('tl494-source-e695-v2.gscad.json')
    x['project']['nets'].append({'id':'extra','name':'EXTRA','route_status':'unrouted',
                                 'members':[{'component_id':x['project']['components'][0]['id'],
                                             'physical_pin_number':'2'}]})
    with pytest.raises(ContractError,match='PIN_MULTI_NET'):validate(x)


def test_frozen_source_substituting_members_with_same_counts_fails():
    x=read('tl494-source-e695-v2.gscad.json')
    a,b=x['project']['nets'][0]['members'][0],x['project']['nets'][1]['members'][0]
    x['project']['nets'][0]['members'][0],x['project']['nets'][1]['members'][0]=b,a
    with pytest.raises(ContractError,match='SOURCE_TOPOLOGY_DRIFT'):validate(x)


def test_v1_to_v2_migration_and_fail_closed():
    old=read('toy-v1.gscad.json')
    new=migrate(old)
    assert new==read('toy-v2.gscad.json')
    assert migrate(new)==new
    assert old['format_version']==1  # no in-place changes
    old['format_version']=19
    with pytest.raises(ContractError,match='VERSION_UNSUPPORTED'):migrate(old)


def test_1um_roundtrip_and_integer_transform_rotation_mirror():
    doc=read('toy-v2.gscad.json')
    doc=read('toy-v2.gscad.json')
    doc['project']['sheets'][0]['instances'][0]['origin_um'][1]+=1
    doc['project']['sheets'][0]['instances'][1]['origin_um'][1]+=1
    for v in doc['project']['sheets'][0]['wires'][0]['vertices']:v['at_um'][1]+=1
    serialized=serialize(doc)
    assert strict_loads(serialized)==doc
    assert doc['project']['sheets'][0]['instances'][0]['origin_um'][1]==30001
    instance={'origin_um':[123,456],'rotation_deg':90,'mirror_x':True}
    assert pin_world(instance,[1000,2000])==(-1877,-544)
    instance['rotation_deg']=270
    assert pin_world(instance,[1000,2000])==(2123,1456)


def test_grid_snap_toggle_does_not_touch_pins_or_nets():
    doc=read('toy-v2.gscad.json')
    before=copy.deepcopy(doc['project']['nets'])
    document=copy.deepcopy(doc)
    document['project']['settings']['grid_visible']=False
    document['project']['settings']['snap_enabled']=True
    assert validate(document)['project']['nets']==before


def test_refdes_rename_does_not_unbind_physical_pinref():
    doc=read('toy-v2.gscad.json')
    members=copy.deepcopy(doc['project']['nets'])
    old_id=doc['project']['components'][0]['id']
    doc['project']['components'][0]['refdes']='R77'
    assert validate(doc)['project']['nets']==members
    assert doc['project']['components'][0]['id']==old_id


def test_x_crossing_has_no_created_junction_or_net_merge():
    doc=read('toy-v2.gscad.json')
    wires=doc['project']['sheets'][0]['wires']
    assert len(wires)==2 and len(doc['project']['sheets'][0]['junctions'])==0
    assert wires[0]['net_id']!=wires[1]['net_id']
    assert validate(doc)


def test_move_rotate_requires_atomic_wire_reanchor():
    doc=read('toy-v2.gscad.json')
    doc['project']['sheets'][0]['instances'][0]['rotation_deg']=90
    with pytest.raises(ContractError,match='PIN_ANCHOR_MISMATCH'):validate(doc)
    # Reposition R1.2 wire endpoint to calculated rotated contact and create an orthogonal bend.
    w=doc['project']['sheets'][0]['wires'][0]
    p=pin_world(doc['project']['sheets'][0]['instances'][0],[10000,0])
    assert p==(10000,40000)
    w['vertices'][0]['at_um']=list(p)
    mid={'id':'vertex-added','at_um':[80000,40000],'anchor':{'kind':'bend'}}
    w['vertices'].insert(1,mid)
    w['segments']=[{'id':'seg-new-a','from_vertex_id':w['vertices'][0]['id'],'to_vertex_id':mid['id']},
                   {'id':'seg-new-b','from_vertex_id':mid['id'],'to_vertex_id':w['vertices'][2]['id']}]
    assert validate(doc)


def test_undo_redo_transaction_and_invalid_transaction_not_applied():
    history=History(read('toy-v2.gscad.json'))
    orig=digest(history.current)
    change=copy.deepcopy(history.current)
    change['project']['components'][0]['value']='15k'
    history.apply(change)
    changed=digest(history.current)
    assert changed!=orig
    history.revert()
    assert digest(history.current)==orig
    history.replay()
    assert digest(history.current)==changed
    bad=copy.deepcopy(history.current)
    bad['project']['sheets'][0]['instances'][0]['rotation_deg']=180
    with pytest.raises(ContractError):history.apply(bad)
    assert digest(history.current)==changed


def test_atomic_failed_save_preserves_previous(tmp_path):
    old=read('toy-v2.gscad.json')
    dest=tmp_path/'project.gscad.json'
    first_digest=atomic_save(dest,old)
    previous=dest.read_bytes()
    doc=copy.deepcopy(old)
    doc['project']['components'][0]['value']='20k'
    with pytest.raises(OSError,match='simulated write failure'):
        atomic_save(dest,doc,simulated_error=True)
    assert dest.read_bytes()==previous
    assert digest(strict_loads(dest.read_bytes()))==first_digest
    assert not list(tmp_path.glob('.gscad-*.tmp'))


def test_hash_excludes_workspace_volatile_view_but_not_engineering_changes():
    doc=read('toy-v2.gscad.json')
    base=digest(doc)
    doc['workspace']['zoom_milli']=1600
    doc['workspace']['panels_px']['right']=550
    assert digest(doc)==base
    doc['project']['components'][0]['value']='2.3k'
    assert digest(doc)!=base


def test_duplicate_json_keys_and_noninteger_are_forbidden():
    with pytest.raises(ContractError,match='JSON_DUPLICATE_KEY'):
        strict_loads('{"a":1,"a":2}')
    with pytest.raises(ContractError,match='JSON_NON_INTEGER'):
        strict_loads('{"x":1.001}')


def test_invalid_int_and_wrong_version_rejected():
    doc=read('toy-v2.gscad.json')
    doc['format_version']=3
    with pytest.raises(ContractError,match='VERSION_UNSUPPORTED'):validate(doc)
    doc['format_version']=2
    doc['project']['sheets'][0]['instances'][0]['origin_um'][0]=1.5
    with pytest.raises(ContractError,match='SCHEMA_INVALID'):validate(doc)


def test_source_excerpt_and_refdes_rename_keep_source_frozen_identity():
    doc=read('tl494-source-e695-v2.gscad.json')
    pin_before=copy.deepcopy(doc['project']['nets'])
    da1=next(x for x in doc['project']['components'] if x['source_refdes']=='DA1')
    assert da1['refdes']=='DA1'
    da1['refdes']='DD99'
    assert validate(doc)['project']['nets']==pin_before
    excerpt=read('tl494-subset-e695-v2.gscad.json')
    validate(excerpt)
    assert (len(excerpt['project']['components']),len(excerpt['project']['nets']),
            sum(len(n['members']) for n in excerpt['project']['nets']))==(3,3,12)
    assert excerpt['project']['provenance']['status']=='source_excerpt_unapproved'


def test_verified_route_cannot_be_claimed_if_wire_removed():
    doc=read('toy-v2.gscad.json')
    assert all(n['route_status']=='verified' for n in doc['project']['nets'])
    assert validate(doc)
    doc['project']['sheets'][0]['wires'].pop()
    with pytest.raises(ContractError,match='ROUTE_INCOMPLETE'):validate(doc)
    doc['project']['nets'][1]['route_status']='unrouted'
    assert validate(doc)


def test_explicit_junction_good_at_T_on_same_net():
    doc=read('toy-v2.gscad.json')
    sh=doc['project']['sheets'][0]
    wire=copy.deepcopy(sh['wires'][0])
    wire['id']='branch-new'
    wire['vertices']=[{'id':'tap','at_um':[40000,30000],
                       'anchor':{'kind':'junction','junction_id':'junction-new'}},
                      {'id':'dangling','at_um':[40000,50000],
                       'anchor':{'kind':'free','free_id':'new-branch-free-end'}}]
    wire['segments']=[{'id':'branch-seg','from_vertex_id':'tap','to_vertex_id':'dangling'}]
    sh['wires'].append(wire)
    sh['junctions'].append({'id':'junction-new','net_id':wire['net_id'],
                            'at_um':[40000,30000],'layer_id':'layer-electric'})
    assert validate(doc)
    assert len(sh['junctions'])==1


def test_autosave_recovery_and_revision_conflict(tmp_path):
    from contract import write_autosave,recover_autosave
    base=read('toy-v2.gscad.json')
    changed=copy.deepcopy(base)
    changed['project']['components'][0]['value']='10k'
    path=tmp_path/'.project.gscad.autosave'
    candidate=write_autosave(path,changed,base_sha256=digest(base))
    assert digest(recover_autosave(path,base_document=base))==candidate
    base_different=copy.deepcopy(base)
    base_different['project']['components'][1]['value']='33n'
    with pytest.raises(ContractError,match='AUTOSAVE_BASE_CONFLICT'):
        recover_autosave(path,base_document=base_different)
    record=json.loads(path.read_text())
    record['candidate_sha256']='f'*64
    path.write_text(json.dumps(record))
    with pytest.raises(ContractError,match='AUTOSAVE_CORRUPT'):
        recover_autosave(path,base_document=base)


def test_project_unknown_fields_fail_closed():
    doc=read('toy-v2.gscad.json')
    doc['project']['mysterious_future_feature']='implicit-net-by-pixel'
    with pytest.raises(ContractError,match='SCHEMA_INVALID'):validate(doc)


def test_python_node_canonical_hash_match():
    import shutil
    import subprocess
    node=shutil.which('node')
    if node is None:pytest.skip('Node.js not installed; TS runtime contract smoke unavailable')
    path=FIX/'tl494-source-e695-v2.gscad.json'
    expected=digest(read(path.name))
    actual=subprocess.check_output([node,str(ROOT/'editor/src/model/verify_hash.mjs'),str(path)],text=True).strip()
    assert actual==expected


def test_schema_rejects_boolean_coordinates_and_unknown_pin_endpoints():
    doc=read('toy-v2.gscad.json')
    doc['project']['sheets'][0]['instances'][0]['origin_um'][0]=True
    with pytest.raises(ContractError,match='SCHEMA_INVALID'):validate(doc)
    doc=read('toy-v2.gscad.json')
    doc['project']['sheets'][0]['wires'][0]['vertices'][0]['anchor']={'kind':'pin','component_id':'x','physical_pin_number':'2','guessed_by_pixel':True}
    with pytest.raises(ContractError,match='SCHEMA_INVALID'):validate(doc)
