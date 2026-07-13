const invoke = window.__TAURI__?.core?.invoke;

const state = {
  config: null,
  checking: false,
};

const statusPanel = document.getElementById("statusPanel");
const statusTitle = document.getElementById("statusTitle");
const statusMessage = document.getElementById("statusMessage");
const actions = document.getElementById("actions");
const retryButton = document.getElementById("retryButton");
const openBrowserButton = document.getElementById("openBrowserButton");

function setStatus(title, message, isError = false) {
  statusTitle.textContent = title;
  statusMessage.textContent = message;
  statusPanel.classList.toggle("error", isError);
}

function showActions(show) {
  actions.hidden = !show;
}

async function logEvent(level, message) {
  if (!invoke) return;
  try {
    await invoke("log_client_event", { level, message });
  } catch (_error) {
    // Logging must never block the client window.
  }
}

async function loadConfig() {
  if (!invoke) {
    throw new Error("API nativa do Tauri indisponível.");
  }
  state.config = await invoke("get_desktop_config");
  return state.config;
}

async function checkAndOpen() {
  if (state.checking) return;
  state.checking = true;
  showActions(false);
  setStatus("Verificando servidor", "Conectando ao Girofy hospedado.");

  try {
    const config = state.config || await loadConfig();
    const result = await invoke("check_health");
    if (!result.ok) {
      throw new Error(result.message || "Servidor indisponível.");
    }

    await logEvent("info", `Servidor online: ${config.app_url}`);
    setStatus("Servidor online", "Abrindo o Girofy.");
    window.location.replace(config.app_url);
  } catch (error) {
    const message = error?.message || String(error);
    await logEvent("error", `Falha ao abrir cliente: ${message}`);
    setStatus("Não foi possível conectar", message, true);
    showActions(true);
  } finally {
    state.checking = false;
  }
}

retryButton.addEventListener("click", checkAndOpen);
openBrowserButton.addEventListener("click", () => {
  if (state.config?.app_url) {
    window.open(state.config.app_url, "_blank", "noopener,noreferrer");
  }
});

document.addEventListener("DOMContentLoaded", checkAndOpen);
