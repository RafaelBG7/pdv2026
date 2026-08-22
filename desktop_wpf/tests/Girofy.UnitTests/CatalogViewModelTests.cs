using Girofy.Application.Abstractions;
using Girofy.Application.Formatting;
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
    public void Product_exposes_complete_formatted_details_for_expanded_row()
    {
        var product = new CatalogProduct
        {
            Name = "Cesta Especial",
            Barcode = "7891234567890",
            Category = new CatalogCategoryReference { Id = 7, Name = "Presentes" },
            CostPrice = 40.50m,
            SalePrice = 65m,
            ProfitAmount = 24.50m,
            ProfitMarginPercent = 37.69m,
            StockQuantity = 2,
            MinStockQuantity = 3,
            IsKit = true,
            KitComponent = new CatalogCategoryReference { Id = 8, Name = "Vinho Base" },
            KitComponentQuantity = 2,
            Active = true,
        };

        Assert.Equal("7891234567890", product.BarcodeText);
        Assert.Equal("Presentes", product.CategoryName);
        Assert.Equal("R$ 40,50", product.CostPriceText);
        Assert.Equal("R$ 65,00", product.SalePriceText);
        Assert.Equal("R$ 24,50", product.ProfitAmountText);
        Assert.Equal("37,69%", product.ProfitMarginText);
        Assert.Equal("Baixa 2 un. de Vinho Base", product.KitCompositionText);
        Assert.Equal("2 un.", product.StockText);
        Assert.Equal("3 un.", product.MinStockText);
        Assert.Equal("Kit", product.ProductTypeText);
        Assert.Equal("Estoque baixo", product.StockStatusText);
        Assert.Equal("Ativo", product.StatusText);
    }

    [Fact]
    public void Product_detail_uses_safe_fallbacks_for_optional_values()
    {
        var product = new CatalogProduct();

        Assert.Equal("Não informado", product.BarcodeText);
        Assert.Equal("Sem categoria", product.CategoryName);
        Assert.Equal("Não disponível", product.CostPriceText);
        Assert.Equal("Não disponível", product.ProfitAmountText);
        Assert.Equal("Não disponível", product.ProfitMarginText);
        Assert.Equal("Não se aplica", product.KitCompositionText);
        Assert.Equal("Produto unitário", product.ProductTypeText);
        Assert.Equal("Sem estoque", product.StockStatusText);
        Assert.Equal("Inativo", product.StatusText);
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
        viewModel.SelectedStockFilter = viewModel.StockFilters[2];
        viewModel.MinPriceText = "5,50";
        viewModel.MaxPriceText = "20,00";
        viewModel.IsMinPriceFilterActive = true;
        viewModel.IsMaxPriceFilterActive = true;
        viewModel.SelectedSort = viewModel.SortOptions[6];

        await viewModel.SearchCommand.ExecuteAsync();

        Assert.Equal("coca", apiClient.LastSearch);
        Assert.Equal(7, apiClient.LastCategoryId);
        Assert.Equal("active", apiClient.LastActiveFilter);
        Assert.Equal("low", apiClient.LastStockFilter);
        Assert.Equal(5.50m, apiClient.LastMinPrice);
        Assert.Equal(20m, apiClient.LastMaxPrice);
        Assert.Equal("created_desc", apiClient.LastSort);
        Assert.Equal(1, apiClient.LastPage);
    }

    [Fact]
    public async Task Search_rejects_invalid_price_range_before_calling_api()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();
        var requestsBeforeSearch = apiClient.ProductListRequestCount;
        viewModel.MinPriceText = "30,00";
        viewModel.MaxPriceText = "10,00";
        viewModel.IsMinPriceFilterActive = true;
        viewModel.IsMaxPriceFilterActive = true;

        await viewModel.SearchCommand.ExecuteAsync();

        Assert.Equal(requestsBeforeSearch, apiClient.ProductListRequestCount);
        Assert.Equal("O preço mínimo não pode ser maior que o preço máximo.", viewModel.ErrorMessage);
    }

    [Fact]
    public async Task Clear_product_filters_restores_defaults_and_reloads_catalog()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();
        viewModel.SearchText = "coca";
        viewModel.SelectedStockFilter = viewModel.StockFilters[3];
        viewModel.MinPriceText = "5";
        viewModel.MaxPriceText = "20";
        viewModel.SelectedSort = viewModel.SortOptions[7];

        await viewModel.ClearProductFiltersCommand.ExecuteAsync();

        Assert.Empty(viewModel.SearchText);
        Assert.Equal("0,00", viewModel.MinPriceText);
        Assert.Equal("0,00", viewModel.MaxPriceText);
        Assert.False(viewModel.IsMinPriceFilterActive);
        Assert.False(viewModel.IsMaxPriceFilterActive);
        Assert.Equal("all", apiClient.LastStockFilter);
        Assert.Null(apiClient.LastMinPrice);
        Assert.Null(apiClient.LastMaxPrice);
        Assert.Equal("name", apiClient.LastSort);
    }

    [Theory]
    [InlineData("1", "0,01")]
    [InlineData("12", "0,12")]
    [InlineData("123", "1,23")]
    [InlineData("1234", "12,34")]
    public void Money_formatter_enters_values_from_right_to_left(string input, string expected)
    {
        Assert.Equal(expected, BrazilianMoneyFormatter.FormatDigits(input));
    }

    [Theory]
    [InlineData("12,50", "12,50")]
    [InlineData("12.50", "12,50")]
    [InlineData("R$ 12,50", "12,50")]
    [InlineData("1.234,56", "1.234,56")]
    [InlineData("1234.56", "1.234,56")]
    public void Money_formatter_normalizes_pasted_values(string input, string expected)
    {
        Assert.True(BrazilianMoneyFormatter.TryNormalize(input, out var formatted));
        Assert.Equal(expected, formatted);
    }

    [Fact]
    public void Money_formatter_removes_digits_in_reverse_order_without_becoming_empty()
    {
        var value = "1.234,56";
        var expected = new[] { "123,45", "12,34", "1,23", "0,12", "0,01", "0,00", "0,00" };

        foreach (var step in expected)
        {
            value = BrazilianMoneyFormatter.RemoveLastDigit(value);
            Assert.Equal(step, value);
        }
    }

    [Theory]
    [InlineData("0,01", "0.01")]
    [InlineData("1,00", "1.00")]
    [InlineData("10,50", "10.50")]
    [InlineData("99,90", "99.90")]
    [InlineData("1.234,56", "1234.56")]
    [InlineData("12.345,67", "12345.67")]
    public void Money_formatter_preserves_decimal_precision(string input, string expected)
    {
        Assert.True(BrazilianMoneyFormatter.TryParse(input, out var amount));
        Assert.Equal(decimal.Parse(expected, System.Globalization.CultureInfo.InvariantCulture), amount);
        Assert.Equal(input, BrazilianMoneyFormatter.Format(amount));
    }

    [Fact]
    public async Task Untouched_zero_price_filters_are_sent_as_null()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        await viewModel.SearchCommand.ExecuteAsync();

        Assert.Equal("0,00", viewModel.MinPriceText);
        Assert.Equal("0,00", viewModel.MaxPriceText);
        Assert.Null(apiClient.LastMinPrice);
        Assert.Null(apiClient.LastMaxPrice);
    }

    [Fact]
    public async Task Category_search_uses_api_query_without_changing_product_category_options()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();
        viewModel.CategorySearchText = "refrigerantes";

        await viewModel.SearchCategoriesCommand.ExecuteAsync();

        Assert.Equal("refrigerantes", apiClient.LastCategorySearch);
        Assert.Single(viewModel.CategoryRows);
        Assert.Single(viewModel.ProductCategories);
        Assert.Equal("1 categoria encontrada", viewModel.CategorySummary);
    }

    [Fact]
    public async Task Clearing_category_search_restores_unfiltered_query()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();
        viewModel.CategorySearchText = "refrigerantes";
        await viewModel.SearchCategoriesCommand.ExecuteAsync();

        await viewModel.ClearCategorySearchCommand.ExecuteAsync();

        Assert.Empty(viewModel.CategorySearchText);
        Assert.Empty(apiClient.LastCategorySearch);
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
        viewModel.EditorCostPrice = "7,25";
        viewModel.EditorSalePrice = "12,50";
        viewModel.EditorStockQuantity = "12";
        viewModel.EditorMinStockQuantity = "3";
        viewModel.EditorStockReason = "Carga inicial";

        await viewModel.SaveProductCommand.ExecuteAsync();

        Assert.NotNull(apiClient.CreatedProductRequest);
        Assert.Equal("Água Mineral", apiClient.CreatedProductRequest.Name);
        Assert.Equal(7, apiClient.CreatedProductRequest.CategoryId);
        Assert.Equal(7.25m, apiClient.CreatedProductRequest.CostPrice);
        Assert.Equal(12.50m, apiClient.CreatedProductRequest.SalePrice);
        Assert.Equal(12, apiClient.CreatedProductRequest.StockQuantity);
        Assert.False(viewModel.IsProductEditorOpen);
    }

    [Fact]
    public async Task Barcode_input_accepts_manual_or_scanner_text_and_commits_without_saving()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.OpenNewProductCommand.Execute(null);
        viewModel.EditorBarcode = "  7894900011517\r\n";
        viewModel.CommitEditorBarcodeInput();

        Assert.Equal("7894900011517", viewModel.EditorBarcode);
        Assert.Null(apiClient.CreatedProductRequest);
        Assert.True(viewModel.IsProductEditorOpen);
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
    public async Task Save_new_kit_sends_component_contract()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();
        var component = viewModel.Products[0];

        viewModel.OpenNewProductCommand.Execute(null);
        viewModel.EditorName = "Kit Coca Cola";
        viewModel.EditorSalePrice = "24,00";
        viewModel.EditorIsKit = true;
        viewModel.EditorKitComponent = component;
        viewModel.EditorKitComponentQuantity = "2";

        await viewModel.SaveProductCommand.ExecuteAsync();

        Assert.NotNull(apiClient.CreatedProductRequest);
        Assert.True(apiClient.CreatedProductRequest.IsKit);
        Assert.Equal(9, apiClient.CreatedProductRequest.KitComponentProductId);
        Assert.Equal(2, apiClient.CreatedProductRequest.KitComponentQuantity);
    }

    [Fact]
    public async Task Delete_existing_product_calls_api_and_closes_editor()
    {
        var sessionContext = new AppSessionContext();
        sessionContext.Set(CreateSession());
        var apiClient = new StubApiClient();
        using var viewModel = new CatalogViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.SelectedProduct = viewModel.Products[0];
        viewModel.OpenEditProductCommand.Execute(null);
        await viewModel.DeleteProductCommand.ExecuteAsync();

        Assert.Equal(9, apiClient.DeletedProductId);
        Assert.False(viewModel.IsProductEditorOpen);
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

        public string LastCategorySearch { get; private set; } = string.Empty;

        public int? LastCategoryId { get; private set; }

        public string LastActiveFilter { get; private set; } = string.Empty;

        public string LastStockFilter { get; private set; } = string.Empty;

        public decimal? LastMinPrice { get; private set; }

        public decimal? LastMaxPrice { get; private set; }

        public string LastSort { get; private set; } = string.Empty;

        public int LastPage { get; private set; }

        public int ProductListRequestCount { get; private set; }

        public CatalogProductMutationRequest? CreatedProductRequest { get; private set; }

        public CatalogProductMutationRequest? UpdatedProductRequest { get; private set; }

        public int? UpdatedProductId { get; private set; }

        public int? DeletedProductId { get; private set; }

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
            LastCategorySearch = search;
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
            => GetCatalogProductsAsync(
                accessToken,
                search,
                categoryId,
                activeFilter,
                "all",
                null,
                null,
                sort,
                page,
                perPage,
                cancellationToken);

        public Task<CatalogProductList> GetCatalogProductsAsync(
            string accessToken,
            string search,
            int? categoryId,
            string activeFilter,
            string stockFilter,
            decimal? minPrice,
            decimal? maxPrice,
            string sort,
            int page,
            int perPage,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            LastSearch = search;
            LastCategoryId = categoryId;
            LastActiveFilter = activeFilter;
            LastStockFilter = stockFilter;
            LastMinPrice = minPrice;
            LastMaxPrice = maxPrice;
            LastSort = sort;
            LastPage = page;
            ProductListRequestCount++;
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

        public Task DeleteCatalogProductAsync(
            string accessToken,
            int productId,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            DeletedProductId = productId;
            return Task.CompletedTask;
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
