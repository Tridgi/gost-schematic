//! Native update boundary. Public metadata alone cannot authorize an install.
use base64::{engine::general_purpose::STANDARD, Engine};
use serde::Serialize;
use serde_json::Value;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_updater::{Update, UpdaterExt};
use uuid::Uuid;

const FEED: &str = "https://github.com/Tridgi/gost-schematic/releases/latest/download/latest.json";
const MAX_INSTALLER_BYTES: usize = 1024 * 1024 * 1024;

fn stable_version(version: &str) -> Option<(u64, u64, u64)> {
    let parts: Vec<_> = version.split('.').collect();
    if parts.len() != 3 || parts.iter().any(|p| p.is_empty()
        || !p.bytes().all(|b| b.is_ascii_digit())
        || (p.len() > 1 && p.starts_with('0'))) {
        return None;
    }
    Some((parts[0].parse().ok()?, parts[1].parse().ok()?, parts[2].parse().ok()?))
}

fn asset_url(version: &str) -> Option<String> {
    stable_version(version)?;
    Some(format!("https://github.com/Tridgi/gost-schematic/releases/download/v{version}/schematik-{version}-x64-setup.exe"))
}

fn secure_policy(config: &Value) -> bool {
    let public_key_ok = config.get("pubkey").and_then(Value::as_str)
        .and_then(|key| STANDARD.decode(key.trim()).ok())
        .and_then(|bytes| String::from_utf8(bytes).ok())
        .is_some_and(|text| {
            let lines: Vec<_> = text.lines().collect();
            lines.len() == 2 && lines[0].starts_with("untrusted comment:")
                && STANDARD.decode(lines[1]).is_ok_and(|key| key.len() == 42 && &key[..2] == b"Ed")
        });
    public_key_ok
        && config.get("requireSignedVersion").and_then(Value::as_bool) == Some(true)
        && config.get("allowDowngrades").and_then(Value::as_bool) == Some(false)
        && config.get("endpoints") == Some(&serde_json::json!([FEED]))
        && ["dangerousInsecureTransportProtocol", "dangerousAcceptInvalidCerts",
            "dangerousAcceptInvalidHostnames", "dangerous-insecure-transport-protocol",
            "dangerous-accept-invalid-certs", "dangerous-accept-invalid-hostnames",
            "allow-downgrades"].iter().all(|key| config.get(key).is_none_or(|v| v.as_bool() == Some(false)))
        && config.get("require-signed-version").is_none()
}

pub fn configured(app: &AppHandle) -> bool {
    cfg!(all(target_os = "windows", target_arch = "x86_64"))
        && app.config().plugins.0.get("updater").is_some_and(secure_policy)
        && !app.config().bundle.windows.allow_downgrades
}

// A lease prevents installer launch while a native file picker, save, open,
// export or close is active, and prevents new file operations during install.
#[derive(Default)]
struct OperationState {
    files: usize,
    installing: bool,
}
#[derive(Default)]
pub struct OperationGate(Arc<Mutex<OperationState>>);
pub struct OperationLease {
    gate: Arc<Mutex<OperationState>>,
    install: bool,
}
impl OperationGate {
    fn acquire(&self, install: bool) -> Result<OperationLease, String> {
        let mut state = self.0.lock().map_err(|_| "UPDATE_OPERATION_LOCK_FAILED")?;
        if state.installing || (install && state.files != 0) {
            return Err("NATIVE_FILE_OR_UPDATE_BUSY".into());
        }
        if install { state.installing = true; }
        else { state.files = state.files.checked_add(1).ok_or("NATIVE_FILE_BUSY")?; }
        Ok(OperationLease { gate: self.0.clone(), install })
    }
    pub fn file(&self) -> Result<OperationLease, String> { self.acquire(false) }
    fn install(&self) -> Result<OperationLease, String> { self.acquire(true) }
}
impl Drop for OperationLease {
    fn drop(&mut self) {
        if let Ok(mut state) = self.gate.lock() {
            if self.install { state.installing = false; }
            else { state.files = state.files.saturating_sub(1); }
        }
    }
}

struct Prepared { update: Update, bytes: Vec<u8>, token: String }
#[derive(Default)]
enum Stage {
    #[default]
    Idle,
    Downloading { received: u64, total: Option<u64> },
    Ready(Prepared),
    Installing,
}
#[derive(Default)]
pub struct UpdateStore(Mutex<Stage>);

#[derive(Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum UpdateStatus {
    Idle,
    Downloading { received: u64, total: Option<u64> },
    Ready { version: String, token: String },
    Installing,
}

#[tauri::command]
pub fn native_signed_update_enabled(app: AppHandle) -> bool {
    configured(&app)
}

#[tauri::command]
pub fn native_signed_update_status(state: State<'_, UpdateStore>) -> Result<UpdateStatus, String> {
    let stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
    Ok(match &*stage {
        Stage::Idle => UpdateStatus::Idle,
        Stage::Downloading { received, total } => UpdateStatus::Downloading { received: *received, total: *total },
        Stage::Ready(prepared) => UpdateStatus::Ready { version: prepared.update.version.clone(), token: prepared.token.clone() },
        Stage::Installing => UpdateStatus::Installing,
    })
}

