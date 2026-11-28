//! Native update boundary. Public metadata alone cannot authorize an install.
use base64::{engine::general_purpose::STANDARD, Engine};
use serde::Serialize;
use serde_json::Value;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_updater::{Update, UpdaterExt};
use uuid::Uuid;
use tokio::sync::oneshot;
use reqwest::{redirect, Url};

const FEED: &str = "https://github.com/Tridgi/gost-schematic/releases/latest/download/latest.json";
const MAX_INSTALLER_BYTES: usize = 1024 * 1024 * 1024;
const MAX_MANIFEST_BYTES: usize = 64 * 1024;
const MAX_SIGNATURE_TEXT_BYTES: usize = 16 * 1024;
const UPDATE_TARGET: &str = "windows-x86_64";

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
                && STANDARD.decode(lines[1]).is_ok_and(|key| key.len() == 42 && &key[..2] == b"Ed" && key[10..].iter().any(|b| *b != 0))
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
    Downloading { received: u64, total: Option<u64>, id: String, cancel: Option<oneshot::Sender<()>> },
    Ready(Prepared),
    Installing,
}
#[derive(Default)]
pub struct UpdateStore(Mutex<Stage>);

#[derive(Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum UpdateStatus {
    Idle,
    Downloading { received: u64, total: Option<u64>, id: String, cancelling: bool },
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
        Stage::Downloading { received, total, id, cancel } => UpdateStatus::Downloading { received: *received, total: *total, id: id.clone(), cancelling: cancel.is_none() },
        Stage::Ready(prepared) => UpdateStatus::Ready { version: prepared.update.version.clone(), token: prepared.token.clone() },
        Stage::Installing => UpdateStatus::Installing,
    })
}

// GitHub Releases can redirect to a dedicated asset CDN. Never follow an
// HTTP, credential-bearing, nonstandard-port or unrelated-host redirect.
fn trusted_download_url(url: &Url) -> bool {
    url.scheme() == "https" && url.port_or_known_default() == Some(443)
        && url.username().is_empty() && url.password().is_none()
        && url.fragment().is_none()
        && match url.host_str() {
            Some("github.com") => url.path().starts_with("/Tridgi/gost-schematic/releases/"),
            Some("release-assets.githubusercontent.com" | "objects.githubusercontent.com") => true,
            _ => false,
        }
}
fn release_redirect_policy() -> redirect::Policy {
    redirect::Policy::custom(|attempt| {
        if attempt.previous().len() >= 8 || !trusted_download_url(attempt.url()) {
            attempt.error("UNTRUSTED_UPDATE_REDIRECT")
        } else { attempt.follow() }
    })
}

// Limit actual bytes, including chunked/unknown-length HTTP responses. The
// previous plugin download buffered the entire response before the size check.
fn append_bounded(buffer: &mut Vec<u8>, chunk: &[u8], limit: usize) -> Result<(), &'static str> {
    let next = buffer.len().checked_add(chunk.len()).filter(|n| *n <= limit)
        .ok_or("UPDATE_SIZE_REJECTED")?;
    if next > buffer.capacity() {
        let target = buffer.capacity().saturating_mul(2).max(next).min(limit);
        buffer.try_reserve_exact(target - buffer.len()).map_err(|_| "UPDATE_MEMORY_LIMIT")?;
    }
    buffer.extend_from_slice(chunk);
    Ok(())
}
fn validate_release_metadata(raw: &[u8], version: &str) -> Result<Value, &'static str> {
    if raw.is_empty() || raw.len() > MAX_MANIFEST_BYTES { return Err("UPDATE_METADATA_SIZE_REJECTED"); }
    let json: Value = serde_json::from_slice(raw).map_err(|_| "UPDATE_METADATA_INVALID")?;
    if stable_version(version).is_none() || json.get("version").and_then(Value::as_str) != Some(version) {
        return Err("UPDATE_MANIFEST_MISMATCH");
    }
    // Require the fixed platform entry emitted by our signed release staging.
    // Other platform entries, dynamic top-level URL/signature and mismatched
    // URLs cannot override the expected installer.
    let entry = json.get("platforms").and_then(|p| p.get(UPDATE_TARGET))
        .ok_or("UPDATE_MANIFEST_MISMATCH")?;
    if json.get("url").is_some() || json.get("signature").is_some()
        || entry.get("url").and_then(Value::as_str) != asset_url(version).as_deref() {
        return Err("UPDATE_MANIFEST_MISMATCH");
    }
    let signature = entry.get("signature").and_then(Value::as_str)
        .filter(|s| !s.is_empty() && s.len() <= MAX_SIGNATURE_TEXT_BYTES)
        .ok_or("UPDATE_METADATA_INVALID")?;
    if STANDARD.decode(signature).is_err() { return Err("UPDATE_METADATA_INVALID"); }
    Ok(json)
}

