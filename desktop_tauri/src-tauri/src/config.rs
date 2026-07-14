use serde::{Deserialize, Serialize};
use std::{
    env,
    error::Error,
    fmt, fs,
    path::{Path, PathBuf},
    time::Duration,
};
use url::Url;

use crate::security;

const DEFAULT_APP_URL: &str = "http://168.75.101.126:18080";
const DEFAULT_TIMEOUT_SECONDS: f64 = 4.0;

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
pub struct DesktopConfig {
    pub app_url: String,
    #[serde(default)]
    pub allowed_hosts: Vec<String>,
    #[serde(default)]
    pub allow_http: bool,
    #[serde(default = "default_environment")]
    pub environment: String,
    #[serde(default = "default_timeout")]
    pub timeout_seconds: f64,
    #[serde(default)]
    pub auto_update_enabled: bool,
    #[serde(default)]
    pub update_check_on_start: bool,
    #[serde(default)]
    pub update_manifest_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct PublicDesktopConfig {
    pub app_url: String,
    pub allowed_hosts: Vec<String>,
    pub allow_http: bool,
    pub environment: String,
    pub timeout_seconds: f64,
    pub auto_update_enabled: bool,
    pub update_check_on_start: bool,
    pub update_manifest_url: Option<String>,
}

#[derive(Debug)]
pub enum ConfigError {
    InvalidUrl(String),
    InvalidProtocol(String),
    HostNotAllowed(String),
    InvalidTimeout,
    Io(std::io::Error),
    Json(serde_json::Error),
}

impl fmt::Display for ConfigError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ConfigError::InvalidUrl(value) => write!(formatter, "URL inválida: {value}"),
            ConfigError::InvalidProtocol(value) => {
                write!(formatter, "Protocolo não permitido: {value}")
            }
            ConfigError::HostNotAllowed(value) => write!(formatter, "Host não permitido: {value}"),
            ConfigError::InvalidTimeout => write!(formatter, "Timeout inválido"),
            ConfigError::Io(error) => write!(formatter, "Falha ao ler configuração: {error}"),
            ConfigError::Json(error) => write!(formatter, "Configuração JSON inválida: {error}"),
        }
    }
}

impl Error for ConfigError {}

impl From<std::io::Error> for ConfigError {
    fn from(value: std::io::Error) -> Self {
        ConfigError::Io(value)
    }
}

impl From<serde_json::Error> for ConfigError {
    fn from(value: serde_json::Error) -> Self {
        ConfigError::Json(value)
    }
}

impl From<DesktopConfig> for PublicDesktopConfig {
    fn from(value: DesktopConfig) -> Self {
        Self {
            app_url: value.app_url,
            allowed_hosts: value.allowed_hosts,
            allow_http: value.allow_http,
            environment: value.environment,
            timeout_seconds: value.timeout_seconds,
            auto_update_enabled: value.auto_update_enabled,
            update_check_on_start: value.update_check_on_start,
            update_manifest_url: value.update_manifest_url,
        }
    }
}

fn default_environment() -> String {
    "development".to_string()
}

fn default_timeout() -> f64 {
    DEFAULT_TIMEOUT_SECONDS
}

impl Default for DesktopConfig {
    fn default() -> Self {
        Self {
            app_url: DEFAULT_APP_URL.to_string(),
            allowed_hosts: vec!["168.75.101.126".to_string()],
            allow_http: true,
            environment: default_environment(),
            timeout_seconds: default_timeout(),
            auto_update_enabled: false,
            update_check_on_start: false,
            update_manifest_url: Some(format!("{DEFAULT_APP_URL}/desktop/update.json")),
        }
    }
}

impl DesktopConfig {
    pub fn load() -> Result<Self, ConfigError> {
        let mut config = if let Some(path) = env::var_os("GIROFY_DESKTOP_CONFIG") {
            Self::from_path(PathBuf::from(path))?
        } else {
            match Self::default_config_path() {
                Some(path) if path.exists() => Self::from_path(path)?,
                Some(path) => {
                    let config = Self::default();
                    let _ = config.write_default_file(&path);
                    config
                }
                None => Self::default(),
            }
        };

        config.apply_env_overrides();
        Ok(config)
    }

    pub fn from_path(path: PathBuf) -> Result<Self, ConfigError> {
        let contents = fs::read_to_string(path)?;
        Ok(serde_json::from_str(&contents)?)
    }

