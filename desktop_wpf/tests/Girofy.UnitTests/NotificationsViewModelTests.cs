using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class NotificationsViewModelTests
{
    [Fact]
    public async Task Popover_loads_only_unread_notifications()
    {
        var apiClient = new StubApiClient();
        using var viewModel = CreateViewModel(apiClient);

        await viewModel.InitializeAsync();

        Assert.Equal("false", apiClient.LastQuery?.ReadFilter);
        Assert.True(viewModel.HasUnread);
        Assert.Single(viewModel.Items);
    }

    [Fact]
    public async Task Mark_all_read_clears_bell_and_pending_items_immediately()
    {
        var apiClient = new StubApiClient();
        using var viewModel = CreateViewModel(apiClient);
        await viewModel.InitializeAsync();

        await viewModel.MarkAllReadCommand.ExecuteAsync();

        Assert.True(apiClient.MarkAllCalled);
        Assert.Equal(0, viewModel.UnreadCount);
        Assert.False(viewModel.HasUnread);
        Assert.False(viewModel.HasItems);
        Assert.True(viewModel.HasNoItems);
    }

    private static NotificationsViewModel CreateViewModel(StubApiClient apiClient)
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(new AuthSession
        {
            AccessToken = "access-token",
            RefreshToken = "refresh-token",
            User = new UserIdentity { Id = 4, Username = "operador" },
            Company = new CompanyIdentity { Id = 2, Name = "Adega JF" },
        });
        return new NotificationsViewModel(apiClient, sessionContext, enablePolling: false);
    }

    private sealed class StubApiClient : IGirofyApiClient
    {
        public NotificationQuery? LastQuery { get; private set; }
        public bool MarkAllCalled { get; private set; }

        public Task<NotificationSnapshot> GetNotificationsAsync(
            string accessToken,
            NotificationQuery query,
            CancellationToken cancellationToken)
        {
            LastQuery = query;
            return Task.FromResult(new NotificationSnapshot
            {
                Items = [new NotificationItem { Id = 10, Title = "Estoque baixo" }],
                Total = 1,
                UnreadCount = 1,
            });
        }

        public Task MarkAllNotificationsReadAsync(string accessToken, CancellationToken cancellationToken)
        {
            MarkAllCalled = true;
            return Task.CompletedTask;
        }

        public Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken) =>
            Task.FromException<HealthStatus>(new NotSupportedException());

        public Task<AuthSession> LoginAsync(string identifier, string password, CancellationToken cancellationToken) =>
            Task.FromException<AuthSession>(new NotSupportedException());

        public Task<AuthSession> RefreshSessionAsync(string refreshToken, CancellationToken cancellationToken) =>
            Task.FromException<AuthSession>(new NotSupportedException());

        public Task<AuthIdentity> GetCurrentIdentityAsync(string accessToken, CancellationToken cancellationToken) =>
            Task.FromException<AuthIdentity>(new NotSupportedException());

        public Task LogoutAsync(string accessToken, CancellationToken cancellationToken) =>
            Task.FromException(new NotSupportedException());

        public Task<DashboardSnapshot> GetDashboardSummaryAsync(string accessToken, CancellationToken cancellationToken) =>
            Task.FromException<DashboardSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(string accessToken, CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> OpenCashRegisterAsync(string accessToken, decimal openingAmount, CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> CloseCashRegisterAsync(string accessToken, int cashRegisterId, decimal closingAmount, CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

        public Task<CatalogCategoryList> GetCatalogCategoriesAsync(string accessToken, string search, CancellationToken cancellationToken) =>
            Task.FromException<CatalogCategoryList>(new NotSupportedException());

        public Task<CatalogProductList> GetCatalogProductsAsync(string accessToken, string search, int? categoryId, string activeFilter, string sort, int page, int perPage, CancellationToken cancellationToken) =>
            Task.FromException<CatalogProductList>(new NotSupportedException());

        public Task<SaleReceipt> CreateSaleAsync(string accessToken, string idempotencyKey, IReadOnlyList<SaleLineRequest> items, decimal discountAmount, IReadOnlyList<SalePaymentRequest> payments, CancellationToken cancellationToken) =>
            Task.FromException<SaleReceipt>(new NotSupportedException());
    }
}
