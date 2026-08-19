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

    [JsonPropertyName("kit_component")]
    public CatalogCategoryReference? KitComponent { get; init; }

    [JsonPropertyName("kit_component_quantity")]
    public int KitComponentQuantity { get; init; }

    [JsonPropertyName("cost_price")]
    public decimal? CostPrice { get; init; }

    [JsonPropertyName("profit_amount")]
    public decimal? ProfitAmount { get; init; }

    [JsonPropertyName("profit_margin_percent")]
    public decimal? ProfitMarginPercent { get; init; }

    public string CategoryName => Category?.Name ?? "Sem categoria";

    public string SalePriceText => $"R$ {SalePrice.ToString("N2", BrazilianCulture)}";

    public string CostPriceText => CostPrice is decimal costPrice
        ? $"R$ {costPrice.ToString("N2", BrazilianCulture)}"
        : "Não disponível";

    public string ProfitAmountText => ProfitAmount is decimal profitAmount
        ? $"R$ {profitAmount.ToString("N2", BrazilianCulture)}"
        : "Não disponível";

    public string ProfitMarginText => ProfitMarginPercent is decimal profitMargin
        ? $"{profitMargin.ToString("N2", BrazilianCulture)}%"
        : "Não disponível";

    public string KitCompositionText => IsKit && KitComponent is not null && KitComponentQuantity > 0
        ? $"Baixa {KitComponentQuantity} un. de {KitComponent.Name}"
        : "Não se aplica";

    public string StockText => $"{StockQuantity} un.";

    public string MinStockText => $"{MinStockQuantity} un.";

    public string BarcodeText => string.IsNullOrWhiteSpace(Barcode)
        ? "Não informado"
        : Barcode;

    public string ProductTypeText => IsKit ? "Kit" : "Produto unitário";

    public string StockStatusText => StockQuantity <= 0
        ? "Sem estoque"
        : StockQuantity <= MinStockQuantity
            ? "Estoque baixo"
            : "Estoque adequado";

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

public sealed record CatalogProductMutationRequest(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("barcode")] string Barcode,
    [property: JsonPropertyName("category_id")] int? CategoryId,
    [property: JsonPropertyName("cost_price")] decimal CostPrice,
    [property: JsonPropertyName("sale_price")] decimal SalePrice,
    [property: JsonPropertyName("stock_quantity")] int StockQuantity,
    [property: JsonPropertyName("min_stock_quantity")] int MinStockQuantity,
    [property: JsonPropertyName("active")] bool Active,
    [property: JsonPropertyName("stock_reason")] string StockReason,
    [property: JsonPropertyName("is_kit")] bool IsKit = false,
    [property: JsonPropertyName("kit_component_product_id")] int? KitComponentProductId = null,
    [property: JsonPropertyName("kit_component_quantity")] int KitComponentQuantity = 0);

public sealed record CatalogCategoryMutationRequest(
    [property: JsonPropertyName("name")] string Name);
