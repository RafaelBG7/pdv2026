using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class LoginViewModelTests
{
    [Fact]
    public async Task Login_saves_encrypted_session_and_remembered_identifier()
    {
        var session = CreateSession();
        var apiClient = new StubApiClient { LoginResult = session };
        var sessionStore = new StubSessionStore();
        var preferencesStore = new StubPreferencesStore();
        var viewModel = CreateViewModel(apiClient, sessionStore, preferencesStore);
        viewModel.Identifier = "  operador  ";
        viewModel.Password = "senha-segura";
        viewModel.RememberUsername = true;

        await viewModel.LoginCommand.ExecuteAsync();

        Assert.True(viewModel.IsAuthenticated);
        Assert.Equal("Rafael Borges", viewModel.AuthenticatedUserName);
        Assert.Equal("Adega JF", viewModel.AuthenticatedCompanyName);
        Assert.Same(session, sessionStore.SavedSession);
        Assert.True(preferencesStore.SavedPreferences!.RememberUsername);
        Assert.Equal("operador", preferencesStore.SavedPreferences.RememberedIdentifier);
        Assert.Equal(string.Empty, viewModel.Password);
        Assert.Equal("operador", apiClient.LastLoginIdentifier);
    }

    [Fact]
    public async Task Login_does_not_persist_password_or_identifier_when_remember_is_disabled()
    {
        var apiClient = new StubApiClient { LoginResult = CreateSession() };
        var preferencesStore = new StubPreferencesStore();
        var viewModel = CreateViewModel(apiClient, new StubSessionStore(), preferencesStore);
        viewModel.Identifier = "operador";
        viewModel.Password = "senha-que-nao-deve-ser-salva";

        await viewModel.LoginCommand.ExecuteAsync();

        Assert.NotNull(preferencesStore.SavedPreferences);
        Assert.False(preferencesStore.SavedPreferences!.RememberUsername);
        Assert.Equal(string.Empty, preferencesStore.SavedPreferences.RememberedIdentifier);
        Assert.Equal(string.Empty, viewModel.Password);
    }

    [Fact]
    public async Task Initialize_refreshes_a_stored_session()
    {
        var storedSession = CreateSession("access-antigo", "refresh-antigo");
        var refreshedSession = CreateSession("access-novo", "refresh-novo");
        var apiClient = new StubApiClient { RefreshResult = refreshedSession };
        var sessionStore = new StubSessionStore { LoadedSession = storedSession };
        var preferencesStore = new StubPreferencesStore
        {
            LoadedPreferences = new UserPreferences
            {
                RememberUsername = true,
                RememberedIdentifier = "operador",
            },
        };
        var viewModel = CreateViewModel(apiClient, sessionStore, preferencesStore);

        await viewModel.InitializeAsync();

        Assert.True(viewModel.IsAuthenticated);
        Assert.Equal("refresh-antigo", apiClient.LastRefreshToken);
        Assert.Same(refreshedSession, sessionStore.SavedSession);
        Assert.Equal("operador", viewModel.Identifier);
        Assert.True(viewModel.RememberUsername);
    }

    [Fact]
    public async Task Login_exposes_the_safe_api_error_and_clears_password()
    {
        var apiClient = new StubApiClient
        {
            LoginException = new GirofyApiException(
                "Usuário ou senha inválidos.",
                "invalid_credentials",
                401),
        };
        var viewModel = CreateViewModel(
            apiClient,
            new StubSessionStore(),
            new StubPreferencesStore());
        viewModel.Identifier = "operador";
        viewModel.Password = "incorreta";

        await viewModel.LoginCommand.ExecuteAsync();

        Assert.False(viewModel.IsAuthenticated);
        Assert.Equal("Usuário ou senha inválidos.", viewModel.ErrorMessage);
        Assert.Equal(string.Empty, viewModel.Password);
    }

    [Fact]
    public async Task Logout_clears_the_local_session_even_when_server_is_unavailable()
    {
        var apiClient = new StubApiClient
        {
            LoginResult = CreateSession(),
            LogoutException = new HttpRequestException("offline"),
        };
        var sessionStore = new StubSessionStore();
        var viewModel = CreateViewModel(apiClient, sessionStore, new StubPreferencesStore());
        viewModel.Identifier = "operador";
        viewModel.Password = "senha";
        await viewModel.LoginCommand.ExecuteAsync();

        await viewModel.LogoutCommand.ExecuteAsync();

        Assert.False(viewModel.IsAuthenticated);
        Assert.True(sessionStore.WasCleared);
    }

    private static LoginViewModel CreateViewModel(
        IGirofyApiClient apiClient,
        ISecureSessionStore sessionStore,
        IUserPreferencesStore preferencesStore) =>
        new(
            apiClient,
            sessionStore,
            preferencesStore,
            new StubBrowserService(),
            new AppSessionContext(),
            new Uri("https://girofy.example/forgot-password"));

    private static AuthSession CreateSession(
        string accessToken = "access-token",
        string refreshToken = "refresh-token") =>
        new()
        {
            AccessToken = accessToken,
            RefreshToken = refreshToken,
            ExpiresIn = 900,
            User = new UserIdentity
            {
                Id = 7,
                Username = "operador",
                FullName = "Rafael Borges",
                Role = "admin",
                RoleLabel = "Administrador",
            },
            Company = new CompanyIdentity
            {
                Id = 4,
                Name = "Adega JF",
                Active = true,
                SubscriptionValid = true,
            },
        };

    private sealed class StubApiClient : IGirofyApiClient
    {
        public AuthSession? LoginResult { get; init; }

        public AuthSession? RefreshResult { get; init; }

        public Exception? LoginException { get; init; }

        public Exception? LogoutException { get; init; }

        public string LastLoginIdentifier { get; private set; } = string.Empty;

        public string LastRefreshToken { get; private set; } = string.Empty;

        public Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken) =>
            Task.FromResult(new HealthStatus { Status = "ok", ApiVersion = "v1" });

        public Task<AuthSession> LoginAsync(
            string identifier,
            string password,
            CancellationToken cancellationToken)
        {
            LastLoginIdentifier = identifier;
            return LoginException is null
                ? Task.FromResult(LoginResult!)
                : Task.FromException<AuthSession>(LoginException);
        }

        public Task<AuthSession> RefreshSessionAsync(
            string refreshToken,
            CancellationToken cancellationToken)
        {
            LastRefreshToken = refreshToken;
            return Task.FromResult(RefreshResult!);
        }

        public Task<AuthIdentity> GetCurrentIdentityAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromResult(new AuthIdentity());

        public Task LogoutAsync(string accessToken, CancellationToken cancellationToken) =>
            LogoutException is null
                ? Task.CompletedTask
                : Task.FromException(LogoutException);

        public Task<DashboardSnapshot> GetDashboardSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException<DashboardSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

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

    private sealed class StubSessionStore : ISecureSessionStore
    {
        public AuthSession? LoadedSession { get; init; }

        public AuthSession? SavedSession { get; private set; }

        public bool WasCleared { get; private set; }

        public Task<AuthSession?> LoadAsync(CancellationToken cancellationToken) =>
            Task.FromResult(LoadedSession);

        public Task SaveAsync(AuthSession session, CancellationToken cancellationToken)
        {
            SavedSession = session;
            return Task.CompletedTask;
        }

        public Task ClearAsync(CancellationToken cancellationToken)
        {
            WasCleared = true;
            SavedSession = null;
            return Task.CompletedTask;
        }
    }

    private sealed class StubPreferencesStore : IUserPreferencesStore
    {
        public UserPreferences LoadedPreferences { get; init; } = new();

        public UserPreferences? SavedPreferences { get; private set; }

        public Task<UserPreferences> LoadAsync(CancellationToken cancellationToken) =>
            Task.FromResult(LoadedPreferences);

        public Task SaveAsync(UserPreferences preferences, CancellationToken cancellationToken)
        {
            SavedPreferences = preferences;
            return Task.CompletedTask;
        }
    }

    private sealed class StubBrowserService : IExternalBrowserService
    {
        public void Open(Uri uri)
        {
        }
    }
}
