//! R4 native file capability boundary. Only OS picker-selected PathBufs reach disk IO.
//! Every open and save crosses the real Python ProjectV2 strict validation IPC.
//! No user-controlled process paths, arbitrary FS API or shell arguments are exposed.
use crate::{internal_engine_request, BridgeState, EngineRequest};
use serde::Serialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::DialogExt;
use uuid::Uuid;

const MAX_PROJECT_BYTES: usize = 850_000;
const FROZEN_E695: &str = "e695c415fdced164b0e0c39c5249d030795a0aa6";

#[derive(Clone)]
struct NativeDocument {
    path: PathBuf,
    project_id: String,
    source_sha: String,
    source_status: String,
    source_path: String,
    topology_sha256: String,
    project_sha256: String,
    disk_sha256: String,
    generation: u64,
    busy: bool,
}

#[derive(Default)]
pub struct NativeFileStore {
    files: Mutex<HashMap<String, NativeDocument>>,
}

#[derive(Serialize)]
pub struct NativeProjectReply {
    handle: String,
    generation: u64,
    project_sha256: String,
    document: Value,
    filename: String,
}

#[derive(Clone)]
struct Canonical {
    document: Value,
    project_id: String,
    project_sha256: String,
    source_sha: String,
    source_status: String,
    source_path: String,
    topology_sha256: String,
}

