use serde::Serialize;

use crate::config::DesktopConfig;

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct HealthResult {
    pub ok: bool,
    pub status_code: Option<u16>,
    pub message: String,
}

impl HealthResult {
    pub fn ok(status_code: u16) -> Self {
        Self {
            ok: true,
            status_code: Some(status_code),
            message: "Servidor disponível.".to_string(),
        }
    }

    pub fn fail(status_code: Option<u16>, message: impl Into<String>) -> Self {
        Self {
            ok: false,
            status_code,
            message: message.into(),
        }
    }
}

pub async fn check_health(config: &DesktopConfig) -> HealthResult {
    let client = match reqwest::Client::builder().timeout(config.timeout()).build() {
        Ok(client) => client,
        Err(error) => {
            return HealthResult::fail(None, format!("Falha ao preparar conexão: {error}"))
        }
    };

    match client.get(config.health_url()).send().await {
        Ok(response) if response.status().is_success() => {
            HealthResult::ok(response.status().as_u16())
        }
        Ok(response) => HealthResult::fail(
            Some(response.status().as_u16()),
            format!(
                "Servidor respondeu com HTTP {}.",
                response.status().as_u16()
            ),
        ),
        Err(error) if error.is_timeout() => {
            HealthResult::fail(None, "Tempo limite ao conectar ao servidor.")
        }
        Err(error) => HealthResult::fail(None, format!("Falha de conexão: {error}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn health_result_ok_has_success_message() {
        let result = HealthResult::ok(200);
        assert!(result.ok);
        assert_eq!(result.status_code, Some(200));
    }

    #[test]
    fn health_result_fail_keeps_status_code() {
        let result = HealthResult::fail(Some(503), "indisponível");
        assert!(!result.ok);
        assert_eq!(result.status_code, Some(503));
    }
}
