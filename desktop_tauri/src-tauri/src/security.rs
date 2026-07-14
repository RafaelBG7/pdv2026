use url::Url;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NavigationDecision {
    Allow,
    OpenExternally,
    Block,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UrlPolicyError {
    InvalidUrl,
    InvalidProtocol,
    MissingHost,
    HostNotAllowed,
}

pub fn normalize_host(host: &str) -> String {
    host.trim().trim_end_matches('.').to_ascii_lowercase()
}

pub fn is_host_allowed(host: &str, allowed_hosts: &[String]) -> bool {
    let host = normalize_host(host);
    allowed_hosts.iter().any(|allowed| {
        let allowed = normalize_host(allowed);
        if let Some(domain) = allowed.strip_prefix('.') {
            host == domain || host.ends_with(&format!(".{domain}"))
        } else {
            host == allowed
        }
    })
}

pub fn validate_url_against_policy(
    url: &str,
    allowed_hosts: &[String],
    allow_http: bool,
) -> Result<(), UrlPolicyError> {
    let parsed = Url::parse(url).map_err(|_| UrlPolicyError::InvalidUrl)?;
    match parsed.scheme() {
        "https" => {}
        "http" if allow_http => {}
        _ => return Err(UrlPolicyError::InvalidProtocol),
    }
    let host = parsed.host_str().ok_or(UrlPolicyError::MissingHost)?;
    if is_host_allowed(host, allowed_hosts) {
        Ok(())
    } else {
        Err(UrlPolicyError::HostNotAllowed)
    }
}

pub fn classify_navigation(
    url: &str,
    allowed_hosts: &[String],
    allow_http: bool,
) -> NavigationDecision {
    let Ok(parsed) = Url::parse(url) else {
        return NavigationDecision::Block;
    };

    match parsed.scheme() {
        "https" | "http" => {
            if validate_url_against_policy(url, allowed_hosts, allow_http).is_ok() {
                NavigationDecision::Allow
            } else {
                NavigationDecision::OpenExternally
            }
        }
        "mailto" | "tel" | "whatsapp" => NavigationDecision::OpenExternally,
        _ => NavigationDecision::Block,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_exact_and_wildcard_hosts() {
        let hosts = vec![
            "app.girofy.com.br".to_string(),
            ".girofy.com.br".to_string(),
        ];
        assert!(is_host_allowed("app.girofy.com.br", &hosts));
        assert!(is_host_allowed("cliente.girofy.com.br", &hosts));
        assert!(!is_host_allowed("girofy.com.br.evil.test", &hosts));
    }

    #[test]
    fn blocks_javascript_urls() {
        let hosts = vec!["168.75.101.126".to_string()];
        assert_eq!(
            classify_navigation("javascript:alert(1)", &hosts, true),
            NavigationDecision::Block
        );
    }

    #[test]
    fn opens_unknown_web_hosts_externally() {
        let hosts = vec!["168.75.101.126".to_string()];
        assert_eq!(
            classify_navigation("https://example.com", &hosts, true),
            NavigationDecision::OpenExternally
        );
    }
}
