using System.Globalization;
using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public static class DashboardFormatting
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    public static string Money(decimal value) => $"R$ {value.ToString("N2", BrazilianCulture)}";

    public static string OptionalMoney(decimal? value) => value.HasValue ? Money(value.Value) : "Restrito";

    public static string DateTimeText(string? value)
    {
        if (DateTimeOffset.TryParse(value, out var parsed))
        {
            return parsed.ToLocalTime().ToString("dd/MM/yyyy HH:mm", BrazilianCulture);
        }
        return "Data não informada";
    }
}

public sealed class DashboardSnapshot
{
    [JsonPropertyName("date")]
    public string Date { get; init; } = string.Empty;

    [JsonPropertyName("permissions")]
    public DashboardPermissions Permissions { get; init; } = new();

    [JsonPropertyName("summary")]
    public DashboardSummary Summary { get; init; } = new();

    [JsonPropertyName("cash_register")]
    public DashboardCashRegister CashRegister { get; init; } = new();

    [JsonPropertyName("payment_totals")]
    public IReadOnlyList<DashboardPaymentTotal> PaymentTotals { get; init; } = [];

    [JsonPropertyName("top_products")]
    public IReadOnlyList<DashboardTopProduct> TopProducts { get; init; } = [];

    [JsonPropertyName("low_stock_products")]
    public IReadOnlyList<DashboardLowStockProduct> LowStockProducts { get; init; } = [];

    [JsonPropertyName("recent_sales")]
    public IReadOnlyList<DashboardRecentSale> RecentSales { get; init; } = [];

    [JsonPropertyName("upcoming_payables")]
    public IReadOnlyList<DashboardPayable> UpcomingPayables { get; init; } = [];

    public string ReferenceDateText => DateTime.TryParse(Date, out var parsed)
        ? parsed.ToString("dd 'de' MMMM 'de' yyyy", CultureInfo.GetCultureInfo("pt-BR"))
        : "Operação de hoje";
}

public sealed class DashboardPermissions
{
    [JsonPropertyName("can_view_reports")]
    public bool CanViewReports { get; init; }

    [JsonPropertyName("can_manage_payables")]
    public bool CanManagePayables { get; init; }
}

public sealed class DashboardSummary
{
    [JsonPropertyName("sales_count")]
    public int SalesCount { get; init; }

    [JsonPropertyName("sales_total")]
    public decimal SalesTotal { get; init; }

    [JsonPropertyName("average_ticket")]
    public decimal? AverageTicket { get; init; }

    [JsonPropertyName("profit")]
    public decimal? Profit { get; init; }

    [JsonPropertyName("low_stock_count")]
    public int LowStockCount { get; init; }

    [JsonPropertyName("payables_due_count")]
    public int? PayablesDueCount { get; init; }

    public string SalesTotalText => DashboardFormatting.Money(SalesTotal);

    public string SalesCountText => SalesCount == 1 ? "1 venda" : $"{SalesCount} vendas";

    public string AverageTicketText => DashboardFormatting.OptionalMoney(AverageTicket);

    public string ProfitText => DashboardFormatting.OptionalMoney(Profit);

    public string ProfitSummaryText => $"Lucro hoje: {ProfitText}";

    public string LowStockText => LowStockCount == 1 ? "1 produto" : $"{LowStockCount} produtos";
}

public sealed class DashboardCashRegister
{
    [JsonPropertyName("id")]
    public int? Id { get; init; }

    [JsonPropertyName("status")]
    public string Status { get; init; } = "closed";

    [JsonPropertyName("opened_at")]
    public string? OpenedAt { get; init; }

    [JsonPropertyName("opening_amount")]
    public decimal? OpeningAmount { get; init; }

    [JsonPropertyName("sales_total")]
    public decimal? SalesTotal { get; init; }

    [JsonPropertyName("profit")]
    public decimal? Profit { get; init; }

    public bool IsOpen => string.Equals(Status, "open", StringComparison.OrdinalIgnoreCase);

    public string StatusText => IsOpen ? "Aberto" : "Fechado";

    public string DescriptionText => IsOpen && Id.HasValue
        ? $"Caixa #{Id.Value} · aberto em {DashboardFormatting.DateTimeText(OpenedAt)}"
        : "Nenhum caixa aberto";

    public string SalesTotalText => DashboardFormatting.OptionalMoney(SalesTotal);

    public string SalesSummaryText => IsOpen
        ? $"Vendas no caixa: {SalesTotalText}"
        : "Abra o caixa para iniciar vendas";
}

public sealed class DashboardPaymentTotal
{
    [JsonPropertyName("method")]
    public string Method { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;

    [JsonPropertyName("amount")]
    public decimal Amount { get; init; }

    public string AmountText => DashboardFormatting.Money(Amount);
}

public sealed class DashboardTopProduct
{
    [JsonPropertyName("product_id")]
    public int ProductId { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("quantity")]
    public int Quantity { get; init; }

    [JsonPropertyName("total")]
    public decimal Total { get; init; }

    [JsonPropertyName("profit")]
    public decimal? Profit { get; init; }

    public string QuantityText => $"{Quantity} un.";

    public string TotalText => DashboardFormatting.Money(Total);
}

public sealed class DashboardLowStockProduct
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("stock_quantity")]
    public int StockQuantity { get; init; }

    [JsonPropertyName("min_stock_quantity")]
    public int MinStockQuantity { get; init; }

    public string StockText => $"{StockQuantity} un.";

    public string MinimumText => $"Mínimo: {MinStockQuantity} un.";
}

public sealed class DashboardRecentSale
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("created_at")]
    public string? CreatedAt { get; init; }

    [JsonPropertyName("final_amount")]
    public decimal FinalAmount { get; init; }

    [JsonPropertyName("payment_status")]
    public string PaymentStatus { get; init; } = string.Empty;

    [JsonPropertyName("user_name")]
    public string UserName { get; init; } = string.Empty;

    [JsonPropertyName("payment_methods")]
    public IReadOnlyList<string> PaymentMethods { get; init; } = [];

    public string NumberText => $"#{Id}";

    public string DateText => DashboardFormatting.DateTimeText(CreatedAt);

    public string FinalAmountText => DashboardFormatting.Money(FinalAmount);

    public string PaymentText => PaymentMethods.Count == 0
        ? "Pagamento não informado"
        : string.Join(" + ", PaymentMethods);
}

public sealed class DashboardPayable
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("description")]
    public string Description { get; init; } = string.Empty;

    [JsonPropertyName("amount")]
    public decimal Amount { get; init; }

    [JsonPropertyName("due_date")]
    public string? DueDate { get; init; }

    [JsonPropertyName("overdue")]
    public bool Overdue { get; init; }

    public string AmountText => DashboardFormatting.Money(Amount);

    public string DueDateText => DateTime.TryParse(DueDate, out var parsed)
        ? $"{(Overdue ? "Vencida" : "Vence")} em {parsed:dd/MM/yyyy}"
        : "Vencimento não informado";
}
