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
        CashRegisterViewModel cashRegister)
    {
        _apiClient = apiClient;
        _browserService = browserService;
        _serverUri = serverUri;
        Login = login;
        Catalog = catalog;
        Dashboard = dashboard;
        CashRegister = cashRegister;
        RetryConnectionCommand = new AsyncRelayCommand(CheckConnectionAsync);
        OpenWebCommand = new RelayCommand(() => _browserService.Open(_serverUri));
        ShowDashboardCommand = new AsyncRelayCommand(ShowDashboardAsync);
        ShowProductsCommand = new AsyncRelayCommand(ShowProductsAsync);
        ShowCategoriesCommand = new AsyncRelayCommand(ShowCategoriesAsync);
        ShowCashRegisterCommand = new AsyncRelayCommand(ShowCashRegisterAsync);
    }

    public LoginViewModel Login { get; }

    public CatalogViewModel Catalog { get; }

    public DashboardViewModel Dashboard { get; }

    public CashRegisterViewModel CashRegister { get; }

    public bool IsDashboardView => string.Equals(_activeView, "dashboard", StringComparison.Ordinal);

    public bool IsCatalogView => string.Equals(_activeView, "catalog", StringComparison.Ordinal);

    public bool IsCashRegisterView => string.Equals(_activeView, "cash-register", StringComparison.Ordinal);

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