// Use the same TLS provider as the pinned Tauri updater. Its check() installs
// the provider internally, but we deliberately replace its unbounded JSON read.
fn update_client(timeout: Duration) -> Result<reqwest::Client, &'static str> {
    if rustls::crypto::CryptoProvider::get_default().is_none() {
        let _ = rustls::crypto::ring::default_provider().install_default();
    }
    reqwest::Client::builder().https_only(true)
        .redirect(release_redirect_policy()).timeout(timeout)
        .connect_timeout(Duration::from_secs(15))
        .user_agent("GOST-Schematic-Updater")
        .build().map_err(|_| "UPDATE_CLIENT_FAILED")
}

async fn fetch_release_metadata(version: &str) -> Result<Value, &'static str> {
    let client = update_client(Duration::from_secs(20))?;
    let mut response = client.get(FEED)
        .header(reqwest::header::ACCEPT, "application/json")
        .header(reqwest::header::ACCEPT_ENCODING, "identity")
        .send().await.map_err(|_| "UPDATE_CHECK_FAILED")?;
    if !trusted_download_url(response.url()) { return Err("UPDATE_HTTP_REJECTED"); }
    if response.status() == reqwest::StatusCode::NO_CONTENT { return Err("NO_SIGNED_UPDATE"); }
    if response.status() != reqwest::StatusCode::OK { return Err("UPDATE_HTTP_REJECTED"); }
    let length = response.content_length();
    if length.is_some_and(|n| n == 0 || n > MAX_MANIFEST_BYTES as u64) {
        return Err("UPDATE_METADATA_SIZE_REJECTED");
    }
    let mut body = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| "UPDATE_CHECK_FAILED")? {
        append_bounded(&mut body, &chunk, MAX_MANIFEST_BYTES)
            .map_err(|_| "UPDATE_METADATA_SIZE_REJECTED")?;
    }
    if length.is_some_and(|n| n != body.len() as u64) { return Err("UPDATE_LENGTH_MISMATCH"); }
    validate_release_metadata(&body, version)
}

async fn download_bounded(update: &Update, state: &UpdateStore) -> Result<Vec<u8>, &'static str> {
    if !trusted_download_url(&update.download_url) { return Err("UPDATE_MANIFEST_MISMATCH"); }
    let client = update_client(Duration::from_secs(300))?;
    let mut response = client.get(update.download_url.clone())
        .header(reqwest::header::ACCEPT, "application/octet-stream")
        .header(reqwest::header::ACCEPT_ENCODING, "identity")
        .send().await.map_err(|_| "UPDATE_DOWNLOAD_FAILED")?;
    if response.status() != reqwest::StatusCode::OK || !trusted_download_url(response.url()) {
        return Err("UPDATE_HTTP_REJECTED");
    }
    let length = response.content_length();
    if length.is_some_and(|n| n == 0 || n > MAX_INSTALLER_BYTES as u64) {
        return Err("UPDATE_SIZE_REJECTED");
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| "UPDATE_DOWNLOAD_FAILED")? {
        append_bounded(&mut bytes, &chunk, MAX_INSTALLER_BYTES)?;
        let mut stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
        if let Stage::Downloading { received, total, cancel, .. } = &mut *stage {
            if cancel.is_none() { return Err("UPDATE_DOWNLOAD_CANCELLED"); }
            *received = bytes.len() as u64;
            *total = length;
        } else { return Err("UPDATE_DOWNLOAD_CANCELLED"); }
    }
    if bytes.is_empty() || length.is_some_and(|n| n != bytes.len() as u64) {
        return Err("UPDATE_LENGTH_MISMATCH");
    }
    // Official Tauri 2.14.1 checks the actual bytes and signed version here
    // and again inside install(). No alternative unsigned installation.
    update.verify(&bytes).map_err(|_| "UPDATE_SIGNATURE_FAILED")?;
    Ok(bytes)
}

