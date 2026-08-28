document.addEventListener('DOMContentLoaded', function () {
  const storedTheme = localStorage.getItem('girofy-theme');
  let accessibilityEnabled = localStorage.getItem('girofy-accessibility-enabled') !== 'false';
  let accessibilityBold = localStorage.getItem('girofy-accessibility-bold') === 'true';
  const storedTextScale = localStorage.getItem('girofy-text-scale') || 'normal';
  const storedContrast = localStorage.getItem('girofy-contrast') || 'default';
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isAuthenticated = document.documentElement.dataset.authenticated === 'true';
  const initialTheme = isAuthenticated ? (storedTheme || (prefersDark ? 'dark' : 'light')) : 'dark';
  const appShell = document.querySelector('.app-shell');
  const sidebarToggle = document.querySelector('[data-sidebar-toggle]');
  const sidebarToggleIcon = document.querySelector('[data-sidebar-toggle-icon]');
  const mobileSidebarToggle = document.querySelector('[data-mobile-sidebar-toggle]');
  const mobileSidebarClose = document.querySelector('[data-mobile-sidebar-close]');
  const mobileSidebarQuery = window.matchMedia('(max-width: 900px)');
  const storedSidebar = localStorage.getItem('adega-jf-sidebar');
  const advancedFilterToggle = document.querySelector('[data-advanced-filter-toggle]');
  const advancedFilterPanel = document.querySelector('[data-advanced-filter-panel]');
  const permissionOverrideModal = document.getElementById('permissionOverrideModal');
  const permissionOverrideUsername = document.getElementById('permissionOverrideUsername');
  const permissionOverridePassword = document.getElementById('permissionOverridePassword');
  const permissionOverrideConfirm = document.querySelector('[data-permission-override-confirm]');
  const userMenu = document.querySelector('[data-user-menu]');
  const notificationMenu = document.querySelector('.notification-menu');
  const globalNewSaleLink = document.querySelector('[data-global-new-sale]');
  const postSaleNewSaleLink = document.querySelector('[data-post-sale-new-sale]');
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  let pendingPermissionForm = null;
  let pendingPermissionSubmitter = null;

  document.querySelectorAll('.system-flash[data-auto-dismiss-ms]').forEach(function (notification) {
    const duration = Number.parseInt(notification.dataset.autoDismissMs || '', 10);
    if (!Number.isFinite(duration) || duration <= 0) {
      return;
    }
    window.setTimeout(function () {
      if (!notification.isConnected) {
        return;
      }
      if (window.bootstrap && window.bootstrap.Alert) {
        window.bootstrap.Alert.getOrCreateInstance(notification).close();
        return;
      }
      notification.remove();
    }, duration);
  });

  function ensureCsrfField(form) {
    if (!csrfToken || !form || (form.method || '').toLowerCase() === 'get') {
      return;
    }
    let csrfField = form.querySelector('input[name="_csrf_token"]');
    if (!csrfField) {
      csrfField = document.createElement('input');
      csrfField.type = 'hidden';
      csrfField.name = '_csrf_token';
      form.appendChild(csrfField);
    }
    csrfField.value = csrfToken;
  }

  document.querySelectorAll('form').forEach(ensureCsrfField);
  document.addEventListener('submit', function (event) {
    ensureCsrfField(event.target);
  }, true);

  if (csrfToken && window.fetch) {
    const originalFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
      const requestInit = init || {};
      const method = (requestInit.method || (input && input.method) || 'GET').toUpperCase();
      if (['POST', 'PUT', 'PATCH', 'DELETE'].indexOf(method) >= 0) {
        const headers = new Headers(requestInit.headers || (input && input.headers) || {});
        if (!headers.has('X-CSRFToken')) {
          headers.set('X-CSRFToken', csrfToken);
        }
        requestInit.headers = headers;
      }
      return originalFetch(input, requestInit);
    };
  }

  function applyTheme(theme, persist = true) {
    document.documentElement.setAttribute('data-theme', theme);
    if (persist) {
      localStorage.setItem('girofy-theme', theme);
    }
    document.querySelectorAll('[data-settings-theme-label]').forEach(function (label) {
      label.textContent = theme === 'dark' ? 'Dark' : 'Light';
    });
    document.querySelectorAll('[data-settings-theme-choice]').forEach(function (button) {
      const active = button.dataset.settingsThemeChoice === theme;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
      const dark = theme === 'dark';
      button.setAttribute('aria-pressed', dark ? 'true' : 'false');
      button.setAttribute('aria-label', dark ? 'Ativar tema claro' : 'Ativar tema escuro');
      button.dataset.themeState = theme;
    });
  }

  const textScaleLabels = {
    normal: 'Padrão',
    large: 'Grande',
    extra: 'Muito grande',
  };

  const contrastLabels = {
    default: 'Padrão',
    high: 'Alto contraste',
    soft: 'Suave',
  };

  function normalizeAccessibilityValue(value, options, fallback) {
    return Object.prototype.hasOwnProperty.call(options, value) ? value : fallback;
  }

  function refreshAccessibilityUi() {
    const selectedScale = normalizeAccessibilityValue(localStorage.getItem('girofy-text-scale') || 'normal', textScaleLabels, 'normal');
    const selectedContrast = normalizeAccessibilityValue(localStorage.getItem('girofy-contrast') || 'default', contrastLabels, 'default');
    const effectiveScale = accessibilityEnabled ? selectedScale : 'normal';
    const effectiveContrast = accessibilityEnabled ? selectedContrast : 'default';
    const effectiveBold = accessibilityEnabled && accessibilityBold;

    document.documentElement.setAttribute('data-accessibility-enabled', accessibilityEnabled ? 'true' : 'false');
    document.documentElement.setAttribute('data-text-scale', effectiveScale);
    document.documentElement.setAttribute('data-contrast', effectiveContrast);
    document.documentElement.setAttribute('data-accessibility-bold', effectiveBold ? 'true' : 'false');
    localStorage.setItem('girofy-accessibility-enabled', accessibilityEnabled ? 'true' : 'false');
    localStorage.setItem('girofy-accessibility-bold', accessibilityBold ? 'true' : 'false');

    document.querySelectorAll('[data-accessibility-status-label]').forEach(function (label) {
      label.textContent = accessibilityEnabled ? 'Ativa' : 'Desativada';
    });
    document.querySelectorAll('[data-accessibility-text-scale-label]').forEach(function (label) {
      label.textContent = accessibilityEnabled ? textScaleLabels[selectedScale] : 'Desativado';
    });
    document.querySelectorAll('[data-accessibility-contrast-label]').forEach(function (label) {
      label.textContent = accessibilityEnabled ? contrastLabels[selectedContrast] : 'Desativado';
    });
    document.querySelectorAll('[data-accessibility-bold-label]').forEach(function (label) {
      label.textContent = effectiveBold ? 'Ativo' : 'Inativo';
    });
    document.querySelectorAll('[data-accessibility-enabled-toggle]').forEach(function (input) {
      input.checked = accessibilityEnabled;
    });
    document.querySelectorAll('[data-accessibility-bold-toggle]').forEach(function (input) {
      input.checked = accessibilityBold;
      input.disabled = !accessibilityEnabled;
    });
    document.querySelectorAll('[data-accessibility-text-scale-choice]').forEach(function (button) {
      const active = button.dataset.accessibilityTextScaleChoice === selectedScale;
      button.classList.toggle('is-active', active);
      button.classList.toggle('is-disabled', !accessibilityEnabled);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    document.querySelectorAll('[data-accessibility-contrast-choice]').forEach(function (button) {
      const active = button.dataset.accessibilityContrastChoice === selectedContrast;
      button.classList.toggle('is-active', active);
      button.classList.toggle('is-disabled', !accessibilityEnabled);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function applyTextScale(scale) {
    const normalizedScale = normalizeAccessibilityValue(scale, textScaleLabels, 'normal');
    localStorage.setItem('girofy-text-scale', normalizedScale);
    refreshAccessibilityUi();
  }

  function applyContrast(contrast) {
    const normalizedContrast = normalizeAccessibilityValue(contrast, contrastLabels, 'default');
    localStorage.setItem('girofy-contrast', normalizedContrast);
    refreshAccessibilityUi();
  }

  function applyAccessibilityEnabled(enabled) {
    accessibilityEnabled = Boolean(enabled);
    refreshAccessibilityUi();
  }

  function applyAccessibilityBold(enabled) {
    accessibilityBold = Boolean(enabled);
    refreshAccessibilityUi();
  }

  applyTheme(initialTheme, isAuthenticated);
  localStorage.setItem('girofy-text-scale', normalizeAccessibilityValue(storedTextScale, textScaleLabels, 'normal'));
  localStorage.setItem('girofy-contrast', normalizeAccessibilityValue(storedContrast, contrastLabels, 'default'));
  refreshAccessibilityUi();

  if (globalNewSaleLink) {
    document.addEventListener('keydown', function (event) {
      const target = event.target;
      const isEditing = target instanceof HTMLElement && (
        target.matches('input, textarea, select') || target.isContentEditable
      );
      if (event.key !== 'F3' || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || isEditing) {
        return;
      }

      const destination = new URL(globalNewSaleLink.href, window.location.href);
      if (window.location.pathname === destination.pathname) {
        return;
      }

      event.preventDefault();
      window.location.assign(destination.href);
    });
  }

  if (postSaleNewSaleLink) {
    document.addEventListener('keydown', function (event) {
      const target = event.target;
      const isEditing = target instanceof HTMLElement && (
        target.matches('input, textarea, select') || target.isContentEditable
      );
      if (isEditing || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
        return;
      }
      if (!['Enter', ' ', 'F3'].includes(event.key)) {
        return;
      }
      event.preventDefault();
      window.location.assign(postSaleNewSaleLink.href);
    });
  }

  const cashRequiredPage = document.querySelector('[data-cash-required-page]');
  const cashOpenConfirmForm = document.querySelector('[data-cash-open-confirm]');
  if (cashRequiredPage && cashOpenConfirmForm) {
    document.addEventListener('keydown', function (event) {
      const target = event.target;
      const isEditing = target instanceof HTMLElement && (
        target.matches('input, textarea, select') || target.isContentEditable
      );
      if (event.key !== 'Enter' || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || isEditing) {
        return;
      }

      event.preventDefault();
      if (typeof cashOpenConfirmForm.requestSubmit === 'function') {
        cashOpenConfirmForm.requestSubmit();
      } else {
        cashOpenConfirmForm.submit();
      }
    });
  }

  function setHiddenField(form, name, value) {
    let input = form.querySelector(`input[name="${name}"]`);
    if (!input) {
      input = document.createElement('input');
      input.type = 'hidden';
      input.name = name;
      form.appendChild(input);
    }
    input.value = value;
  }

  function openPermissionOverride(form, submitter) {
    pendingPermissionForm = form;
    pendingPermissionSubmitter = submitter || null;

    if (permissionOverrideUsername) {
      permissionOverrideUsername.value = '';
    }
    if (permissionOverridePassword) {
      permissionOverridePassword.value = '';
    }

    if (window.bootstrap && permissionOverrideModal) {
      window.bootstrap.Modal.getOrCreateInstance(permissionOverrideModal).show();
      setTimeout(function () {
        if (permissionOverrideUsername) {
          permissionOverrideUsername.focus();
        }
      }, 150);
    }
  }

  document.addEventListener('submit', function (event) {
    const form = event.target;
    if (!form || !form.matches('form[data-permission-override="true"]')) {
      return;
    }
    if (form.dataset.permissionOverrideReady === 'true') {
      form.dataset.permissionOverrideReady = 'false';
      return;
    }

    event.preventDefault();
    openPermissionOverride(form, event.submitter);
  }, true);

  if (permissionOverrideConfirm) {
    permissionOverrideConfirm.addEventListener('click', function () {
      if (!pendingPermissionForm) {
        return;
      }

      const username = permissionOverrideUsername ? permissionOverrideUsername.value.trim() : '';
      const password = permissionOverridePassword ? permissionOverridePassword.value : '';
      if (!username || !password) {
        if (permissionOverridePassword) {
          permissionOverridePassword.focus();
        }
        return;
      }

      setHiddenField(pendingPermissionForm, '_permission_override_username', username);
      setHiddenField(pendingPermissionForm, '_permission_override_password', password);
      pendingPermissionForm.dataset.permissionOverrideReady = 'true';

      if (window.bootstrap && permissionOverrideModal) {
        window.bootstrap.Modal.getOrCreateInstance(permissionOverrideModal).hide();
      }

      if (pendingPermissionSubmitter && typeof pendingPermissionForm.requestSubmit === 'function') {
        pendingPermissionForm.requestSubmit(pendingPermissionSubmitter);
      } else {
        pendingPermissionForm.submit();
      }
      pendingPermissionForm = null;
      pendingPermissionSubmitter = null;
    });
  }

  function applySidebar(collapsed) {
    if (!appShell) {
      return;
    }

    appShell.classList.toggle('sidebar-collapsed', collapsed);
    document.documentElement.setAttribute('data-sidebar-state', collapsed ? 'collapsed' : 'expanded');
    localStorage.setItem('adega-jf-sidebar', collapsed ? 'collapsed' : 'expanded');

    if (sidebarToggle) {
      sidebarToggle.setAttribute('aria-label', collapsed ? 'Expandir menu' : 'Minimizar menu');
      sidebarToggle.setAttribute('title', collapsed ? 'Expandir menu' : 'Minimizar menu');
    }

    if (sidebarToggleIcon) {
      sidebarToggleIcon.textContent = '‹';
    }
  }

  applySidebar(storedSidebar === 'collapsed');

  function setMobileSidebar(open) {
    if (!appShell) {
      return;
    }

    const shouldOpen = Boolean(open && mobileSidebarQuery.matches);
    appShell.classList.toggle('mobile-sidebar-open', shouldOpen);
    document.body.classList.toggle('mobile-navigation-open', shouldOpen);
    if (mobileSidebarToggle) {
      mobileSidebarToggle.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
      mobileSidebarToggle.setAttribute('aria-label', shouldOpen ? 'Fechar menu' : 'Abrir menu');
    }
  }

  if (mobileSidebarToggle) {
    mobileSidebarToggle.addEventListener('click', function () {
      setMobileSidebar(!appShell.classList.contains('mobile-sidebar-open'));
    });
  }

  if (mobileSidebarClose) {
    mobileSidebarClose.addEventListener('click', function () {
      setMobileSidebar(false);
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && appShell && appShell.classList.contains('mobile-sidebar-open')) {
      setMobileSidebar(false);
      if (mobileSidebarToggle) {
        mobileSidebarToggle.focus();
      }
    }
  });

  mobileSidebarQuery.addEventListener('change', function () {
    setMobileSidebar(false);
  });

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function () {
      const collapsed = appShell && appShell.classList.contains('sidebar-collapsed');
      if (appShell) {
        appShell.classList.add('sidebar-animating');
        window.setTimeout(function () {
          appShell.classList.remove('sidebar-animating');
        }, 220);
      }
      applySidebar(!collapsed);
    });
  }

  let sidebarNavigationLockTimer = null;

  function lockCollapsedSidebarDuringNavigation() {
    if (!appShell || !appShell.classList.contains('sidebar-collapsed')) {
      return;
    }

    document.body.classList.add('sidebar-navigation-lock');
    document.documentElement.setAttribute('data-sidebar-state', 'collapsed');
    appShell.classList.add('sidebar-collapsed');
    appShell.classList.remove('sidebar-animating');

    window.clearTimeout(sidebarNavigationLockTimer);
    sidebarNavigationLockTimer = window.setTimeout(function () {
      document.body.classList.remove('sidebar-navigation-lock');
    }, 900);
  }

  document.querySelectorAll('.sidebar .nav-link').forEach(function (link) {
    link.addEventListener('pointerdown', lockCollapsedSidebarDuringNavigation, { passive: true });
    link.addEventListener('click', function () {
      lockCollapsedSidebarDuringNavigation();
      setMobileSidebar(false);
    }, { passive: true });
  });

  document.querySelectorAll('.table-responsive').forEach(function (tableRegion) {
    if (!tableRegion.hasAttribute('tabindex')) {
      tableRegion.setAttribute('tabindex', '0');
    }
    if (!tableRegion.hasAttribute('role')) {
      tableRegion.setAttribute('role', 'region');
    }
    if (!tableRegion.hasAttribute('aria-label')) {
      tableRegion.setAttribute('aria-label', 'Tabela com rolagem horizontal');
    }
  });

  document.querySelectorAll('[data-settings-theme-choice]').forEach(function (button) {
    button.addEventListener('click', function () {
      applyTheme(button.dataset.settingsThemeChoice || 'light');
    });
  });

  document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
    button.addEventListener('click', function () {
      const current = document.documentElement.getAttribute('data-theme') || 'light';
      applyTheme(current === 'dark' ? 'light' : 'dark');
    });
  });

  document.querySelectorAll('[data-accessibility-text-scale-choice]').forEach(function (button) {
    button.addEventListener('click', function () {
      applyTextScale(button.dataset.accessibilityTextScaleChoice || 'normal');
    });
  });

  document.querySelectorAll('[data-accessibility-contrast-choice]').forEach(function (button) {
    button.addEventListener('click', function () {
      applyContrast(button.dataset.accessibilityContrastChoice || 'default');
    });
  });

  document.querySelectorAll('[data-accessibility-enabled-toggle]').forEach(function (input) {
    input.addEventListener('change', function () {
      applyAccessibilityEnabled(input.checked);
    });
  });

  document.querySelectorAll('[data-accessibility-bold-toggle]').forEach(function (input) {
    input.addEventListener('change', function () {
      applyAccessibilityBold(input.checked);
    });
  });

  document.querySelectorAll('[data-accessibility-reset]').forEach(function (button) {
    button.addEventListener('click', function () {
      applyAccessibilityEnabled(true);
      applyAccessibilityBold(false);
      applyTextScale('normal');
      applyContrast('default');
    });
  });

  if (userMenu) {
    userMenu.addEventListener('toggle', function () {
      if (userMenu.open && notificationMenu) {
        notificationMenu.removeAttribute('open');
      }
    });
    document.addEventListener('click', function (event) {
      if (userMenu.open && !userMenu.contains(event.target)) {
        userMenu.removeAttribute('open');
      }
    });
  }

  if (notificationMenu) {
    notificationMenu.addEventListener('toggle', function () {
      if (notificationMenu.open && userMenu) {
        userMenu.removeAttribute('open');
      }
    });
    document.addEventListener('click', function (event) {
      if (notificationMenu.open && !notificationMenu.contains(event.target)) {
        notificationMenu.removeAttribute('open');
      }
    });
  }

  document.querySelectorAll('[data-key-preset-days]').forEach(function (button) {
    button.addEventListener('click', function () {
      const target = document.getElementById(button.dataset.keyPresetTarget || '');
      const days = Number.parseInt(button.dataset.keyPresetDays || '0', 10);
      if (!target || !days) {
        return;
      }
      const form = button.closest('form');
      const companySelect = form ? form.querySelector('#renew_company_id') : null;
      const selectedCompany = companySelect ? companySelect.options[companySelect.selectedIndex] : null;
      const currentExpiry = selectedCompany ? selectedCompany.dataset.currentExpiry : '';
      const date = currentExpiry ? new Date(currentExpiry + 'T12:00:00') : new Date();
      if (date < new Date()) {
        date.setTime(Date.now());
      }
      date.setDate(date.getDate() + days);
      target.value = date.toISOString().slice(0, 10);
      const presetInput = form ? form.querySelector('input[name="preset_days"]') : null;
      if (presetInput) {
        presetInput.value = String(days);
      }
      target.dispatchEvent(new Event('change', { bubbles: true }));
    });
  });

  const renewalPreview = document.querySelector('[data-renewal-preview-value]');
  const renewalDateInput = document.getElementById('renew_renews_at');
  if (renewalPreview && renewalDateInput) {
    const updateRenewalPreview = function () {
      if (!renewalDateInput.value) {
        renewalPreview.textContent = 'Selecione uma data';
        return;
      }
      renewalPreview.textContent = new Intl.DateTimeFormat('pt-BR').format(new Date(renewalDateInput.value + 'T12:00:00'));
    };
    renewalDateInput.addEventListener('change', updateRenewalPreview);
  }

  document.querySelectorAll('.master-key-renew-form').forEach(function (form) {
    const period = form.querySelector('select[name="preset_days"]');
    const preview = form.querySelector('[data-key-renew-preview]');
    const renderPreview = function () {
      if (!period || !preview) return;
      const current = form.dataset.currentExpiry || '';
      const base = current ? new Date(current + 'T12:00:00') : new Date();
      if (base < new Date()) base.setTime(Date.now());
      base.setDate(base.getDate() + Number.parseInt(period.value || '0', 10));
      preview.textContent = 'Novo vencimento: ' + new Intl.DateTimeFormat('pt-BR').format(base);
    };
    if (period) period.addEventListener('change', renderPreview);
    renderPreview();
  });

  document.querySelectorAll('[data-revoke-key-form]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      const message = 'Tem certeza que deseja revogar esta key?\n\nKey: ' + (form.dataset.key || '-') + '\nEmpresa: ' + (form.dataset.company || 'Avulsa') + '\nVencimento: ' + (form.dataset.expiry || '-');
      if (!window.confirm(message)) event.preventDefault();
    });
  });

  document.querySelectorAll('[data-company-row-toggle]').forEach(function (row) {
    const selector = row.dataset.companyRowToggle || '';
    const details = selector ? document.querySelector(selector) : null;
    if (!details) return;

    const toggleDetails = function () {
      if (!window.bootstrap || !window.bootstrap.Collapse) return;
      window.bootstrap.Collapse.getOrCreateInstance(details, { toggle: false }).toggle();
    };

    row.addEventListener('click', function (event) {
      if (event.target.closest('a, button, input, select, textarea, form')) return;
      toggleDetails();
    });
    row.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      toggleDetails();
    });
    details.addEventListener('show.bs.collapse', function () {
      row.setAttribute('aria-expanded', 'true');
      row.classList.add('is-expanded');
    });
    details.addEventListener('hide.bs.collapse', function () {
      row.setAttribute('aria-expanded', 'false');
      row.classList.remove('is-expanded');
    });
  });

  function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.top = '-999px';
    document.body.appendChild(textarea);
    textarea.select();

    try {
      document.execCommand('copy');
      return Promise.resolve();
    } catch (error) {
      return Promise.reject(error);
    } finally {
      document.body.removeChild(textarea);
    }
  }

  document.querySelectorAll('[data-copy-key]').forEach(function (button) {
    const originalLabel = button.textContent;
    button.addEventListener('click', function () {
      const key = button.dataset.copyKey || '';
      if (!key) {
        return;
      }

      copyTextToClipboard(key).then(function () {
        button.textContent = 'Copiada';
        button.classList.add('is-copied');
        setTimeout(function () {
          button.textContent = originalLabel;
          button.classList.remove('is-copied');
        }, 1800);
      }).catch(function () {
        button.textContent = 'Erro';
        setTimeout(function () {
          button.textContent = originalLabel;
        }, 1800);
      });
    });
  });

  document.querySelectorAll('[data-settings-tabs]').forEach(function (tabs) {
    const buttons = Array.from(tabs.querySelectorAll('[data-settings-tab]'));
    const panels = Array.from(tabs.querySelectorAll('[data-settings-panel]'));
    const shouldPersistTabs = tabs.dataset.settingsTabsPersist !== 'false';
    const storageKey = tabs.dataset.settingsTabsStorage || 'adega-jf-settings-tab';
    const defaultTab = tabs.dataset.settingsTabsDefault || '';

    function activateTab(tabName) {
      buttons.forEach(function (button) {
        const active = button.dataset.settingsTab === tabName;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      panels.forEach(function (panel) {
        panel.classList.toggle('is-active', panel.dataset.settingsPanel === tabName);
      });
      if (shouldPersistTabs) {
        localStorage.setItem(storageKey, tabName);
      }
    }

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        activateTab(button.dataset.settingsTab);
      });
    });

    const hashTab = window.location.hash === '#accessibility' ? 'accessibility' : '';
    const storedTab = shouldPersistTabs ? localStorage.getItem(storageKey) : '';
    if (hashTab && buttons.some(function (button) { return button.dataset.settingsTab === hashTab; })) {
      activateTab(hashTab);
    } else if (storedTab && buttons.some(function (button) { return button.dataset.settingsTab === storedTab; })) {
      activateTab(storedTab);
    } else if (defaultTab && buttons.some(function (button) { return button.dataset.settingsTab === defaultTab; })) {
      activateTab(defaultTab);
    }
  });

  function autocompleteMatchRank(term, primaryText, secondaryText) {
    const normalizedTerm = normalizeSuggestionText(term);
    const primary = normalizeSuggestionText(primaryText);
    const secondary = normalizeSuggestionText(secondaryText);
    const combined = normalizeSuggestionText(`${primaryText || ''} ${secondaryText || ''}`);

    if (!normalizedTerm) {
      return 99;
    }
    if (primary === normalizedTerm || secondary === normalizedTerm) {
      return 0;
    }
    if (primary.startsWith(normalizedTerm)) {
      return 1;
    }
    if (primary.split(/\s+/).some(function (word) { return word.startsWith(normalizedTerm); })) {
      return 2;
    }
    if (secondary.startsWith(normalizedTerm)) {
      return 3;
    }
    if (combined.includes(normalizedTerm)) {
      return 4;
    }
    return 99;
  }

  function compareAutocompleteMatches(left, right, term, primaryGetter, secondaryGetter) {
    const leftPrimary = primaryGetter(left);
    const rightPrimary = primaryGetter(right);
    const leftSecondary = secondaryGetter ? secondaryGetter(left) : '';
    const rightSecondary = secondaryGetter ? secondaryGetter(right) : '';
    const leftRank = autocompleteMatchRank(term, leftPrimary, leftSecondary);
    const rightRank = autocompleteMatchRank(term, rightPrimary, rightSecondary);

    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }

    return String(leftPrimary || '').localeCompare(String(rightPrimary || ''), 'pt-BR', {
      numeric: true,
      sensitivity: 'base',
    });
  }

  document.querySelectorAll('[data-employee-search]').forEach(function (searchArea) {
    const input = searchArea.querySelector('[data-employee-search-input]');
    const countLabel = searchArea.querySelector('[data-employee-search-count]');
    const suggestionList = searchArea.querySelector('[data-employee-suggestion-list]');
    const panel = searchArea.closest('[data-settings-panel]') || document;
    const cards = Array.from(panel.querySelectorAll('[data-employee-card]'));
    const emptyState = panel.querySelector('[data-employee-search-empty]');
    let activeEmployeeIndex = 0;

    function normalizeSearch(value) {
      return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[.-]/g, '');
    }

    function matchingCards() {
      const term = normalizeSearch(input.value);
      return cards.filter(function (card) {
        const text = normalizeSearch(card.dataset.employeeSearchText || card.textContent);
        return !term || text.includes(term);
      }).sort(function (left, right) {
        return compareAutocompleteMatches(
          left,
          right,
          input.value,
          function (card) { return card.dataset.employeeName || card.textContent; },
          function (card) { return `${card.dataset.employeeSearchText || ''} ${card.dataset.employeeMeta || ''}`; }
        );
      });
    }

    function openEmployeeCard(card) {
      const collapseElement = card.querySelector('.collapse');
      if (!collapseElement) {
        return;
      }

      if (window.bootstrap && window.bootstrap.Collapse) {
        window.bootstrap.Collapse.getOrCreateInstance(collapseElement, { toggle: false }).show();
      } else {
        collapseElement.classList.add('show');
      }
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function closeEmployeeSuggestions() {
      if (!suggestionList) {
        return;
      }
      suggestionList.classList.remove('is-open');
      suggestionList.innerHTML = '';
    }

    function renderEmployeeSuggestions() {
      if (!suggestionList) {
        return;
      }

      if (!input.value.trim()) {
        closeEmployeeSuggestions();
        return;
      }

      const matches = matchingCards().slice(0, 8);
      suggestionList.innerHTML = '';
      activeEmployeeIndex = Math.min(activeEmployeeIndex, Math.max(matches.length - 1, 0));

      if (!matches.length) {
        const empty = document.createElement('div');
        empty.className = 'product-suggestion-empty';
        empty.textContent = 'Nenhum funcionário encontrado';
        suggestionList.appendChild(empty);
        suggestionList.classList.add('is-open');
        return;
      }

      matches.forEach(function (card, index) {
        const button = document.createElement('button');
        const title = document.createElement('span');
        const meta = document.createElement('span');

        button.type = 'button';
        button.className = 'product-suggestion-item';
        button.classList.toggle('is-active', index === activeEmployeeIndex);
        title.className = 'product-suggestion-title';
        meta.className = 'product-suggestion-meta';
        title.textContent = card.dataset.employeeName || 'Funcionário';
        meta.textContent = card.dataset.employeeMeta || '';

        button.appendChild(title);
        if (meta.textContent) {
          button.appendChild(meta);
        }
        button.addEventListener('mousedown', function (event) {
          event.preventDefault();
          input.value = card.dataset.employeeName || input.value;
          updateEmployeeList();
          closeEmployeeSuggestions();
          openEmployeeCard(card);
        });
        suggestionList.appendChild(button);
      });

      suggestionList.classList.add('is-open');
    }

    function updateEmployeeList() {
      let visibleCount = 0;
      const matches = matchingCards();

      cards.forEach(function (card) {
        const visible = matches.includes(card);
        card.classList.toggle('is-hidden', !visible);
        if (visible) {
          visibleCount += 1;
        }
      });

      if (countLabel) {
        countLabel.textContent = `${visibleCount} encontrado${visibleCount === 1 ? '' : 's'}`;
      }

      if (emptyState) {
        emptyState.classList.toggle('is-hidden', visibleCount !== 0);
      }
    }

    if (input) {
      input.addEventListener('input', function () {
        activeEmployeeIndex = 0;
        updateEmployeeList();
        if (input.value.trim()) {
          renderEmployeeSuggestions();
        } else {
          closeEmployeeSuggestions();
        }
      });
      input.addEventListener('blur', function () {
        setTimeout(closeEmployeeSuggestions, 120);
      });
      input.addEventListener('keydown', function (event) {
        const matches = input.value.trim() ? matchingCards().slice(0, 8) : [];
        if (event.key === 'ArrowDown' && matches.length) {
          event.preventDefault();
          activeEmployeeIndex = (activeEmployeeIndex + 1) % matches.length;
          renderEmployeeSuggestions();
        } else if (event.key === 'ArrowUp' && matches.length) {
          event.preventDefault();
          activeEmployeeIndex = (activeEmployeeIndex - 1 + matches.length) % matches.length;
          renderEmployeeSuggestions();
        } else if (event.key === 'Enter' && matches.length) {
          const selected = matches[activeEmployeeIndex] || matches[0];
          if (selected) {
            event.preventDefault();
            input.value = selected.dataset.employeeName || input.value;
            updateEmployeeList();
            openEmployeeCard(selected);
            closeEmployeeSuggestions();
          }
        } else if (event.key === 'Escape') {
          event.preventDefault();
          closeEmployeeSuggestions();
        }
      });
      document.addEventListener('mousedown', function (event) {
        if (!searchArea.contains(event.target)) {
          closeEmployeeSuggestions();
        }
      });
      updateEmployeeList();
    }
  });

  document.querySelectorAll('[data-email-list]').forEach(function (list) {
    const hiddenInput = list.querySelector('[data-email-list-hidden]');
    const emailInput = list.querySelector('[data-email-list-input]');
    const addButton = list.querySelector('[data-email-list-add]');
    const itemList = list.querySelector('[data-email-list-items]');

    if (!hiddenInput || !emailInput || !addButton || !itemList) {
      return;
    }

    let recipients = hiddenInput.value.split(',')
      .map(function (email) { return email.trim(); })
      .filter(Boolean);
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    function syncRecipients() {
      hiddenInput.value = recipients.join(', ');
    }

    function renderRecipients() {
      itemList.innerHTML = '';

      if (!recipients.length) {
        const empty = document.createElement('span');
        empty.className = 'email-recipient-empty';
        empty.textContent = 'Nenhum email adicionado';
        itemList.appendChild(empty);
        return;
      }

      recipients.forEach(function (email) {
        const item = document.createElement('span');
        const label = document.createElement('span');
        const removeButton = document.createElement('button');

        item.className = 'email-recipient-chip';
        label.textContent = email;
        removeButton.type = 'button';
        removeButton.className = 'email-recipient-remove';
        removeButton.textContent = 'x';
        removeButton.setAttribute('aria-label', `Remover ${email}`);
        removeButton.addEventListener('click', function () {
          recipients = recipients.filter(function (recipient) {
            return recipient.toLowerCase() !== email.toLowerCase();
          });
          syncRecipients();
          renderRecipients();
        });

        item.appendChild(label);
        item.appendChild(removeButton);
        itemList.appendChild(item);
      });
    }

    function addRecipient() {
      const email = emailInput.value.trim();
      const duplicated = recipients.some(function (recipient) {
        return recipient.toLowerCase() === email.toLowerCase();
      });

      if (!email) {
        return;
      }

      if (!emailPattern.test(email)) {
        emailInput.classList.add('is-invalid');
        emailInput.focus();
        return;
      }

      if (!duplicated) {
        recipients.push(email);
      }

      emailInput.value = '';
      emailInput.classList.remove('is-invalid');
      syncRecipients();
      renderRecipients();
    }

    addButton.addEventListener('click', addRecipient);
    emailInput.addEventListener('input', function () {
      emailInput.classList.remove('is-invalid');
    });
    emailInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        addRecipient();
      }
    });

    syncRecipients();
    renderRecipients();
  });

  if (advancedFilterToggle && advancedFilterPanel) {
    advancedFilterToggle.addEventListener('click', function () {
      advancedFilterPanel.classList.toggle('is-open');
    });
  }

  function normalizeSuggestionText(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  }

  function closeCatalogSuggestionLists(exceptList) {
    document.querySelectorAll('[data-autocomplete-list]').forEach(function (list) {
      if (list !== exceptList) {
        list.classList.remove('is-open');
        list.innerHTML = '';
      }
    });
  }

  function setupRemoteCatalogAutocomplete(autocomplete) {
    const input = autocomplete.querySelector('[data-autocomplete-input]');
    const hiddenInput = autocomplete.querySelector('[data-autocomplete-hidden]');
    const list = autocomplete.querySelector('[data-autocomplete-list]');
    const endpoint = autocomplete.dataset.autocompleteUrl;
    const excludeId = autocomplete.dataset.autocompleteExcludeId || '';
    let debounceTimer = null;
    let requestController = null;
    let options = [];
    let activeOptionIndex = -1;

    function setExpanded(expanded) {
      input.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      list.classList.toggle('is-open', expanded);
    }

    function renderMessage(message, className) {
      list.innerHTML = '';
      const state = document.createElement('div');
      state.className = className || 'product-suggestion-empty';
      state.textContent = message;
      list.appendChild(state);
      setExpanded(true);
    }

    function selectOption(option) {
      input.value = option.value;
      hiddenInput.value = option.id;
      options = [];
      list.innerHTML = '';
      setExpanded(false);
      input.focus();
    }

    function renderOptions() {
      list.innerHTML = '';
      if (!options.length) {
        renderMessage('Nenhum produto encontrado.', 'product-suggestion-empty');
        return;
      }
      options.forEach(function (option, index) {
        const button = document.createElement('button');
        const title = document.createElement('span');
        const meta = document.createElement('span');
        button.type = 'button';
        button.id = `${list.id || 'product-suggestion'}-${index}`;
        button.className = 'product-suggestion-item';
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', index === activeOptionIndex ? 'true' : 'false');
        button.classList.toggle('is-active', index === activeOptionIndex);
        title.className = 'product-suggestion-title';
        meta.className = 'product-suggestion-meta';
        title.textContent = option.title || option.value;
        meta.textContent = option.meta || '';
        button.appendChild(title);
        if (option.meta) button.appendChild(meta);
        button.addEventListener('mousedown', function (event) {
          event.preventDefault();
          selectOption(option);
        });
        list.appendChild(button);
      });
      setExpanded(true);
      const active = list.querySelector('.is-active');
      if (active) {
        input.setAttribute('aria-activedescendant', active.id);
        active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      } else {
        input.removeAttribute('aria-activedescendant');
      }
    }

    async function loadOptions(term) {
      if (requestController) requestController.abort();
      requestController = new AbortController();
      renderMessage('Buscando produtos...', 'product-suggestion-loading');
      const query = new URLSearchParams({ q: term });
      if (excludeId) query.set('exclude_id', excludeId);
      try {
        const response = await fetch(`${endpoint}?${query.toString()}`, {
          headers: { Accept: 'application/json' },
          signal: requestController.signal,
        });
        if (!response.ok) throw new Error('request_failed');
        const payload = await response.json();
        options = Array.isArray(payload.items) ? payload.items : [];
        activeOptionIndex = options.length ? 0 : -1;
        renderOptions();
      } catch (error) {
        if (error.name === 'AbortError') return;
        options = [];
        activeOptionIndex = -1;
        renderMessage('Não foi possível buscar os produtos. Tente novamente.', 'product-suggestion-error');
      }
    }

    input.addEventListener('input', function () {
      hiddenInput.value = '';
      options = [];
      activeOptionIndex = -1;
      window.clearTimeout(debounceTimer);
      if (input.value.trim().length < 2) {
        list.innerHTML = '';
        setExpanded(false);
        return;
      }
      debounceTimer = window.setTimeout(function () {
        loadOptions(input.value.trim());
      }, 320);
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' && options.length) {
        event.preventDefault();
        activeOptionIndex = (activeOptionIndex + 1) % options.length;
        renderOptions();
      } else if (event.key === 'ArrowUp' && options.length) {
        event.preventDefault();
        activeOptionIndex = (activeOptionIndex - 1 + options.length) % options.length;
        renderOptions();
      } else if (event.key === 'Enter' && options.length && list.classList.contains('is-open')) {
        event.preventDefault();
        selectOption(options[Math.max(activeOptionIndex, 0)]);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        list.innerHTML = '';
        setExpanded(false);
      }
    });
    input.addEventListener('blur', function () {
      window.setTimeout(function () { setExpanded(false); }, 140);
    });
  }

  document.querySelectorAll('[data-catalog-autocomplete]').forEach(function (autocomplete) {
    if (autocomplete.dataset.autocompleteUrl) {
      setupRemoteCatalogAutocomplete(autocomplete);
      return;
    }
    const input = autocomplete.querySelector('[data-autocomplete-input]');
    const hiddenInput = autocomplete.querySelector('[data-autocomplete-hidden]');
    const list = autocomplete.querySelector('[data-autocomplete-list]');
    const idMode = autocomplete.hasAttribute('data-autocomplete-id-mode');
    const optionsSourceSelector = autocomplete.dataset.autocompleteOptionsSource;
    const optionsSource = optionsSourceSelector ? document.querySelector(optionsSourceSelector) : autocomplete;
    let activeOptionIndex = 0;
    const options = Array.from((optionsSource || autocomplete).querySelectorAll('[data-autocomplete-option]')).map(function (option) {
      return {
        id: option.dataset.id || '',
        value: option.dataset.value || '',
        title: option.dataset.title || option.dataset.value || '',
        meta: option.dataset.meta || '',
      };
    });

    function matchingOptions() {
      const term = normalizeSuggestionText(input.value);
      if (!term) {
        return [];
      }

      return options.filter(function (option) {
        return normalizeSuggestionText(`${option.title} ${option.meta} ${option.value}`).includes(term);
      }).sort(function (left, right) {
        return compareAutocompleteMatches(
          left,
          right,
          input.value,
          function (option) { return option.title || option.value; },
          function (option) { return `${option.value || ''} ${option.meta || ''}`; }
        );
      }).slice(0, 8);
    }

    function chooseOption(option) {
      input.value = option.value;
      if (hiddenInput) {
        hiddenInput.value = option.id;
      }
      list.classList.remove('is-open');
      list.innerHTML = '';
    }

    function syncHiddenInput() {
      if (!idMode || !hiddenInput) {
        return;
      }

      const selected = options.find(function (option) {
        return normalizeSuggestionText(option.value) === normalizeSuggestionText(input.value);
      });
      hiddenInput.value = selected ? selected.id : '';
    }

    function renderSuggestions() {
      if (!input.value.trim()) {
        list.classList.remove('is-open');
        list.innerHTML = '';
        return;
      }

      const matches = matchingOptions();
      closeCatalogSuggestionLists(list);
      list.innerHTML = '';
      activeOptionIndex = Math.min(activeOptionIndex, Math.max(matches.length - 1, 0));

      if (!matches.length) {
        const empty = document.createElement('div');
        empty.className = 'product-suggestion-empty';
        empty.textContent = 'Nenhuma sugestão encontrada';
        list.appendChild(empty);
        list.classList.add('is-open');
        return;
      }

      matches.forEach(function (option, index) {
        const button = document.createElement('button');
        const title = document.createElement('span');
        const meta = document.createElement('span');

        button.type = 'button';
        button.className = 'product-suggestion-item';
        button.classList.toggle('is-active', index === activeOptionIndex);
        title.className = 'product-suggestion-title';
        meta.className = 'product-suggestion-meta';
        title.textContent = option.title;
        meta.textContent = option.meta;

        button.appendChild(title);
        if (option.meta) {
          button.appendChild(meta);
        }
        button.addEventListener('mousedown', function (event) {
          event.preventDefault();
          chooseOption(option);
        });
        list.appendChild(button);
      });

      list.classList.add('is-open');
    }

    input.addEventListener('input', function () {
      activeOptionIndex = 0;
      syncHiddenInput();
      if (input.value.trim()) {
        renderSuggestions();
      } else {
        list.classList.remove('is-open');
        list.innerHTML = '';
      }
    });
    input.addEventListener('change', syncHiddenInput);
    input.addEventListener('blur', function () {
      setTimeout(function () {
        list.classList.remove('is-open');
      }, 120);
    });
    input.addEventListener('keydown', function (event) {
      const matches = input.value.trim() ? matchingOptions() : [];
      if (event.key === 'ArrowDown' && matches.length) {
        event.preventDefault();
        activeOptionIndex = (activeOptionIndex + 1) % matches.length;
        renderSuggestions();
      } else if (event.key === 'ArrowUp' && matches.length) {
        event.preventDefault();
        activeOptionIndex = (activeOptionIndex - 1 + matches.length) % matches.length;
        renderSuggestions();
      } else if (event.key === 'Enter' && list.classList.contains('is-open')) {
        const selected = matches[activeOptionIndex] || matches[0];
        if (selected) {
          event.preventDefault();
          chooseOption(selected);
        }
      } else if (event.key === 'Escape') {
        event.preventDefault();
        list.classList.remove('is-open');
        list.innerHTML = '';
      }
    });
  });

  document.addEventListener('mousedown', function (event) {
    if (!event.target.closest('[data-catalog-autocomplete]')) {
      closeCatalogSuggestionLists();
    }
  });

  function formatCurrencyInputValue(value) {
    const digits = String(value || '').replace(/\D/g, '');
    const cents = Number.parseInt(digits || '0', 10);
    return (cents / 100).toLocaleString('pt-BR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function isCurrencyInputControlKey(event) {
    if (event.ctrlKey || event.metaKey) {
      return true;
    }

    return [
      'Backspace',
      'Delete',
      'Tab',
      'Enter',
      'Escape',
      'ArrowLeft',
      'ArrowRight',
      'ArrowUp',
      'ArrowDown',
      'Home',
      'End',
    ].includes(event.key);
  }

  function moveCurrencyCaretToEnd(input) {
    window.requestAnimationFrame(function () {
      try {
        input.setSelectionRange(input.value.length, input.value.length);
      } catch (error) {
        // Alguns campos/navegadores nao suportam selecao manual.
      }
    });
  }

  document.querySelectorAll('[data-currency-input]').forEach(function (input) {
    input.setAttribute('inputmode', 'numeric');
    input.setAttribute('autocomplete', 'off');
    // Campos de moeda sao exibidos em formato brasileiro (0,00); pattern numerico bloqueia o envio.
    input.removeAttribute('pattern');
    input.value = formatCurrencyInputValue(input.value);
    input.addEventListener('keydown', function (event) {
      if (isCurrencyInputControlKey(event) || /^[0-9]$/.test(event.key)) {
        return;
      }

      event.preventDefault();
    });
    input.addEventListener('input', function () {
      input.value = formatCurrencyInputValue(input.value);
      moveCurrencyCaretToEnd(input);
      input.dispatchEvent(new Event('currencychange', { bubbles: true }));
    });
    input.addEventListener('paste', function (event) {
      const clipboardText = event.clipboardData ? event.clipboardData.getData('text') : '';
      const digits = clipboardText.replace(/\D/g, '');

      event.preventDefault();
      input.value = formatCurrencyInputValue(digits);
      moveCurrencyCaretToEnd(input);
      input.dispatchEvent(new Event('currencychange', { bubbles: true }));
    });
    input.addEventListener('blur', function () {
      input.value = formatCurrencyInputValue(input.value);
    });
  });

  function applyKitVisibility(toggle) {
    const container = toggle.closest('.product-kit-fields') || document;
    const targetId = toggle.dataset.kitTarget;
    const fields = targetId
      ? [document.getElementById(targetId)].filter(Boolean)
      : Array.from(container.querySelectorAll('.kit-fields'));

    fields.forEach(function (field) {
      field.classList.toggle('is-hidden', !toggle.checked);
      field.querySelectorAll('input, select, textarea').forEach(function (input) {
        input.disabled = !toggle.checked;
      });
    });
  }

  document.querySelectorAll('[data-kit-toggle]').forEach(function (toggle) {
    applyKitVisibility(toggle);
    toggle.addEventListener('change', function () {
      applyKitVisibility(toggle);
    });
  });

  document.querySelectorAll('.product-create-form').forEach(function (form) {
    const costInput = form.querySelector('#cost_price');
    const saleInput = form.querySelector('#sale_price');
    const marginOutput = form.querySelector('[data-product-profit-margin]');
    const amountOutput = form.querySelector('[data-product-profit-amount]');
    const submitButton = form.querySelector('[data-product-form-submit]');
    const resetButton = form.querySelector('[data-product-form-reset]');
    let submitting = false;

    function currencyNumber(value) {
      const normalized = String(value || '0').replace(/\./g, '').replace(',', '.');
      const number = Number.parseFloat(normalized);
      return Number.isFinite(number) ? Math.max(number, 0) : 0;
    }

    function renderProfit() {
      if (!costInput || !saleInput || !marginOutput || !amountOutput) return;
      const cost = currencyNumber(costInput.value);
      const sale = currencyNumber(saleInput.value);
      const profit = sale - cost;
      const margin = sale > 0 ? (profit / sale) * 100 : 0;
      marginOutput.textContent = margin.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%';
      amountOutput.textContent = 'Lucro ' + profit.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
      marginOutput.classList.toggle('is-negative', profit < 0);
    }

    [costInput, saleInput].filter(Boolean).forEach(function (input) {
      input.addEventListener('input', renderProfit);
      input.addEventListener('currencychange', renderProfit);
    });
    renderProfit();

    form.addEventListener('submit', function (event) {
      if (submitting) {
        event.preventDefault();
        return;
      }
      if (!form.checkValidity()) return;
      submitting = true;
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.classList.add('is-loading');
        submitButton.dataset.originalText = submitButton.textContent;
        submitButton.textContent = submitButton.dataset.loadingText || 'Salvando...';
      }
    });

    if (resetButton) {
      resetButton.addEventListener('click', function (event) {
        event.preventDefault();
        const hasContent = Boolean(
          (form.querySelector('#name')?.value || '').trim()
          || (form.querySelector('#barcode')?.value || '').trim()
          || (form.querySelector('[name="category_id"]')?.value || '').trim()
          || currencyNumber(costInput?.value) > 0
          || currencyNumber(saleInput?.value) > 0
          || Number.parseInt(form.querySelector('#stock_quantity')?.value || '0', 10) > 0
          || Number.parseInt(form.querySelector('#min_stock_quantity')?.value || '0', 10) > 0
          || form.querySelector('#is_kit')?.checked
        );
        if (hasContent && !window.confirm('Limpar formulário?\n\nTodos os dados preenchidos serão removidos.')) return;
        form.querySelectorAll('input:not([type="checkbox"]):not([type="hidden"])').forEach(function (input) {
          input.value = input.hasAttribute('data-currency-input') ? '0,00' : (input.type === 'number' ? '0' : '');
        });
        form.querySelectorAll('[data-autocomplete-hidden]').forEach(function (input) { input.value = ''; });
        const activeToggle = form.querySelector('#active');
        const kitToggle = form.querySelector('#is_kit');
        if (activeToggle) activeToggle.checked = true;
        if (kitToggle) {
          kitToggle.checked = false;
          applyKitVisibility(kitToggle);
        }
        renderProfit();
        const firstInput = form.querySelector('#name');
        if (firstInput) firstInput.focus();
      });
    }
  });

  document.querySelectorAll('[data-cash-register-toggle]').forEach(function (row) {
    row.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        row.click();
      }
    });
  });

  const salesFilterPanel = document.querySelector('[data-sales-filters]');
  const salesTable = document.querySelector('[data-sales-table]');
  if (salesFilterPanel && salesTable) {
    const filterInputs = Array.from(salesFilterPanel.querySelectorAll('[data-sales-filter]'));
    const sortInputs = Array.from(salesFilterPanel.querySelectorAll('[data-sales-sort]'));
    const filterOptionButtons = Array.from(salesFilterPanel.querySelectorAll('[data-sales-filter-option]'));
    const clearButton = salesFilterPanel.querySelector('[data-sales-filter-clear]');
    const columnFilters = Array.from(salesFilterPanel.querySelectorAll('.sales-column-filter'));
    const rows = Array.from(salesTable.querySelectorAll('[data-sales-row]'));
    const emptyRow = salesTable.querySelector('[data-sales-empty-row]');
    const tableBody = salesTable.querySelector('tbody');

    function normalizeFilterValue(value) {
      return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim();
    }

    function rowMatchesFilters(row) {
      return filterInputs.every(function (input) {
        const filterValue = normalizeFilterValue(input.value);
        if (!filterValue) {
          return true;
        }
        const key = input.dataset.salesFilter;
        const rowValue = normalizeFilterValue(row.dataset[`sale${key.charAt(0).toUpperCase()}${key.slice(1)}`]);
        return rowValue.includes(filterValue);
      });
    }

    function saleNumberValue(row) {
      const value = Number.parseFloat(row.dataset.saleTotalNumber || '0');
      return Number.isFinite(value) ? value : 0;
    }

    function syncSalesFilterOptions() {
      filterOptionButtons.forEach(function (button) {
        const target = document.getElementById(button.dataset.filterTarget || '');
        const isActive = Boolean(target) && normalizeFilterValue(target.value) === normalizeFilterValue(button.dataset.filterValue || '');
        button.classList.toggle('is-active', isActive);
        button.setAttribute('aria-selected', isActive ? 'true' : 'false');
      });
    }

    function applySalesSorting() {
      if (!tableBody) {
        return;
      }

      const totalSort = sortInputs.find(function (input) {
        return input.dataset.salesSort === 'total' && input.value;
      });
      const orderedRows = rows.slice();

      if (totalSort) {
        orderedRows.sort(function (left, right) {
          const delta = saleNumberValue(left) - saleNumberValue(right);
          return totalSort.value === 'asc' ? delta : -delta;
        });
      }

      orderedRows.forEach(function (row) {
        tableBody.insertBefore(row, emptyRow || null);
      });
    }

    function applySalesFilters() {
      let visibleCount = 0;
      syncSalesFilterOptions();
      filterInputs.forEach(function (input) {
        const filter = input.closest('.sales-column-filter');
        if (filter) {
          filter.classList.toggle('is-filtered', Boolean(normalizeFilterValue(input.value)));
        }
      });
      sortInputs.forEach(function (input) {
        const filter = input.closest('.sales-column-filter');
        if (filter) {
          filter.classList.toggle('is-filtered', Boolean(normalizeFilterValue(input.value)) || filter.classList.contains('is-filtered'));
        }
      });
      rows.forEach(function (row) {
        const visible = rowMatchesFilters(row);
        row.classList.toggle('is-hidden', !visible);
        if (visible) {
          visibleCount += 1;
        }
      });
      if (emptyRow) {
        emptyRow.classList.toggle('is-hidden', visibleCount !== 0 || rows.length === 0);
      }
      applySalesSorting();
    }

    filterInputs.forEach(function (input) {
      input.addEventListener('input', applySalesFilters);
      input.addEventListener('change', applySalesFilters);
    });

    sortInputs.forEach(function (input) {
      input.addEventListener('change', applySalesFilters);
    });

    filterOptionButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        const target = document.getElementById(button.dataset.filterTarget || '');
        if (!target) {
          return;
        }

        target.value = button.dataset.filterValue || '';
        target.dispatchEvent(new Event('change', { bubbles: true }));
        applySalesFilters();
      });
    });

    if (clearButton) {
      clearButton.addEventListener('click', function () {
        filterInputs.forEach(function (input) {
          input.value = '';
        });
        sortInputs.forEach(function (input) {
          input.value = '';
        });
        columnFilters.forEach(function (filter) {
          filter.removeAttribute('open');
          filter.classList.remove('is-filtered');
        });
        applySalesFilters();
      });
    }

    columnFilters.forEach(function (filter) {
      filter.addEventListener('toggle', function () {
        if (!filter.open) {
          return;
        }

        columnFilters.forEach(function (otherFilter) {
          if (otherFilter !== filter) {
            otherFilter.removeAttribute('open');
          }
        });

        const field = filter.querySelector('[data-sales-filter]:not([type="hidden"]), [data-sales-sort], [data-sales-filter-option]');
        if (field) {
          window.setTimeout(function () {
            field.focus();
            if (typeof field.select === 'function') {
              field.select();
            }
          }, 0);
        }
      });
    });

    document.addEventListener('click', function (event) {
      if (!salesFilterPanel.contains(event.target)) {
        columnFilters.forEach(function (filter) {
          filter.removeAttribute('open');
        });
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        columnFilters.forEach(function (filter) {
          filter.removeAttribute('open');
        });
      }
    });

    applySalesFilters();
  }

  const saleForm = document.querySelector('[data-sale-form]');
  if (saleForm) {
    const saleItems = saleForm.querySelector('[data-sale-items]');
    const saleRowTemplate = saleForm.querySelector('[data-sale-row-template]');
    const saleItemsEmpty = saleForm.querySelector('[data-sale-items-empty]');
    const productPickerInput = saleForm.querySelector('[data-sale-picker-search]');
    const productPickerList = saleForm.querySelector('[data-sale-picker-suggestion-list]');
    const quantityModal = saleForm.querySelector('[data-sale-quantity-modal]');
    const quantityProduct = saleForm.querySelector('[data-sale-quantity-product]');
    const quantityMeta = saleForm.querySelector('[data-sale-quantity-meta]');
    const quantityInput = saleForm.querySelector('[data-sale-quantity-input]');
    const quantityCloseButton = saleForm.querySelector('[data-sale-quantity-close]');
    const quantityAddButton = saleForm.querySelector('[data-sale-quantity-add]');
    const totalTarget = saleForm.querySelector('[data-sale-total]');
    const paymentStepTotalTarget = saleForm.querySelector('[data-payment-step-total]');
    const subtotalTarget = saleForm.querySelector('[data-sale-subtotal]');
    const discountLabels = Array.from(saleForm.querySelectorAll('[data-sale-discount-label]'));
    const paidTarget = saleForm.querySelector('[data-paid-total]');
    const missingTarget = saleForm.querySelector('[data-missing-total]');
    const changeTarget = saleForm.querySelector('[data-change-total]');
    const discountInput = saleForm.querySelector('[data-discount-input]');
    const discountOpenButtons = Array.from(saleForm.querySelectorAll('[data-discount-open]'));
    const discountModal = saleForm.querySelector('[data-discount-modal]');
    const discountModalInput = saleForm.querySelector('[data-discount-modal-input]');
    const discountCloseButton = saleForm.querySelector('[data-discount-close]');
    const discountApplyButton = saleForm.querySelector('[data-discount-apply]');
    const discountPercent = saleForm.querySelector('[data-discount-percent]');
    const discountSubtotal = saleForm.querySelector('[data-discount-subtotal]');
    const discountNewTotal = saleForm.querySelector('[data-discount-new-total]');
    const paymentStep = saleForm.querySelector('[data-payment-step]');
    const openPaymentStepButton = saleForm.querySelector('[data-open-payment-step]');
    const closePaymentStepButton = saleForm.querySelector('[data-close-payment-step]');
    const finalizeSaleButton = saleForm.querySelector('[data-finalize-sale]');
    const paymentInputs = Array.from(saleForm.querySelectorAll('[data-payment-input]'));
    let autoPaymentInput = null;
    let autoPaymentValue = '';
    let isAutofillingPayment = false;
    let pendingProduct = null;
    let activeProductIndex = 0;
    let productSuggestionTimer = null;
    let productSearchAbortController = null;
    let currentProductResults = [];
    const productSearchUrl = saleForm.dataset.productSearchUrl || '';
    const productSuggestions = [];
    const productSuggestionById = new Map();
    const productSearchCache = new Map();
    Array.from(document.querySelectorAll('#sale-product-suggestions option')).forEach(function (option) {
      rememberProduct({
        id: option.dataset.id,
        name: option.value,
        barcode: option.dataset.barcode || '',
        price: Number.parseFloat(option.dataset.price || '0'),
        stock: Number.parseInt(option.dataset.stock || '0', 10),
      });
    });

    function parseCurrency(value) {
      const normalized = String(value || '0').replace(/\./g, '').replace(',', '.');
      const amount = Number.parseFloat(normalized);
      return Number.isFinite(amount) ? Math.max(amount, 0) : 0;
    }

    function formatCurrency(value) {
      return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
      }).format(value || 0);
    }

    function formatPercent(value) {
      return `${(value || 0).toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}%`;
    }

    function formatCurrencyField(value) {
      return (value || 0).toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    }

    function rowTotal(row) {
      const productOption = selectedProductOption(row);
      const quantity = Number.parseInt(row.querySelector('[data-quantity-input]').value || '0', 10);
      const price = productOption ? productOption.price : 0;
      return Math.max(quantity || 0, 0) * Math.max(price || 0, 0);
    }

    function selectedProductOption(row) {
      const productId = row.querySelector('[data-product-id]').value;
      return productSuggestionById.get(productId);
    }

    function syncProductId(row) {
      const productOption = selectedProductOption(row);
      const productIdInput = row.querySelector('[data-product-id]');
      if (!productOption) {
        productIdInput.value = '';
      }
    }

    function normalizeSearch(value) {
      return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase();
    }

    function normalizeProduct(product) {
      return {
        id: String(product.id || ''),
        name: String(product.name || ''),
        barcode: String(product.barcode || ''),
        price: Number.parseFloat(product.price || '0'),
        stock: Number.parseInt(product.stock || '0', 10),
      };
    }

    function rememberProduct(product) {
      const normalizedProduct = normalizeProduct(product);
      if (!normalizedProduct.id) {
        return null;
      }

      const existingIndex = productSuggestions.findIndex(function (item) {
        return item.id === normalizedProduct.id;
      });
      if (existingIndex >= 0) {
        productSuggestions[existingIndex] = normalizedProduct;
      } else {
        productSuggestions.push(normalizedProduct);
      }
      productSuggestionById.set(normalizedProduct.id, normalizedProduct);
      return normalizedProduct;
    }

    function localMatchingProducts(term) {
      const normalizedTerm = normalizeSearch(term);
      if (!normalizedTerm) {
        return [];
      }

      return productSuggestions.filter(function (product) {
        return normalizeSearch(product.name).includes(normalizedTerm)
          || normalizeSearch(product.barcode).includes(normalizedTerm)
          || product.id === normalizedTerm;
      }).sort(function (left, right) {
        return compareAutocompleteMatches(
          left,
          right,
          term,
          function (product) { return product.name; },
          function (product) { return `${product.barcode || ''} ${product.id || ''}`; }
        );
      }).slice(0, 8);
    }

    function fetchProductSuggestions(term) {
      const normalizedTerm = normalizeSearch(term);
      if (!normalizedTerm) {
        return Promise.resolve([]);
      }
      if (productSearchCache.has(normalizedTerm)) {
        return Promise.resolve(productSearchCache.get(normalizedTerm));
      }
      if (!productSearchUrl || !window.fetch) {
        const localResults = localMatchingProducts(term);
        productSearchCache.set(normalizedTerm, localResults);
        return Promise.resolve(localResults);
      }

      if (productSearchAbortController) {
        productSearchAbortController.abort();
      }
      productSearchAbortController = new AbortController();

      const url = new URL(productSearchUrl, window.location.origin);
      url.searchParams.set('q', term);
      url.searchParams.set('limit', '8');

      return fetch(url.toString(), {
        headers: { Accept: 'application/json' },
        signal: productSearchAbortController.signal,
      }).then(function (response) {
        if (!response.ok) {
          return localMatchingProducts(term);
        }
        return response.json().then(function (payload) {
          return Array.isArray(payload.products) ? payload.products.map(rememberProduct).filter(Boolean) : [];
        });
      }).then(function (products) {
        productSearchCache.set(normalizedTerm, products);
        return products;
      }).catch(function (error) {
        if (error && error.name === 'AbortError') {
          return [];
        }
        return localMatchingProducts(term);
      });
    }

    function scheduleProductSuggestions() {
      window.clearTimeout(productSuggestionTimer);
      productSuggestionTimer = window.setTimeout(renderProductSuggestions, 120);
    }

    function closeSuggestionLists() {
      if (productPickerList) {
        productPickerList.classList.remove('is-open');
        productPickerList.innerHTML = '';
      }
    }

    function syncActiveProductSuggestion(scrollBehavior) {
      if (!productPickerList) {
        return;
      }

      const suggestionButtons = Array.from(productPickerList.querySelectorAll('.product-suggestion-item'));
      suggestionButtons.forEach(function (button, index) {
        const isActive = index === activeProductIndex;
        button.classList.toggle('is-active', isActive);
        button.setAttribute('aria-selected', isActive ? 'true' : 'false');
      });

      const activeButton = suggestionButtons[activeProductIndex];
      if (!activeButton) {
        return;
      }

      const visibleTop = productPickerList.scrollTop;
      const visibleBottom = visibleTop + productPickerList.clientHeight;
      const itemTop = activeButton.offsetTop;
      const itemBottom = itemTop + activeButton.offsetHeight;
      let targetTop = null;

      if (itemTop < visibleTop) {
        targetTop = itemTop;
      } else if (itemBottom > visibleBottom) {
        targetTop = itemBottom - productPickerList.clientHeight;
      }

      if (targetTop !== null) {
        productPickerList.scrollTo({
          top: Math.max(targetTop, 0),
          behavior: scrollBehavior || 'smooth',
        });
      }
    }

    function setRowProduct(row, product, quantity) {
      row.querySelector('[data-product-search]').value = product.name;
      row.querySelector('[data-product-id]').value = product.id;
      row.querySelector('[data-quantity-input]').value = String(quantity || 1);
    }

    function clearSaleRow(row) {
      row.querySelector('[data-product-search]').value = '';
      row.querySelector('[data-product-id]').value = '';
      row.querySelector('[data-quantity-input]').value = '1';
      row.querySelector('[data-unit-price]').value = formatCurrency(0);
      row.querySelector('[data-stock-available]').value = '0 un.';
      row.querySelector('[data-line-total]').value = formatCurrency(0);
    }

    function createSaleRow() {
      const row = saleRowTemplate.content.firstElementChild.cloneNode(true);
      clearSaleRow(row);
      saleItems.appendChild(row);
      bindSaleRow(row);
      return row;
    }

    function focusProductSearch() {
      if (productPickerInput) {
        productPickerInput.focus();
        productPickerInput.select();
      }
    }

    function renderProductSuggestions() {
      const term = productPickerInput.value.trim();
      if (!term) {
        currentProductResults = [];
        closeSuggestionLists();
        return;
      }

      fetchProductSuggestions(term).then(function (products) {
        if (productPickerInput.value.trim() !== term) {
          return;
        }

        currentProductResults = products;
        productPickerList.innerHTML = '';
        activeProductIndex = Math.min(activeProductIndex, Math.max(products.length - 1, 0));

        if (!products.length) {
          const empty = document.createElement('div');
          empty.className = 'product-suggestion-empty';
          empty.textContent = 'Nenhum produto encontrado';
          productPickerList.appendChild(empty);
          productPickerList.classList.add('is-open');
          return;
        }

        products.forEach(function (product, index) {
          const button = document.createElement('button');
          const title = document.createElement('span');
          const meta = document.createElement('span');

          button.type = 'button';
          button.className = 'product-suggestion-item';
          button.setAttribute('role', 'option');
          title.className = 'product-suggestion-title';
          meta.className = 'product-suggestion-meta';
          title.textContent = product.name;
          const barcodeLabel = product.barcode ? ` · código ${product.barcode}` : '';
          meta.textContent = `${formatCurrency(product.price)}${barcodeLabel} · estoque ${Number.isFinite(product.stock) ? product.stock : 0} un.`;
          button.classList.toggle('is-active', index === activeProductIndex);

          button.appendChild(title);
          button.appendChild(meta);
          button.addEventListener('mousedown', function (event) {
            event.preventDefault();
            openQuantityModal(product);
          });
          productPickerList.appendChild(button);
        });

        productPickerList.classList.add('is-open');
        window.requestAnimationFrame(function () {
          syncActiveProductSuggestion('auto');
        });
      });
    }

    function openQuantityModal(product) {
      if (!quantityModal || !quantityInput || !product) {
        return;
      }

      pendingProduct = product;
      quantityProduct.textContent = product.name;
      quantityMeta.textContent = `${formatCurrency(product.price)} · estoque ${Number.isFinite(product.stock) ? product.stock : 0} un.`;
      quantityInput.value = '1';
      closeSuggestionLists();
      quantityModal.classList.add('is-open');
      quantityModal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('sale-quantity-open');
      setTimeout(function () {
        quantityInput.focus();
        quantityInput.select();
      }, 0);
    }

    function closeQuantityModal() {
      if (!quantityModal) {
        return;
      }

      quantityModal.classList.remove('is-open');
      quantityModal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('sale-quantity-open');
      pendingProduct = null;
      focusProductSearch();
    }

    function addPendingProduct() {
      const quantity = Number.parseInt(quantityInput.value || '1', 10);
      if (!pendingProduct || !Number.isFinite(quantity) || quantity < 1) {
        quantityInput.value = '1';
        quantityInput.focus();
        quantityInput.select();
        return;
      }

      const existingRow = Array.from(saleForm.querySelectorAll('[data-sale-item-row]')).find(function (row) {
        return row.querySelector('[data-product-id]').value === pendingProduct.id;
      });

      if (existingRow) {
        const existingQuantity = Number.parseInt(existingRow.querySelector('[data-quantity-input]').value || '0', 10);
        existingRow.querySelector('[data-quantity-input]').value = String(Math.max(existingQuantity || 0, 0) + quantity);
      } else {
        const row = createSaleRow();
        setRowProduct(row, pendingProduct, quantity);
      }

      productPickerInput.value = '';
      updateSaleTotals();
      closeQuantityModal();
    }

    function updateSaleTotals() {
      let subtotal = 0;
      saleForm.querySelectorAll('[data-sale-item-row]').forEach(function (row) {
        syncProductId(row);
        const productOption = selectedProductOption(row);
        const price = productOption ? productOption.price : 0;
        const stock = productOption ? productOption.stock : 0;
        const unitPriceInput = row.querySelector('[data-unit-price]');
        const stockInput = row.querySelector('[data-stock-available]');
        const stockWarning = row.querySelector('[data-stock-warning]');
        const quantity = Number.parseInt(row.querySelector('[data-quantity-input]').value || '0', 10);
        const totalInput = row.querySelector('[data-line-total]');
        const lineTotal = rowTotal(row);
        const insufficientStock = Boolean(productOption && Math.max(quantity || 0, 0) > stock);
        subtotal += lineTotal;
        unitPriceInput.value = formatCurrency(price);
        stockInput.value = `${Number.isFinite(stock) ? stock : 0} un.`;
        totalInput.value = formatCurrency(lineTotal);
        row.classList.toggle('has-stock-warning', insufficientStock);
        if (stockWarning) {
          stockWarning.classList.toggle('is-visible', insufficientStock);
        }
      });

      if (saleItemsEmpty) {
        saleItemsEmpty.classList.toggle('is-hidden', Boolean(saleForm.querySelector('[data-sale-item-row]')));
      }

      const discount = Math.min(parseCurrency(discountInput ? discountInput.value : '0'), subtotal);
      const discountRate = subtotal > 0 ? (discount / subtotal) * 100 : 0;
      const total = Math.max(subtotal - discount, 0);

      let paid = 0;
      saleForm.querySelectorAll('[data-payment-input]').forEach(function (input) {
        paid += parseCurrency(input.value);
      });

      const missing = Math.max(total - paid, 0);
      const change = Math.max(paid - total, 0);

      if (subtotalTarget) {
        subtotalTarget.textContent = formatCurrency(subtotal);
      }
      discountLabels.forEach(function (label) {
        label.textContent = `${formatCurrency(discount)} (${formatPercent(discountRate)})`;
      });
      if (discountPercent) {
        discountPercent.textContent = `${formatPercent(discountRate)} de desconto`;
      }
      totalTarget.textContent = formatCurrency(total);
      if (paymentStepTotalTarget) {
        paymentStepTotalTarget.textContent = formatCurrency(total);
      }
      paidTarget.textContent = formatCurrency(paid);
      missingTarget.textContent = formatCurrency(missing);
      changeTarget.textContent = formatCurrency(change);
    }

    function currentSubtotalAmount() {
      return Array.from(saleForm.querySelectorAll('[data-sale-item-row]')).reduce(function (sum, row) {
        return sum + rowTotal(row);
      }, 0);
    }

    function updateDiscountPreview() {
      const subtotal = currentSubtotalAmount();
      const requestedDiscount = parseCurrency(discountModalInput ? discountModalInput.value : '0');
      const discount = Math.min(requestedDiscount, subtotal);
      const discountRate = subtotal > 0 ? (discount / subtotal) * 100 : 0;

      if (discountSubtotal) {
        discountSubtotal.textContent = formatCurrency(subtotal);
      }
      if (discountNewTotal) {
        discountNewTotal.textContent = formatCurrency(Math.max(subtotal - discount, 0));
      }
      if (discountPercent) {
        discountPercent.textContent = requestedDiscount > subtotal
          ? `O desconto máximo é ${formatCurrency(subtotal)}`
          : `${formatPercent(discountRate)} de desconto`;
      }
    }

    function openDiscountModal() {
      if (!discountModal || !discountModalInput) {
        return;
      }

      if (quantityModal && quantityModal.classList.contains('is-open')) {
        closeQuantityModal();
      }

      discountModalInput.value = discountInput ? discountInput.value : '0,00';
      discountModal.classList.add('is-open');
      discountModal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('sale-discount-open');
      updateDiscountPreview();
      setTimeout(function () {
        discountModalInput.focus();
        discountModalInput.select();
      }, 0);
    }

    function closeDiscountModal() {
      if (!discountModal) {
        return;
      }

      discountModal.classList.remove('is-open');
      discountModal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('sale-discount-open');
    }

    function applyDiscount() {
      if (discountInput && discountModalInput) {
        const subtotal = currentSubtotalAmount();
        const discount = parseCurrency(discountModalInput.value);
        if (discount > subtotal) {
          updateDiscountPreview();
          discountModalInput.focus();
          discountModalInput.select();
          return;
        }
        discountInput.value = formatCurrencyField(discount);
        if (autoPaymentInput && autoPaymentInput.value === autoPaymentValue) {
          const remaining = Math.max(currentOrderTotal() - paidAmountExcluding(autoPaymentInput), 0);
          autoPaymentInput.value = formatCurrencyField(remaining);
          autoPaymentValue = autoPaymentInput.value;
        }
      }
      updateSaleTotals();
      closeDiscountModal();
    }

    function currentOrderTotal() {
      let subtotal = 0;
      saleForm.querySelectorAll('[data-sale-item-row]').forEach(function (row) {
        subtotal += rowTotal(row);
      });

      const discount = Math.min(parseCurrency(discountInput ? discountInput.value : '0'), subtotal);
      return Math.max(subtotal - discount, 0);
    }

    function currentPaidAmount() {
      return paymentInputs.reduce(function (sum, input) {
        return sum + parseCurrency(input.value);
      }, 0);
    }

    function paidAmountExcluding(excludedInput) {
      return paymentInputs.reduce(function (sum, input) {
        if (input === excludedInput) {
          return sum;
        }
        return sum + parseCurrency(input.value);
      }, 0);
    }

    function removeBlankSaleRows() {
      const rows = Array.from(saleForm.querySelectorAll('[data-sale-item-row]'));
      rows.forEach(function (row) {
        syncProductId(row);
      });

      rows.forEach(function (row) {
        const productIdInput = row.querySelector('[data-product-id]');
        const searchInput = row.querySelector('[data-product-search]');
        const currentRows = saleForm.querySelectorAll('[data-sale-item-row]');
        const isBlank = !productIdInput.value && !searchInput.value.trim();

        if (isBlank && currentRows.length > 1) {
          row.remove();
        }
      });
    }

    function firstInvalidSaleRow() {
      return Array.from(saleForm.querySelectorAll('[data-sale-item-row]')).find(function (row) {
        const searchInput = row.querySelector('[data-product-search]');
        const productIdInput = row.querySelector('[data-product-id]');
        return searchInput.value.trim() && !productIdInput.value;
      });
    }

    function canSubmitSaleByShortcut() {
      removeBlankSaleRows();
      updateSaleTotals();

      const invalidRow = firstInvalidSaleRow();
      if (invalidRow) {
        focusProductSearch();
        return false;
      }

      if (!Array.from(saleForm.querySelectorAll('[data-product-id]')).some(function (input) { return Boolean(input.value); })) {
        focusProductSearch();
        return false;
      }

      const total = currentOrderTotal();
      const paid = currentPaidAmount();
      if (paid + 0.001 < total) {
        openPaymentStep();
        const firstPaymentInput = paymentInputs.find(function (input) { return parseCurrency(input.value) === 0; }) || paymentInputs[0];
        if (firstPaymentInput) {
          firstPaymentInput.focus();
          firstPaymentInput.select();
        }
        return false;
      }

      return true;
    }

    function fillPayment(input) {
      const total = currentOrderTotal();

      if (!paymentInputs.length || total <= 0) {
        return;
      }

      if (autoPaymentInput && autoPaymentInput !== input && autoPaymentInput.value === autoPaymentValue) {
        autoPaymentInput.value = formatCurrencyField(0);
        autoPaymentInput = null;
        autoPaymentValue = '';
      }

      if (input !== autoPaymentInput && parseCurrency(input.value) > 0) {
        updateSaleTotals();
        input.select();
        return;
      }

      const remaining = Math.max(total - paidAmountExcluding(input), 0);
      isAutofillingPayment = true;
      input.value = formatCurrencyField(remaining);
      autoPaymentInput = input;
      autoPaymentValue = input.value;
      isAutofillingPayment = false;
      updateSaleTotals();
      input.select();
    }

    function openPaymentStep() {
      if (!paymentStep) {
        return;
      }

      if (quantityModal && quantityModal.classList.contains('is-open')) {
        closeQuantityModal();
      }

      paymentStep.classList.add('is-open');
      paymentStep.setAttribute('aria-hidden', 'false');
      document.body.classList.add('sale-payment-open');
      updateSaleTotals();
      setTimeout(function () {
        if (paymentInputs[0]) {
          paymentInputs[0].focus();
        }
      }, 0);
    }

    function closePaymentStep() {
      if (paymentStep) {
        paymentStep.classList.remove('is-open');
        paymentStep.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('sale-payment-open');
      }
    }

    function finishSaleByShortcut() {
      if (discountModal && discountModal.classList.contains('is-open')) {
        closeDiscountModal();
      }

      if (paymentStep && paymentStep.classList.contains('is-open')) {
        if (!canSubmitSaleByShortcut()) {
          return;
        }

        if (finalizeSaleButton) {
          finalizeSaleButton.click();
        } else if (saleForm.requestSubmit) {
          saleForm.requestSubmit();
        }
        return;
      }

      openPaymentStep();
    }

    function bindSaleRow(row) {
      row.querySelector('[data-quantity-input]').addEventListener('input', updateSaleTotals);
      row.querySelector('[data-quantity-input]').addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          updateSaleTotals();
          focusProductSearch();
        }
      });
      row.querySelector('[data-remove-sale-item]').addEventListener('click', function () {
        row.remove();
        updateSaleTotals();
        focusProductSearch();
      });
    }

    saleForm.querySelectorAll('[data-sale-item-row]').forEach(bindSaleRow);
    if (productPickerInput && productPickerList) {
      productPickerInput.addEventListener('input', function () {
        activeProductIndex = 0;
        if (productPickerInput.value.trim()) {
          scheduleProductSuggestions();
        } else {
          currentProductResults = [];
          closeSuggestionLists();
        }
      });
      productPickerInput.addEventListener('blur', function () {
        setTimeout(closeSuggestionLists, 120);
      });
      productPickerInput.addEventListener('keydown', function (event) {
        const products = currentProductResults;

        if (event.key === 'ArrowDown' && products.length) {
          event.preventDefault();
          activeProductIndex = (activeProductIndex + 1) % products.length;
          syncActiveProductSuggestion('smooth');
        } else if (event.key === 'ArrowUp' && products.length) {
          event.preventDefault();
          activeProductIndex = (activeProductIndex - 1 + products.length) % products.length;
          syncActiveProductSuggestion('smooth');
        } else if (event.key === 'Home' && products.length) {
          event.preventDefault();
          activeProductIndex = 0;
          syncActiveProductSuggestion('smooth');
        } else if (event.key === 'End' && products.length) {
          event.preventDefault();
          activeProductIndex = products.length - 1;
          syncActiveProductSuggestion('smooth');
        } else if (event.key === 'Enter' && products.length) {
          event.preventDefault();
          openQuantityModal(products[activeProductIndex] || products[0]);
        } else if (event.key === 'Enter' && productPickerInput.value.trim()) {
          event.preventDefault();
          fetchProductSuggestions(productPickerInput.value.trim()).then(function (items) {
            if (items.length) {
              openQuantityModal(items[0]);
            } else {
              renderProductSuggestions();
            }
          });
        } else if (event.key === 'Escape') {
          event.preventDefault();
          currentProductResults = [];
          closeSuggestionLists();
        }
      });
    }

    if (quantityInput) {
      quantityInput.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          addPendingProduct();
        } else if (event.key === 'Escape') {
          event.preventDefault();
          closeQuantityModal();
        }
      });
    }
    if (quantityAddButton) {
      quantityAddButton.addEventListener('click', addPendingProduct);
    }
    if (quantityCloseButton) {
      quantityCloseButton.addEventListener('click', closeQuantityModal);
    }
    if (quantityModal) {
      quantityModal.addEventListener('mousedown', function (event) {
        if (event.target === quantityModal) {
          closeQuantityModal();
        }
      });
    }

    paymentInputs.forEach(function (input) {
      input.addEventListener('input', function () {
        if (!isAutofillingPayment && input === autoPaymentInput) {
          autoPaymentInput = null;
          autoPaymentValue = '';
        }
        updateSaleTotals();
      });
      input.addEventListener('currencychange', updateSaleTotals);
      input.addEventListener('focus', function () {
        fillPayment(input);
      });
      input.addEventListener('click', function () {
        fillPayment(input);
      });
      input.addEventListener('keydown', function (event) {
        const currentIndex = paymentInputs.indexOf(input);
        let nextIndex = currentIndex;

        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
          nextIndex = (currentIndex + 1) % paymentInputs.length;
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
          nextIndex = (currentIndex - 1 + paymentInputs.length) % paymentInputs.length;
        } else {
          return;
        }

        event.preventDefault();
        paymentInputs[nextIndex].focus();
        paymentInputs[nextIndex].select();
      });
    });

    if (discountInput) {
      discountInput.addEventListener('input', updateSaleTotals);
      discountInput.addEventListener('currencychange', updateSaleTotals);
    }

    if (discountModalInput) {
      discountModalInput.addEventListener('input', updateDiscountPreview);
      discountModalInput.addEventListener('currencychange', updateDiscountPreview);
      discountModalInput.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          applyDiscount();
        }
      });
    }

    discountOpenButtons.forEach(function (button) {
      button.addEventListener('click', openDiscountModal);
    });

    if (discountCloseButton) {
      discountCloseButton.addEventListener('click', closeDiscountModal);
    }

    if (discountApplyButton) {
      discountApplyButton.addEventListener('click', applyDiscount);
    }

    if (openPaymentStepButton) {
      openPaymentStepButton.addEventListener('click', openPaymentStep);
    }

    if (closePaymentStepButton) {
      closePaymentStepButton.addEventListener('click', closePaymentStep);
    }

    if (finalizeSaleButton) {
      finalizeSaleButton.addEventListener('click', function (event) {
        if (!canSubmitSaleByShortcut()) {
          event.preventDefault();
        }
      });
    }

    saleForm.addEventListener('submit', function (event) {
      if (!canSubmitSaleByShortcut()) {
        event.preventDefault();
      }
    });

    if (discountModal) {
      discountModal.addEventListener('mousedown', function (event) {
        if (event.target === discountModal) {
          closeDiscountModal();
        }
      });
    }

    document.addEventListener('keydown', function (event) {
      if (event.key === 'F2') {
        event.preventDefault();
        event.stopPropagation();
        finishSaleByShortcut();
      }

      if (event.key === 'F3') {
        event.preventDefault();
        event.stopPropagation();
        openDiscountModal();
      }

      if (event.key === 'Escape') {
        if (quantityModal && quantityModal.classList.contains('is-open')) {
          closeQuantityModal();
        } else if (discountModal && discountModal.classList.contains('is-open')) {
          closeDiscountModal();
        } else if (paymentStep && paymentStep.classList.contains('is-open')) {
          closePaymentStep();
        }
      }
    }, true);

    updateSaleTotals();
    focusProductSearch();
    if (paymentStep && paymentStep.classList.contains('is-open')) {
      paymentStep.setAttribute('aria-hidden', 'false');
      document.body.classList.add('sale-payment-open');
    }

    document.addEventListener('mousedown', function (event) {
      const productPicker = saleForm.querySelector('[data-sale-product-picker]');
      if (!productPicker || !productPicker.contains(event.target)) {
        closeSuggestionLists();
      }
    });
  }

  const reportForm = document.querySelector('[data-report-filter-form]');
  if (reportForm) {
    const periodInput = reportForm.querySelector('[data-report-period]');
    const startInput = reportForm.querySelector('[data-report-start-date]');
    const endInput = reportForm.querySelector('[data-report-end-date]');

    function formatDate(date) {
      return date.toISOString().slice(0, 10);
    }

    function shiftDate(days) {
      const date = new Date();
      date.setHours(12, 0, 0, 0);
      date.setDate(date.getDate() - days);
      return date;
    }

    function applyReportDates() {
      if (!periodInput || !startInput || !endInput || periodInput.value === 'custom') {
        return;
      }

      const daysByPeriod = {
        daily: 0,
        weekly: 7,
        monthly: 30,
        annual: 365,
      };
      const days = daysByPeriod[periodInput.value] || 0;
      const today = shiftDate(0);

      startInput.value = formatDate(shiftDate(days));
      endInput.value = formatDate(today);
    }

    if (periodInput) {
      periodInput.addEventListener('change', applyReportDates);
    }
  }

  document.querySelectorAll('.report-chart').forEach(function (chart) {
    const tooltip = chart.querySelector('[data-report-chart-tooltip]');
    const columns = Array.from(chart.querySelectorAll('[data-chart-label]'));
    if (!tooltip || !columns.length) {
      return;
    }

    function showChartTooltip(column) {
      tooltip.innerHTML = '';
      const label = document.createElement('strong');
      label.textContent = column.dataset.chartLabel || '-';
      tooltip.appendChild(label);

      if (column.dataset.chartCount !== undefined) {
        const count = document.createElement('span');
        const revenue = document.createElement('span');
        count.textContent = `Vendas: ${column.dataset.chartCount || '0'}`;
        revenue.textContent = `Faturamento: ${column.dataset.chartValue || 'R$ 0,00'}`;
        tooltip.appendChild(count);
        tooltip.appendChild(revenue);

        if (column.dataset.chartPeak === 'true') {
          const peak = document.createElement('span');
          peak.className = 'report-chart-tooltip-peak';
          peak.textContent = 'Horário de pico';
          tooltip.appendChild(peak);
        }
      } else {
        const value = document.createElement('span');
        value.textContent = `Total vendido: ${column.dataset.chartValue || 'R$ 0,00'}`;
        tooltip.appendChild(value);
      }
      tooltip.classList.add('is-visible');

      const chartRect = chart.getBoundingClientRect();
      const columnRect = column.getBoundingClientRect();
      const tooltipWidth = tooltip.offsetWidth;
      const preferredLeft = columnRect.left - chartRect.left + (columnRect.width / 2) - (tooltipWidth / 2);
      const maximumLeft = Math.max(chart.clientWidth - tooltipWidth - 8, 8);
      tooltip.style.left = `${Math.min(Math.max(preferredLeft, 8), maximumLeft)}px`;
    }

    function hideChartTooltip() {
      tooltip.classList.remove('is-visible');
    }

    columns.forEach(function (column) {
      column.addEventListener('mouseenter', function () { showChartTooltip(column); });
      column.addEventListener('focus', function () { showChartTooltip(column); });
      column.addEventListener('mouseleave', hideChartTooltip);
      column.addEventListener('blur', hideChartTooltip);
    });
  });
});