#[tauri::command]
pub async fn native_prepare_signed_update(
    app: AppHandle, state: State<'_, UpdateStore>, version: String,
) -> Result<(), String> {
    if !configured(&app) { return Err("SIGNED_UPDATE_NOT_CONFIGURED".into()); }
    let current = stable_version(&app.package_info().version.to_string()).ok_or("INVALID_APP_VERSION")?;
    if stable_version(&version).is_none_or(|v| v <= current) {
        return Err("UPDATE_VERSION_NOT_NEWER".into());
    }
    {
        let mut stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
        if !matches!(&*stage, Stage::Idle) { return Err("UPDATE_BUSY_OR_PREPARED".into()); }
        *stage = Stage::Downloading { received: 0, total: None };
    }
    let result = async {
        let updater = app.updater_builder()
            .timeout(Duration::from_secs(300))
            .build().map_err(|_| "UPDATE_CONFIGURATION_FAILED")?;
        let update = updater.check().await.map_err(|_| "UPDATE_CHECK_FAILED")?
            .ok_or("NO_SIGNED_UPDATE")?;
        if update.version != version || asset_url(&version).as_deref() != Some(update.download_url.as_str()) {
            return Err("UPDATE_MANIFEST_MISMATCH");
        }
        let bytes = update.download(|chunk, total| {
            if let Ok(mut stage) = state.0.lock() {
                if let Stage::Downloading { received, total: current_total } = &mut *stage {
                    *received = received.saturating_add(chunk as u64);
                    *current_total = total;
                }
            }
        }, || {}).await.map_err(|_| "UPDATE_DOWNLOAD_OR_SIGNATURE_FAILED")?;
        if bytes.is_empty() || bytes.len() > MAX_INSTALLER_BYTES { return Err("UPDATE_SIZE_REJECTED"); }
        update.verify(&bytes).map_err(|_| "UPDATE_SIGNATURE_FAILED")?;
        Ok(Prepared { update, bytes, token: Uuid::new_v4().simple().to_string() })
    }.await;
    let mut stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
    match result {
        Ok(prepared) => { *stage = Stage::Ready(prepared); Ok(()) }
        Err(error) => { *stage = Stage::Idle; Err(error.into()) }
    }
}

#[tauri::command]
pub fn native_discard_signed_update(state: State<'_, UpdateStore>) -> Result<(), String> {
    let mut stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
    if matches!(&*stage, Stage::Downloading { .. } | Stage::Installing) {
        return Err("UPDATE_BUSY".into());
    }
    *stage = Stage::Idle;
    Ok(())
}

#[tauri::command]
pub async fn native_install_signed_update(
    app: AppHandle, state: State<'_, UpdateStore>, token: String, project_safe: bool,
) -> Result<(), String> {
    if !configured(&app) { return Err("SIGNED_UPDATE_NOT_CONFIGURED".into()); }
    // Frontend must confirm a clean, saved project immediately before invoking.
    if !project_safe { return Err("SAVE_PROJECT_BEFORE_UPDATE".into()); }
    let _lease = app.state::<OperationGate>().install()?;
    let prepared = {
        let mut stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
        if !matches!(&*stage, Stage::Ready(p) if p.token == token) {
            return Err("STALE_UPDATE_TOKEN".into());
        }
        match std::mem::replace(&mut *stage, Stage::Installing) {
            Stage::Ready(prepared) => prepared,
            _ => unreachable!(),
        }
    };
    // Update::install verifies the signature and signed version again before
    // starting NSIS; on success Windows exits and restarts the application.
    let result = prepared.update.install(&prepared.bytes).map_err(|_| "UPDATE_INSTALL_FAILED".to_string());
    if let Ok(mut stage) = state.0.lock() { *stage = Stage::Idle; }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_release_asset_and_stable_version() {
        assert_eq!(stable_version("0.10.0"), Some((0,10,0)));
        assert_eq!(asset_url("0.2.0").unwrap(), "https://github.com/Tridgi/gost-schematic/releases/download/v0.2.0/schematik-0.2.0-x64-setup.exe");
        for bad in ["v0.2.0", "0.2.0-rc.1", "00.2.0", "../0.2.0", "0.2.0/evil", "999999999999999999999.0.0"] {
            assert!(asset_url(bad).is_none());
        }
    }
    #[test]
    fn missing_key_or_unsafe_policy_disables_update() {
        assert!(!secure_policy(&serde_json::json!({})));
        let mut policy = serde_json::json!({"pubkey":"", "endpoints":[FEED], "requireSignedVersion":true, "allowDowngrades":false});
        assert!(!secure_policy(&policy));
        // Structural test key only, not a production verification identity.
        let mut key = vec![0u8; 42]; key[..2].copy_from_slice(b"Ed");
        policy["pubkey"] = Value::String(STANDARD.encode(format!("untrusted comment: test only\n{}", STANDARD.encode(key))));
        assert!(secure_policy(&policy));
        for (field, value) in [("allowDowngrades", Value::Bool(true)), ("requireSignedVersion", Value::Bool(false)), ("dangerousAcceptInvalidCerts", Value::Bool(true)), ("endpoints", serde_json::json!(["https://example.invalid"]))] {
            let mut bad = policy.clone(); bad[field] = value;
            assert!(!secure_policy(&bad));
        }
    }
    #[test]
    fn installation_and_file_operations_are_mutually_exclusive() {
        let gate = OperationGate::default();
        let file1 = gate.file().unwrap(); let file2 = gate.file().unwrap();
        assert!(gate.install().is_err()); drop(file1); assert!(gate.install().is_err()); drop(file2);
        let install = gate.install().unwrap(); assert!(gate.file().is_err()); assert!(gate.install().is_err());
        drop(install); assert!(gate.file().is_ok());
    }
}