#[tauri::command]
pub fn native_cancel_signed_download(state: State<'_, UpdateStore>, id: String) -> Result<(), String> {
    cancel_download(&state, &id)
}
fn cancel_download(state: &UpdateStore, id: &str) -> Result<(), String> {
    let mut stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
    match &mut *stage {
        Stage::Downloading { id: active, cancel, .. } if active.as_str() == id => {
            if let Some(sender) = cancel.take() { let _ = sender.send(()); }
            Ok(())
        }
        _ => Err("STALE_UPDATE_DOWNLOAD".into()),
    }
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
    let (cancel, mut cancelled) = oneshot::channel();
    {
        let mut stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
        if !matches!(&*stage, Stage::Idle) { return Err("UPDATE_BUSY_OR_PREPARED".into()); }
        *stage = Stage::Downloading { received: 0, total: None, id: Uuid::new_v4().simple().to_string(), cancel: Some(cancel) };
    }
    let work = async {
        let metadata = fetch_release_metadata(&version).await?;
        // Official Tauri 2.14.1 restore_update applies the version comparator
        // and runtime public key and always requires a signed version.
        let updater = app.updater_builder()
            .target(UPDATE_TARGET)
            .build().map_err(|_| "UPDATE_CONFIGURATION_FAILED")?;
        let update = updater.restore_update(metadata).map_err(|_| "UPDATE_CHECK_FAILED")?
            .ok_or("NO_SIGNED_UPDATE")?;
        if update.version != version || asset_url(&version).as_deref() != Some(update.download_url.as_str()) {
            return Err("UPDATE_MANIFEST_MISMATCH");
        }
        let bytes = download_bounded(&update, &state).await?;
        Ok(Prepared { update, bytes, token: Uuid::new_v4().simple().to_string() })
    };
    let result = tokio::select! {
        biased;
        _ = &mut cancelled => Err("UPDATE_DOWNLOAD_CANCELLED"),
        outcome = work => outcome,
    };
    let mut stage = state.0.lock().map_err(|_| "UPDATE_LOCK_FAILED")?;
    if matches!(&*stage, Stage::Downloading { cancel: None, .. }) {
        *stage = Stage::Idle;
        return Err("UPDATE_DOWNLOAD_CANCELLED".into());
    }
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
        let mut key = vec![1u8; 42]; key[..2].copy_from_slice(b"Ed");
        policy["pubkey"] = Value::String(STANDARD.encode(format!("untrusted comment: test only\n{}", STANDARD.encode(key))));
        assert!(secure_policy(&policy));
        for (field, value) in [("allowDowngrades", Value::Bool(true)), ("requireSignedVersion", Value::Bool(false)), ("dangerousAcceptInvalidCerts", Value::Bool(true)), ("endpoints", serde_json::json!(["https://example.invalid"]))] {
            let mut bad = policy.clone(); bad[field] = value;
            assert!(!secure_policy(&bad));
        }
    }
    #[test]
    fn download_rejects_unknown_length_overflow_before_append() {
        let mut bytes = Vec::new();
        append_bounded(&mut bytes, b"abc", 5).unwrap();
        append_bounded(&mut bytes, b"de", 5).unwrap();
        assert_eq!(append_bounded(&mut bytes, b"x", 5), Err("UPDATE_SIZE_REJECTED"));
        assert_eq!(bytes, b"abcde");
    }
    #[test]
    fn redirect_policy_only_allows_https_release_hosts() {
        for good in [FEED, "https://release-assets.githubusercontent.com/a?token=test", "https://objects.githubusercontent.com/a"] {
            assert!(trusted_download_url(&Url::parse(good).unwrap()));
        }
        for bad in ["http://github.com/Tridgi/gost-schematic/releases/latest", "https://evil.example/Tridgi/gost-schematic/releases/a", "https://github.com.evil.example/a", "https://github.com:444/Tridgi/gost-schematic/releases/a", "https://user@github.com/Tridgi/gost-schematic/releases/a", "https://github.com/other/repo/releases/a", "https://github.com/Tridgi/gost-schematic/releases/a#fragment"] {
            assert!(!trusted_download_url(&Url::parse(bad).unwrap()));
        }
    }
    #[test]
    fn release_metadata_requires_exact_version_platform_and_asset() {
        let valid = serde_json::json!({"version":"0.2.0","platforms":{UPDATE_TARGET:{
            "url":asset_url("0.2.0").unwrap(),"signature":STANDARD.encode("fixture")}}});
        let encode = |v: &Value| serde_json::to_vec(v).unwrap();
        assert_eq!(validate_release_metadata(&encode(&valid), "0.2.0").unwrap(), valid);
        assert!(validate_release_metadata(&encode(&valid), "0.2.1").is_err());
        assert!(validate_release_metadata(&encode(&valid), "v0.2.0").is_err());
        let mut bad = valid.clone(); bad["platforms"] = serde_json::json!({"linux-x86_64":valid["platforms"][UPDATE_TARGET]});
        assert!(validate_release_metadata(&encode(&bad), "0.2.0").is_err());
        let mut bad = valid.clone(); bad["url"] = Value::String("https://example.invalid".into());
        assert!(validate_release_metadata(&encode(&bad), "0.2.0").is_err());
        let mut bad = valid.clone(); bad["platforms"][UPDATE_TARGET]["url"] = Value::String(asset_url("0.1.0").unwrap());
        assert!(validate_release_metadata(&encode(&bad), "0.2.0").is_err());
        let mut bad = valid.clone(); bad["platforms"][UPDATE_TARGET]["signature"] = Value::String("not base64!".into());
        assert!(validate_release_metadata(&encode(&bad), "0.2.0").is_err());
        let mut bad = valid.clone(); bad["platforms"][UPDATE_TARGET]["signature"] = Value::String("A".repeat(MAX_SIGNATURE_TEXT_BYTES+4));
        assert!(validate_release_metadata(&encode(&bad), "0.2.0").is_err());
        assert!(validate_release_metadata(b"{broken", "0.2.0").is_err());
    }
    #[test]
    fn metadata_limit_rejects_chunked_overflow_and_empty_body() {
        assert_eq!(validate_release_metadata(&[], "0.2.0"), Err("UPDATE_METADATA_SIZE_REJECTED"));
        let mut body = Vec::new();
        append_bounded(&mut body, &vec![b' '; MAX_MANIFEST_BYTES], MAX_MANIFEST_BYTES).unwrap();
        assert_eq!(append_bounded(&mut body, b"x", MAX_MANIFEST_BYTES), Err("UPDATE_SIZE_REJECTED"));
        body.push(b'x');
        assert_eq!(validate_release_metadata(&body, "0.2.0"), Err("UPDATE_METADATA_SIZE_REJECTED"));
    }
    #[test]
    fn update_http_client_initializes_tls_without_plugin_check() {
        assert!(update_client(Duration::from_secs(1)).is_ok());
    }
    #[test]
    fn cancellation_cannot_target_another_download() {
        let (sender, mut receiver) = oneshot::channel();
        let store = UpdateStore(Mutex::new(Stage::Downloading {
            received: 0, total: None, id: "current".into(), cancel: Some(sender),
        }));
        assert!(cancel_download(&store, "old").is_err());
        assert!(matches!(receiver.try_recv(), Err(oneshot::error::TryRecvError::Empty)));
        cancel_download(&store, "current").unwrap();
        assert_eq!(receiver.try_recv(), Ok(()));
        assert!(matches!(&*store.0.lock().unwrap(), Stage::Downloading { cancel: None, .. }));
        cancel_download(&store, "current").unwrap();
        *store.0.lock().unwrap() = Stage::Idle;
        assert!(cancel_download(&store, "current").is_err());
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
