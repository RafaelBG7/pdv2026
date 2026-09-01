using System.ComponentModel;
using System.Globalization;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class ConnectionViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IExternalBrowserService _browserService;
    private readonly Uri _serverUri;
    private string _statusTitle = "Preparando conexão";
    private string _statusDescription = "Verificando se o servidor SkyGest está disponível.";
    private string _lastCheckedText = "Ainda não verificado";
    private bool _isBusy;
    private bool _isConnected;
    private bool _hasConnectionError;
    private string _activeView = "dashboard";
    private CancellationTokenSource? _navigationCancellation;
    private int _navigationVersion;

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
        NotificationsViewModel notifications,
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
        Notifications = notifications;
        Settings = settings;
        RetryConnectionCommand = new AsyncRelayCommand(CheckConnectionAsync);
        OpenWebCommand = new RelayCommand(() => _browserService.Open(_serverUri));
        ShowDashboardCommand = new AsyncRelayCommand(ShowDashboardAsync);
        ShowProductsCommand = new AsyncRelayCommand(ShowProductsAsync);
        ShowCategoriesCommand = new AsyncRelayCommand(ShowCategoriesAsync);
        ShowCashRegisterCommand = new AsyncRelayCommand(ShowCashRegisterAsync);
        ShowSalesCommand = new AsyncRelayCommand(ShowSalesAsync);
        StartSaleCommand = new AsyncRelayCommand(
            StartSaleAsync,
            () => IsDashboardView && Sales.IsAvailable);
        SalesScreenF3Command = new AsyncRelayCommand(
            ExecuteSalesScreenF3Async,
            () => IsSalesView && Sales.IsAvailable);
        ShowStockCommand = new AsyncRelayCommand(ShowStockAsync);
        ShowPayablesCommand = new AsyncRelayCommand(ShowPayablesAsync);
        ShowReportsCommand = new AsyncRelayCommand(ShowReportsAsync);
        ShowAuditCommand = new AsyncRelayCommand(ShowAuditAsync);
        ShowNotificationsCommand = new AsyncRelayCommand(ShowNotificationsAsync);
        ShowSettingsCommand = new AsyncRelayCommand(ShowSettingsAsync);
        Sales.PropertyChanged += HandleSalesPropertyChanged;
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
    public NotificationsViewModel Notifications { get; }

    public SettingsViewModel Settings { get; }

    public bool IsDashboardView => string.Equals(_activeView, "dashboard", StringComparison.Ordinal);

    public bool IsCatalogView => string.Equals(_activeView, "catalog", StringComparison.Ordinal);

    public bool IsCashRegisterView => string.Equals(_activeView, "cash-register", StringComparison.Ordinal);

    public bool IsSalesView => string.Equals(_activeView, "sales", StringComparison.Ordinal);

    public bool IsStockView => string.Equals(_activeView, "stock", StringComparison.Ordinal);

    public bool IsPayablesView => string.Equals(_activeView, "payables", StringComparison.Ordinal);

    public bool IsReportsView => string.Equals(_activeView, "reports", StringComparison.Ordinal);

    public bool IsAuditView => string.Equals(_activeView, "audit", StringComparison.Ordinal);
    public bool IsNotificationsView => string.Equals(_activeView, "notifications", StringComparison.Ordinal);

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

    public AsyncRelayCommand StartSaleCommand { get; }

    public AsyncRelayCommand SalesScreenF3Command { get; }

    public AsyncRelayCommand ShowStockCommand { get; }

    public AsyncRelayCommand ShowPayablesCommand { get; }

    public AsyncRelayCommand ShowReportsCommand { get; }

    public AsyncRelayCommand ShowAuditCommand { get; }
    public AsyncRelayCommand ShowNotificationsCommand { get; }

    public AsyncRelayCommand ShowSettingsCommand { get; }

    public Task InitializeAsync(CancellationToken cancellationToken = default) =>
        CheckConnectionAsync(cancellationToken);

    private Task ShowDashboardAsync(CancellationToken cancellationToken) =>
        NavigateAsync("dashboard", Dashboard.InitializeAsync, cancellationToken);

    private Task ShowProductsAsync(CancellationToken cancellationToken) =>
        NavigateAsync(
            "catalog",
            Catalog.InitializeAsync,
            cancellationToken,
            () => Catalog.ShowProductsCommand.Execute(null));

    private Task ShowCategoriesAsync(CancellationToken cancellationToken) =>
        NavigateAsync(
            "catalog",
            Catalog.InitializeAsync,
            cancellationToken,
            () => Catalog.ShowCategoriesCommand.Execute(null));

    private Task ShowCashRegisterAsync(CancellationToken cancellationToken) =>
        NavigateAsync(
            "cash-register",
            CashRegister.InitializeAsync,
            cancellationToken,
            CashRegister.ReturnToInitialState);

    private Task ShowSalesAsync(CancellationToken cancellationToken) =>
        NavigateAsync(
            "sales",
            Sales.InitializeAsync,
            cancellationToken,
            Sales.ReturnToInitialState);

    private async Task StartSaleAsync(CancellationToken cancellationToken)
    {
        await NavigateAsync("sales", Sales.InitializeAsync, cancellationToken);
        if (cancellationToken.IsCancellationRequested || !IsSalesView)
        {
            return;
        }

        await Sales.OpenSaleEditorCommand.ExecuteAsync(cancellationToken);
    }

    private async Task ExecuteSalesScreenF3Async(CancellationToken cancellationToken)
    {
        if (Sales.IsPaymentStepVisible)
        {
            if (Sales.OpenDiscountPopupCommand.CanExecute(null))
            {
                Sales.OpenDiscountPopupCommand.Execute(null);
            }
            return;
        }

        if (Sales.IsSaleEditorOpen || Sales.IsOpenCashPromptOpen)
        {
            return;
        }

        if (Sales.OpenSaleEditorCommand.CanExecute(null))
        {
            await Sales.OpenSaleEditorCommand.ExecuteAsync(cancellationToken);
        }
    }

    private Task ShowStockAsync(CancellationToken cancellationToken) =>
        NavigateAsync(
            "stock",
            Stock.InitializeAsync,
            cancellationToken,
            () => Stock.ShowMovementsTabCommand.Execute(null));

    private Task ShowPayablesAsync(CancellationToken cancellationToken) =>
        NavigateAsync("payables", Payables.InitializeAsync, cancellationToken);

    private Task ShowReportsAsync(CancellationToken cancellationToken) =>
        NavigateAsync(
            "reports",
            Reports.InitializeAsync,
            cancellationToken,
            () => Reports.ShowSummaryTabCommand.Execute(null));

    private Task ShowAuditAsync(CancellationToken cancellationToken) =>
        NavigateAsync("audit", Audit.InitializeAsync, cancellationToken);

    private Task ShowNotificationsAsync(CancellationToken cancellationToken) =>
        NavigateAsync("notifications", Notifications.InitializeAsync, cancellationToken);

    private Task ShowSettingsAsync(CancellationToken cancellationToken) =>
        NavigateAsync("settings", Settings.InitializeAsync, cancellationToken);

    private async Task NavigateAsync(
        string activeView,
        Func<CancellationToken, Task> initialize,
        CancellationToken commandCancellation,
        Action? beforeInitialize = null)
    {
        var navigationVersion = ++_navigationVersion;
        _navigationCancellation?.Cancel();
        var navigationCancellation = CancellationTokenSource.CreateLinkedTokenSource(
            commandCancellation);
        _navigationCancellation = navigationCancellation;

        SetActiveView(activeView);
        beforeInitialize?.Invoke();
        try
        {
            await initialize(navigationCancellation.Token);
        }
        catch (OperationCanceledException) when (navigationCancellation.IsCancellationRequested)
        {
        }
        finally
        {
            if (navigationVersion == _navigationVersion &&
                ReferenceEquals(_navigationCancellation, navigationCancellation))
            {
                _navigationCancellation = null;
            }
            navigationCancellation.Dispose();
        }
    }

    private void SetActiveView(string activeView)
    {
        if (string.Equals(_activeView, activeView, StringComparison.Ordinal))
        {
            return;
        }

        if (string.Equals(_activeView, "sales", StringComparison.Ordinal) &&
            !string.Equals(activeView, "sales", StringComparison.Ordinal))
        {
            Sales.ReturnToInitialState();
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
        OnPropertyChanged(nameof(IsNotificationsView));
        OnPropertyChanged(nameof(IsSettingsView));
        StartSaleCommand.NotifyCanExecuteChanged();
        SalesScreenF3Command.NotifyCanExecuteChanged();
    }

    private async Task CheckConnectionAsync(CancellationToken cancellationToken)
    {
        IsBusy = true;
        IsConnected = false;
        HasConnectionError = false;
        StatusTitle = "Conectando ao SkyGest";
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
            LastCheckedText = $"Última verificação: {BrazilianDateFormatting.FormatTimestamp(DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture))}";
            IsBusy = false;
        }
    }

    public void Dispose()
    {
        _navigationCancellation?.Cancel();
        Sales.PropertyChanged -= HandleSalesPropertyChanged;
    }

    private void HandleSalesPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(SalesViewModel.IsAvailable))
        {
            StartSaleCommand.NotifyCanExecuteChanged();
            SalesScreenF3Command.NotifyCanExecuteChanged();
        }
    }
}
