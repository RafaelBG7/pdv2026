using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class ConnectionViewModelTests
{
    [Fact]
    public async Task Dashboard_start_sale_is_available_on_first_session_load()
    {
        var sessionContext = new AppSessionContext();
        using var viewModel = CreateConnectionViewModel(new StubApiClient(new HealthStatus()), sessionContext);

        sessionContext.Set(CreateSession(canManageSales: true));
        await viewModel.Dashboard.InitializeAsync();

        Assert.True(viewModel.IsDashboardView);
        Assert.True(viewModel.StartSaleCommand.CanExecute(null));
    }

    [Fact]
    public void Start_sale_notifies_can_execute_when_permissions_finish_loading()
    {
        var sessionContext = new AppSessionContext();
        using var viewModel = CreateConnectionViewModel(new StubApiClient(new HealthStatus()), sessionContext);
        var notifications = 0;
        viewModel.StartSaleCommand.CanExecuteChanged += (_, _) => notifications++;

        Assert.False(viewModel.StartSaleCommand.CanExecute(null));
        sessionContext.Set(CreateSession(canManageSales: true));

        Assert.True(notifications > 0);
        Assert.True(viewModel.StartSaleCommand.CanExecute(null));
    }

    [Fact]
    public void Dashboard_start_sale_remains_blocked_without_sales_permission()
    {
        var sessionContext = new AppSessionContext();
        using var viewModel = CreateConnectionViewModel(new StubApiClient(new HealthStatus()), sessionContext);

        sessionContext.Set(CreateSession(canManageSales: false));

        Assert.False(viewModel.StartSaleCommand.CanExecute(null));
    }

    [Fact]
    public async Task Dashboard_start_sale_remains_available_after_navigation_reentry()
    {
        var sessionContext = new AppSessionContext();
        using var viewModel = CreateConnectionViewModel(new StubApiClient(new HealthStatus()), sessionContext);
        sessionContext.Set(CreateSession(canManageSales: true));

        await viewModel.ShowProductsCommand.ExecuteAsync();
        Assert.False(viewModel.StartSaleCommand.CanExecute(null));

        await viewModel.ShowDashboardCommand.ExecuteAsync();
        Assert.True(viewModel.StartSaleCommand.CanExecute(null));
    }

    [Fact]
    public async Task Leaving_sales_discards_the_current_sale_draft()
    {
        var sessionContext = new AppSessionContext();
        var apiClient = new StubApiClient(new HealthStatus());
        using var viewModel = CreateConnectionViewModel(apiClient, sessionContext);
        sessionContext.Set(CreateSession(canManageSales: true));

        await viewModel.ShowSalesCommand.ExecuteAsync();
        await viewModel.Sales.OpenSaleEditorCommand.ExecuteAsync();
        viewModel.Sales.CartItems.Add(new SaleCartItemViewModel(
            new CatalogProduct { Id = 9, Name = "Produto", SalePrice = 12m, Active = true },
            1));
        viewModel.Sales.MoneyText = "12,00";

        await viewModel.ShowDashboardCommand.ExecuteAsync();

        Assert.Empty(viewModel.Sales.CartItems);
        Assert.Equal("0,00", viewModel.Sales.MoneyText);
        Assert.False(viewModel.Sales.IsSaleEditorOpen);
    }

    [Fact]
    public async Task Sales_f3_is_available_immediately_and_does_not_open_duplicate_editor()
    {
        var sessionContext = new AppSessionContext();
        var apiClient = new StubApiClient(new HealthStatus());
        using var viewModel = CreateConnectionViewModel(apiClient, sessionContext);
        sessionContext.Set(CreateSession(canManageSales: true));

        await viewModel.ShowSalesCommand.ExecuteAsync();

        Assert.True(viewModel.IsSalesView);
        Assert.True(viewModel.SalesScreenF3Command.CanExecute(null));
        await viewModel.SalesScreenF3Command.ExecuteAsync();
        Assert.True(viewModel.Sales.IsSaleEditorOpen);
        Assert.Equal(1, apiClient.CashRegisterSummaryCalls);

        await viewModel.SalesScreenF3Command.ExecuteAsync();
        Assert.Equal(1, apiClient.CashRegisterSummaryCalls);

        viewModel.Sales.CloseSaleEditorCommand.Execute(null);
        await viewModel.SalesScreenF3Command.ExecuteAsync();
        Assert.True(viewModel.Sales.IsSaleEditorOpen);
        Assert.Equal(2, apiClient.CashRegisterSummaryCalls);
    }

    [Fact]
    public async Task Sales_f3_opens_discount_while_composing_an_order()
    {
        var sessionContext = new AppSessionContext();
        var apiClient = new StubApiClient(new HealthStatus());
        using var viewModel = CreateConnectionViewModel(apiClient, sessionContext);
        sessionContext.Set(CreateSession(canManageSales: true));

        await viewModel.ShowSalesCommand.ExecuteAsync();
        await viewModel.SalesScreenF3Command.ExecuteAsync();
        viewModel.Sales.CartItems.Add(new SaleCartItemViewModel(
            new CatalogProduct { Id = 1, Name = "Produto", SalePrice = 10m, StockQuantity = 1 },
            1));

        Assert.True(viewModel.Sales.IsProductStepOpen);
        await viewModel.SalesScreenF3Command.ExecuteAsync();

        Assert.True(viewModel.Sales.IsDiscountPopupVisible);
        Assert.False(viewModel.Sales.IsPaymentStepVisible);
    }

    [Fact]
    public async Task Sales_f3_remains_blocked_without_sales_permission()
    {
        var sessionContext = new AppSessionContext();
        using var viewModel = CreateConnectionViewModel(new StubApiClient(new HealthStatus()), sessionContext);
        sessionContext.Set(CreateSession(canManageSales: false));

        await viewModel.ShowSalesCommand.ExecuteAsync();

        Assert.False(viewModel.SalesScreenF3Command.CanExecute(null));
    }

    [Fact]
    public async Task InitializeAsync_marks_server_as_connected_when_health_is_valid()
    {
        var apiClient = new StubApiClient(new HealthStatus
        {
            Status = "ok",
            Service = "girofy",
            ApiVersion = "v1",
        });
        var viewModel = new ConnectionViewModel(
            apiClient,
            new StubBrowserService(),
            new Uri("https://girofy.example"),
            CreateLoginViewModel(apiClient),
            CreateCatalogViewModel(apiClient),
            CreateDashboardViewModel(apiClient),
            CreateCashRegisterViewModel(apiClient),
            CreateSalesViewModel(apiClient),
            CreateStockViewModel(apiClient),
            CreatePayablesViewModel(apiClient),
            CreateReportsViewModel(apiClient),
            CreateAuditViewModel(apiClient),
            CreateNotificationsViewModel(apiClient),
            CreateSettingsViewModel(apiClient));

        await viewModel.InitializeAsync();

        Assert.True(viewModel.IsConnected);
        Assert.False(viewModel.HasConnectionError);
        Assert.Equal("Servidor disponível", viewModel.StatusTitle);
    }

    [Fact]
    public async Task InitializeAsync_exposes_a_safe_message_when_connection_fails()
    {
        var viewModel = new ConnectionViewModel(
            new StubApiClient(new HttpRequestException("internal diagnostic")),
            new StubBrowserService(),
            new Uri("https://girofy.example"),
            CreateLoginViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateCatalogViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateDashboardViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateCashRegisterViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateSalesViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateStockViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreatePayablesViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateReportsViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateAuditViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateNotificationsViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))),
            CreateSettingsViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))));

        await viewModel.InitializeAsync();

        Assert.False(viewModel.IsConnected);
        Assert.True(viewModel.HasConnectionError);
        Assert.Equal("Não foi possível conectar", viewModel.StatusTitle);
        Assert.DoesNotContain("internal diagnostic", viewModel.StatusDescription);
    }

    private static LoginViewModel CreateLoginViewModel(IGirofyApiClient apiClient) =>
        new(
            apiClient,
            new StubSessionStore(),
            new StubPreferencesStore(),
            new StubBrowserService(),
            new AppSessionContext(),
            new ForgotPasswordViewModel(new StubPasswordRecoveryService()),
            new Uri("https://girofy.example/login?auth_tab=register"));

    private static ConnectionViewModel CreateConnectionViewModel(
        IGirofyApiClient apiClient,
        AppSessionContext sessionContext) =>
        new(
            apiClient,
            new StubBrowserService(),
            new Uri("https://girofy.example"),
            new LoginViewModel(
                apiClient,
                new StubSessionStore(),
                new StubPreferencesStore(),
                new StubBrowserService(),
                sessionContext,
                new ForgotPasswordViewModel(new StubPasswordRecoveryService()),
                new Uri("https://girofy.example/login?auth_tab=register")),
            new CatalogViewModel(apiClient, sessionContext),
            new DashboardViewModel(apiClient, sessionContext),
            new CashRegisterViewModel(apiClient, sessionContext),
            new SalesViewModel(apiClient, sessionContext),
            new StockViewModel(apiClient, sessionContext),
            new PayablesViewModel(apiClient, sessionContext),
            new ReportsViewModel(apiClient, sessionContext),
            new AuditViewModel(apiClient, sessionContext),
            new NotificationsViewModel(apiClient, sessionContext, enablePolling: false),
            new SettingsViewModel(
                apiClient,
                sessionContext,
                new StubBrowserService(),
                new StubFileSaveService(),
                new StubFilePickerService(),
                new Uri("https://girofy.example/configuracoes")));

    private static AuthSession CreateSession(bool canManageSales) => new()
    {
        AccessToken = "access-token",
        RefreshToken = "refresh-token",
        User = new UserIdentity
        {
            Id = 1,
            Username = "operator",
            Permissions = new Dictionary<string, bool>
            {
                ["can_manage_sales"] = canManageSales,
            },
        },
        Company = new CompanyIdentity { Id = 1, Name = "Adega JF", Active = true },
    };

    private static CatalogViewModel CreateCatalogViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static DashboardViewModel CreateDashboardViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static CashRegisterViewModel CreateCashRegisterViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static SalesViewModel CreateSalesViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static StockViewModel CreateStockViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static PayablesViewModel CreatePayablesViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static ReportsViewModel CreateReportsViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static AuditViewModel CreateAuditViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static NotificationsViewModel CreateNotificationsViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static SettingsViewModel CreateSettingsViewModel(IGirofyApiClient apiClient) =>
        new(
            apiClient,
            new AppSessionContext(),
            new StubBrowserService(),
            new StubFileSaveService(),
            new StubFilePickerService(),
            new Uri("https://girofy.example/configuracoes"));

    private sealed class StubFileSaveService : IFileSaveService
    {
        public Task<string?> SaveFileAsync(
            string suggestedFileName,
            string filter,
            byte[] content,
            CancellationToken cancellationToken) =>
            Task.FromResult<string?>(null);
    }

    private sealed class StubFilePickerService : IFilePickerService
    {
        public Task<PickedFile?> PickFileAsync(
            string filter,
            CancellationToken cancellationToken) =>
            Task.FromResult<PickedFile?>(null);
    }

    private sealed class StubApiClient : IGirofyApiClient
    {
        private readonly HealthStatus? _health;
        private readonly Exception? _exception;

        public StubApiClient(HealthStatus health) => _health = health;

        public StubApiClient(Exception exception) => _exception = exception;

        public int CashRegisterSummaryCalls { get; private set; }

        public Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken)
        {
            if (_exception is not null)
            {
                return Task.FromException<HealthStatus>(_exception);
            }

            return Task.FromResult(_health!);
        }

        public Task<AuthSession> LoginAsync(
            string identifier,
            string password,
            CancellationToken cancellationToken) =>
            Task.FromException<AuthSession>(new NotSupportedException());

        public Task<AuthSession> RefreshSessionAsync(
            string refreshToken,
            CancellationToken cancellationToken) =>
            Task.FromException<AuthSession>(new NotSupportedException());

        public Task<AuthIdentity> GetCurrentIdentityAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException<AuthIdentity>(new NotSupportedException());

        public Task LogoutAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException(new NotSupportedException());

        public Task<DashboardSnapshot> GetDashboardSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException<DashboardSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken)
        {
            CashRegisterSummaryCalls++;
            return Task.FromResult(new CashRegisterSnapshot
            {
                CurrentRegister = new CashRegisterRecord { Id = 1, Status = "open" },
            });
        }

        public Task<CashRegisterSnapshot> OpenCashRegisterAsync(
            string accessToken,
            decimal openingAmount,
            CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> CloseCashRegisterAsync(
            string accessToken,
            int cashRegisterId,
            decimal closingAmount,
            CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

        public Task<CatalogCategoryList> GetCatalogCategoriesAsync(
            string accessToken,
            string search,
            CancellationToken cancellationToken) =>
            Task.FromException<CatalogCategoryList>(new NotSupportedException());

        public Task<CatalogProductList> GetCatalogProductsAsync(
            string accessToken,
            string search,
            int? categoryId,
            string activeFilter,
            string sort,
            int page,
            int perPage,
            CancellationToken cancellationToken) =>
            Task.FromException<CatalogProductList>(new NotSupportedException());

        public Task<SaleReceipt> CreateSaleAsync(
            string accessToken,
            string idempotencyKey,
            IReadOnlyList<SaleLineRequest> items,
            decimal discountAmount,
            IReadOnlyList<SalePaymentRequest> payments,
            CancellationToken cancellationToken) =>
            Task.FromException<SaleReceipt>(new NotSupportedException());
    }

    private sealed class StubBrowserService : IExternalBrowserService
    {
        public void Open(Uri uri)
        {
        }
    }

    private sealed class StubPasswordRecoveryService : IPasswordRecoveryService
    {
        public Task RequestAsync(string identifier, CancellationToken cancellationToken = default) =>
            Task.CompletedTask;
    }

    private sealed class StubSessionStore : ISecureSessionStore
    {
        public Task<AuthSession?> LoadAsync(CancellationToken cancellationToken) =>
            Task.FromResult<AuthSession?>(null);

        public Task SaveAsync(AuthSession session, CancellationToken cancellationToken) =>
            Task.CompletedTask;

        public Task ClearAsync(CancellationToken cancellationToken) =>
            Task.CompletedTask;
    }

    private sealed class StubPreferencesStore : IUserPreferencesStore
    {
        public Task<UserPreferences> LoadAsync(CancellationToken cancellationToken) =>
            Task.FromResult(new UserPreferences());

        public Task SaveAsync(UserPreferences preferences, CancellationToken cancellationToken) =>
            Task.CompletedTask;
    }
}
