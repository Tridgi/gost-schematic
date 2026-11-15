"""Generate strict draft-2020-12 schema and reproducible provenance fixtures."""
import copy
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT
S = ROOT.parent / 'contracts'

def string(min_len=1): return {'type':'string','minLength':min_len,'maxLength':256}
def integer(low=-1_000_000_000,high=1_000_000_000): return {'type':'integer','minimum':low,'maximum':high}
def obj(properties, required=None, *, additional=False):
    return {'type':'object','additionalProperties':additional,'properties':properties,'required':list(properties) if required is None else required}
def arr(items, min_items=0): return {'type':'array','items':items,'minItems':min_items}
def ref(name): return {'$ref':'#/$defs/'+name}
uid=string(); point={'type':'array','prefixItems':[integer(),integer()],'items':False,'minItems':2,'maxItems':2}
physical_pin=obj({'number':uid,'name':string(0),'electrical_type':{'enum':['passive','input','output','bidirectional','power_input','power_output','open_collector','unspecified']}})
symbol_pin=obj({'physical_pin_number':uid,'at_um':ref('point_um'),'side':{'enum':['left','right','top','bottom']}})
part=obj({'id':uid,'reference_prefix':uid,'symbol_ids':arr(uid,1),'physical_pins':arr(physical_pin,1)})
primitive=obj({'kind':{'enum':['line','rect','polyline']},'points_um':arr(ref('point_um'),2),'stroke_um':integer(1,100_000)})
symbol=obj({'id':uid,'part_id':uid,'revision':integer(1,10**6),'status':{'enum':['draft','approved','deprecated']},'pins':arr(symbol_pin,1),'graphics':arr(primitive,1),'standard_refs':arr(string(0))})
component=obj({'id':uid,'refdes':uid,'source_refdes':uid,'part_id':uid,'value':string(0)})
pinref=obj({'component_id':uid,'physical_pin_number':uid})
net=obj({'id':uid,'name':uid,'members':arr(ref('pin_ref'),1),'route_status':{'enum':['unrouted','partial','verified']}})
layer=obj({'id':uid,'name':uid,'kind':{'enum':['electrical','annotation','drawing','diagnostics']},'visible':{'type':'boolean'},'printable':{'type':'boolean'},'locked':{'type':'boolean'}})
instance=obj({'id':uid,'component_id':uid,'symbol_id':uid,'origin_um':ref('point_um'),'rotation_deg':{'enum':[0,90,180,270]},'mirror_x':{'type':'boolean'},'layer_id':uid})
endpoint={ 'oneOf':[
    obj({'kind':{'const':'pin'},'component_id':uid,'physical_pin_number':uid}),
    obj({'kind':{'const':'junction'},'junction_id':uid}),
    obj({'kind':{'const':'splice'},'splice_id':uid}),
    obj({'kind':{'const':'free'},'free_id':uid}),
    obj({'kind':{'const':'bend'}}),
] }
vertex=obj({'id':uid,'at_um':ref('point_um'),'anchor':ref('wire_endpoint')})
segment=obj({'id':uid,'from_vertex_id':uid,'to_vertex_id':uid})
wire=obj({'id':uid,'net_id':uid,'layer_id':uid,'vertices':arr(ref('vertex'),2),'segments':arr(ref('wire_segment'),1),'mode':{'const':'orthogonal'},'needs_routing_review':{'type':'boolean'}}, required=['id','net_id','layer_id','vertices','segments','mode'])
junction=obj({'id':uid,'net_id':uid,'at_um':ref('point_um'),'layer_id':uid})
text=obj({'id':uid,'layer_id':uid,'text':string(0),'at_um':ref('point_um'),'rotation_deg':{'enum':[0,90,180,270]},'height_um':integer(1,100_000)})
label=obj({'id':uid,'layer_id':uid,'text':uid,'at_um':ref('point_um'),'role':{'enum':['visual','net_annotation']},'net_id':{'anyOf':[uid,{'type':'null'}]}})
graphic=obj({'id':uid,'layer_id':uid,'kind':{'enum':['line','polyline','source_b_continuation']},'points_um':arr(ref('point_um'),2),'stroke_um':integer(1,100_000)})
frame=obj({'size_um':ref('point_um'),'margin_um':integer(0,100_000),'paper':uid})
title=obj({'designation':string(0),'title':string(0),'organization':string(0),'revision':string(0),'sheet_number':integer(1,10000)})
sheet=obj({'id':uid,'name':uid,'index':integer(1,10000),'frame':ref('sheet_frame'),'title_block':ref('title_block'),'layers':arr(ref('layer'),1),'instances':arr(ref('symbol_instance')),'wires':arr(ref('wire_polyline')),'junctions':arr(ref('junction')),'splices':arr(ref('splice')),'texts':arr(ref('text')),'labels':arr(ref('label')),'graphics':arr(ref('graphic'))})
settings=obj({'units':{'const':'um'},'grid_visible':{'type':'boolean'},'snap_enabled':{'type':'boolean'},'grid_step_um':integer(1,1_000_000),'orthogonal_wires':{'type':'boolean'}})
source=obj({'source_sha':{'type':'string','pattern':'^[a-f0-9]{40}$'},'source_path':uid,'status':{'enum':['source_traced_unapproved','source_excerpt_unapproved','synthetic']},'expected_counts':obj({'components':integer(0,1_000_000),'nets':integer(0,1_000_000),'memberships':integer(0,1_000_000),'da1_pins':integer(0,1000),'b_graphics':integer(0,1000)})})
project=obj({'id':uid,'title':uid,'part_definitions':arr(ref('part_definition')),'symbol_definitions':arr(ref('symbol_definition')),'components':arr(ref('component')),'nets':arr(ref('net')),'sheets':arr(ref('sheet'),1),'settings':ref('settings'),'provenance':ref('provenance')})
workspace=obj({'active_sheet_id':uid,'camera_center_um':ref('point_um'),'zoom_milli':integer(50,100_000),'selected_ids':arr(uid),'panels_px':obj({'left':integer(100,2000),'right':integer(100,2000),'bottom':integer(0,1000)})})
operation=obj({'kind':{'enum':['replace_entity','add_entity','remove_entity']},'entity_type':{'enum':['component','instance','wire','junction','splice','text','label','graphic','net']},'entity_id':uid,'before':{'type':['object','null']},'after':{'type':['object','null']}})
transaction=obj({'id':uid,'base_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'generation':integer(0,10**12),'source_topology_hash':{'type':'string','pattern':'^[a-f0-9]{64}$'},'commands':arr(ref('history_command'),1)})

definitions={'point_um':point,'physical_pin':physical_pin,'symbol_pin':symbol_pin,'part_definition':part,'graphic_primitive':primitive,'symbol_definition':symbol,'component':component,'pin_ref':pinref,'net':net,'layer':layer,'symbol_instance':instance,'wire_endpoint':endpoint,'vertex':vertex,'wire_segment':segment,'wire_polyline':wire,'junction':junction,'splice':junction,'text':text,'label':label,'graphic':graphic,'sheet_frame':frame,'title_block':title,'sheet':sheet,'settings':settings,'provenance':source,'project':project,'workspace':workspace,'history_command':operation,'history_transaction':transaction}
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:gscad:experimental:visual-cad-chat6:project-v2','title':'GOST Schematic CAD project v2 (experimental contract)','$comment':'Schema verifies structure; contract.py verifies cross-references, physical pins, wire graph and provenance.','type':'object','additionalProperties':False,'required':['format','format_version','project','workspace'],'properties':{'format':{'const':'gscad-project'},'format_version':{'const':2},'project':ref('project'),'workspace':ref('workspace')},'$defs':definitions}
S.mkdir(exist_ok=True)
(S/'project-v2.schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')

def stable(kind,name): return str(uuid.uuid5(uuid.NAMESPACE_URL,'gscad-chat6:'+kind+':'+name))
L=[dict(id='layer-electric',name='Electrical',kind='electrical',visible=True,printable=True,locked=False),dict(id='layer-draw',name='Drawing',kind='drawing',visible=True,printable=True,locked=False),dict(id='layer-debug',name='Diagnostics',kind='diagnostics',visible=False,printable=False,locked=True)]
def sheet(name='Sheet 1'):
    return {'id':'sheet-1','name':name,'index':1,'frame':{'size_um':[420000,297000],'margin_um':10000,'paper':'A3 landscape'},'title_block':{'designation':'GSCAD-CHAT6','title':name,'organization':'R&D','revision':'DRAFT','sheet_number':1},'layers':copy.deepcopy(L),'instances':[],'wires':[],'junctions':[],'splices':[],'texts':[],'labels':[],'graphics':[]}
def physical(n,electrical='passive'):
    return {'number':str(n),'name':str(n),'electrical_type':electrical}
def pin(n,xy,side): return {'physical_pin_number':str(n),'at_um':xy,'side':side}
def library(part_id,numbers):
    if len(numbers)==16:
        pn=[pin(n,([-8000 if i<8 else 68000, (i%8+1)*10000]),'left' if i<8 else 'right') for i,n in enumerate(numbers)]
        graphics=[{'kind':'rect','points_um':[[0,0],[60000,92000]],'stroke_um':300}]
    elif len(numbers)==3:
        pn=[pin(numbers[0],[-10000,0],'left'),pin(numbers[1],[10000,0],'right'),pin(numbers[2],[0,10000],'bottom')]
        graphics=[{'kind':'rect','points_um':[[-4000,-2000],[4000,2000]],'stroke_um':300}]
    else:
        pn=[pin(numbers[0],[-10000,0],'left'),pin(numbers[1],[10000,0],'right')]
        graphics=[{'kind':'rect','points_um':[[-4000,-2000],[4000,2000]],'stroke_um':300}]
    s_id='symbol/'+part_id
    part={'id':part_id,'reference_prefix':part_id.split('.')[0].upper(),'symbol_ids':[s_id],'physical_pins':[physical(n) for n in numbers]}
    if part_id=='reference.tl494cn':
        for x in part['physical_pins']:
            if x['number']=='3':x.update({'name':'FEEDBACK','electrical_type':'input'})
            if x['number']=='13':x.update({'name':'OUTPUT CTRL','electrical_type':'input'})
    symbol={'id':s_id,'part_id':part_id,'revision':1,'status':'draft','pins':pn,'graphics':graphics,'standard_refs':['DRAFT: source-inspired CAD data shape, not approved ESKD UGO']}
    return part,symbol

def project(title,prov):
    return {'format':'gscad-project','format_version':2,'project':{'id':stable('project',title),'title':title,'part_definitions':[],'symbol_definitions':[],'components':[],'nets':[],'sheets':[sheet(title)],'settings':{'units':'um','grid_visible':True,'snap_enabled':False,'grid_step_um':1000,'orthogonal_wires':True},'provenance':prov},'workspace':{'active_sheet_id':'sheet-1','camera_center_um':[0,0],'zoom_milli':1000,'selected_ids':[],'panels_px':{'left':280,'right':320,'bottom':160}}}

def add_def(doc,part_id,numbers):
    p,s=library(part_id,numbers)
    if p['id'] not in {x['id'] for x in doc['project']['part_definitions']}:
        doc['project']['part_definitions'].append(p);doc['project']['symbol_definitions'].append(s)

def add_component(doc,refdes,part_id,x,y):
    cid=stable('component',refdes)
    doc['project']['components'].append({'id':cid,'refdes':refdes,'source_refdes':refdes,'part_id':part_id,'value':''})
    doc['project']['sheets'][0]['instances'].append({'id':stable('instance',refdes),'component_id':cid,'symbol_id':'symbol/'+part_id,'origin_um':[x,y],'rotation_deg':0,'mirror_x':False,'layer_id':'layer-electric'})
    return cid

def net(doc,name,members,route='unrouted'):
    byref={x['refdes']:x['id'] for x in doc['project']['components']}
    doc['project']['nets'].append({'id':stable('net',name),'name':name,'members':[{'component_id':byref[ref],'physical_pin_number':str(pin)} for ref,pin in members],'route_status':route})

def wire(doc,name,p1,p2,points,refs=None):
    endpoints=refs or [{'kind':'free','free_id':stable('free',name+':start')},{'kind':'free','free_id':stable('free',name+':end')}]
    vids=[stable('vertex',name+str(i)) for i in range(len(points))]
    vertices=[{'id':v,'at_um':pt,'anchor':endpoints[0] if i==0 else endpoints[-1] if i==len(points)-1 else {'kind':'bend'}} for i,(v,pt) in enumerate(zip(vids,points))]
    segments=[{'id':stable('segment',name+str(i)),'from_vertex_id':vids[i],'to_vertex_id':vids[i+1]} for i in range(len(vids)-1)]
    doc['project']['sheets'][0]['wires'].append({'id':stable('wire',name),'net_id':stable('net',name),'layer_id':'layer-electric','vertices':vertices,'segments':segments,'mode':'orthogonal'})

def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

toy=project('Toy two nets crossing',{'source_sha':'0'*40,'source_path':'fixtures/synthetic','status':'synthetic','expected_counts':{'components':4,'nets':2,'memberships':4,'da1_pins':0,'b_graphics':0}})
add_def(toy,'resistor.fixed',['1','2']);add_def(toy,'capacitor.fixed',['1','2'])
ids={}
for refdes,part,x,y in [('R1','resistor.fixed',10000,30000),('C1','capacitor.fixed',90000,30000),('R2','resistor.fixed',50000,10000),('C2','capacitor.fixed',50000,90000)]:ids[refdes]=add_component(toy,refdes,part,x,y)
net(toy,'N_HORIZONTAL',[('R1','2'),('C1','1')],'verified');net(toy,'N_VERTICAL',[('R2','2'),('C2','1')],'verified')
wire(toy,'N_HORIZONTAL','R1','C1',[[20000,30000],[80000,30000]],[{'kind':'pin','component_id':ids['R1'],'physical_pin_number':'2'},{'kind':'pin','component_id':ids['C1'],'physical_pin_number':'1'}]);wire(toy,'N_VERTICAL','R2','C2',[[60000,10000],[50000,10000],[50000,90000],[40000,90000]],[{'kind':'pin','component_id':ids['R2'],'physical_pin_number':'2'},{'kind':'pin','component_id':ids['C2'],'physical_pin_number':'1'}])
# Both wires reach actual physical pins; X crossing has no junction and stays electrically distinct.
toy['project']['sheets'][0]['texts'].append({'id':'text-title','layer_id':'layer-draw','text':'Two networks; X is not a junction','at_um':[22000,12000],'rotation_deg':0,'height_um':3500})
save('toy-v2.gscad.json',toy)
minimal=project('Empty schematic project',{'source_sha':'0'*40,'source_path':'fixtures/synthetic','status':'synthetic','expected_counts':{'components':0,'nets':0,'memberships':0,'da1_pins':0,'b_graphics':0}})
minimal['project']['sheets'][0]['layers']=[L[0]]
save('minimal-v2.gscad.json',minimal)
v1=copy.deepcopy(toy);v1['format_version']=1;del v1['workspace']
for sh in v1['project']['sheets']:
    del sh['splices']
    for wire_obj in sh['wires']:
        for vertex in wire_obj['vertices']:
            a=vertex.pop('anchor')
            if a['kind']=='free':a={'kind':'free'}
            vertex['endpoint']=a
save('toy-v1.gscad.json',v1)

# Transcribed from source-locked examples/tl494_full_native_model.py, e695c415fdced164b0e0c39c5249d030795a0aa6.
source_sha='e695c415fdced164b0e0c39c5249d030795a0aa6'
spec={**{f'C{x}':'capacitor.polarized' for x in [1,2,3,5,6]},'C4':'capacitor.fixed','C7':'capacitor.fixed',**{f'R{x}':'resistor.fixed' for x in [1,2,3,4,6,7,8]},'R5':'resistor.variable','VT1':'transistor.mosfet_n_enh','VD1':'diode.schottky','L1':'inductor.ferromagnetic','L2':'inductor.ferromagnetic','FU1':'fuse.general','X1':'reference.connector.x1','X2':'reference.connector.x2','DA1':'reference.tl494cn'}
traced={
 'a_INPUT_PLUS':[('X1','1'),('L1','1'),('DA1','12'),('DA1','8'),('DA1','11')],
 'COMMON':[('X1','2'),('X2','2'),('VT1','3'),('VD1','2'),('C5','1'),('C6','1'),('DA1','7'),('DA1','1'),('DA1','16'),('DA1','13'),('R6','2'),('R7','2'),('R8','2'),('C7','2')],
 'SWITCH':[('L1','2'),('VT1','2'),('C1','1'),('C2','1')],
 'TRANSFER':[('C1','2'),('C2','2'),('VD1','1'),('L2','1')],
 'OUT_BEFORE_FUSE':[('L2','2'),('FU1','1'),('C5','2'),('C6','2')],
 'b_NEGATIVE_OUTPUT':[('FU1','2'),('X2','1'),('R5','2')],
 'CONTROL_REFERENCE':[('DA1','14'),('DA1','15'),('R1','1'),('R2','1'),('C3','1')],
 'SOFT_START':[('DA1','4'),('R1','2'),('C3','2'),('R6','1')],
 'ERROR_INPUT':[('DA1','2'),('R2','2'),('R4','1'),('C4','1')],
 'RC_CORRECTION':[('C4','2'),('R3','1')],
 'FEEDBACK':[('R3','2'),('DA1','3')],
 'ADJUSTED_DIVIDER':[('R4','2'),('R5','1'),('R5','3')],
 'OSCILLATOR_CT':[('C7','1'),('DA1','5')],
 'OSCILLATOR_RT':[('R7','1'),('DA1','6')],
 'GATE_DRIVE':[('DA1','9'),('DA1','10'),('R8','1'),('VT1','1')],
}
all_numbers={'reference.tl494cn':[str(i) for i in range(1,17)],'resistor.variable':['1','2','3'],'transistor.mosfet_n_enh':['1','2','3']}
target=project('TL494 source E695 inventory, unrouted',{'source_sha':source_sha,'source_path':'examples/tl494_full_native_model.py','status':'source_traced_unapproved','expected_counts':{'components':23,'nets':15,'memberships':62,'da1_pins':16,'b_graphics':2}})
for index,(r,p) in enumerate(spec.items()):
    add_def(target,p,all_numbers.get(p,['1','2']));add_component(target,r,p,(index%6)*68000+20000,(index//6)*56000+18000)
for n,members in traced.items():net(target,n,members)
for idx,x in enumerate([5000,8000]):
    target['project']['sheets'][0]['graphics'].append({'id':'source-b-graphic-'+str(idx+1),'layer_id':'layer-draw','kind':'source_b_continuation','points_um':[[x,280000],[x+2000,280000]],'stroke_um':300})
target['project']['sheets'][0]['labels'].append({'id':'label-source-b','layer_id':'layer-draw','text':'b','at_um':[10500,280000],'role':'visual','net_id':None})
save('tl494-source-e695-v2.gscad.json',target)
# Source excerpt preserves literal original membership for the retained components,
# but *does not* claim the complete source: 3 components, 3 partial source nets.
excerpt=copy.deepcopy(target)
keep={'X1','L1','DA1'}
excerpt['project']['title']='TL494 E695 source excerpt (not full circuit)'
excerpt['project']['components']=[c for c in excerpt['project']['components'] if c['source_refdes'] in keep]
keep_ids={c['id'] for c in excerpt['project']['components']}
excerpt['project']['sheets'][0]['instances']=[x for x in excerpt['project']['sheets'][0]['instances'] if x['component_id'] in keep_ids]
excerpt['project']['nets']=[{**n,'members':[m for m in n['members'] if m['component_id'] in keep_ids]}
                           for n in excerpt['project']['nets'] if n['name'] in {'a_INPUT_PLUS','COMMON','CONTROL_REFERENCE'}]
excerpt['project']['part_definitions']=[p for p in excerpt['project']['part_definitions'] if p['id'] in {'reference.connector.x1','inductor.ferromagnetic','reference.tl494cn'}]
excerpt['project']['symbol_definitions']=[p for p in excerpt['project']['symbol_definitions'] if p['part_id'] in {'reference.connector.x1','inductor.ferromagnetic','reference.tl494cn'}]
excerpt['project']['provenance']['status']='source_excerpt_unapproved'
excerpt['project']['provenance']['expected_counts']={'components':3,'nets':3,'memberships':12,'da1_pins':16,'b_graphics':2}
save('tl494-subset-e695-v2.gscad.json',excerpt)
assert len(spec)==23 and len(traced)==15 and sum(map(len,traced.values()))==62
# Mutations all structurally well-typed (semantic gate must reject).
negatives={}
a=copy.deepcopy(target);a['project']['nets'][0]['members'].append({'component_id':next(x['id'] for x in a['project']['components'] if x['refdes']=='DA1'),'physical_pin_number':'17'});negatives['fake-da1-pin']=a
b=copy.deepcopy(toy);b['project']['sheets'][0]['junctions'].append({'id':'false-cross','net_id':stable('net','N_HORIZONTAL'),'at_um':[50000,30000],'layer_id':'layer-electric'});negatives['false-cross-junction']=b
c=copy.deepcopy(toy);c['project']['sheets'][0]['instances'][0]['symbol_id']='symbol/capacitor.fixed';negatives['part-symbol-mismatch']=c
d=copy.deepcopy(target);d['project']['nets'].append({'id':'extra-net','name':'FABRICATED','members':[copy.deepcopy(d['project']['nets'][0]['members'][0])],'route_status':'unrouted'});negatives['source-extra-net']=d
e=copy.deepcopy(toy);e['project']['sheets'][0]['wires'][0]['vertices'][0]['at_um'][0]+=1;negatives['pin-offset-1um']=e
for n,d in negatives.items():save('negative/'+n+'.gscad.json',d)
print('generated schema and',2+1+1+len(negatives),'fixtures; source:',len(spec),len(traced),sum(map(len,traced.values())))