document.querySelectorAll('[data-expand-row]').forEach(function (row) {
  row.addEventListener('click', function () {
    const detail = row.nextElementSibling;
    if (!detail || !detail.classList.contains('expandable-detail-row')) {
      return;
    }
    row.classList.toggle('is-expanded');
    detail.classList.toggle('is-visible');
  });
});

document.querySelectorAll('.stock-operation-card').forEach(function (form) {
  const productSelect = form.querySelector('[name="product_id"]');
  const quantityInput = form.querySelector('[name="quantity"]');
  const targetInput = form.querySelector('[name="target_stock"]');
  const modeSelect = form.querySelector('[name="adjustment_mode"]');
  const directionSelect = form.querySelector('[name="direction"]');
  const currentOutput = form.querySelector('[data-stock-current]');
  const resultOutput = form.querySelector('[data-stock-result]');

  function selectedStock() {
    const option = productSelect && productSelect.selectedOptions ? productSelect.selectedOptions[0] : null;
    return Number.parseInt(option ? option.dataset.stock || '0' : '0', 10) || 0;
  }

  function currentQuantity() {
    return Number.parseInt(quantityInput ? quantityInput.value || '0' : '0', 10) || 0;
  }

  function updatePreview() {
    const currentStock = selectedStock();
    let resultStock = currentStock;
    if (targetInput && modeSelect && modeSelect.value === 'target') {
      resultStock = Number.parseInt(targetInput.value || '0', 10) || 0;
    } else if (directionSelect) {
      resultStock = directionSelect.value === 'out' ? currentStock - currentQuantity() : currentStock + currentQuantity();
    } else {
      resultStock = currentStock + currentQuantity();
    }
    if (currentOutput) currentOutput.textContent = `${currentStock} un.`;
    if (resultOutput) resultOutput.textContent = `${resultStock} un.`;
  }

  [productSelect, quantityInput, targetInput, modeSelect, directionSelect].forEach(function (element) {
    if (element) element.addEventListener('input', updatePreview);
    if (element) element.addEventListener('change', updatePreview);
  });
  updatePreview();
});

