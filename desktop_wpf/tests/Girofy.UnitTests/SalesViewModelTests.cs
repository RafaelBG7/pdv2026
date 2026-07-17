using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class SalesViewModelTests
{
    [Fact]
    public async Task Search_orders_products_and_adds_the_selected_quantity()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "coca",
        };

        await viewModel.SearchCommand.ExecuteAsync();

        Assert.Equal(["Coca Cola 2L", "Coca Zero 2L"], viewModel.SearchResults.Select(item => item.Name));
        Assert.Equal("Coca Cola 2L", viewModel.SelectedSearchProduct?.Name);

        viewModel.QuantityText = "2";
        viewModel.AddProductCommand.Execute(null);

        Assert.Single(viewModel.CartItems);
        Assert.Equal(2, viewModel.CartItems[0].Quantity);
        Assert.Equal(24m, viewModel.Subtotal);
        Assert.Equal("R$ 24,00", viewModel.SubtotalText);
        Assert.Equal(string.Empty, viewModel.SearchText);
        Assert.Empty(viewModel.SearchResults);
    }

    [Fact]
    public async Task Failure_preserves_the_order_and_retry_reuses_the_idempotency_key()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient { FailFirstSaleAttempt = true };
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "789",
        };
        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.SelectedSearchProduct = viewModel.SearchResults.Single(item => item.Barcode == "789");
        viewModel.QuantityText = "2";
        viewModel.AddProductCommand.Execute(null);
        viewModel.DiscountText = "2,00";
        viewModel.MoneyText = "10,00";
        viewModel.FillPixCommand.Execute(null);

        Assert.Equal(22m, viewModel.Total);
        Assert.Equal("12,00", viewModel.PixText);

        await viewModel.FinalizeCommand.ExecuteAsync();

        Assert.True(viewModel.HasError);
        Assert.Contains("preservado", viewModel.ErrorMessage, StringComparison.OrdinalIgnoreCase);
        Assert.Single(viewModel.CartItems);
        Assert.Equal("2,00", viewModel.DiscountText);
        Assert.Equal("10,00", viewModel.MoneyText);
        Assert.Equal("12,00", viewModel.PixText);
        Assert.Single(apiClient.IdempotencyKeys);

        await viewModel.FinalizeCommand.ExecuteAsync();

        Assert.True(viewModel.HasReceipt);
        Assert.Equal(42, viewModel.Receipt?.Id);
        Assert.Empty(viewModel.CartItems);
        Assert.Equal(2, apiClient.IdempotencyKeys.Count);
        Assert.Equal(apiClient.IdempotencyKeys[0], apiClient.IdempotencyKeys[1]);
        Assert.Equal(2m, apiClient.LastDiscountAmount);
        Assert.Equal([10m, 12m], apiClient.LastPayments.Select(payment => payment.Amount));
    }

    [Fact]
    public async Task Discount_above_subtotal_is_rejected_before_the_api_call()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "789",
        };
        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.AddProductCommand.Execute(null);
        viewModel.DiscountText = "20,00";
        viewModel.MoneyText = "20,00";

        await viewModel.FinalizeCommand.ExecuteAsync();

        Assert.True(viewModel.HasError);
        Assert.Empty(apiClient.IdempotencyKeys);
        Assert.Single(viewModel.CartItems);
    }

    private static AppSessionContext SessionContext()
    {
        var context = new AppSessionContext();
        context.Set(new AuthSession
        {
            AccessToken = "access-token",
            RefreshToken = "refresh-token",
            User = new UserIdentity
            {
                Id = 4,
                Username = "operador",
                Permissions = new Dictionary<string, bool> { ["can_manage_sales"] = true },
            },
            Company = new CompanyIdentity { Id = 2, Name = "Adega JF" },
        });
        return context;
    }

    private sealed class StubApiClient : IGirofyApiClient
    {
        private int _saleAttempts;

        public bool FailFirstSaleAttempt { get; init; }

        public List<string> IdempotencyKeys { get; } = [];

        public decimal LastDiscountAmount { get; private set; }

        public IReadOnlyList<SalePaymentRequest> LastPayments { get; private set; } = [];

        public Task<CatalogProductList> GetCatalogProductsAsync(
            string accessToken,
            string search,
            int? categoryId,
            string activeFilter,
            string sort,
            int page,
            int perPage,
            CancellationToken cancellationToken) =>
            Task.FromResult(new CatalogProductList
            {
                Items =
                [
                    new CatalogProduct
                    {
                        Id = 10,
                        Name = "Coca Zero 2L",
                        Barcode = "790",
                        SalePrice = 13m,
                        StockQuantity = 5,
                        Active = true,
                    },
                    new CatalogProduct
                    {
                        Id = 9,
                        Name = "Coca Cola 2L",
                        Barcode = "789",
                        SalePrice = 12m,
                        StockQuantity = 8,
                        Active = true,
                    },
                ],
                Pagination = new CatalogPagination
                {
                    Page = 1,
                    PerPage = 30,
                    Total = 2,
                    TotalPages = 1,
                },
            });

        public Task<SaleReceipt> CreateSaleAsync(
            string accessToken,
            string idempotencyKey,
            IReadOnlyList<SaleLineRequest> items,
            decimal discountAmount,
            IReadOnlyList<SalePaymentRequest> payments,
            CancellationToken cancellationToken)
        {
            _saleAttempts++;
            IdempotencyKeys.Add(idempotencyKey);
            LastDiscountAmount = discountAmount;
            LastPayments = payments;
            if (FailFirstSaleAttempt && _saleAttempts == 1)
            {
                return Task.FromException<SaleReceipt>(new HttpRequestException("offline"));
            }

            return Task.FromResult(new SaleReceipt
            {
                Id = 42,
                IdempotencyKey = idempotencyKey,
                CashRegisterId = 8,
                Subtotal = 24m,
                DiscountAmount = 2m,
                FinalAmount = 22m,
                PaidAmount = 22m,
                Payments =
                [
                    new SaleReceiptPayment { Method = "money", Label = "Dinheiro", Amount = 10m },
                    new SaleReceiptPayment { Method = "pix", Label = "Pix", Amount = 12m },
                ],
            });
        }

        public Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken) =>
            Task.FromException<HealthStatus>(new NotSupportedException());

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
    }
}
