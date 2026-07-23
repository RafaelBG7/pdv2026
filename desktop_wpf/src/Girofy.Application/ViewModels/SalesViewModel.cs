using System.Collections.ObjectModel;
using System.Globalization;
using System.Text;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class SaleCartItemViewModel : ObservableObject
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");
    private int _quantity;

    public SaleCartItemViewModel(CatalogProduct product, int quantity)
    {
        Product = product;
        _quantity = quantity;
    }

    public event EventHandler? QuantityChanged;

    public CatalogProduct Product { get; }

    public int ProductId => Product.Id;

    public string Name => Product.Name;

    public string UnitPriceText => FormatMoney(Product.SalePrice);

    public string StockText => $"{Product.StockQuantity} un.";

    public int Quantity
    {
        get => _quantity;
        set
        {
            var safeValue = Math.Clamp(value, 1, 100000);
            if (!SetProperty(ref _quantity, safeValue))
            {
                return;
            }
            OnPropertyChanged(nameof(LineTotal));
            OnPropertyChanged(nameof(LineTotalText));
            QuantityChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    public decimal LineTotal => Product.SalePrice * Quantity;

    public string LineTotalText => FormatMoney(LineTotal);

    private static string FormatMoney(decimal value) =>
        $"R$ {value.ToString("N2", BrazilianCulture)}";
}

public sealed class SaleHistoryItemViewModel : ObservableObject
{
    private bool _isExpanded;
    private bool _isLoadingDetail;
    private SaleReceipt? _detail;
    private string _detailError = string.Empty;

    public SaleHistoryItemViewModel(DashboardRecentSale sale) => Sale = sale;

    public DashboardRecentSale Sale { get; }

    public int Id => Sale.Id;

    public string NumberText => Sale.NumberText;

    public string DateText => Sale.DateText;

    public string UserName => Sale.UserName;

    public string FinalAmountText => Sale.FinalAmountText;

    public string PaymentText => Sale.PaymentText;

    public string PaymentStatus => Sale.PaymentStatus;

    public string PaymentStatusText =>
        string.Equals(Sale.PaymentStatus, "paid", StringComparison.OrdinalIgnoreCase)
            ? "Pago"
            : "Pendente";

    public string ExpandHint => IsExpanded ? "Ocultar" : "Detalhes";

    public bool IsExpanded
    {
        get => _isExpanded;
        set
        {
            if (SetProperty(ref _isExpanded, value))
            {
                OnPropertyChanged(nameof(ExpandHint));
            }
        }
    }

    public bool IsLoadingDetail
    {
        get => _isLoadingDetail;
        set => SetProperty(ref _isLoadingDetail, value);
    }

    public SaleReceipt? Detail
    {
        get => _detail;
        set
        {
            if (SetProperty(ref _detail, value))
            {
                OnPropertyChanged(nameof(HasDetail));
                OnPropertyChanged(nameof(DetailPaymentsText));
            }
        }
    }

    public string DetailError
    {
        get => _detailError;
        set
        {
            if (SetProperty(ref _detailError, value))
            {
                OnPropertyChanged(nameof(HasDetailError));
            }
        }
    }

    public bool HasDetail => Detail is not null;

    public bool HasDetailError => !string.IsNullOrWhiteSpace(DetailError);

    public string DetailPaymentsText => Detail is null
        ? string.Empty
        : string.Join(" + ", Detail.Payments.Select(payment => $"{payment.Label}: {payment.AmountText}"));
}

public sealed class SalesViewModel : ObservableObject, IDisposable
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private string _searchText = string.Empty;
    private CatalogProduct? _selectedSearchProduct;
    private string _quantityText = "1";
    private string _discountText = "0,00";
    private string _draftDiscountText = "0,00";
    private string _moneyText = "0,00";
    private string _pixText = "0,00";
    private string _debitText = "0,00";
    private string _creditText = "0,00";
    private string _errorMessage = string.Empty;
    private string _successMessage = string.Empty;
    private bool _isBusy;
    private bool _isSearching;
    private bool _isSaleEditorOpen;
    private bool _isPaymentStepOpen;
    private bool _isDiscountPopupOpen;
    private bool _isOpenCashPromptOpen;
    private bool _updatingPaymentText;
    private string _openingCashText = "0,00";
    private CancellationTokenSource? _searchDebounceCts;
    private string? _idempotencyKey;
    private SaleReceipt? _receipt;
    private readonly HashSet<string> _manualPaymentMethods = [];
    private readonly HashSet<string> _autoPaymentMethods = [];

    public SalesViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        SearchCommand = new AsyncRelayCommand(SearchAsync);
        AddProductCommand = new RelayCommand(AddSelectedProduct);
        RemoveItemCommand = new RelayCommand<SaleCartItemViewModel>(RemoveItem);
        IncreaseQuantityCommand = new RelayCommand<SaleCartItemViewModel>(
            item => item.Quantity++);
        DecreaseQuantityCommand = new RelayCommand<SaleCartItemViewModel>(
            item => item.Quantity--,
            item => item.Quantity > 1);
        FillMoneyCommand = new RelayCommand(() => FillRemaining("money", markAsManual: true));
        FillPixCommand = new RelayCommand(() => FillRemaining("pix", markAsManual: true));
        FillDebitCommand = new RelayCommand(() => FillRemaining("debit", markAsManual: true));
        FillCreditCommand = new RelayCommand(() => FillRemaining("credit", markAsManual: true));
        FinalizeCommand = new AsyncRelayCommand(FinalizeAsync);
        OpenSaleEditorCommand = new AsyncRelayCommand(OpenSaleEditorAsync);
        CloseSaleEditorCommand = new RelayCommand(CloseSaleEditor);
        ConfirmOpenCashBeforeSaleCommand = new AsyncRelayCommand(ConfirmOpenCashBeforeSaleAsync, () => !IsBusy);
        CancelOpenCashBeforeSaleCommand = new RelayCommand(CancelOpenCashBeforeSale);
        OpenPaymentStepCommand = new RelayCommand(OpenPaymentStep, () => HasCart && !IsBusy);
        BackToProductsCommand = new RelayCommand(BackToProducts);
        OpenDiscountPopupCommand = new RelayCommand(OpenDiscountPopup, () => HasCart && !IsBusy);
        CloseDiscountPopupCommand = new RelayCommand(CloseDiscountPopup);
        ApplyDiscountCommand = new RelayCommand(ApplyDiscount);
        NewSaleCommand = new RelayCommand(StartNewSale);
        ToggleTodaySaleCommand = new RelayCommand<SaleHistoryItemViewModel>(
            sale => _ = ToggleTodaySaleAsync(sale));
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<CatalogProduct> SearchResults { get; } = [];

    public ObservableCollection<SaleCartItemViewModel> CartItems { get; } = [];

    public ObservableCollection<SaleHistoryItemViewModel> TodaySales { get; } = [];

    public string SearchText
    {
        get => _searchText;
        set
        {
            if (!SetProperty(ref _searchText, value))
            {
                return;
            }
            if (string.IsNullOrWhiteSpace(value))
            {
                CancelPendingSearch();
                ClearSearchResults();
                return;
            }

            QueueSearch();
        }
    }

    public CatalogProduct? SelectedSearchProduct
    {
        get => _selectedSearchProduct;
        set => SetProperty(ref _selectedSearchProduct, value);
    }

    public string QuantityText
    {
        get => _quantityText;
        set => SetProperty(ref _quantityText, value);
    }

    public string DiscountText
    {
        get => _discountText;
        set
        {
            if (SetProperty(ref _discountText, value))
            {
                NotifyTotalsChanged();
            }
        }
    }

    public string DraftDiscountText
    {
        get => _draftDiscountText;
        set
        {
            if (SetProperty(ref _draftDiscountText, value))
            {
                NotifyDraftDiscountChanged();
            }
        }
    }

    public string MoneyText
    {
        get => _moneyText;
        set => SetPaymentText(ref _moneyText, value, nameof(MoneyText));
    }

    public string PixText
    {
        get => _pixText;
        set => SetPaymentText(ref _pixText, value, nameof(PixText));
    }

    public string DebitText
    {
        get => _debitText;
        set => SetPaymentText(ref _debitText, value, nameof(DebitText));
    }

    public string CreditText
    {
        get => _creditText;
        set => SetPaymentText(ref _creditText, value, nameof(CreditText));
    }

    public decimal Subtotal => CartItems.Sum(item => item.LineTotal);

    public decimal DiscountAmount => ParsedMoneyOrZero(DiscountText);

    public decimal Total => Math.Max(0, Subtotal - DiscountAmount);

    public decimal DraftDiscountAmount => ParsedMoneyOrZero(DraftDiscountText);

    public decimal DraftTotalAfterDiscount => Math.Max(0, Subtotal - DraftDiscountAmount);

    public decimal PaidAmount =>
        ParsedMoneyOrZero(MoneyText) +
        ParsedMoneyOrZero(PixText) +
        ParsedMoneyOrZero(DebitText) +
        ParsedMoneyOrZero(CreditText);

    public decimal MissingAmount => Math.Max(0, Total - PaidAmount);

    public decimal ChangeAmount => Math.Max(0, PaidAmount - Total);

    public string SubtotalText => FormatMoney(Subtotal);

    public string DiscountAmountText => FormatMoney(DiscountAmount);

    public string TotalText => FormatMoney(Total);

    public string DiscountPercentText => FormatPercent(DiscountAmount, Subtotal);

    public string DraftDiscountAmountText => FormatMoney(DraftDiscountAmount);

    public string DraftDiscountPercentText => FormatPercent(DraftDiscountAmount, Subtotal);

    public string DraftTotalAfterDiscountText => FormatMoney(DraftTotalAfterDiscount);

    public string PaidAmountText => FormatMoney(PaidAmount);

    public string MissingAmountText => FormatMoney(MissingAmount);

    public string ChangeAmountText => FormatMoney(ChangeAmount);

    public string CartSummary => CartItems.Count == 1
        ? "1 produto no pedido"
        : $"{CartItems.Count} produtos no pedido";

    public bool HasSearchResults => SearchResults.Count > 0;

    public bool HasCart => CartItems.Count > 0;

    public bool HasTodaySales => TodaySales.Count > 0;

    public bool HasNoTodaySales => !HasTodaySales;

    public SaleReceipt? Receipt
    {
        get => _receipt;
        private set
        {
            if (SetProperty(ref _receipt, value))
            {
                OnPropertyChanged(nameof(HasReceipt));
                OnPropertyChanged(nameof(HasNoReceipt));
                OnPropertyChanged(nameof(ReceiptPaymentsText));
                OnPropertyChanged(nameof(ReceiptStockWarningsText));
                NotifySaleEditorStateChanged();
            }
        }
    }

    public bool HasReceipt => Receipt is not null;

    public bool HasNoReceipt => Receipt is null;

    public string ReceiptPaymentsText => Receipt is null
        ? string.Empty
        : string.Join(" + ", Receipt.Payments.Select(payment => $"{payment.Label}: {payment.AmountText}"));

    public string ReceiptStockWarningsText => Receipt is null
        ? string.Empty
        : string.Join(" | ", Receipt.StockWarnings);

    public bool IsAvailable
    {
        get
        {
            var permissions = _sessionContext.Current?.User.Permissions;
            return permissions is not null &&
                permissions.TryGetValue("can_manage_sales", out var allowed) &&
                allowed;
        }
    }

    public string ErrorMessage
    {
        get => _errorMessage;
        private set
        {
            if (SetProperty(ref _errorMessage, value))
            {
                OnPropertyChanged(nameof(HasError));
            }
        }
    }

    public string SuccessMessage
    {
        get => _successMessage;
        private set
        {
            if (SetProperty(ref _successMessage, value))
            {
                OnPropertyChanged(nameof(HasSuccess));
            }
        }
    }

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    public bool HasSuccess => !string.IsNullOrWhiteSpace(SuccessMessage);

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetProperty(ref _isBusy, value))
            {
                OnPropertyChanged(nameof(CanProceedToPayment));
                OpenPaymentStepCommand.NotifyCanExecuteChanged();
                OpenDiscountPopupCommand.NotifyCanExecuteChanged();
                ConfirmOpenCashBeforeSaleCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public bool IsSearching
    {
        get => _isSearching;
        private set => SetProperty(ref _isSearching, value);
    }

    public bool IsSaleEditorOpen
    {
        get => _isSaleEditorOpen;
        private set
        {
            if (SetProperty(ref _isSaleEditorOpen, value))
            {
                NotifySaleEditorStateChanged();
            }
        }
    }

    public bool IsPaymentStepOpen
    {
        get => _isPaymentStepOpen;
        private set
        {
            if (SetProperty(ref _isPaymentStepOpen, value))
            {
                NotifySaleEditorStateChanged();
            }
        }
    }

    public bool IsProductStepOpen => IsSaleEditorOpen && !IsPaymentStepOpen && !HasReceipt;

    public bool IsPaymentStepVisible => IsSaleEditorOpen && IsPaymentStepOpen && !HasReceipt;

    public bool IsDiscountPopupOpen
    {
        get => _isDiscountPopupOpen;
        private set
        {
            if (SetProperty(ref _isDiscountPopupOpen, value))
            {
                OnPropertyChanged(nameof(IsDiscountPopupVisible));
            }
        }
    }

    public bool IsDiscountPopupVisible => IsSaleEditorOpen && IsDiscountPopupOpen && !HasReceipt;

    public bool IsOpenCashPromptOpen
    {
        get => _isOpenCashPromptOpen;
        private set => SetProperty(ref _isOpenCashPromptOpen, value);
    }

    public string OpeningCashText
    {
        get => _openingCashText;
        set
        {
            var normalizedValue = NormalizePaymentText(value);
            SetProperty(ref _openingCashText, normalizedValue);
        }
    }

    public bool CanProceedToPayment => HasCart && !IsBusy;

    public AsyncRelayCommand SearchCommand { get; }

    public RelayCommand AddProductCommand { get; }

    public RelayCommand<SaleCartItemViewModel> RemoveItemCommand { get; }

    public RelayCommand<SaleCartItemViewModel> IncreaseQuantityCommand { get; }

    public RelayCommand<SaleCartItemViewModel> DecreaseQuantityCommand { get; }

    public RelayCommand FillMoneyCommand { get; }

    public RelayCommand FillPixCommand { get; }

    public RelayCommand FillDebitCommand { get; }

    public RelayCommand FillCreditCommand { get; }

    public AsyncRelayCommand FinalizeCommand { get; }

    public AsyncRelayCommand OpenSaleEditorCommand { get; }

    public RelayCommand CloseSaleEditorCommand { get; }

    public AsyncRelayCommand ConfirmOpenCashBeforeSaleCommand { get; }

    public RelayCommand CancelOpenCashBeforeSaleCommand { get; }

    public RelayCommand OpenPaymentStepCommand { get; }

    public RelayCommand BackToProductsCommand { get; }

    public RelayCommand OpenDiscountPopupCommand { get; }

    public RelayCommand CloseDiscountPopupCommand { get; }

    public RelayCommand ApplyDiscountCommand { get; }

    public RelayCommand NewSaleCommand { get; }

    public RelayCommand<SaleHistoryItemViewModel> ToggleTodaySaleCommand { get; }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_sessionContext.Current is null || !IsAvailable)
        {
            ResetAll();
            return;
        }

        await LoadTodaySalesAsync(cancellationToken);
    }

    private Task SearchAsync(CancellationToken cancellationToken) =>
        SearchProductsAsync(showMessages: true, cancellationToken);

    private async Task ToggleTodaySaleAsync(SaleHistoryItemViewModel? sale)
    {
        if (sale is null)
        {
            return;
        }

        if (sale.IsExpanded)
        {
            sale.IsExpanded = false;
            return;
        }

        foreach (var item in TodaySales.Where(item => !ReferenceEquals(item, sale)))
        {
            item.IsExpanded = false;
        }

        sale.IsExpanded = true;
        if (sale.Detail is not null || sale.IsLoadingDetail)
        {
            return;
        }

        var session = RequireSession();
        sale.IsLoadingDetail = true;
        sale.DetailError = string.Empty;
        try
        {
            var detail = await _apiClient.GetSaleDetailAsync(
                session.AccessToken,
                sale.Id,
                CancellationToken.None);
            if (!IsSameSession(session))
            {
                return;
            }

            sale.Detail = detail;
        }
        catch (Exception exception)
        {
            sale.DetailError = exception switch
            {
                GirofyApiException apiException => apiException.Message,
                TaskCanceledException => "O servidor demorou para responder.",
                HttpRequestException => "Não foi possível conectar ao servidor.",
                _ => "Não foi possível carregar os detalhes desta venda.",
            };
        }
        finally
        {
            sale.IsLoadingDetail = false;
        }
    }

    private async Task SearchProductsAsync(bool showMessages, CancellationToken cancellationToken)
    {
        var term = SearchText.Trim();
        if (term.Length < 1)
        {
            if (showMessages)
            {
                ErrorMessage = "Digite o nome ou código do produto.";
            }
            ClearSearchResults();
            return;
        }

        var session = RequireSession();
        IsSearching = true;
        if (showMessages)
        {
            ClearMessages();
        }
        try
        {
            var result = await _apiClient.GetCatalogProductsAsync(
                session.AccessToken,
                term,
                null,
                "active",
                "name",
                1,
                30,
                cancellationToken);
            if (!IsSameSession(session))
            {
                return;
            }

            SearchResults.Clear();
            foreach (var product in RankSearchResults(result.Items, term))
            {
                SearchResults.Add(product);
            }
            SelectedSearchProduct = SearchResults.FirstOrDefault();
            OnPropertyChanged(nameof(HasSearchResults));
            if (SearchResults.Count == 0 && showMessages)
            {
                ErrorMessage = "Nenhum produto ativo foi encontrado.";
            }
        }
        catch (Exception exception)
        {
            if (showMessages)
            {
                SetSafeError(exception, "Não foi possível pesquisar os produtos agora.");
            }
            else
            {
                ClearSearchResults();
            }
        }
        finally
        {
            IsSearching = false;
        }
    }

    private static IEnumerable<CatalogProduct> RankSearchResults(IEnumerable<CatalogProduct> products, string term)
    {
        var normalizedTerm = NormalizeSearchText(term);
        return products
            .Where(product => ProductMatchesSearch(product, normalizedTerm))
            .OrderBy(product => GetProductSearchRank(product, normalizedTerm))
            .ThenBy(product => NormalizeSearchText(product.Name), StringComparer.OrdinalIgnoreCase)
            .ThenBy(product => product.Name, StringComparer.CurrentCultureIgnoreCase)
            .Take(12);
    }

    private static bool ProductMatchesSearch(CatalogProduct product, string normalizedTerm)
    {
        var name = NormalizeSearchText(product.Name);
        var barcode = NormalizeSearchText(product.Barcode);
        return name.Contains(normalizedTerm, StringComparison.OrdinalIgnoreCase)
               || barcode.Contains(normalizedTerm, StringComparison.OrdinalIgnoreCase);
    }

    private static int GetProductSearchRank(CatalogProduct product, string normalizedTerm)
    {
        var barcode = NormalizeSearchText(product.Barcode);
        if (string.Equals(barcode, normalizedTerm, StringComparison.OrdinalIgnoreCase))
        {
            return 0;
        }

        if (barcode.StartsWith(normalizedTerm, StringComparison.OrdinalIgnoreCase))
        {
            return 1;
        }

        var name = NormalizeSearchText(product.Name);
        if (name.StartsWith(normalizedTerm, StringComparison.OrdinalIgnoreCase))
        {
            return 2;
        }

        if (name.Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .Any(part => part.StartsWith(normalizedTerm, StringComparison.OrdinalIgnoreCase)))
        {
            return 3;
        }

        if (name.Contains(normalizedTerm, StringComparison.OrdinalIgnoreCase))
        {
            return 4;
        }

        if (barcode.Contains(normalizedTerm, StringComparison.OrdinalIgnoreCase))
        {
            return 5;
        }

        return 6;
    }

    private static string NormalizeSearchText(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var normalized = value.Trim().Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(normalized.Length);
        foreach (var character in normalized)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.ToUpperInvariant(character));
            }
        }

        return builder.ToString().Normalize(NormalizationForm.FormC);
    }

    private void QueueSearch()
    {
        CancelPendingSearch();
        var cts = new CancellationTokenSource();
        _searchDebounceCts = cts;
        _ = SearchAfterDelayAsync(cts);
    }

    private async Task SearchAfterDelayAsync(CancellationTokenSource cts)
    {
        try
        {
            await Task.Delay(220, cts.Token);
            await SearchProductsAsync(showMessages: false, cts.Token);
        }
        catch (OperationCanceledException)
        {
        }
        finally
        {
            if (ReferenceEquals(_searchDebounceCts, cts))
            {
                _searchDebounceCts = null;
            }
            cts.Dispose();
        }
    }

    private void CancelPendingSearch()
    {
        _searchDebounceCts?.Cancel();
        _searchDebounceCts = null;
    }

    private void AddSelectedProduct()
    {
        var product = SelectedSearchProduct;
        if (product is null)
        {
            ErrorMessage = "Selecione um produto da busca.";
            return;
        }
        if (!int.TryParse(QuantityText.Trim(), out var quantity) || quantity < 1 || quantity > 100000)
        {
            ErrorMessage = "Informe uma quantidade inteira maior que zero.";
            return;
        }

        ClearMessages();
        var existing = CartItems.FirstOrDefault(item => item.ProductId == product.Id);
        if (existing is not null)
        {
            existing.Quantity = Math.Min(100000, existing.Quantity + quantity);
        }
        else
        {
            var item = new SaleCartItemViewModel(product, quantity);
            item.QuantityChanged += HandleCartQuantityChanged;
            CartItems.Add(item);
        }

        SearchText = string.Empty;
        QuantityText = "1";
        ClearSearchResults();
        NotifyCartChanged();
    }

    private void RemoveItem(SaleCartItemViewModel item)
    {
        item.QuantityChanged -= HandleCartQuantityChanged;
        CartItems.Remove(item);
        NotifyCartChanged();
    }

    private void HandleCartQuantityChanged(object? sender, EventArgs e)
    {
        DecreaseQuantityCommand.NotifyCanExecuteChanged();
        NotifyTotalsChanged();
    }

    public void AutoCompletePaymentIfEmpty(string method)
    {
        if (!IsPaymentStepVisible || Total <= 0)
        {
            return;
        }
        if (_manualPaymentMethods.Contains(method))
        {
            return;
        }

        ClearAutoFilledPaymentsExcept(method);
        if (MissingAmount > 0 || PaymentAmount(method) > 0)
        {
            FillRemaining(method);
        }
    }

    private void FillRemaining(string method, bool markAsManual = false)
    {
        var paidWithoutTarget = method switch
        {
            "money" => PaidAmount - ParsedMoneyOrZero(MoneyText),
            "pix" => PaidAmount - ParsedMoneyOrZero(PixText),
            "debit" => PaidAmount - ParsedMoneyOrZero(DebitText),
            "credit" => PaidAmount - ParsedMoneyOrZero(CreditText),
            _ => PaidAmount,
        };
        var value = Math.Max(0, Total - paidWithoutTarget).ToString("N2", BrazilianCulture);
        SetPaymentAmount(method, value, markAsManual);
    }

    private void ClearAutoFilledPaymentsExcept(string method)
    {
        foreach (var autoMethod in _autoPaymentMethods.ToArray())
        {
            if (string.Equals(autoMethod, method, StringComparison.Ordinal))
            {
                continue;
            }

            SetPaymentAmount(autoMethod, "0,00");
        }
    }

    private decimal PaymentAmount(string method) => method switch
    {
        "money" => ParsedMoneyOrZero(MoneyText),
        "pix" => ParsedMoneyOrZero(PixText),
        "debit" => ParsedMoneyOrZero(DebitText),
        "credit" => ParsedMoneyOrZero(CreditText),
        _ => 0,
    };

    private void SetPaymentAmount(string method, string value, bool markAsManual = false)
    {
        _updatingPaymentText = true;
        try
        {
            switch (method)
            {
                case "money": MoneyText = value; break;
                case "pix": PixText = value; break;
                case "debit": DebitText = value; break;
                case "credit": CreditText = value; break;
            }
        }
        finally
        {
            _updatingPaymentText = false;
        }

        if (markAsManual)
        {
            _manualPaymentMethods.Add(method);
            _autoPaymentMethods.Remove(method);
            return;
        }

        _manualPaymentMethods.Remove(method);
        if (ParsedMoneyOrZero(value) > 0)
        {
            _autoPaymentMethods.Add(method);
        }
        else
        {
            _autoPaymentMethods.Remove(method);
        }
    }

    private async Task FinalizeAsync(CancellationToken cancellationToken)
    {
        if (CartItems.Count == 0)
        {
            ErrorMessage = "Adicione pelo menos um produto à venda.";
            return;
        }
        if (!TryParseMoney(DiscountText, out var discount) || discount > Subtotal)
        {
            ErrorMessage = "Informe um desconto válido e menor que o subtotal.";
            return;
        }
        if (!TryBuildPayments(out var payments))
        {
            return;
        }
        if (payments.Sum(payment => payment.Amount) < Subtotal - discount)
        {
            ErrorMessage = $"Ainda falta pagar {MissingAmountText}.";
            return;
        }

        var session = RequireSession();
        _idempotencyKey ??= $"windows-{Guid.NewGuid():N}";
        var items = CartItems
            .Select(item => new SaleLineRequest(item.ProductId, item.Quantity))
            .ToArray();

        IsBusy = true;
        ClearMessages();
        try
        {
            var receipt = await _apiClient.CreateSaleAsync(
                session.AccessToken,
                _idempotencyKey,
                items,
                discount,
                payments,
                cancellationToken);
            if (!IsSameSession(session))
            {
                return;
            }

            Receipt = receipt;
            SuccessMessage = receipt.AlreadyProcessed
                ? $"{receipt.SaleNumberText} já estava registrada e foi recuperada sem duplicação."
                : $"{receipt.SaleNumberText} finalizada com sucesso.";
            await LoadTodaySalesAsync(cancellationToken);
            ResetDraftAfterSuccess();
            IsPaymentStepOpen = false;
            IsSaleEditorOpen = false;
        }
        catch (Exception exception)
        {
            SetSafeError(exception, "Não foi possível finalizar a venda. O pedido foi preservado.");
        }
        finally
        {
            IsBusy = false;
        }
    }

    private bool TryBuildPayments(out IReadOnlyList<SalePaymentRequest> payments)
    {
        var values = new[]
        {
            (Method: "money", Text: MoneyText),
            (Method: "pix", Text: PixText),
            (Method: "debit", Text: DebitText),
            (Method: "credit", Text: CreditText),
        };
        var result = new List<SalePaymentRequest>();
        foreach (var value in values)
        {
            if (!TryParseMoney(value.Text, out var amount))
            {
                ErrorMessage = "Revise os valores informados nas formas de pagamento.";
                payments = [];
                return false;
            }
            if (amount > 0)
            {
                result.Add(new SalePaymentRequest(value.Method, amount));
            }
        }
        payments = result;
        return true;
    }

    private void StartNewSale()
    {
        Receipt = null;
        SuccessMessage = string.Empty;
        ErrorMessage = string.Empty;
        IsOpenCashPromptOpen = false;
        ResetDraftAfterSuccess();
        IsSaleEditorOpen = true;
        IsPaymentStepOpen = false;
    }

    private async Task OpenSaleEditorAsync(CancellationToken cancellationToken)
    {
        if (HasReceipt)
        {
            StartNewSale();
            return;
        }

        ClearMessages();
        IsOpenCashPromptOpen = false;
        var session = RequireSession();
        IsBusy = true;
        try
        {
            var snapshot = await _apiClient.GetCashRegisterSummaryAsync(session.AccessToken, cancellationToken);
            if (!IsSameSession(session))
            {
                return;
            }

            if (snapshot.CurrentRegister?.IsOpen == true)
            {
                IsDiscountPopupOpen = false;
                IsPaymentStepOpen = false;
                IsSaleEditorOpen = true;
                return;
            }

            OpeningCashText = "0,00";
            IsDiscountPopupOpen = false;
            IsPaymentStepOpen = false;
            IsSaleEditorOpen = false;
            ErrorMessage = "O caixa está fechado. Abra o caixa para registrar a venda.";
            IsOpenCashPromptOpen = true;
        }
        catch (Exception exception)
        {
            SetSafeError(exception, "Não foi possível verificar o caixa agora.");
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task ConfirmOpenCashBeforeSaleAsync(CancellationToken cancellationToken)
    {
        if (!TryParseMoney(OpeningCashText, out var openingAmount))
        {
            ErrorMessage = "Informe um valor inicial válido para abrir o caixa.";
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var snapshot = await _apiClient.OpenCashRegisterAsync(session.AccessToken, openingAmount, cancellationToken);
            if (!IsSameSession(session))
            {
                return;
            }

            if (snapshot.CurrentRegister?.IsOpen != true)
            {
                ErrorMessage = "Não foi possível abrir o caixa.";
                return;
            }

            IsOpenCashPromptOpen = false;
            OpeningCashText = "0,00";
            IsDiscountPopupOpen = false;
            IsPaymentStepOpen = false;
            IsSaleEditorOpen = true;
        }
        catch (Exception exception)
        {
            SetSafeError(exception, "Não foi possível abrir o caixa agora.");
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void CancelOpenCashBeforeSale()
    {
        ClearMessages();
        IsOpenCashPromptOpen = false;
        OpeningCashText = "0,00";
    }

    private void CloseSaleEditor()
    {
        ClearMessages();
        IsDiscountPopupOpen = false;
        IsPaymentStepOpen = false;
        IsOpenCashPromptOpen = false;
        IsSaleEditorOpen = false;
    }

    private void OpenPaymentStep()
    {
        if (!HasCart)
        {
            ErrorMessage = "Adicione pelo menos um produto antes de finalizar.";
            return;
        }

        ClearMessages();
        IsDiscountPopupOpen = false;
        IsPaymentStepOpen = true;
        if (PaidAmount == 0 && Total > 0)
        {
            FillRemaining("money");
        }
    }

    private void BackToProducts()
    {
        ClearMessages();
        IsDiscountPopupOpen = false;
        IsPaymentStepOpen = false;
    }

    private void OpenDiscountPopup()
    {
        if (!HasCart)
        {
            ErrorMessage = "Adicione pelo menos um produto antes de aplicar desconto.";
            return;
        }

        ClearMessages();
        DraftDiscountText = DiscountText;
        IsDiscountPopupOpen = true;
    }

    private void CloseDiscountPopup()
    {
        ClearMessages();
        IsDiscountPopupOpen = false;
    }

    private void ApplyDiscount()
    {
        if (!TryParseMoney(DraftDiscountText, out var discount) || discount > Subtotal)
        {
            ErrorMessage = "Informe um desconto válido e menor que o subtotal.";
            return;
        }

        DiscountText = discount.ToString("N2", BrazilianCulture);
        ClearMessages();
        IsDiscountPopupOpen = false;
    }

    private void SetPaymentText(ref string field, string value, string propertyName)
    {
        var normalizedValue = NormalizePaymentText(value);
        if (SetProperty(ref field, normalizedValue, propertyName))
        {
            if (!_updatingPaymentText)
            {
                var method = PaymentMethodFromProperty(propertyName);
                if (method is not null)
                {
                    _manualPaymentMethods.Add(method);
                    _autoPaymentMethods.Remove(method);
                }
            }
            NotifyTotalsChanged();
        }
    }

    private static string NormalizePaymentText(string value) =>
        string.IsNullOrWhiteSpace(value) ? "0,00" : value.Trim();

    private void NotifyCartChanged()
    {
        OnPropertyChanged(nameof(HasCart));
        OnPropertyChanged(nameof(CartSummary));
        OnPropertyChanged(nameof(CanProceedToPayment));
        OpenPaymentStepCommand.NotifyCanExecuteChanged();
        OpenDiscountPopupCommand.NotifyCanExecuteChanged();
        NotifyTotalsChanged();
    }

    private void NotifyTotalsChanged()
    {
        OnPropertyChanged(nameof(Subtotal));
        OnPropertyChanged(nameof(DiscountAmount));
        OnPropertyChanged(nameof(Total));
        OnPropertyChanged(nameof(PaidAmount));
        OnPropertyChanged(nameof(MissingAmount));
        OnPropertyChanged(nameof(ChangeAmount));
        OnPropertyChanged(nameof(SubtotalText));
        OnPropertyChanged(nameof(DiscountAmountText));
        OnPropertyChanged(nameof(DiscountPercentText));
        OnPropertyChanged(nameof(TotalText));
        OnPropertyChanged(nameof(PaidAmountText));
        OnPropertyChanged(nameof(MissingAmountText));
        OnPropertyChanged(nameof(ChangeAmountText));
        NotifyDraftDiscountChanged();
    }

    private void NotifyDraftDiscountChanged()
    {
        OnPropertyChanged(nameof(DraftDiscountAmount));
        OnPropertyChanged(nameof(DraftTotalAfterDiscount));
        OnPropertyChanged(nameof(DraftDiscountAmountText));
        OnPropertyChanged(nameof(DraftDiscountPercentText));
        OnPropertyChanged(nameof(DraftTotalAfterDiscountText));
    }

    private void NotifySaleEditorStateChanged()
    {
        OnPropertyChanged(nameof(IsProductStepOpen));
        OnPropertyChanged(nameof(IsPaymentStepVisible));
        OnPropertyChanged(nameof(IsDiscountPopupVisible));
    }

    private void ClearSearchResults()
    {
        SearchResults.Clear();
        SelectedSearchProduct = null;
        OnPropertyChanged(nameof(HasSearchResults));
    }

    private void ResetDraftAfterSuccess()
    {
        foreach (var item in CartItems)
        {
            item.QuantityChanged -= HandleCartQuantityChanged;
        }
        CartItems.Clear();
        SearchText = string.Empty;
        QuantityText = "1";
        DiscountText = "0,00";
        DraftDiscountText = "0,00";
        MoneyText = "0,00";
        PixText = "0,00";
        DebitText = "0,00";
        CreditText = "0,00";
        OpeningCashText = "0,00";
        IsDiscountPopupOpen = false;
        IsOpenCashPromptOpen = false;
        _idempotencyKey = null;
        _manualPaymentMethods.Clear();
        _autoPaymentMethods.Clear();
        ClearSearchResults();
        NotifyCartChanged();
    }

    private void ResetAll()
    {
        Receipt = null;
        ResetDraftAfterSuccess();
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        IsBusy = false;
        IsPaymentStepOpen = false;
        IsSaleEditorOpen = false;
        TodaySales.Clear();
        OnPropertyChanged(nameof(HasTodaySales));
        OnPropertyChanged(nameof(HasNoTodaySales));
        OnPropertyChanged(nameof(IsAvailable));
    }

    private void HandleSessionChanged(object? sender, EventArgs e) => ResetAll();

    private AuthSession RequireSession() => _sessionContext.Current
        ?? throw new GirofyApiException(
            "Sua sessão terminou. Entre novamente para continuar.",
            "session_required",
            401);

    private bool IsSameSession(AuthSession session) => string.Equals(
        _sessionContext.Current?.AccessToken,
        session.AccessToken,
        StringComparison.Ordinal);

    private void ClearMessages()
    {
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
    }

    private void SetSafeError(Exception exception, string fallback)
    {
        ErrorMessage = exception switch
        {
            GirofyApiException apiException => apiException.Message,
            TaskCanceledException => "O servidor demorou para responder. O pedido foi preservado.",
            HttpRequestException => "Não foi possível conectar ao servidor. O pedido foi preservado.",
            _ => fallback,
        };
    }

    private static decimal ParsedMoneyOrZero(string text) =>
        TryParseMoney(text, out var value) ? value : 0;

    private static bool TryParseMoney(string text, out decimal value)
    {
        var normalized = (text ?? string.Empty).Trim();
        if (string.IsNullOrEmpty(normalized))
        {
            value = 0;
            return true;
        }
        var culture = normalized.Contains(',') ? BrazilianCulture : CultureInfo.InvariantCulture;
        return decimal.TryParse(normalized, NumberStyles.Number, culture, out value) && value >= 0;
    }

    private static string FormatMoney(decimal value) =>
        $"R$ {value.ToString("N2", BrazilianCulture)}";

    private static string FormatPercent(decimal value, decimal total)
    {
        if (total <= 0)
        {
            return "0,00%";
        }

        var percent = value / total * 100;
        return $"{percent.ToString("N2", BrazilianCulture)}%";
    }

    private async Task LoadTodaySalesAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !IsAvailable)
        {
            TodaySales.Clear();
            OnPropertyChanged(nameof(HasTodaySales));
            OnPropertyChanged(nameof(HasNoTodaySales));
            return;
        }

        try
        {
            var snapshot = await _apiClient.GetTodaySalesHistoryAsync(session.AccessToken, cancellationToken);
            if (!IsSameSession(session))
            {
                return;
            }

            TodaySales.Clear();
            foreach (var sale in snapshot.Sales)
            {
                TodaySales.Add(new SaleHistoryItemViewModel(sale));
            }
            OnPropertyChanged(nameof(HasTodaySales));
            OnPropertyChanged(nameof(HasNoTodaySales));
        }
        catch
        {
            TodaySales.Clear();
            OnPropertyChanged(nameof(HasTodaySales));
            OnPropertyChanged(nameof(HasNoTodaySales));
        }
    }

    private static string? PaymentMethodFromProperty(string propertyName) => propertyName switch
    {
        nameof(MoneyText) => "money",
        nameof(PixText) => "pix",
        nameof(DebitText) => "debit",
        nameof(CreditText) => "credit",
        _ => null,
    };

    public void Dispose()
    {
        CancelPendingSearch();
        _sessionContext.Changed -= HandleSessionChanged;
    }
}
