using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class NotificationsViewModelTests
{
    [Fact]
    public async Task Initialize_loads_items_and_unread_badge()
    {
        var session = CreateSessionContext();
        var api = new StubApiClient();
        using var viewModel = new NotificationsViewModel(api, session);

        await viewModel.InitializeAsync();

        Assert.Single(viewModel.Items);
        Assert.Equal(1, viewModel.UnreadCount);
        Assert.True(viewModel.HasUnread);
        Assert.Equal("1", viewModel.UnreadText);
        Assert.Equal("access-token", api.LastAccessToken);
    }

    [Fact]
    public async Task Read_and_dismiss_commands_call_api_and_refresh()
    {
        var session = CreateSessionContext();
        var api = new StubApiClient();
        using var viewModel = new NotificationsViewModel(api, session);
        await viewModel.InitializeAsync();

        viewModel.MarkReadCommand.Execute(viewModel.Items[0]);
        await WaitUntilAsync(() => api.ReadId == 12);
        viewModel.DismissCommand.Execute(viewModel.Items[0]);
        await WaitUntilAsync(() => api.DismissedId == 12);

        Assert.Equal(12, api.ReadId);
        Assert.Equal(12, api.DismissedId);
        Assert.True(api.GetCalls >= 3);
    }

    [Fact]
    public async Task Clearing_session_removes_notifications_and_badge()
    {
        var session = CreateSessionContext();
        using var viewModel = new NotificationsViewModel(new StubApiClient(), session);
        await viewModel.InitializeAsync();

        session.Clear();

        Assert.Empty(viewModel.Items);
        Assert.Equal(0, viewModel.UnreadCount);
        Assert.False(viewModel.HasUnread);
    }

    private static AppSessionContext CreateSessionContext()
    {
        var context = new AppSessionContext();
        context.Set(new AuthSession
        {
            AccessToken = "access-token",
            RefreshToken = "refresh-token",
            User = new UserIdentity { Id = 4, Username = "operador" },
            Company = new CompanyIdentity { Id = 2, Name = "Adega JF" },
        });
        return context;
    }

    private static async Task WaitUntilAsync(Func<bool> condition)
    {
        for (var attempt = 0; attempt < 100 && !condition(); attempt++)
            await Task.Delay(10);
        Assert.True(condition());
    }

    private sealed class StubApiClient : IGirofyApiClient
    {
        public int GetCalls { get; private set; }
        public int? ReadId { get; private set; }
        public int? DismissedId { get; private set; }
        public string LastAccessToken { get; private set; } = string.Empty;

        public Task<NotificationSnapshot> GetNotificationsAsync(
            string accessToken, NotificationQuery query, CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            GetCalls++;
            return Task.FromResult(new NotificationSnapshot
            {
                Items = [new NotificationItem { Id = 12, Title = "Estoque baixo", Severity = "warning" }],
                Total = 1,
                UnreadCount = 1,
            });
        }

        public Task<NotificationItem> MarkNotificationReadAsync(
            string accessToken, int notificationId, CancellationToken cancellationToken)
        {
            ReadId = notificationId;
            return Task.FromResult(new NotificationItem { Id = notificationId, IsRead = true });
        }

        public Task DismissNotificationAsync(
            string accessToken, int notificationId, CancellationToken cancellationToken)
        {
            DismissedId = notificationId;
            return Task.CompletedTask;
        }

        public Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<AuthSession> LoginAsync(string identifier, string password, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<AuthSession> RefreshSessionAsync(string refreshToken, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<AuthIdentity> GetCurrentIdentityAsync(string accessToken, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task LogoutAsync(string accessToken, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<DashboardSnapshot> GetDashboardSummaryAsync(string accessToken, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(string accessToken, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<CashRegisterSnapshot> OpenCashRegisterAsync(string accessToken, decimal openingAmount, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<CashRegisterSnapshot> CloseCashRegisterAsync(string accessToken, int cashRegisterId, decimal closingAmount, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<CatalogCategoryList> GetCatalogCategoriesAsync(string accessToken, string search, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<CatalogProductList> GetCatalogProductsAsync(string accessToken, string search, int? categoryId, string activeFilter, string sort, int page, int perPage, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<SaleReceipt> CreateSaleAsync(string accessToken, string idempotencyKey, IReadOnlyList<SaleLineRequest> items, decimal discountAmount, IReadOnlyList<SalePaymentRequest> payments, CancellationToken cancellationToken) => throw new NotSupportedException();
    }
}