    pub fn default_config_path() -> Option<PathBuf> {
        let base = env::var_os("PROGRAMDATA")
            .map(PathBuf::from)
            .or_else(|| dirs_next::data_dir());
        base.map(|path| path.join("Girofy").join("config").join("desktop.json"))
    }

    pub fn write_default_file(&self, path: &Path) -> Result<(), ConfigError> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let contents = serde_json::to_string_pretty(self)?;
        fs::write(path, contents)?;
        Ok(())
    }

    pub fn validate(mut self) -> Result<Self, ConfigError> {
        if !(1.0..=30.0).contains(&self.timeout_seconds) {
            return Err(ConfigError::InvalidTimeout);
        }

        let parsed =
            Url::parse(&self.app_url).map_err(|_| ConfigError::InvalidUrl(self.app_url.clone()))?;
        let scheme = parsed.scheme();
        if scheme != "https" && !(scheme == "http" && self.allow_http) {
            return Err(ConfigError::InvalidProtocol(scheme.to_string()));
        }

        let host = parsed.host_str().unwrap_or_default();
        if host.is_empty() {
            return Err(ConfigError::InvalidUrl(self.app_url.clone()));
        }

        if self.allowed_hosts.is_empty() {
            self.allowed_hosts.push(host.to_string());
        }

        if !security::is_host_allowed(host, &self.allowed_hosts) {
            return Err(ConfigError::HostNotAllowed(host.to_string()));
        }

        if let Some(manifest_url) = &self.update_manifest_url {
            security::validate_url_against_policy(
                manifest_url,
                &self.allowed_hosts,
                self.allow_http,
            )
            .map_err(|_| ConfigError::InvalidUrl(manifest_url.clone()))?;
        }

        Ok(self)
    }

    pub fn health_url(&self) -> String {
        let mut url = self.app_url.trim_end_matches('/').to_string();
        url.push_str("/health");
        url
    }

    pub fn timeout(&self) -> Duration {
        Duration::from_secs_f64(self.timeout_seconds)
    }

    fn apply_env_overrides(&mut self) {
        if let Ok(value) = env::var("GIROFY_DESKTOP_APP_URL") {
            if !value.trim().is_empty() {
                self.app_url = value;
            }
        }
        if let Ok(value) = env::var("GIROFY_DESKTOP_ALLOWED_HOSTS") {
            self.allowed_hosts = value
                .split(',')
                .map(str::trim)
                .filter(|entry| !entry.is_empty())
                .map(ToOwned::to_owned)
                .collect();
        }
        if let Ok(value) = env::var("GIROFY_DESKTOP_ALLOW_HTTP") {
            self.allow_http = matches!(value.as_str(), "1" | "true" | "TRUE" | "sim" | "SIM");
        }
        if let Ok(value) = env::var("GIROFY_DESKTOP_ENV") {
            self.environment = value;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config_points_to_current_oci_ip() {
        let config = DesktopConfig::default().validate().unwrap();
        assert_eq!(config.app_url, DEFAULT_APP_URL);
        assert_eq!(config.health_url(), "http://168.75.101.126:18080/health");
    }

    #[test]
    fn rejects_http_when_not_allowed() {
        let config = DesktopConfig {
            allow_http: false,
            ..DesktopConfig::default()
        };
        assert!(matches!(
            config.validate(),
            Err(ConfigError::InvalidProtocol(_))
        ));
    }

    #[test]
    fn rejects_unknown_host() {
        let config = DesktopConfig {
            app_url: "https://evil.example.com".to_string(),
            allowed_hosts: vec!["app.girofy.com.br".to_string()],
            allow_http: false,
            ..DesktopConfig::default()
        };
        assert!(matches!(
            config.validate(),
            Err(ConfigError::HostNotAllowed(_))
        ));
    }

    #[test]
    fn reads_config_from_file() {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path().join("desktop.json");
        fs::write(
            &path,
            r#"{"app_url":"https://app.girofy.com.br","allowed_hosts":["app.girofy.com.br"],"allow_http":false}"#,
        )
        .unwrap();

        let config = DesktopConfig::from_path(path).unwrap().validate().unwrap();
        assert_eq!(config.app_url, "https://app.girofy.com.br");
    }

    #[test]
    fn writes_default_config_file() {
        let temp = tempfile::tempdir().unwrap();
        let path = temp
            .path()
            .join("Girofy")
            .join("config")
            .join("desktop.json");
        DesktopConfig::default().write_default_file(&path).unwrap();

        let contents = fs::read_to_string(path).unwrap();
        assert!(contents.contains(DEFAULT_APP_URL));
    }
}
