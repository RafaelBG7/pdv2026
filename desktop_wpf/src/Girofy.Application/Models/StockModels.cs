using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class StockMovementList
{
    [JsonPropertyName("items")]
    public IReadOnlyList<StockMovementRecord> Items { get; init; } = [];

    [JsonPropertyName("pagination")]
    public CatalogPagination Pagination { get; init; } = new();

    [JsonPropertyName("summary")]
    public StockMovementSummary Summary { get; init; } = new();

    [JsonPropertyName("movement_types")]
    public IReadOnlyList<CatalogFilterOption> MovementTypes { get; init; } = [];

    [JsonPropertyName("source_types")]
    public IReadOnlyList<CatalogFilterOption> SourceTypes { get; init; } = [];

    [JsonPropertyName("responsible_users")]
    public IReadOnlyList<CatalogFilterOption> ResponsibleUsers { get; init; } = [];

    [JsonPropertyName("costs_visible")]
    public bool CostsVisible { get; init; }
}

public sealed class StockMovementSummary
{
    [JsonPropertyName("entries_quantity")]
    public int EntriesQuantity { get; init; }

    [JsonPropertyName("exits_quantity")]
    public int ExitsQuantity { get; init; }

    [JsonPropertyName("movement_count")]
    public int MovementCount { get; init; }

    [JsonPropertyName("product_count")]
    public int ProductCount { get; init; }

    public string EntriesText => $"{EntriesQuantity} un.";

    public string ExitsText => $"{ExitsQuantity} un.";

    public string MovementCountText => MovementCount == 1 ? "1 movimentação" : $"{MovementCount} movimentações";

    public string ProductCountText => ProductCount == 1 ? "1 produto" : $"{ProductCount} produtos";
}

public sealed class StockMovementRecord
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("created_at")]
    public string? CreatedAt { get; init; }

    [JsonPropertyName("product")]
    public StockProductReference? Product { get; init; }

    [JsonPropertyName("user")]
    public StockUserReference? User { get; init; }

    [JsonPropertyName("movement_type")]
    public string MovementType { get; init; } = string.Empty;

    [JsonPropertyName("movement_type_label")]
    public string MovementTypeLabel { get; init; } = string.Empty;

    [JsonPropertyName("source_type")]
    public string SourceType { get; init; } = string.Empty;

    [JsonPropertyName("source_type_label")]
    public string SourceTypeLabel { get; init; } = string.Empty;

    [JsonPropertyName("origin")]
    public string Origin { get; init; } = string.Empty;

    [JsonPropertyName("origin_label")]
    public string OriginLabel { get; init; } = string.Empty;

    [JsonPropertyName("source_id")]
    public int? SourceId { get; init; }

    [JsonPropertyName("reference")]
    public string Reference { get; init; } = string.Empty;

    [JsonPropertyName("quantity")]
    public int Quantity { get; init; }

    [JsonPropertyName("signed_quantity")]
    public int SignedQuantity { get; init; }

    [JsonPropertyName("previous_stock")]
    public int PreviousStock { get; init; }

    [JsonPropertyName("new_stock")]
    public int NewStock { get; init; }

    [JsonPropertyName("unit_cost")]
    public decimal? UnitCost { get; init; }

    [JsonPropertyName("total_cost")]
    public decimal? TotalCost { get; init; }

    [JsonPropertyName("balance_consistent")]
    public bool BalanceConsistent { get; init; } = true;

    [JsonPropertyName("reason")]
    public string Reason { get; init; } = string.Empty;

    [JsonPropertyName("notes")]
    public string Notes { get; init; } = string.Empty;

    public string CreatedAtText => DashboardFormatting.DateTimeText(CreatedAt);

    public string ProductName => Product?.Name ?? "Produto removido";

    public string CategoryName => Product?.Category?.Name ?? "Sem categoria";

    public string UserName => User?.Username ?? "Sistema";

    public string TypeLabel => string.IsNullOrWhiteSpace(MovementTypeLabel)
        ? "Não informado"
        : MovementTypeLabel;

    public string OriginText => !string.IsNullOrWhiteSpace(OriginLabel)
        ? OriginLabel
        : !string.IsNullOrWhiteSpace(SourceTypeLabel)
            ? SourceTypeLabel
            : "Não informado";

    public string QuantityText
    {
        get
        {
            var value = SignedQuantity != 0 ? SignedQuantity : NewStock - PreviousStock;
            return $"{(value > 0 ? "+" : string.Empty)}{value} un.";
        }
    }

    public string PreviousStockText => $"{PreviousStock} un.";

    public string NewStockText => $"{NewStock} un.";

    public string UnitCostText => DashboardFormatting.OptionalMoney(UnitCost);

    public string TotalCostText => DashboardFormatting.OptionalMoney(TotalCost);

    public string ReasonText => string.IsNullOrWhiteSpace(Reason) ? "Não informado" : Reason;

    public string NotesText => string.IsNullOrWhiteSpace(Notes) ? "Sem observação" : Notes;

    public string ReferenceText => string.IsNullOrWhiteSpace(Reference) ? "Sem referência" : Reference;

    public string BalanceStatusText => BalanceConsistent ? "Saldo conferido" : "Saldo inconsistente";
}

public sealed class StockProductReference
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("category")]
    public CatalogCategoryReference? Category { get; init; }
}

public sealed class StockUserReference
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("username")]
    public string Username { get; init; } = string.Empty;
}

public sealed record StockMovementQuery(
    string Search,
    int? CategoryId,
    string MovementType,
    string SourceType,
    int? UserId,
    DateTime? StartDate,
    DateTime? EndDate,
    int Page,
    int PerPage);

public sealed record StockEntryRequest(
    [property: JsonPropertyName("product_id")] int ProductId,
    [property: JsonPropertyName("quantity")] int Quantity,
    [property: JsonPropertyName("unit_cost")] decimal UnitCost,
    [property: JsonPropertyName("reason")] string Reason,
    [property: JsonPropertyName("notes")] string Notes,
    [property: JsonPropertyName("update_cost")] bool UpdateCost);

public sealed record StockAdjustmentRequest(
    [property: JsonPropertyName("product_id")] int ProductId,
    [property: JsonPropertyName("adjustment_mode")] string AdjustmentMode,
    [property: JsonPropertyName("target_stock")] int TargetStock,
    [property: JsonPropertyName("direction")] string Direction,
    [property: JsonPropertyName("quantity")] int Quantity,
    [property: JsonPropertyName("reason")] string Reason,
    [property: JsonPropertyName("notes")] string Notes);

public sealed class StockAdjustmentResult
{
    [JsonPropertyName("changed")]
    public bool Changed { get; init; }

    [JsonPropertyName("message")]
    public string Message { get; init; } = string.Empty;

    [JsonPropertyName("movement")]
    public StockMovementRecord? Movement { get; init; }
}
