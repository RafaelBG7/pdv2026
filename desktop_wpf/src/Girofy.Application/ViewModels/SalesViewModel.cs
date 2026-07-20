using System.Collections.ObjectModel;
using System.Globalization;
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

public sealed class SalesViewModel : ObservableObject, IDisposable
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private string _searchText = string.Empty;
    private CatalogProduct? _selectedSearchProduct;
    private string _quantityText = "1";
    private string _discountText = "0,00";
    private string _moneyText = "0,00";
    private string _pixText = "0,00";
    private string _debitText = "0,00";
    private string _creditText = "0,00";
    private string _errorMessage = string.Empty;
    private string _successMessage = string.Empty;
    private bool _isBusy;
    private bool _isSaleEditorOpen;
    private bool _isPaymentStepOpen;
    private string? _idempotencyKey;
    private SaleReceipt? _receipt;

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
        FillMoneyCommand = new RelayCommand(() => FillRemaining("money"));
        FillPixCommand = new RelayCommand(() => FillRemaining("pix"));
        FillDebitCommand = new RelayCommand(() => FillRemaining("debit"));
        FillCreditCommand = new RelayCommand(() => FillRemaining("credit"));
        FinalizeCommand = new AsyncRelayCommand(FinalizeAsync);
        OpenSaleEditorCommand = new RelayCommand(OpenSaleEditor);
        CloseSaleEditorCommand = new RelayCommand(CloseSaleEditor);
        OpenPaymentStepCommand = new RelayCommand(OpenPaymentStep, () => HasCart && !IsBusy);
        BackToProductsCommand = new RelayCommand(BackToProducts);
        NewSaleCommand = new RelayCommand(StartNewSale);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<CatalogProduct> SearchResults { get; } = [];

    public ObservableCollection<SaleCartItemViewModel> CartItems { get; } = [];

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
                ClearSearchResults();
            }
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

    public string PaidAmountText => FormatMoney(PaidAmount);

    public string MissingAmountText => FormatMoney(MissingAmount);

    public string ChangeAmountText => FormatMoney(ChangeAmount);

    public string CartSummary => CartItems.Count == 1
        ? "1 produto no pedido"
        : $"{CartItems.Count} produtos no pedido";

    public bool HasSearchResults => SearchResults.Count > 0;

    public bool HasCart => CartItems.Count > 0;

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
            }
        }
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

    public RelayCommand OpenSaleEditorCommand { get; }

    public RelayCommand CloseSaleEditorCommand { get; }

    public RelayCommand OpenPaymentStepCommand { get; }

    public RelayCommand BackToProductsCommand { get; }

    public RelayCommand NewSaleCommand { get; }

    public Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_sessionContext.Current is null || !IsAvailable)
        {
            ResetAll();
        }
        return Task.CompletedTask;
    }

    private async Task SearchAsync(CancellationToken cancellationToken)
    {
        var term = SearchText.Trim();
        if (term.Length < 1)
        {
            ErrorMessage = "Digite o nome ou código do produto.";
            ClearSearchResults();
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
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
            foreach (var product in result.Items.OrderBy(
                product => product.Name,
                StringComparer.CurrentCultureIgnoreCase))
            {
                SearchResults.Add(product);
            }
            SelectedSearchProduct = SearchResults.FirstOrDefault(product =>
                string.Equals(product.Barcode, term, StringComparison.OrdinalIgnoreCase))
                ?? SearchResults.FirstOrDefault();
            OnPropertyChanged(nameof(HasSearchResults));
            if (SearchResults.Count == 0)
            {
                ErrorMessage = "Nenhum produto ativo foi encontrado.";
            }
        }
        catch (Exception exception)
        {
            SetSafeError(exception, "Não foi possível pesquisar os produtos agora.");
        }
        finally
        {
            IsBusy = false;
        }
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

    private void FillRemaining(string method)
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
        switch (method)
        {
            case "money": MoneyText = value; break;
            case "pix": PixText = value; break;
            case "debit": DebitText = value; break;
            case "credit": CreditText = value; break;
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
        ResetDraftAfterSuccess();
        IsSaleEditorOpen = true;
        IsPaymentStepOpen = false;
    }

    private void OpenSaleEditor()
    {
        if (HasReceipt)
        {
            StartNewSale();
            return;
        }

        ClearMessages();
        IsSaleEditorOpen = true;
        IsPaymentStepOpen = false;
    }

    private void CloseSaleEditor()
    {
        ClearMessages();
        IsPaymentStepOpen = false;
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
        IsPaymentStepOpen = true;
        if (PaidAmount == 0 && Total > 0)
        {
            FillRemaining("money");
        }
    }

    private void BackToProducts()
    {
        ClearMessages();
        IsPaymentStepOpen = false;
    }

    private void SetPaymentText(ref string field, string value, string propertyName)
    {
        if (SetProperty(ref field, value, propertyName))
        {
            NotifyTotalsChanged();
        }
    }

    private void NotifyCartChanged()
    {
        OnPropertyChanged(nameof(HasCart));
        OnPropertyChanged(nameof(CartSummary));
        OnPropertyChanged(nameof(CanProceedToPayment));
        OpenPaymentStepCommand.NotifyCanExecuteChanged();
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
        OnPropertyChanged(nameof(TotalText));
        OnPropertyChanged(nameof(PaidAmountText));
        OnPropertyChanged(nameof(MissingAmountText));
        OnPropertyChanged(nameof(ChangeAmountText));
    }

    private void NotifySaleEditorStateChanged()
    {
        OnPropertyChanged(nameof(IsProductStepOpen));
        OnPropertyChanged(nameof(IsPaymentStepVisible));
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
        MoneyText = "0,00";
        PixText = "0,00";
        DebitText = "0,00";
        CreditText = "0,00";
        _idempotencyKey = null;
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

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;
}
