using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class CatalogViewModelTests
{
    [Fact]
    public async Task Initialize_loads_categories_and_first_product_page()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);

        await viewModel.InitializeAsync();

        Assert.Equal(2, viewModel.Categories.Count);
        Assert.Equal("Todas", viewModel.Categories[0].Name);
        Assert.Single(viewModel.Products);
        Assert.Equal("Coca Cola 2L", viewModel.Products[0].Name);
        Assert.Equal("R$ 12,00", viewModel.Products[0].SalePriceText);
        Assert.Equal("1 produto encontrado", viewModel.ProductSummary);
        Assert.Equal("Página 1 de 1", viewModel.PageSummary);
        Assert.Equal("access-token", apiClient.LastAccessToken);
    }

    [Fact]
    public async Task Search_sends_selected_filters_and_resets_page()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();
        viewModel.SearchText = "coca";
        viewModel.SelectedCategory = viewModel.Categories[1];
        viewModel.SelectedActiveFilter = viewModel.ActiveFilters[1];
        viewModel.SelectedSort = viewModel.SortOptions[3];

        await viewModel.SearchCommand.ExecuteAsync();

        Assert.Equal("coca", apiClient.LastSearch);
        Assert.Equal(7, apiClient.LastCategoryId);
        Assert.Equal("active", apiClient.LastActiveFilter);
        Assert.Equal("price_desc", apiClient.LastSort);
        Assert.Equal(1, apiClient.LastPage);
    }

    [Fact]
    public async Task Clearing_session_removes_catalog_data()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        using var viewModel = new CatalogViewModel(new StubApiClient(), sessionContext);
        await viewModel.InitializeAsync();

        sessionContext.Clear();

        Assert.Empty(viewModel.Products);
        Assert.Empty(viewModel.Categories);
        Assert.Equal(0, viewModel.TotalProducts);
    }

    private static AuthSession CreateSession() => new()
    {
        AccessToken = "access-token",
        RefreshToken = "refresh-token",
        User = new UserIdentity
        {
            Id = 4,
            Username = "operador",
            Permissions = new Dictionary<string, bool> { ["can_view_products"] = true },
        },
        Company = new CompanyIdentity { Id = 2, Name = "Adega JF" },
    };

    private sealed class StubApiClient : IGirofyApiClient
    {
        public string LastAccessToken { get; private set; } = string.Empty;

        public string LastSearch { get; private set; } = string.Empty;

        public int? LastCategoryId { get; private set; }

        public string LastActiveFilter { get; private set; } = string.Empty;

        public string LastSort { get; private set; } = string.Empty;

        public int LastPage { get; private set; }

        public Task<CatalogCategoryList> GetCatalogCategoriesAsync(
            string accessToken,
            string search,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            return Task.FromResult(new CatalogCategoryList
            {
                Total = 1,
                Items =
                [
                    new CatalogCategory { Id = 7, Name = "Refrigerantes", ProductCount = 1 },
                ],
            });
        }

        public Task<CatalogProductList> GetCatalogProductsAsync(
            string accessToken,
            string search,
            int? categoryId,
            string activeFilter,
            string sort,
            int page,
            int perPage,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            LastSearch = search;
            LastCategoryId = categoryId;
            LastActiveFilter = activeFilter;
            LastSort = sort;
            LastPage = page;
            return Task.FromResult(new CatalogProductList
            {
                Items =
                [
                    new CatalogProduct
                    {
                        Id = 9,
                        Name = "Coca Cola 2L",
                        Category = new CatalogCategoryReference { Id = 7, Name = "Refrigerantes" },
                        SalePrice = 12,
                        StockQuantity = 8,
                        Active = true,
                    },
                ],
                Pagination = new CatalogPagination
                {
                    Page = page,
                    PerPage = perPage,
                    Total = 1,
                    TotalPages = 1,
                },
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
    }
}
