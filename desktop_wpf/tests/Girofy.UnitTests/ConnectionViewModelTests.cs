using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class ConnectionViewModelTests
{
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
            CreateDashboardViewModel(apiClient));

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
            CreateDashboardViewModel(new StubApiClient(new HttpRequestException("internal diagnostic"))));

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
            new Uri("https://girofy.example/forgot-password"));

    private static CatalogViewModel CreateCatalogViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private static DashboardViewModel CreateDashboardViewModel(IGirofyApiClient apiClient) =>
        new(apiClient, new AppSessionContext());

    private sealed class StubApiClient : IGirofyApiClient
    {
        private readonly HealthStatus? _health;
        private readonly Exception? _exception;

        public StubApiClient(HealthStatus health) => _health = health;

        public StubApiClient(Exception exception) => _exception = exception;

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
    }

    private sealed class StubBrowserService : IExternalBrowserService
    {
        public void Open(Uri uri)
        {
        }
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