const destructiveConfirmationModal = document.querySelector('[data-destructive-confirmation-modal]');

if (destructiveConfirmationModal) {
  const confirmationInput = destructiveConfirmationModal.querySelector('[data-destructive-confirmation-input]');
  const confirmationTarget = destructiveConfirmationModal.querySelector('[data-destructive-confirmation-target]');
  const confirmationKind = destructiveConfirmationModal.querySelector('[data-destructive-confirmation-kind]');
  const confirmationError = destructiveConfirmationModal.querySelector('[data-destructive-confirmation-error]');
  const confirmationSubmit = destructiveConfirmationModal.querySelector('[data-destructive-confirmation-submit]');
  const cancellationButtons = destructiveConfirmationModal.querySelectorAll('[data-destructive-confirmation-cancel]');
  let pendingDestructiveForm = null;
  let expectedConfirmation = '';
  let lastFocusedElement = null;

  function confirmationMatches() {
    return confirmationInput && confirmationInput.value.trim() === expectedConfirmation;
  }

  function updateConfirmationState() {
    const matches = confirmationMatches();
    if (confirmationSubmit) confirmationSubmit.disabled = !matches;
    if (confirmationError) confirmationError.hidden = true;
  }

  function closeDestructiveConfirmation() {
    destructiveConfirmationModal.classList.remove('is-open');
    destructiveConfirmationModal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('has-destructive-confirmation');
    pendingDestructiveForm = null;
    expectedConfirmation = '';
    if (confirmationInput) confirmationInput.value = '';
    if (confirmationSubmit) confirmationSubmit.disabled = true;
    if (confirmationError) confirmationError.hidden = true;
    if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') lastFocusedElement.focus();
    lastFocusedElement = null;
  }

  function openDestructiveConfirmation(form) {
    pendingDestructiveForm = form;
    expectedConfirmation = form.dataset.destructiveConfirmation || '';
    lastFocusedElement = document.activeElement;
    if (confirmationTarget) confirmationTarget.textContent = expectedConfirmation;
    if (confirmationKind) confirmationKind.textContent = form.dataset.destructiveKind || 'o registro e seus dados';
    if (confirmationInput) confirmationInput.value = '';
    updateConfirmationState();
    destructiveConfirmationModal.classList.add('is-open');
    destructiveConfirmationModal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('has-destructive-confirmation');
    window.requestAnimationFrame(function () {
      if (confirmationInput) confirmationInput.focus();
    });
  }

  function confirmDestructiveAction() {
    if (!pendingDestructiveForm || !confirmationMatches()) {
      if (confirmationError) confirmationError.hidden = false;
      if (confirmationInput) confirmationInput.focus();
      return;
    }

    const form = pendingDestructiveForm;
    const confirmationField = form.querySelector('input[name="confirmation"]');
    if (!confirmationField) return;
    confirmationField.value = confirmationInput.value.trim();
    form.dataset.destructiveConfirmed = 'true';
    closeDestructiveConfirmation();
    form.requestSubmit();
  }

  document.querySelectorAll('form[data-destructive-confirmation]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (form.dataset.destructiveConfirmed === 'true') {
        delete form.dataset.destructiveConfirmed;
        return;
      }
      event.preventDefault();
      openDestructiveConfirmation(form);
    });
  });

  if (confirmationInput) {
    confirmationInput.addEventListener('input', updateConfirmationState);
    confirmationInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        confirmDestructiveAction();
      }
    });
  }
  if (confirmationSubmit) confirmationSubmit.addEventListener('click', confirmDestructiveAction);
  cancellationButtons.forEach(function (button) {
    button.addEventListener('click', closeDestructiveConfirmation);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && destructiveConfirmationModal.classList.contains('is-open')) {
      event.preventDefault();
      closeDestructiveConfirmation();
    }
  });
}
