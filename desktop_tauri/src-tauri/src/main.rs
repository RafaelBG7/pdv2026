use girofy_tauri_client::config::{DesktopConfig, PublicDesktopConfig};
use girofy_tauri_client::network::HealthResult;
use girofy_tauri_client::{logging, network};
use tauri::Manager;

#[tauri::command]
fn get_desktop_config() -> Result<PublicDesktopConfig, String> {
    DesktopConfig::load()
        .and_then(|config| config.validate())
        .map(PublicDesktopConfig::from)
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn check_health() -> Result<HealthResult, String> {
    let config = DesktopConfig::load()
        .and_then(|config| config.validate())
        .map_err(|error| error.to_string())?;
    Ok(network::check_health(&config).await)
}

#[tauri::command]
fn log_client_event(level: String, message: String) -> Result<(), String> {
    logging::append_log(&level, &message).map_err(|error| error.to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            get_desktop_config,
            check_health,
            log_client_event
        ])
        .run(tauri::generate_context!())
        .expect("falha ao iniciar o cliente Girofy");
}
