using System.Globalization;
using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class CatalogCategory
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("product_count")]
    public int ProductCount { get; init; }
}

public sealed class CatalogCategoryReference
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;
}

public sealed class CatalogProduct
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("barcode")]
    public string Barcode { get; init; } = string.Empty;

    [JsonPropertyName("category")]
    public CatalogCategoryReference? Category { get; init; }

    [JsonPropertyName("sale_price")]
    public decimal SalePrice { get; init; }

    [JsonPropertyName("stock_quantity")]
    public int StockQuantity { get; init; }

    [JsonPropertyName("min_stock_quantity")]
    public int MinStockQuantity { get; init; }

    [JsonPropertyName("active")]
    public bool Active { get; init; }

    [JsonPropertyName("is_kit")]
    public bool IsKit { get; init; }

    [JsonPropertyName("cost_price")]
    public decimal? CostPrice { get; init; }

    [JsonPropertyName("profit_amount")]
    public decimal? ProfitAmount { get; init; }

    public string CategoryName => Category?.Name ?? "Sem categoria";

    public string SalePriceText => $"R$ {SalePrice.ToString("N2", BrazilianCulture)}";

    public string StockText => $"{StockQuantity} un.";

    public string StatusText => Active ? "Ativo" : "Inativo";
}

public sealed class CatalogCategoryList
{
    [JsonPropertyName("items")]
    public IReadOnlyList<CatalogCategory> Items { get; init; } = [];

    [JsonPropertyName("total")]
    public int Total { get; init; }
}

public sealed class CatalogProductList
{
    [JsonPropertyName("items")]
    public IReadOnlyList<CatalogProduct> Items { get; init; } = [];

    [JsonPropertyName("pagination")]
    public CatalogPagination Pagination { get; init; } = new();
}

public sealed class CatalogPagination
{
    [JsonPropertyName("page")]
    public int Page { get; init; }

    [JsonPropertyName("per_page")]
    public int PerPage { get; init; }

    [JsonPropertyName("total")]
    public int Total { get; init; }

    [JsonPropertyName("total_pages")]
    public int TotalPages { get; init; }
}

public sealed record CatalogFilterOption(string Value, string Label);
