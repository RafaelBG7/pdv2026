using Girofy.Application.Abstractions;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class ConnectionViewModel : ObservableObject
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IExternalBrowserService _browserService;
    private readonly Uri _serverUri;
    private string _statusTitle = "Preparando conexão";
    private string _statusDescription = "Verificando se o servidor Girofy está disponível.";
    private string _lastCheckedText = "Ainda não verificado";
    private bool _isBusy;
    private bool _isConnected;
    private bool _hasConnectionError;
    private string _activeView = "dashboard";

    public ConnectionViewModel(
        IGirofyApiClient apiClient,
        IExternalBrowserService browserService,
        Uri serverUri,
        LoginViewModel login,
        CatalogViewModel catalog,
        DashboardViewModel dashboard,
        CashRegisterViewModel cashRegister,
        SalesViewModel sales,
        StockViewModel stock,
        PayablesViewModel payables,
        ReportsViewModel reports,
        AuditViewModel audit,
        SettingsViewModel settings)
    {
        _apiClient = apiClient;
        _browserService = browserService;
        _serverUri = serverUri;
        Login = login;
        Catalog = catalog;
        Dashboard = dashboard;
        CashRegister = cashRegister;
        Sales = sales;
        Stock = stock;
        Payables = payables;
        Reports = reports;
        Audit = audit;
        Settings = settings;
        RetryConnectionCommand = new AsyncRelayCommand(CheckConnectionAsync);
        OpenWebCommand = new RelayCommand(() => _browserService.Open(_serverUri));
        ShowDashboardCommand = new AsyncRelayCommand(ShowDashboardAsync);
        ShowProductsCommand = new AsyncRelayCommand(ShowProductsAsync);
        ShowCategoriesCommand = new AsyncRelayCommand(ShowCategoriesAsync);
        ShowCashRegisterCommand = new AsyncRelayCommand(ShowCashRegisterAsync);
        ShowSalesCommand = new AsyncRelayCommand(ShowSalesAsync);
        ShowStockCommand = new AsyncRelayCommand(ShowStockAsync);
        ShowPayablesCommand = new AsyncRelayCommand(ShowPayablesAsync);
        ShowReportsCommand = new AsyncRelayCommand(ShowReportsAsync);
        ShowAuditCommand = new AsyncRelayCommand(ShowAuditAsync);
        ShowSettingsCommand = new AsyncRelayCommand(ShowSettingsAsync);
    }

    public LoginViewModel Login { get; }

    public CatalogViewModel Catalog { get; }

    public DashboardViewModel Dashboard { get; }

    public CashRegisterViewModel CashRegister { get; }

    public SalesViewModel Sales { get; }

    public StockViewModel Stock { get; }

    public PayablesViewModel Payables { get; }

    public ReportsViewModel Reports { get; }

    public AuditViewModel Audit { get; }

    public SettingsViewModel Settings { get; }

    public bool IsDashboardView => string.Equals(_activeView, "dashboard", StringComparison.Ordinal);

    public bool IsCatalogView => string.Equals(_activeView, "catalog", StringComparison.Ordinal);

    public bool IsCashRegisterView => string.Equals(_activeView, "cash-register", StringComparison.Ordinal);

    public bool IsSalesView => string.Equals(_activeView, "sales", StringComparison.Ordinal);

    public bool IsStockView => string.Equals(_activeView, "stock", StringComparison.Ordinal);

    public bool IsPayablesView => string.Equals(_activeView, "payables", StringComparison.Ordinal);

    public bool IsReportsView => string.Equals(_activeView, "reports", StringComparison.Ordinal);

    public bool IsAuditView => string.Equals(_activeView, "audit", StringComparison.Ordinal);

    public bool IsSettingsView => string.Equals(_activeView, "settings", StringComparison.Ordinal);

    public string StatusTitle
    {
        get => _statusTitle;
        private set => SetProperty(ref _statusTitle, value);
    }

    public string StatusDescription
    {
        get => _statusDescription;
        private set => SetProperty(ref _statusDescription, value);
    }

    public string LastCheckedText
    {
        get => _lastCheckedText;
        private set => SetProperty(ref _lastCheckedText, value);
    }

    public string ServerAddress => _serverUri.GetLeftPart(UriPartial.Authority);

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public bool IsConnected
    {
        get => _isConnected;
        private set => SetProperty(ref _isConnected, value);
    }

    public bool HasConnectionError
    {
        get => _hasConnectionError;
        private set => SetProperty(ref _hasConnectionError, value);
    }

    public AsyncRelayCommand RetryConnectionCommand { get; }

    public RelayCommand OpenWebCommand { get; }

    public AsyncRelayCommand ShowDashboardCommand { get; }

    public AsyncRelayCommand ShowProductsCommand { get; }

    public AsyncRelayCommand ShowCategoriesCommand { get; }

    public AsyncRelayCommand ShowCashRegisterCommand { get; }

    public AsyncRelayCommand ShowSalesCommand { get; }

    public AsyncRelayCommand ShowStockCommand { get; }

    public AsyncRelayCommand ShowPayablesCommand { get; }

    public AsyncRelayCommand ShowReportsCommand { get; }

    public AsyncRelayCommand ShowAuditCommand { get; }

    public AsyncRelayCommand ShowSettingsCommand { get; }

    public Task InitializeAsync(CancellationToken cancellationToken = default) =>
        CheckConnectionAsync(cancellationToken);

    private async Task ShowDashboardAsync(CancellationToken cancellationToken)
    {
        SetActiveView("dashboard");
        await Dashboard.InitializeAsync(cancellationToken);
    }

    private async Task ShowProductsAsync(CancellationToken cancellationToken)
    {
        SetActiveView("catalog");
        Catalog.ShowProductsCommand.Execute(null);
        await Catalog.InitializeAsync(cancellationToken);
    }

    private async Task ShowCategoriesAsync(CancellationToken cancellationToken)
    {
        SetActiveView("catalog");
        Catalog.ShowCategoriesCommand.Execute(null);
        await Catalog.InitializeAsync(cancellationToken);
    }

    private async Task ShowCashRegisterAsync(CancellationToken cancellationToken)
    {
        SetActiveView("cash-register");
        await CashRegister.InitializeAsync(cancellationToken);
    }

    private async Task ShowSalesAsync(CancellationToken cancellationToken)
    {
        SetActiveView("sales");
        await Sales.InitializeAsync(cancellationToken);
    }

    private async Task ShowStockAsync(CancellationToken cancellationToken)
    {
        SetActiveView("stock");
        await Stock.InitializeAsync(cancellationToken);
    }

    private async Task ShowPayablesAsync(CancellationToken cancellationToken)
    {
        SetActiveView("payables");
        await Payables.InitializeAsync(cancellationToken);
    }

    private async Task ShowReportsAsync(CancellationToken cancellationToken)
    {
        SetActiveView("reports");
        await Reports.InitializeAsync(cancellationToken);
    }

    private async Task ShowAuditAsync(CancellationToken cancellationToken)
    {
        SetActiveView("audit");
        await Audit.InitializeAsync(cancellationToken);
    }

    private async Task ShowSettingsAsync(CancellationToken cancellationToken)
    {
        SetActiveView("settings");
        await Settings.InitializeAsync(cancellationToken);
    }

    private void SetActiveView(string activeView)
    {
        if (string.Equals(_activeView, activeView, StringComparison.Ordinal))
        {
            return;
        }

        _activeView = activeView;
        OnPropertyChanged(nameof(IsDashboardView));
        OnPropertyChanged(nameof(IsCatalogView));
        OnPropertyChanged(nameof(IsCashRegisterView));
        OnPropertyChanged(nameof(IsSalesView));
        OnPropertyChanged(nameof(IsStockView));
        OnPropertyChanged(nameof(IsPayablesView));
        OnPropertyChanged(nameof(IsReportsView));
        OnPropertyChanged(nameof(IsAuditView));
        OnPropertyChanged(nameof(IsSettingsView));
    }

    private async Task CheckConnectionAsync(CancellationToken cancellationToken)
    {
        IsBusy = true;
        IsConnected = false;
        HasConnectionError = false;
        StatusTitle = "Conectando ao Girofy";
        StatusDescription = "Validando a disponibilidade da API do sistema.";

        try
        {
            var health = await _apiClient.GetHealthAsync(cancellationToken);
            await Login.InitializeAsync(cancellationToken);
            IsConnected = true;
            StatusTitle = "Servidor disponível";
            StatusDescription = Login.IsAuthenticated
                ? $"API {health.ApiVersion} conectada e sessão restaurada com segurança."
                : $"API {health.ApiVersion} conectada. Entre para acessar sua adega.";
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            HasConnectionError = true;
            StatusTitle = "Tempo de conexão esgotado";
            StatusDescription = "O servidor demorou para responder. Verifique a internet e tente novamente.";
        }
        catch (Exception)
        {
            HasConnectionError = true;
            StatusTitle = "Não foi possível conectar";
            StatusDescription = "Confira sua internet ou abra temporariamente a versão web.";
        }
        finally
        {
            LastCheckedText = $"Última verificação: {DateTimeOffset.Now:dd/MM/yyyy HH:mm:ss}";
            IsBusy = false;
        }
    }
}
