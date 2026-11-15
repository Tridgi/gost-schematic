//! DRAFT Rust mapping for IPC sidecar; intentionally not compiled or vendor-locked.
//! Uses serde 1.x (MIT OR Apache-2.0), serde_json 1.x (MIT OR Apache-2.0).
//! Cross-reference validation requires an extra domain pass (not derive-only).
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PhysicalPin { pub number: String, pub name: String, pub electrical_type: String }
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PartDefinition { pub id:String, pub reference_prefix:String, pub symbol_ids:Vec<String>, pub physical_pins:Vec<PhysicalPin> }
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SymbolPin { pub physical_pin_number:String, pub at_um:[i64;2], pub side:String }
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SymbolInstance {
    pub id:String, pub component_id:String, pub symbol_id:String,
    pub origin_um:[i64;2], pub rotation_deg:i32, pub mirror_x:bool, pub layer_id:String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag="kind", rename_all="snake_case", deny_unknown_fields)]
pub enum WireEndpoint {
    Pin {component_id:String, physical_pin_number:String},
    Junction {junction_id:String},
    Splice {splice_id:String},
    Free {free_id:String},
    Bend {},
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WireVertex {pub id:String, pub at_um:[i64;2], pub anchor:WireEndpoint}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WireSegment {pub id:String,pub from_vertex_id:String,pub to_vertex_id:String}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WirePolyline {
    pub id:String,pub net_id:String,pub layer_id:String,pub vertices:Vec<WireVertex>,
    pub segments:Vec<WireSegment>,pub mode:String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PinRef {pub component_id:String,pub physical_pin_number:String}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Net {pub id:String,pub name:String,pub members:Vec<PinRef>,pub route_status:String}

pub fn pin_world(instance:&SymbolInstance, local:[i64;2])->Result<[i64;2], &'static str> {
    let (mut x, mut y)=(local[0],local[1]);
    if instance.mirror_x {x=x.checked_neg().ok_or("OVERFLOW")?;}
    (x,y)=match instance.rotation_deg {
        0=>(x,y), 90=>(y.checked_neg().ok_or("OVERFLOW")?,x),
        180=>(x.checked_neg().ok_or("OVERFLOW")?,y.checked_neg().ok_or("OVERFLOW")?),
        270=>(y,x.checked_neg().ok_or("OVERFLOW")?),
        _=>return Err("INVALID_ROTATION"),
    };
    Ok([instance.origin_um[0].checked_add(x).ok_or("OVERFLOW")?,
        instance.origin_um[1].checked_add(y).ok_or("OVERFLOW")?])
}
