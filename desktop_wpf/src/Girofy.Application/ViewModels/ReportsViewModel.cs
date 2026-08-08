using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class ReportsViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private CatalogFilterOption _selectedPeriod;
    private CatalogFilterOption _selectedMetric;
    private CatalogFilterOption _selectedProductSort;
    private string _productSearchText = string.Empty;
    private string _startDateText = string.Empty;
    private string _endDateText = string.Empty;
    private string _errorMessage = string.Empty;
    private bool _isBusy;
    private bool _isInitialized;
    private bool _isSummaryTabSelected = true;
    private ReportsSnapshot _snapshot = new();
    private ProductReportSnapshot _productSnapshot = new();

    public ReportsViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        PeriodOptions =
        [
            new("daily", "Diário"),
            new("weekly", "Semanal"),
            new("monthly", "Mensal"),
            new("annual", "Anual"),
            new("custom", "Personalizado"),
        ];
        MetricOptions =
        [
            new("revenue", "Faturamento"),
            new("quantity", "Quantidade"),
        ];
        ProductSortOptions =
        [
            new("quantity_desc", "Mais vendidos"),
            new("revenue_desc", "Maior faturamento"),
            new("profit_desc", "Maior lucro"),
            new("stock_asc", "Menor estoque"),
            new("no_sales", "Sem venda"),
        ];
        _selectedPeriod = PeriodOptions[0];
        _selectedMetric = MetricOptions[0];
        _selectedProductSort = ProductSortOptions[0];
        RefreshCommand = new AsyncRelayCommand(RefreshAsync, () => CanViewReports && !IsBusy);
        ApplyFiltersCommand = new AsyncRelayCommand(ApplyFiltersAsync, () => CanViewReports && !IsBusy);
        ApplyProductFiltersCommand = new AsyncRelayCommand(ApplyProductFiltersAsync, () => CanViewReports && !IsBusy);
        PreviousProductPageCommand = new AsyncRelayCommand(
            PreviousProductPageAsync,
            () => CanViewReports && !IsBusy && ProductSnapshot.Pagination.HasPrevious);
        NextProductPageCommand = new AsyncRelayCommand(
            NextProductPageAsync,
            () => CanViewReports && !IsBusy && ProductSnapshot.Pagination.HasNext);
        ShowSummaryTabCommand = new RelayCommand(() => IsSummaryTabSelected = true);
        ShowProductsTabCommand = new RelayCommand(() => IsSummaryTabSelected = false);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public IReadOnlyList<CatalogFilterOption> PeriodOptions { get; }

    public IReadOnlyList<CatalogFilterOption> MetricOptions { get; }

    public IReadOnlyList<CatalogFilterOption> ProductSortOptions { get; }

    public CatalogFilterOption SelectedPeriod
    {
        get => _selectedPeriod;
        set => SetProperty(ref _selectedPeriod, value);
    }

    public CatalogFilterOption SelectedMetric
    {
        get => _selectedMetric;
        set => SetProperty(ref _selectedMetric, value);
    }

    public CatalogFilterOption SelectedProductSort
    {
        get => _selectedProductSort;
        set => SetProperty(ref _selectedProductSort, value);
    }

    public string ProductSearchText
    {
        get => _productSearchText;
        set => SetProperty(ref _productSearchText, value);
    }

    public string StartDateText
    {
        get => _startDateText;
        set => SetProperty(ref _startDateText, value);
    }

    public string EndDateText
    {
        get => _endDateText;
        set => SetProperty(ref _endDateText, value);
    }

    public ReportsSnapshot Snapshot
    {
        get => _snapshot;
        private set
        {
            if (SetProperty(ref _snapshot, value))
            {
                OnPropertyChanged(nameof(Summary));
                OnPropertyChanged(nameof(PaymentTotals));
                OnPropertyChanged(nameof(TopProducts));
                OnPropertyChanged(nameof(ChartBuckets));
                OnPropertyChanged(nameof(HasSales));
            }
        }
    }

    public ReportSummary Summary => Snapshot.Summary;

    public IReadOnlyList<ReportPaymentTotal> PaymentTotals => Snapshot.PaymentTotals;

    public IReadOnlyList<ReportTopProduct> TopProducts => Snapshot.TopProducts;

    public IReadOnlyList<ReportChartBucket> ChartBuckets => Snapshot.Chart.Buckets;

    public bool HasSales => Summary.SalesCount > 0;

    public ProductReportSnapshot ProductSnapshot
    {
        get => _productSnapshot;
        private set
        {
            if (SetProperty(ref _productSnapshot, value))
            {
                OnPropertyChanged(nameof(ProductSummary));
                OnPropertyChanged(nameof(ProductRows));
                OnPropertyChanged(nameof(ProductPagination));
                OnPropertyChanged(nameof(HasProductRows));
                NotifyProductCommands();
            }
        }
    }

    public ProductReportSummary ProductSummary => ProductSnapshot.Summary;

    public IReadOnlyList<ProductReportItem> ProductRows => ProductSnapshot.Items;

    public ReportPagination ProductPagination => ProductSnapshot.Pagination;

    public bool HasProductRows => ProductRows.Count > 0;

    public bool IsSummaryTabSelected
    {
        get => _isSummaryTabSelected;
        private set
        {
            if (SetProperty(ref _isSummaryTabSelected, value))
            {
                OnPropertyChanged(nameof(IsProductsTabSelected));
            }
        }
    }

    public bool IsProductsTabSelected => !IsSummaryTabSelected;

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

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetProperty(ref _isBusy, value))
            {
                RefreshCommand.NotifyCanExecuteChanged();
                ApplyFiltersCommand.NotifyCanExecuteChanged();
                ApplyProductFiltersCommand.NotifyCanExecuteChanged();
                NotifyProductCommands();
            }
        }
    }

    public bool CanViewReports => HasPermission("can_view_reports");

    public bool IsAvailable => CanViewReports;

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand ApplyFiltersCommand { get; }

    public AsyncRelayCommand ApplyProductFiltersCommand { get; }

    public AsyncRelayCommand PreviousProductPageCommand { get; }

    public AsyncRelayCommand NextProductPageCommand { get; }

    public RelayCommand ShowSummaryTabCommand { get; }

    public RelayCommand ShowProductsTabCommand { get; }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_sessionContext.Current is null || !CanViewReports)
        {
            Reset();
            return;
        }

        if (_isInitialized)
        {
            return;
        }

        await LoadAsync(cancellationToken);
    }

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;

    private void HandleSessionChanged(object? sender, EventArgs e) => Reset();

    private async Task RefreshAsync(CancellationToken cancellationToken) => await LoadAsync(cancellationToken);

    private async Task ApplyFiltersAsync(CancellationToken cancellationToken)
    {
        _isInitialized = false;
        await LoadAsync(cancellationToken);
    }

    private async Task ApplyProductFiltersAsync(CancellationToken cancellationToken)
        => await LoadProductReportAsync(1, cancellationToken);

    private async Task PreviousProductPageAsync(CancellationToken cancellationToken)
        => await LoadProductReportAsync(ProductSnapshot.Pagination.Page - 1, cancellationToken);

    private async Task NextProductPageAsync(CancellationToken cancellationToken)
        => await LoadProductReportAsync(ProductSnapshot.Pagination.Page + 1, cancellationToken);

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            Snapshot = await _apiClient.GetReportsSummaryAsync(
                session.AccessToken,
                new ReportsQuery(
                    SelectedPeriod.Value,
                    SelectedMetric.Value,
                    NormalizeDate(StartDateText),
                    NormalizeDate(EndDateText)),
                cancellationToken);
            ProductSnapshot = await _apiClient.GetProductReportsAsync(
                session.AccessToken,
                BuildProductReportsQuery(1),
                cancellationToken);
            _isInitialized = true;
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LoadProductReportAsync(int page, CancellationToken cancellationToken)
    {
        var session = RequireSession();
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            ProductSnapshot = await _apiClient.GetProductReportsAsync(
                session.AccessToken,
                BuildProductReportsQuery(page),
                cancellationToken);
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            IsBusy = false;
        }
    }

    private ProductReportsQuery BuildProductReportsQuery(int page) => new(
        SelectedPeriod.Value,
        NormalizeDate(StartDateText),
        NormalizeDate(EndDateText),
        ProductSearchText,
        SelectedProductSort.Value,
        Math.Max(1, page),
        25);

    private static string? NormalizeDate(string value)
    {
        var trimmed = value.Trim();
        return string.IsNullOrWhiteSpace(trimmed) ? null : trimmed;
    }

    private bool HasPermission(string permission)
    {
        var permissions = _sessionContext.Current?.User.Permissions;
        return permissions is not null &&
            permissions.TryGetValue(permission, out var allowed) &&
            allowed;
    }

    private AuthSession RequireSession() => _sessionContext.Current
        ?? throw new GirofyApiException(
            "Sua sessão terminou. Entre novamente para continuar.",
            "session_required",
            401);

    private void SetSafeError(Exception exception)
    {
        ErrorMessage = exception switch
        {
            GirofyApiException apiException => apiException.Message,
            TaskCanceledException => "O servidor demorou para responder. Tente novamente.",
            HttpRequestException => "Não foi possível consultar os relatórios agora.",
            _ => "Não foi possível carregar os relatórios. Tente novamente.",
        };
    }

    private void Reset()
    {
        _isInitialized = false;
        Snapshot = new ReportsSnapshot();
        ProductSnapshot = new ProductReportSnapshot();
        ProductSearchText = string.Empty;
        SelectedProductSort = ProductSortOptions[0];
        ErrorMessage = string.Empty;
        OnPropertyChanged(nameof(CanViewReports));
        OnPropertyChanged(nameof(IsAvailable));
        RefreshCommand.NotifyCanExecuteChanged();
        ApplyFiltersCommand.NotifyCanExecuteChanged();
        ApplyProductFiltersCommand.NotifyCanExecuteChanged();
        NotifyProductCommands();
    }

    private void NotifyProductCommands()
    {
        PreviousProductPageCommand.NotifyCanExecuteChanged();
        NextProductPageCommand.NotifyCanExecuteChanged();
    }
}
