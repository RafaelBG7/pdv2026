#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UpdateMode {
    Disabled,
    ManualManifest,
    TauriUpdaterReady,
}

pub fn select_update_mode(
    auto_update_enabled: bool,
    has_manifest_url: bool,
    has_tauri_endpoint: bool,
) -> UpdateMode {
    if !auto_update_enabled {
        return UpdateMode::Disabled;
    }
    if has_tauri_endpoint {
        return UpdateMode::TauriUpdaterReady;
    }
    if has_manifest_url {
        return UpdateMode::ManualManifest;
    }
    UpdateMode::Disabled
}

pub fn is_newer_version(current: &str, candidate: &str) -> bool {
    parse_version(candidate) > parse_version(current)
}

fn parse_version(value: &str) -> Vec<u32> {
    value
        .split('.')
        .map(|part| part.trim().parse::<u32>().unwrap_or(0))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compares_semver_like_versions() {
        assert!(is_newer_version("1.0.9", "1.1.0"));
        assert!(!is_newer_version("1.2.0", "1.1.9"));
    }

    #[test]
    fn disables_update_when_not_enabled() {
        assert_eq!(select_update_mode(false, true, true), UpdateMode::Disabled);
        assert_eq!(
            select_update_mode(true, true, false),
            UpdateMode::ManualManifest
        );
        assert_eq!(
            select_update_mode(true, true, true),
            UpdateMode::TauriUpdaterReady
        );
    }
}