fn sha(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn trusted_file(path: &Path) -> Result<(), String> {
    // File paths originate exclusively in native dialogs, never JS or NDJSON.
    // Enforce the expected extension and refuse links/directories as extra guards.
    let name = path.file_name().ok_or("INVALID_NATIVE_FILENAME")?.to_string_lossy();
    if !name.to_ascii_lowercase().ends_with(".json") {
        return Err("INVALID_PROJECT_EXTENSION".into());
    }
    if let Ok(meta) = fs::symlink_metadata(path) {
        if meta.file_type().is_symlink() || !meta.is_file() {
            return Err("UNSAFE_PROJECT_FILE".into());
        }
    }
    Ok(())
}
fn get_string<'a>(obj: &'a Value, key: &str) -> Result<&'a str, String> {
    obj.get(key).and_then(Value::as_str).ok_or_else(|| format!("MISSING_CANONICAL_{key}"))
}
async fn canonicalize(app: &AppHandle, blob: String) -> Result<Canonical, String> {
    if blob.len() > MAX_PROJECT_BYTES {
        return Err("NATIVE_PROJECT_TOO_LARGE".into());
    }
    // JS can supply a DOCUMENT, never a pathname. The Python fixed-file
    // source/schema import refuses duplicate JSON members and malformed PinRef.
    let request = EngineRequest {
        v: 1, id: format!("native_{}", Uuid::new_v4().simple()),
        op: "parse_document_blob".into(), args: json!({"blob": blob}),
    };
    let response = internal_engine_request(app.clone(), app.state::<BridgeState>(), request).await?;
    if response.get("ok").and_then(Value::as_bool) != Some(true) {
        return Err(response.get("error").and_then(|x| x.get("code"))
            .and_then(Value::as_str).unwrap_or("PYTHON_MODEL_REJECTED").to_owned());
    }
    let r = response.get("result").ok_or("BAD_PYTHON_VALIDATION_RESPONSE")?;
    let document = r.get("document").cloned().ok_or("MISSING_VALIDATED_DOCUMENT")?;
    Ok(Canonical {
        document,
        project_id: get_string(r, "project_id")?.to_owned(),
        project_sha256: get_string(r, "project_sha256")?.to_owned(),
        topology_sha256: get_string(r, "source_topology_sha256")?.to_owned(),
        source_sha: get_string(r, "source_sha")?.to_owned(),
        source_status: get_string(r, "provenance_status")?.to_owned(),
        source_path: get_string(r, "source_path")?.to_owned(),
    })
}
fn source_safe(prior: &NativeDocument, next: &Canonical) -> Result<(), String> {
    if next.project_id != prior.project_id ||
        next.source_sha != prior.source_sha ||
        next.source_status != prior.source_status ||
        next.source_path != prior.source_path {
        return Err("SOURCE_OR_PROJECT_MISMATCH".into());
    }
    if prior.source_status != "synthetic" && next.topology_sha256 != prior.topology_sha256 {
        return Err("SOURCE_TOPOLOGY_CHANGED".into());
    }
    if prior.source_status == "synthetic" && next.source_sha == FROZEN_E695 {
        return Err("SYNTHETIC_SOURCE_SPOOF".into());
    }
    Ok(())
}
fn serialize_document(value: &Value) -> Result<Vec<u8>, String> {
    let mut bytes = serde_json::to_vec_pretty(value).map_err(|_| "SERIALIZE_FAILED")?;
    bytes.push(b'\n');
    if bytes.len() > MAX_PROJECT_BYTES {
        return Err("NATIVE_PROJECT_TOO_LARGE".into());
    }
    Ok(bytes)
}
fn read_disk(path: &Path) -> Result<Vec<u8>, String> {
    trusted_file(path)?;
    let metadata = fs::metadata(path).map_err(|_| "PROJECT_READ_DENIED")?;
    if metadata.len() > MAX_PROJECT_BYTES as u64 {
        return Err("NATIVE_PROJECT_TOO_LARGE".into());
    }
    let content = fs::read(path).map_err(|_| "PROJECT_READ_DENIED")?;
    if content.len() > MAX_PROJECT_BYTES {
        return Err("NATIVE_PROJECT_TOO_LARGE".into());
    }
    Ok(content)
}
fn write_temp(path: &Path, bytes: &[u8]) -> Result<PathBuf, String> {
    let parent = path.parent().ok_or("INVALID_PROJECT_PARENT")?;
    let temp = parent.join(format!(".gscad-{}.tmp", Uuid::new_v4()));
    let mut out = OpenOptions::new().create_new(true).write(true)
        .open(&temp).map_err(|_| "TEMP_CREATE_DENIED")?;
    if let Err(_) = out.write_all(bytes).and_then(|_| out.sync_all()) {
        drop(out);
        let _ = fs::remove_file(&temp);
        return Err("ATOMIC_WRITE_FAILED".into());
    }
    Ok(temp)
}
fn commit_replace(temp: &Path, target: &Path) -> Result<(), String> {
    #[cfg(windows)] {
        use std::os::windows::ffi::OsStrExt;
        use windows_sys::Win32::Storage::FileSystem::{
            MoveFileExW, MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH
        };
        let src: Vec<u16> = temp.as_os_str().encode_wide().chain(Some(0)).collect();
        let dst: Vec<u16> = target.as_os_str().encode_wide().chain(Some(0)).collect();
        let ok = unsafe {
            MoveFileExW(src.as_ptr(), dst.as_ptr(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)
        };
        if ok == 0 { return Err("ATOMIC_REPLACE_DENIED".into()); }
    }
    #[cfg(not(windows))]
    fs::rename(temp, target).map_err(|_| "ATOMIC_REPLACE_DENIED")?;
    Ok(())
}
fn atomic_save(path: &Path, bytes: &[u8], expected_disk_sha256: Option<&str>) -> Result<String, String> {
    trusted_file(path)?;
    if let Some(expected) = expected_disk_sha256 {
        let existing = read_disk(path)?;
        if sha(&existing) != expected { return Err("EXTERNAL_FILE_CHANGED".into()); }
    } else if path.exists() {
        return Err("SAVE_AS_TARGET_EXISTS".into());
    }
    let temp = write_temp(path, bytes)?;
    let result = if expected_disk_sha256.is_some() {
        // Recheck once more immediately before replacement. The pending file
        // is on the same filesystem; Windows MoveFileExW replaces atomically.
        let guard = expected_disk_sha256.unwrap();
        match read_disk(path) {
            Ok(old) if sha(&old) == guard => commit_replace(&temp, path),
            _ => Err("EXTERNAL_FILE_CHANGED".into()),
        }
    } else {
        // A hard link makes a new destination visible atomically and refuses
        // even a concurrent target creation. Both paths share one parent/volume.
        fs::hard_link(&temp, path).map_err(|_| "SAVE_AS_TARGET_EXISTS".into())
    };
    let _ = fs::remove_file(&temp);
    result?;
    Ok(sha(bytes))
}
fn display_name(path: &Path) -> String {
    path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| "project.json".into())
}
fn reply(handle: String, state: &NativeDocument, document: Value) -> NativeProjectReply {
    NativeProjectReply {
        handle, generation: state.generation,
        project_sha256: state.project_sha256.clone(),
        filename: display_name(&state.path), document,
    }
}
#[tauri::command]
pub async fn native_open_project(app: AppHandle) -> Result<NativeProjectReply, String> {
    let file = app.dialog().file().add_filter("GSCAD ProjectV2", &["json"])
        .blocking_pick_file().ok_or("CANCELLED")?;
    let path = file.into_path().map_err(|_| "UNSUPPORTED_NATIVE_PATH")?;
    let bytes = read_disk(&path)?;
    let blob = String::from_utf8(bytes.clone()).map_err(|_| "INVALID_UTF8")?;
    let validated = canonicalize(&app, blob).await?;
    let doc = NativeDocument {
        path, project_id: validated.project_id, source_sha: validated.source_sha,
        source_status: validated.source_status, source_path: validated.source_path,
        topology_sha256: validated.topology_sha256,
        project_sha256: validated.project_sha256, disk_sha256: sha(&bytes),
        generation: 0, busy: false,
    };
    let handle = Uuid::new_v4().to_string();
    let response = reply(handle.clone(), &doc, validated.document);
    app.state::<NativeFileStore>().files.lock().map_err(|_| "FILE_LOCK_FAILED")?
        .insert(handle, doc);
    Ok(response)
}
#[tauri::command]
pub async fn native_save_project(app: AppHandle, handle: String,
    expected_generation: u64, expected_project_sha256: String,
    document: Value) -> Result<NativeProjectReply, String> {
    // Reserve this handle while Python validates and the OS write completes.
    let previous = {
        let state = app.state::<NativeFileStore>();
        let mut map = state.files.lock().map_err(|_| "FILE_LOCK_FAILED")?;
        let session = map.get_mut(&handle).ok_or("UNKNOWN_DOCUMENT_HANDLE")?;
        if session.busy { return Err("SESSION_BUSY".into()); }
        if session.generation != expected_generation ||
           session.project_sha256 != expected_project_sha256 {
            return Err("STALE_DOCUMENT_CAS".into());
        }
        session.busy = true;
        session.clone()
    };
    let result = async {
        let raw = serde_json::to_string(&document).map_err(|_| "INVALID_JSON")?;
        let validated = canonicalize(&app, raw).await?;
        source_safe(&previous, &validated)?;
        let content = serialize_document(&validated.document)?;
        let file_sha = atomic_save(&previous.path, &content, Some(&previous.disk_sha256))?;
        Ok::<_, String>((validated, file_sha))
    }.await;
    let state = app.state::<NativeFileStore>();
    let mut map = state.files.lock().map_err(|_| "FILE_LOCK_FAILED")?;
    let entry = map.get_mut(&handle).ok_or("UNKNOWN_DOCUMENT_HANDLE")?;
    entry.busy = false;
    match result {
        Ok((validated, file_sha)) => {
            entry.disk_sha256 = file_sha;
            entry.project_sha256 = validated.project_sha256;
            entry.topology_sha256 = validated.topology_sha256;
            entry.generation += 1;
            Ok(reply(handle, entry, validated.document))
        }
        Err(e) => Err(e),
    }
}
#[tauri::command]
pub async fn native_save_as_project(app: AppHandle, document: Value,
    previous_handle: Option<String>,
    expected_generation: Option<u64>, expected_project_sha256: Option<String>
) -> Result<NativeProjectReply, String> {
    // No JS pathname accepted. Save picker is the only authority for destination.
    let selected = app.dialog().file().add_filter("GSCAD ProjectV2", &["json"])
        .blocking_save_file().ok_or("CANCELLED")?;
    let path = selected.into_path().map_err(|_| "UNSUPPORTED_NATIVE_PATH")?;
    let raw = serde_json::to_string(&document).map_err(|_| "INVALID_JSON")?;
    let validated = canonicalize(&app, raw).await?;
    if let Some(handle) = previous_handle.as_ref() {
        let state = app.state::<NativeFileStore>();
        let map = state.files.lock().map_err(|_| "FILE_LOCK_FAILED")?;
        let old = map.get(handle).ok_or("UNKNOWN_DOCUMENT_HANDLE")?;
        if old.busy || Some(old.generation) != expected_generation ||
           Some(old.project_sha256.as_str()) != expected_project_sha256.as_deref() {
            return Err("STALE_DOCUMENT_CAS".into());
        }
        source_safe(old, &validated)?;
    } else if validated.source_status == "synthetic" && validated.source_sha == FROZEN_E695 {
        return Err("SYNTHETIC_SOURCE_SPOOF".into());
    }
    let content = serialize_document(&validated.document)?;
    let file_sha = atomic_save(&path, &content, None)?;
    let native = NativeDocument {
        path, project_id: validated.project_id, source_sha: validated.source_sha,
        source_status: validated.source_status, source_path: validated.source_path,
        topology_sha256: validated.topology_sha256,
        project_sha256: validated.project_sha256,
        disk_sha256: file_sha, generation: 0, busy: false,
    };
    let handle = Uuid::new_v4().to_string();
    let response = reply(handle.clone(), &native, validated.document);
    app.state::<NativeFileStore>().files.lock().map_err(|_| "FILE_LOCK_FAILED")?
        .insert(handle,native);
    Ok(response)
}
#[tauri::command]
pub fn native_close_project(app: AppHandle, handle: String) -> Result<(), String> {
    let state = app.state::<NativeFileStore>();
    let mut map = state.files.lock().map_err(|_| "FILE_LOCK_FAILED")?;
    if map.get(&handle).is_some_and(|s| s.busy) { return Err("SESSION_BUSY".into()); }
    map.remove(&handle);
    Ok(())
}
/// Explicit engineering PREVIEW export through the existing canonical Python
/// source exporter. Returned bytes are verified and written only to an
/// OS-picked destination. This never labels DRAFT font geometry as GOST print.
#[tauri::command]
pub async fn native_export_project(
    app: AppHandle, document: Value, sheet_id: String, format: String
) -> Result<String, String> {
    if !matches!(format.as_str(), "svg" | "png300") ||
        sheet_id.is_empty() || sheet_id.len()>256 {
        return Err("INVALID_EXPORT_ARGS".into());
    }
    let request = EngineRequest {
        v: 1, id: format!("native_{}", Uuid::new_v4().simple()),
        op: "native_export_preview".into(),
        args: json!({"document":document,"sheet_id":sheet_id,"format":format})
    };
    let response = internal_engine_request(app.clone(),app.state::<BridgeState>(),request).await?;
    if response.get("ok").and_then(Value::as_bool)!=Some(true) {
        return Err(response.get("error").and_then(|e|e.get("code"))
            .and_then(Value::as_str).unwrap_or("PYTHON_EXPORT_REJECTED").into());
    }
    let output = response.get("result").ok_or("MALFORMED_PYTHON_EXPORT")?;
    if get_string(output,"approval")? != "NOT_ESKD_CERTIFIED" ||
       get_string(output,"format")? != format {
        return Err("UNTRUSTED_EXPORT_METADATA".into());
    }
    use base64::{engine::general_purpose::STANDARD,Engine as _};
    let bytes=STANDARD.decode(get_string(output,"payload")?)
        .map_err(|_|"INVALID_EXPORT_BASE64")?;
    if bytes.len()>2_600_000 || sha(&bytes)!=get_string(output,"payload_sha256")? {
        return Err("CORRUPT_EXPORT_BYTES".into());
    }
    if format=="png300" && !bytes.starts_with(&[137,80,78,71,13,10,26,10]) {
        return Err("NOT_PNG".into());
    }
    if format=="svg" && !bytes.starts_with(b"<?xml") && !bytes.starts_with(b"<svg") {
        return Err("NOT_SVG".into());
    }
    let ext=if format=="svg" {"svg"} else {"png"};
    let selected=app.dialog().file().add_filter("GSCAD engineering PREVIEW", &[ext])
        .blocking_save_file().ok_or("CANCELLED")?;
    let path=selected.into_path().map_err(|_|"UNSUPPORTED_NATIVE_PATH")?;
    if path.extension().and_then(|e|e.to_str())!=Some(ext) {
        return Err("INVALID_EXPORT_EXTENSION".into());
    }
    if path.exists() {return Err("EXPORT_TARGET_EXISTS".into());}
    let temp=write_temp(&path,&bytes)?;
    let result: Result<(), String> = fs::hard_link(&temp,&path)
        .map_err(|_| "EXPORT_TARGET_EXISTS".to_string());
    let _=fs::remove_file(&temp);
    result?;
    Ok(display_name(&path))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn filename_extension_guard() {
        assert!(trusted_file(Path::new("test.gscad.json")).is_ok());
        assert!(trusted_file(Path::new("test.exe")).is_err());
        assert!(trusted_file(Path::new("")).is_err());
    }

    #[test]
    fn windows_atomic_disk_save_as_cas_and_external_change_are_fail_closed() {
        // Isolated disposable path, never a user's document.
        let dir = std::env::temp_dir().join(format!("gscad-native-test-{}", Uuid::new_v4()));
        fs::create_dir(&dir).unwrap();
        let file = dir.join("engineering-test.gscad.json");
        let first = b"{\"project\":1}\n";
        let second = b"{\"project\":2}\n";
        let first_sha = atomic_save(&file, first, None).unwrap();
        assert_eq!(first_sha, sha(first));
        assert_eq!(fs::read(&file).unwrap(), first);
        // Save As never overwrites even a valid pre-existing JSON file.
        assert_eq!(atomic_save(&file, second, None).unwrap_err(), "SAVE_AS_TARGET_EXISTS");
        assert_eq!(fs::read(&file).unwrap(), first);
        // External modification or stale disk hash must abort without changing bytes.
        assert_eq!(
            atomic_save(&file, second, Some(&"f".repeat(64))).unwrap_err(),
            "EXTERNAL_FILE_CHANGED"
        );
        assert_eq!(fs::read(&file).unwrap(), first);
        let second_sha = atomic_save(&file, second, Some(&first_sha)).unwrap();
        assert_eq!(second_sha, sha(second));
        assert_eq!(fs::read(&file).unwrap(), second);
        assert_eq!(
            atomic_save(&file, first, Some(&first_sha)).unwrap_err(),
            "EXTERNAL_FILE_CHANGED"
        );
        assert_eq!(fs::read(&file).unwrap(), second);
        fs::remove_file(file).unwrap();
        fs::remove_dir(dir).unwrap();
    }

    #[test]
    fn source_guard_allows_user_authored_nets_but_refuses_different_project_or_frozen_source() {
        let base = NativeDocument {
            path: PathBuf::from("user.json"), project_id: "project-1".into(),
            source_sha: "0".repeat(40), source_status: "synthetic".into(),
            source_path: "user-created/project-1".into(), topology_sha256: "a".repeat(64),
            project_sha256: "b".repeat(64), disk_sha256: "c".repeat(64),
            generation: 1, busy: false,
        };
        let mut changed = Canonical {
            document: json!({}), project_id: "project-1".into(),
            project_sha256: "d".repeat(64), topology_sha256: "f".repeat(64),
            source_sha: "0".repeat(40), source_status: "synthetic".into(),
            source_path: "user-created/project-1".into(),
        };
        assert!(source_safe(&base, &changed).is_ok());
        changed.project_id = "project-2".into();
        assert_eq!(source_safe(&base, &changed).unwrap_err(), "SOURCE_OR_PROJECT_MISMATCH");
        changed.project_id = "project-1".into();
        changed.source_sha = FROZEN_E695.into();
        assert_eq!(source_safe(&base, &changed).unwrap_err(), "SOURCE_OR_PROJECT_MISMATCH");
        let source = NativeDocument {
            source_sha: FROZEN_E695.into(),
            source_status: "source_traced_unapproved".into(),
            source_path: "frozen-e695.json".into(),
            ..base
        };
        changed.source_sha = FROZEN_E695.into();
        changed.source_status = "source_traced_unapproved".into();
        changed.source_path = "frozen-e695.json".into();
        assert_eq!(source_safe(&source, &changed).unwrap_err(), "SOURCE_TOPOLOGY_CHANGED");
    }
    #[test]
    fn strict_source_identity_refuses_e695_downgrade() {
        let old = NativeDocument {
            path: PathBuf::from("a.json"),project_id:"p".into(),
            source_sha:FROZEN_E695.into(),source_status:"source_traced_unapproved".into(),
            source_path:"source".into(),topology_sha256:"a".repeat(64),
            project_sha256:"b".repeat(64),disk_sha256:"c".repeat(64),
            generation:0,busy:false
        };
        let attempt = Canonical {
            document:json!({}),project_id:"p".into(),project_sha256:"b".repeat(64),
            source_sha:FROZEN_E695.into(),source_status:"synthetic".into(),
            source_path:"source".into(),topology_sha256:"a".repeat(64),
        };
        assert!(source_safe(&old,&attempt).is_err());
    }
}
