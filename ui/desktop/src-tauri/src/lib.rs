//! Isolated Windows desktop bridge: allowlisted Rust commands, packaged Python sidecar.
//! NOTE: not compiled in this sandbox; Windows/CI native smoke remains a release gate.
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Mutex;
use std::time::Duration;
use tauri::State;
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};

const REQUEST_LIMIT: usize = 1_048_576;
const RESPONSE_LIMIT: usize = 4_194_304;

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct EngineRequest {
    v: u8,
    id: String,
    op: String,
    args: Value,
}

#[derive(Default)]
struct BridgeState {
    // None = cancellation killed the process, request ID still reserved until
    // original invoke finishes (so an old cleanup cannot kill a reused ID).
    active: Mutex<HashMap<String, Option<CommandChild>>>,
}

fn safe_id(id: &str) -> bool {
    (1..=64).contains(&id.len())
        && id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}

fn allowlisted(op: &str) -> bool {
    matches!(op, "hello" | "unit_roundtrip" | "check_symbol" | "render_symbol" | "validate_document" | "source_snapshot" | "verify_net" | "wire_snapshot" | "validate_wire_candidate" | "engine_projection")
}

#[tauri::command]
async fn engine_request(
    app: tauri::AppHandle,
    state: State<'_, BridgeState>,
    request: EngineRequest,
) -> Result<Value, String> {
    if request.v != 1 || !safe_id(&request.id) || !allowlisted(&request.op) || !request.args.is_object() {
        return Err("UNSUPPORTED_OR_UNSAFE_REQUEST".into());
    }
    let mut data = serde_json::to_vec(&request).map_err(|_| "INVALID_JSON")?;
    if data.len() + 1 > REQUEST_LIMIT {
        return Err("PAYLOAD_TOO_LARGE".into());
    }
    data.push(b'\n');

    // Fixed packaged program; no user-controlled executable path, shell, args or files.
    let cmd = app.shell().sidecar("engine-bridge").map_err(|_| "SIDECAR_NOT_PACKAGED")?
        .set_process_group(true).kill_on_drop(true);
    let (mut rx, mut child) = cmd.spawn().map_err(|_| "ENGINE_SPAWN_FAILED")?;
    if child.write(&data).is_err() {
        let _ = child.kill();
        return Err("ENGINE_WRITE_FAILED".into());
    }
    {
        let mut jobs = state.active.lock().map_err(|_| "BRIDGE_LOCK_FAILED")?;
        if jobs.contains_key(&request.id) {
            let _ = child.kill();
            return Err("DUPLICATE_REQUEST_ID".into());
        }
        jobs.insert(request.id.clone(), Some(child));
    }

    let result = tokio::time::timeout(Duration::from_secs(15), async {
        while let Some(event) = rx.recv().await {
            match event {
                // tauri-plugin-shell emits line-delimited Stdout events stripped of newline.
                CommandEvent::Stdout(bytes) => {
                    if bytes.len() > RESPONSE_LIMIT {
                        return Err("RESPONSE_TOO_LARGE".into());
                    }
                    let reply: Value = serde_json::from_slice(&bytes)
                        .map_err(|_| "MALFORMED_ENGINE_RESPONSE")?;
                    if reply.get("v").and_then(Value::as_u64) != Some(1)
                        || reply.get("id").and_then(Value::as_str) != Some(request.id.as_str())
                        || !reply.get("ok").is_some_and(Value::is_boolean) {
                        return Err("CORRUPT_ENGINE_ENVELOPE".into());
                    }
                    return Ok(reply);
                }
                // Stderr stays local diagnostic; never leak logs/user paths to JS.
                CommandEvent::Error(_) => return Err("ENGINE_IO_ERROR".into()),
                CommandEvent::Terminated(_) => return Err("ENGINE_TERMINATED".into()),
                _ => {}
            }
        }
        Err("ENGINE_STREAM_CLOSED".into())
    }).await.unwrap_or(Err("ENGINE_TIMEOUT".into()));

    if let Ok(mut jobs) = state.active.lock() {
        if let Some(Some(child)) = jobs.remove(&request.id) {
            let _ = child.kill();
        }
    }
    result
}

#[tauri::command]
fn cancel_engine_request(state: State<'_, BridgeState>, id: String) -> Result<bool, String> {
    if !safe_id(&id) {
        return Err("INVALID_ID".into());
    }
    let mut jobs = state.active.lock().map_err(|_| "BRIDGE_LOCK_FAILED")?;
    if let Some(slot) = jobs.get_mut(&id) {
        if let Some(child) = slot.take() {
            let _ = child.kill();
            return Ok(true);
        }
    }
    Ok(false)
}

pub fn run() {
    tauri::Builder::default()
        .manage(BridgeState::default())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![engine_request, cancel_engine_request])
        .run(tauri::generate_context!())
        .expect("cannot start GOST CAD desktop IPC shell");
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unsafe_ids_rejected() {
        assert!(safe_id("wire_004"));
        for bad in ["", "../../", "a/b", "a b", "ü", "a:1"] {
            assert!(!safe_id(bad));
        }
    }
    #[test]
    fn app_never_allows_js_arbitrary_process() {
        for bad in ["shell", "exec", "position_edit", "export_png", "render_svg"] {
            assert!(!allowlisted(bad));
        }
    }
}
