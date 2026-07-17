using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class DashboardViewModelTests
{
    [Fact]
    public async Task Initialize_loads_dashboard_for_current_session()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new DashboardViewModel(apiClient, sessionContext);

        await viewModel.InitializeAsync();

        Assert.True(viewModel.HasData);
        Assert.False(viewModel.HasError);
        Assert.Equal("access-token", apiClient.LastAccessToken);
        Assert.Equal("R$ 34,00", viewModel.Snapshot!.Summary.SalesTotalText);
        Assert.Equal("2 vendas", viewModel.Snapshot.Summary.SalesCountText);
        Assert.Equal("Aberto", viewModel.Snapshot.CashRegister.StatusText);
        Assert.Single(viewModel.Snapshot.RecentSales);
    }

    [Fact]
    public async Task Clearing_session_removes_dashboard_data()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        using var viewModel = new DashboardViewModel(new StubApiClient(), sessionContext);
        await viewModel.InitializeAsync();

        sessionContext.Clear();

        Assert.False(viewModel.HasData);
        Assert.Null(viewModel.Snapshot);
    }

    private static AuthSession CreateSession() => new()
    {
        AccessToken = "access-token",
        RefreshToken = "refresh-token",
        User = new UserIdentity { Id = 4, Username = "operador" },
        Company = new CompanyIdentity { Id = 2, Name = "Adega JF" },
    };

    private sealed class StubApiClient : IGirofyApiClient
    {
        public string LastAccessToken { get; private set; } = string.Empty;

        public Task<DashboardSnapshot> GetDashboardSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            return Task.FromResult(new DashboardSnapshot
            {
                Date = "2026-07-16",
                Summary = new DashboardSummary
                {
                    SalesCount = 2,
                    SalesTotal = 34,
                    AverageTicket = 17,
                    Profit = 15,
                    LowStockCount = 1,
                },
                CashRegister = new DashboardCashRegister
                {
                    Id = 5,
                    Status = "open",
                    SalesTotal = 34,
                },
                RecentSales =
                [
                    new DashboardRecentSale
                    {
                        Id = 10,
                        FinalAmount = 10,
                        UserName = "Operador",
                        PaymentMethods = ["Pix"],
                    },
                ],
            });
        }

        public Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken) =>
            Task.FromException<HealthStatus>(new NotSupportedException());

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

        public Task LogoutAsync(string accessToken, CancellationToken cancellationToken) =>
            Task.FromException(new NotSupportedException());

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
}
