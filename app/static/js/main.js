document.addEventListener('DOMContentLoaded', function () {
  const storedTheme = localStorage.getItem('adega-jf-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialTheme = storedTheme || (prefersDark ? 'dark' : 'light');
  const appShell = document.querySelector('.app-shell');
  const sidebarToggle = document.querySelector('[data-sidebar-toggle]');
  const sidebarToggleIcon = document.querySelector('[data-sidebar-toggle-icon]');
  const storedSidebar = localStorage.getItem('adega-jf-sidebar');
  const advancedFilterToggle = document.querySelector('[data-advanced-filter-toggle]');
  const advancedFilterPanel = document.querySelector('[data-advanced-filter-panel]');

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('adega-jf-theme', theme);
    document.querySelectorAll('[data-settings-theme-label]').forEach(function (label) {
      label.textContent = theme === 'dark' ? 'Dark' : 'Light';
    });
    document.querySelectorAll('[data-settings-theme-choice]').forEach(function (button) {
      const active = button.dataset.settingsThemeChoice === theme;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  applyTheme(initialTheme);

  function applySidebar(collapsed) {
    if (!appShell) {
      return;
    }

    appShell.classList.toggle('sidebar-collapsed', collapsed);
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

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function () {
      const collapsed = appShell && appShell.classList.contains('sidebar-collapsed');
      applySidebar(!collapsed);
    });
  }

  document.querySelectorAll('[data-settings-theme-choice]').forEach(function (button) {
    button.addEventListener('click', function () {
      applyTheme(button.dataset.settingsThemeChoice || 'light');
    });
  });

  document.querySelectorAll('[data-settings-tabs]').forEach(function (tabs) {
    const buttons = Array.from(tabs.querySelectorAll('[data-settings-tab]'));
    const panels = Array.from(tabs.querySelectorAll('[data-settings-panel]'));

    function activateTab(tabName) {
      buttons.forEach(function (button) {
        const active = button.dataset.settingsTab === tabName;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      panels.forEach(function (panel) {
        panel.classList.toggle('is-active', panel.dataset.settingsPanel === tabName);
      });
      localStorage.setItem('adega-jf-settings-tab', tabName);
    }

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        activateTab(button.dataset.settingsTab);
      });
    });

    const storedTab = localStorage.getItem('adega-jf-settings-tab');
    if (storedTab && buttons.some(function (button) { return button.dataset.settingsTab === storedTab; })) {
      activateTab(storedTab);
    }
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

  document.querySelectorAll('[data-catalog-autocomplete]').forEach(function (autocomplete) {
    const input = autocomplete.querySelector('[data-autocomplete-input]');
    const hiddenInput = autocomplete.querySelector('[data-autocomplete-hidden]');
    const list = autocomplete.querySelector('[data-autocomplete-list]');
    const idMode = autocomplete.hasAttribute('data-autocomplete-id-mode');
    const options = Array.from(autocomplete.querySelectorAll('[data-autocomplete-option]')).map(function (option) {
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
        return options.slice(0, 8);
      }

      return options.filter(function (option) {
        return normalizeSuggestionText(`${option.title} ${option.meta} ${option.value}`).includes(term);
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
      const matches = matchingOptions();
      closeCatalogSuggestionLists(list);
      list.innerHTML = '';

      if (!matches.length) {
        const empty = document.createElement('div');
        empty.className = 'product-suggestion-empty';
        empty.textContent = 'Nenhuma sugestão encontrada';
        list.appendChild(empty);
        list.classList.add('is-open');
        return;
      }

      matches.forEach(function (option) {
        const button = document.createElement('button');
        const title = document.createElement('span');
        const meta = document.createElement('span');

        button.type = 'button';
        button.className = 'product-suggestion-item';
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
      syncHiddenInput();
      renderSuggestions();
    });
    input.addEventListener('focus', renderSuggestions);
    input.addEventListener('change', syncHiddenInput);
    input.addEventListener('blur', function () {
      setTimeout(function () {
        list.classList.remove('is-open');
      }, 120);
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' && list.classList.contains('is-open')) {
        const first = matchingOptions()[0];
        if (first) {
          event.preventDefault();
          chooseOption(first);
        }
      }
    });
  });

  function formatCurrencyInputValue(value) {
    const digits = String(value || '').replace(/\D/g, '');
    const cents = Number.parseInt(digits || '0', 10);
    return (cents / 100).toLocaleString('pt-BR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  document.querySelectorAll('[data-currency-input]').forEach(function (input) {
    input.value = formatCurrencyInputValue(input.value);
    input.addEventListener('input', function () {
      input.value = formatCurrencyInputValue(input.value);
      input.dispatchEvent(new Event('currencychange', { bubbles: true }));
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

  const saleForm = document.querySelector('[data-sale-form]');
  if (saleForm) {
    const saleItems = saleForm.querySelector('[data-sale-items]');
    const firstRow = saleForm.querySelector('[data-sale-item-row]');
    const addButton = saleForm.querySelector('[data-add-sale-item]');
    const totalTarget = saleForm.querySelector('[data-sale-total]');
    const paymentStepTotalTarget = saleForm.querySelector('[data-payment-step-total]');
    const subtotalTarget = saleForm.querySelector('[data-sale-subtotal]');
    const discountLabel = saleForm.querySelector('[data-sale-discount-label]');
    const paidTarget = saleForm.querySelector('[data-paid-total]');
    const missingTarget = saleForm.querySelector('[data-missing-total]');
    const changeTarget = saleForm.querySelector('[data-change-total]');
    const discountInput = saleForm.querySelector('[data-discount-input]');
    const discountOpenButton = saleForm.querySelector('[data-discount-open]');
    const discountModal = saleForm.querySelector('[data-discount-modal]');
    const discountModalInput = saleForm.querySelector('[data-discount-modal-input]');
    const discountCloseButton = saleForm.querySelector('[data-discount-close]');
    const discountApplyButton = saleForm.querySelector('[data-discount-apply]');
    const discountPercent = saleForm.querySelector('[data-discount-percent]');
    const paymentStep = saleForm.querySelector('[data-payment-step]');
    const openPaymentStepButton = saleForm.querySelector('[data-open-payment-step]');
    const closePaymentStepButton = saleForm.querySelector('[data-close-payment-step]');
    const paymentInputs = Array.from(saleForm.querySelectorAll('[data-payment-input]'));
    let autoPaymentInput = null;
    let autoPaymentValue = '';
    let isAutofillingPayment = false;
    const productSuggestions = Array.from(document.querySelectorAll('#sale-product-suggestions option')).map(function (option) {
      return {
        id: option.dataset.id,
        name: option.value,
        price: Number.parseFloat(option.dataset.price || '0'),
        stock: Number.parseInt(option.dataset.stock || '0', 10),
      };
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
      const searchInput = row.querySelector('[data-product-search]');
      return productSuggestions.find(function (option) {
        return option.name === searchInput.value;
      });
    }

    function syncProductId(row) {
      const productOption = selectedProductOption(row);
      const productIdInput = row.querySelector('[data-product-id]');
      productIdInput.value = productOption ? productOption.id : '';
    }

    function normalizeSearch(value) {
      return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase();
    }

    function matchingProducts(term) {
      const normalizedTerm = normalizeSearch(term);
      if (!normalizedTerm) {
        return productSuggestions.slice(0, 8);
      }

      return productSuggestions.filter(function (product) {
        return normalizeSearch(product.name).includes(normalizedTerm);
      }).slice(0, 8);
    }

    function closeSuggestionLists(exceptList) {
      saleForm.querySelectorAll('[data-product-suggestion-list]').forEach(function (list) {
        if (list !== exceptList) {
          list.classList.remove('is-open');
          list.innerHTML = '';
        }
      });
    }

    function chooseProduct(row, product) {
      row.querySelector('[data-product-search]').value = product.name;
      row.querySelector('[data-product-id]').value = product.id;
      const list = row.querySelector('[data-product-suggestion-list]');
      list.classList.remove('is-open');
      list.innerHTML = '';
      updateSaleTotals();
    }

    function firstMatchingProduct(row) {
      const input = row.querySelector('[data-product-search]');
      const exactMatch = selectedProductOption(row);
      return exactMatch || matchingProducts(input.value)[0] || null;
    }

    function clearSaleRow(row) {
      row.querySelector('[data-product-search]').value = '';
      row.querySelector('[data-product-id]').value = '';
      row.querySelector('[data-product-suggestion-list]').innerHTML = '';
      row.querySelector('[data-product-suggestion-list]').classList.remove('is-open');
      row.querySelector('[data-quantity-input]').value = '1';
      row.querySelector('[data-unit-price]').value = formatCurrency(0);
      row.querySelector('[data-stock-available]').value = '0 un.';
      row.querySelector('[data-line-total]').value = formatCurrency(0);
    }

    function createSaleRow() {
      const row = firstRow.cloneNode(true);
      clearSaleRow(row);
      saleItems.appendChild(row);
      bindSaleRow(row);
      return row;
    }

    function focusProductSearch(row) {
      const input = row.querySelector('[data-product-search]');
      input.focus();
      input.select();
    }

    function registerCurrentRow(row) {
      const product = firstMatchingProduct(row);
      const quantityInput = row.querySelector('[data-quantity-input]');
      const quantity = Number.parseInt(quantityInput.value || '0', 10);

      if (!product) {
        renderProductSuggestions(row);
        row.querySelector('[data-product-search]').focus();
        return;
      }

      if (!quantity || quantity < 1) {
        quantityInput.value = '1';
      }

      chooseProduct(row, product);
      const nextRow = createSaleRow();
      updateSaleTotals();
      focusProductSearch(nextRow);
    }

    function renderProductSuggestions(row) {
      const input = row.querySelector('[data-product-search]');
      const list = row.querySelector('[data-product-suggestion-list]');
      const products = matchingProducts(input.value);

      closeSuggestionLists(list);
      list.innerHTML = '';

      if (!products.length) {
        const empty = document.createElement('div');
        empty.className = 'product-suggestion-empty';
        empty.textContent = 'Nenhum produto encontrado';
        list.appendChild(empty);
        list.classList.add('is-open');
        return;
      }

      products.forEach(function (product) {
        const button = document.createElement('button');
        const title = document.createElement('span');
        const meta = document.createElement('span');

        button.type = 'button';
        button.className = 'product-suggestion-item';
        title.className = 'product-suggestion-title';
        meta.className = 'product-suggestion-meta';
        title.textContent = product.name;
        meta.textContent = `${formatCurrency(product.price)} · estoque ${Number.isFinite(product.stock) ? product.stock : 0} un.`;

        button.appendChild(title);
        button.appendChild(meta);
        button.addEventListener('mousedown', function (event) {
          event.preventDefault();
          chooseProduct(row, product);
        });
        list.appendChild(button);
      });

      list.classList.add('is-open');
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
        const totalInput = row.querySelector('[data-line-total]');
        const lineTotal = rowTotal(row);
        subtotal += lineTotal;
        unitPriceInput.value = formatCurrency(price);
        stockInput.value = `${Number.isFinite(stock) ? stock : 0} un.`;
        totalInput.value = formatCurrency(lineTotal);
      });

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
      if (discountLabel) {
        discountLabel.textContent = `${formatCurrency(discount)} (${formatPercent(discountRate)})`;
      }
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

    function openDiscountModal() {
      if (!discountModal || !discountModalInput) {
        return;
      }

      discountModalInput.value = discountInput ? discountInput.value : '0,00';
      discountModal.classList.add('is-open');
      discountModal.setAttribute('aria-hidden', 'false');
      updateSaleTotals();
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
    }

    function applyDiscount() {
      if (discountInput && discountModalInput) {
        discountInput.value = discountModalInput.value;
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

    function fillPayment(input) {
      const total = currentOrderTotal();

      if (!paymentInputs.length || total <= 0) {
        return;
      }

      if (autoPaymentInput && autoPaymentInput !== input && autoPaymentInput.value === autoPaymentValue) {
        autoPaymentInput.value = formatCurrencyField(0);
      }

      if (input !== autoPaymentInput && parseCurrency(input.value) > 0) {
        updateSaleTotals();
        return;
      }

      isAutofillingPayment = true;
      input.value = formatCurrencyField(total);
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

      paymentStep.classList.add('is-open');
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
      }
    }

    function finishSaleByShortcut() {
      if (discountModal && discountModal.classList.contains('is-open')) {
        closeDiscountModal();
      }

      openPaymentStep();
    }

    function bindSaleRow(row) {
      row.querySelector('[data-product-search]').addEventListener('input', function () {
        syncProductId(row);
        renderProductSuggestions(row);
        updateSaleTotals();
      });
      row.querySelector('[data-product-search]').addEventListener('focus', function () {
        renderProductSuggestions(row);
      });
      row.querySelector('[data-product-search]').addEventListener('blur', function () {
        setTimeout(function () {
          row.querySelector('[data-product-suggestion-list]').classList.remove('is-open');
        }, 120);
      });
      row.querySelector('[data-product-search]').addEventListener('change', updateSaleTotals);
      row.querySelector('[data-quantity-input]').addEventListener('input', updateSaleTotals);
      row.querySelector('[data-product-search]').addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          registerCurrentRow(row);
        }
      });
      row.querySelector('[data-quantity-input]').addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          registerCurrentRow(row);
        }
      });
      row.querySelector('[data-remove-sale-item]').addEventListener('click', function () {
        if (saleForm.querySelectorAll('[data-sale-item-row]').length > 1) {
          row.remove();
          updateSaleTotals();
        }
      });
    }

    bindSaleRow(firstRow);
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
      discountModalInput.addEventListener('input', function () {
        if (discountInput) {
          discountInput.value = discountModalInput.value;
        }
        updateSaleTotals();
      });
      discountModalInput.addEventListener('currencychange', updateSaleTotals);
      discountModalInput.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          applyDiscount();
        }
      });
    }

    if (discountOpenButton) {
      discountOpenButton.addEventListener('click', openDiscountModal);
    }

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
        finishSaleByShortcut();
      }

      if (event.key === 'F3') {
        event.preventDefault();
        openDiscountModal();
      }

      if (event.key === 'Escape' && discountModal && discountModal.classList.contains('is-open')) {
        closeDiscountModal();
      }
    });

    addButton.addEventListener('click', function () {
      const row = createSaleRow();
      focusProductSearch(row);
    });

    updateSaleTotals();

    document.addEventListener('mousedown', function (event) {
      if (!saleForm.contains(event.target)) {
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
});
