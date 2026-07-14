use std::{
    env,
    fs::{self, OpenOptions},
    io::{self, Write},
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

const MAX_LOG_BYTES: u64 = 1_048_576;

pub fn append_log(level: &str, message: &str) -> io::Result<()> {
    let path = log_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    rotate_if_needed(&path)?;

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or_default();
    let line = format!(
        "{} [{}] {}\n",
        timestamp,
        sanitize_level(level),
        sanitize_message(message)
    );
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?
        .write_all(line.as_bytes())
}

pub fn log_path() -> PathBuf {
    let base = env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .or_else(dirs_next::data_local_dir)
        .unwrap_or_else(env::temp_dir);
    base.join("Girofy").join("logs").join("tauri-client.log")
}

pub fn sanitize_level(level: &str) -> String {
    match level.trim().to_ascii_lowercase().as_str() {
        "debug" => "DEBUG".to_string(),
        "warn" | "warning" => "WARN".to_string(),
        "error" => "ERROR".to_string(),
        _ => "INFO".to_string(),
    }
}

pub fn sanitize_message(message: &str) -> String {
    let mut clean = message.replace(['\n', '\r'], " ");
    for marker in ["password=", "token=", "secret=", "key="] {
        if let Some(index) = clean.to_ascii_lowercase().find(marker) {
            clean.truncate(index + marker.len());
            clean.push_str("[mascarado]");
        }
    }
    clean.chars().take(1000).collect()
}

fn rotate_if_needed(path: &Path) -> io::Result<()> {
    if fs::metadata(path)
        .map(|metadata| metadata.len())
        .unwrap_or(0)
        <= MAX_LOG_BYTES
    {
        return Ok(());
    }
    let rotated = path.with_extension("log.1");
    let _ = fs::remove_file(&rotated);
    fs::rename(path, rotated)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitizes_log_level() {
        assert_eq!(sanitize_level("warning"), "WARN");
        assert_eq!(sanitize_level("other"), "INFO");
    }

    #[test]
    fn masks_sensitive_message_parts() {
        assert_eq!(
            sanitize_message("erro com token=abc123 e dados"),
            "erro com token=[mascarado]"
        );
    }
}
