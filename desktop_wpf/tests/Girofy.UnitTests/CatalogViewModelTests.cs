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
        Assert.Single(viewModel.CategoryRows);
        Assert.Equal("Refrigerantes", viewModel.CategoryRows[0].Name);
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

    [Fact]
    public async Task Save_new_product_sends_create_request_and_reloads_catalog()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.OpenNewProductCommand.Execute(null);
        viewModel.EditorName = "Água Mineral";
        viewModel.EditorBarcode = "789";
        viewModel.EditorCategory = viewModel.Categories[1];
        viewModel.EditorCostPrice = "2,50";
        viewModel.EditorSalePrice = "5,00";
        viewModel.EditorStockQuantity = "12";
        viewModel.EditorMinStockQuantity = "3";
        viewModel.EditorStockReason = "Carga inicial";

        await viewModel.SaveProductCommand.ExecuteAsync();

        Assert.NotNull(apiClient.CreatedProductRequest);
        Assert.Equal("Água Mineral", apiClient.CreatedProductRequest.Name);
        Assert.Equal(7, apiClient.CreatedProductRequest.CategoryId);
        Assert.Equal(2.50m, apiClient.CreatedProductRequest.CostPrice);
        Assert.Equal(5.00m, apiClient.CreatedProductRequest.SalePrice);
        Assert.Equal(12, apiClient.CreatedProductRequest.StockQuantity);
        Assert.False(viewModel.IsProductEditorOpen);
    }

    [Fact]
    public async Task Save_existing_product_sends_update_request()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.SelectedProduct = viewModel.Products[0];
        viewModel.OpenEditProductCommand.Execute(null);
        viewModel.EditorName = "Coca Cola 2L Retornavel";
        viewModel.EditorSalePrice = "13,50";
        viewModel.EditorStockQuantity = "6";
        viewModel.EditorActive = false;

        await viewModel.SaveProductCommand.ExecuteAsync();

        Assert.Equal(9, apiClient.UpdatedProductId);
        Assert.NotNull(apiClient.UpdatedProductRequest);
        Assert.Equal("Coca Cola 2L Retornavel", apiClient.UpdatedProductRequest.Name);
        Assert.Equal(13.50m, apiClient.UpdatedProductRequest.SalePrice);
        Assert.Equal(6, apiClient.UpdatedProductRequest.StockQuantity);
        Assert.False(apiClient.UpdatedProductRequest.Active);
    }

    [Fact]
    public async Task Save_new_category_sends_create_request_and_reloads_catalog()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.OpenNewCategoryCommand.Execute(null);
        viewModel.CategoryEditorName = "Destilados";

        await viewModel.SaveCategoryCommand.ExecuteAsync();

        Assert.NotNull(apiClient.CreatedCategoryRequest);
        Assert.Equal("Destilados", apiClient.CreatedCategoryRequest.Name);
        Assert.False(viewModel.IsCategoryEditorOpen);
    }

    [Fact]
    public async Task Save_existing_category_sends_update_request()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.SelectedCategoryRow = viewModel.CategoryRows[0];
        viewModel.OpenEditCategoryCommand.Execute(null);
        viewModel.CategoryEditorName = "Refrigerantes Gelados";

        await viewModel.SaveCategoryCommand.ExecuteAsync();

        Assert.Equal(7, apiClient.UpdatedCategoryId);
        Assert.NotNull(apiClient.UpdatedCategoryRequest);
        Assert.Equal("Refrigerantes Gelados", apiClient.UpdatedCategoryRequest.Name);
        Assert.False(viewModel.IsCategoryEditorOpen);
    }

    [Fact]
    public async Task Delete_category_calls_api_and_reloads_catalog()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.SelectedCategoryRow = viewModel.CategoryRows[0];

        await viewModel.DeleteCategoryCommand.ExecuteAsync();

        Assert.Equal(7, apiClient.DeletedCategoryId);
    }

    [Fact]
    public async Task Save_product_rejects_invalid_values_before_calling_api()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.OpenNewProductCommand.Execute(null);
        viewModel.EditorName = "Produto inválido";
        viewModel.EditorSalePrice = "abc";

        await viewModel.SaveProductCommand.ExecuteAsync();

        Assert.Null(apiClient.CreatedProductRequest);
        Assert.True(viewModel.HasError);
        Assert.Equal("Informe um valor de venda válido.", viewModel.ErrorMessage);
    }

    private static AuthSession CreateSession() => new()
    {
        AccessToken = "access-token",
        RefreshToken = "refresh-token",
        User = new UserIdentity
        {
            Id = 4,
            Username = "operador",
            Permissions = new Dictionary<string, bool>
            {
                ["can_view_products"] = true,
                ["can_manage_products"] = true,
                ["can_manage_categories"] = true,
            },
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

        public CatalogProductMutationRequest? CreatedProductRequest { get; private set; }

        public CatalogProductMutationRequest? UpdatedProductRequest { get; private set; }

        public int? UpdatedProductId { get; private set; }

        public CatalogCategoryMutationRequest? CreatedCategoryRequest { get; private set; }

        public CatalogCategoryMutationRequest? UpdatedCategoryRequest { get; private set; }

        public int? UpdatedCategoryId { get; private set; }

        public int? DeletedCategoryId { get; private set; }

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

        public Task<CatalogCategory> CreateCatalogCategoryAsync(
            string accessToken,
            CatalogCategoryMutationRequest category,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            CreatedCategoryRequest = category;
            return Task.FromResult(new CatalogCategory
            {
                Id = 31,
                Name = category.Name,
                ProductCount = 0,
            });
        }

        public Task<CatalogCategory> UpdateCatalogCategoryAsync(
            string accessToken,
            int categoryId,
            CatalogCategoryMutationRequest category,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            UpdatedCategoryId = categoryId;
            UpdatedCategoryRequest = category;
            return Task.FromResult(new CatalogCategory
            {
                Id = categoryId,
                Name = category.Name,
                ProductCount = 1,
            });
        }

        public Task DeleteCatalogCategoryAsync(
            string accessToken,
            int categoryId,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            DeletedCategoryId = categoryId;
            return Task.CompletedTask;
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

        public Task<CatalogProduct> CreateCatalogProductAsync(
            string accessToken,
            CatalogProductMutationRequest product,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            CreatedProductRequest = product;
            return Task.FromResult(new CatalogProduct
            {
                Id = 20,
                Name = product.Name,
                Category = product.CategoryId is > 0
                    ? new CatalogCategoryReference { Id = product.CategoryId.Value, Name = "Refrigerantes" }
                    : null,
                SalePrice = product.SalePrice,
                StockQuantity = product.StockQuantity,
                MinStockQuantity = product.MinStockQuantity,
                Active = product.Active,
                CostPrice = product.CostPrice,
            });
        }

        public Task<CatalogProduct> UpdateCatalogProductAsync(
            string accessToken,
            int productId,
            CatalogProductMutationRequest product,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            UpdatedProductId = productId;
            UpdatedProductRequest = product;
            return Task.FromResult(new CatalogProduct
            {
                Id = productId,
                Name = product.Name,
                Category = product.CategoryId is > 0
                    ? new CatalogCategoryReference { Id = product.CategoryId.Value, Name = "Refrigerantes" }
                    : null,
                SalePrice = product.SalePrice,
                StockQuantity = product.StockQuantity,
                MinStockQuantity = product.MinStockQuantity,
                Active = product.Active,
                CostPrice = product.CostPrice,
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
