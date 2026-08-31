using System.Globalization;
using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public static class DashboardFormatting
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    public static string Money(decimal value) => $"R$ {value.ToString("N2", BrazilianCulture)}";

    public static string OptionalMoney(decimal? value) => value.HasValue ? Money(value.Value) : "Restrito";

    public static DateTimeOffset? LocalDateTime(string? value) => BrazilianDateFormatting.ToBusinessTime(value);

    public static string DateTimeText(string? value)
    {
        return BrazilianDateFormatting.FormatTimestamp(value);
    }

    public static DateOnly BusinessToday()
    {
        return BrazilianDateFormatting.BusinessToday();
    }
}

public sealed class DashboardSnapshot
{
    [JsonPropertyName("period")]
    public DashboardPeriod Period { get; init; } = new();
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

    [JsonPropertyName("revenue_series")]
    public DashboardRevenueSeries RevenueSeries { get; init; } = new();

    [JsonPropertyName("category_sales")]
    public IReadOnlyList<DashboardCategorySale> CategorySales { get; init; } = [];

    [JsonPropertyName("low_stock_products")]
    public IReadOnlyList<DashboardLowStockProduct> LowStockProducts { get; init; } = [];

    [JsonPropertyName("recent_sales")]
    public IReadOnlyList<DashboardRecentSale> RecentSales { get; init; } = [];

    [JsonPropertyName("upcoming_payables")]
    public IReadOnlyList<DashboardPayable> UpcomingPayables { get; init; } = [];

    public string ReferenceDateText => string.IsNullOrWhiteSpace(Period.Label) ? "Operação de hoje" : Period.Label;
    public string PeriodRangeText => string.IsNullOrWhiteSpace(Period.StartDate) || string.IsNullOrWhiteSpace(Period.EndDate)
        ? ReferenceDateText
        : $"{ReferenceDateText} · {FormatPeriodDate(Period.StartDate)} a {FormatPeriodDate(Period.EndDate)}";
    public bool HasRevenueData => Summary.SalesCount > 0 && RevenueSeries.Points.Any(point => point.Total > 0);
    public bool HasCategorySales => CategorySales.Any(item => item.Total > 0);
    public bool HasTopProducts => TopProducts.Count > 0;
    public bool HasRecentSales => RecentSales.Count > 0;
    public bool HasLowStockProducts => LowStockProducts.Count > 0;
    public bool HasUpcomingPayables => UpcomingPayables.Count > 0;

    private static string FormatPeriodDate(string value) =>
        DateOnly.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.None, out var date)
            ? date.ToString("dd/MM/yyyy", CultureInfo.InvariantCulture)
            : value.Replace('-', '/');
}

public sealed class DashboardPeriod
{
    [JsonPropertyName("key")] public string Key { get; init; } = "today";
    [JsonPropertyName("label")] public string Label { get; init; } = "Hoje";
    [JsonPropertyName("start_date")] public string StartDate { get; init; } = string.Empty;
    [JsonPropertyName("end_date")] public string EndDate { get; init; } = string.Empty;
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

    [JsonPropertyName("sales_total_change")] public decimal? SalesTotalChange { get; init; }
    [JsonPropertyName("sales_count_change")] public decimal? SalesCountChange { get; init; }
    [JsonPropertyName("profit_change")] public decimal? ProfitChange { get; init; }
    [JsonPropertyName("customers_available")] public bool CustomersAvailable { get; init; }

    public string SalesTotalText => DashboardFormatting.Money(SalesTotal);

    public string SalesCountText => SalesCount == 1 ? "1 venda" : $"{SalesCount} vendas";

    public string SalesCountDetailText => $"{SalesCountChangeText} · ticket {AverageTicketText}";

    public string AverageTicketText => DashboardFormatting.OptionalMoney(AverageTicket);

    public string ProfitText => DashboardFormatting.OptionalMoney(Profit);

    public string ProfitSummaryText => $"Lucro hoje: {ProfitText}";

    public string LowStockText => LowStockCount == 1 ? "1 produto" : $"{LowStockCount} produtos";
    public string SalesTotalChangeText => ChangeText(SalesTotalChange);
    public string SalesCountChangeText => ChangeText(SalesCountChange);
    public string ProfitChangeText => ChangeText(ProfitChange);
    private static string ChangeText(decimal? value) => !value.HasValue ? "Sem base anterior" : $"{(value >= 0 ? "↑" : "↓")} {Math.Abs(value.Value):N1}% vs. anterior";
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
    [JsonPropertyName("category")]
    public string Category { get; init; } = "Sem categoria";
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

public sealed class DashboardRevenueSeries
{
    [JsonPropertyName("granularity")] public string Granularity { get; init; } = "day";
    [JsonPropertyName("points")] public IReadOnlyList<DashboardRevenuePoint> Points { get; init; } = [];
}

public sealed class DashboardRevenuePoint
{
    [JsonPropertyName("label")] public string Label { get; init; } = string.Empty;
    [JsonPropertyName("total")] public decimal Total { get; init; }
    [JsonPropertyName("ratio")] public double Ratio { get; init; }
    public string TotalText => DashboardFormatting.Money(Total);
}

public sealed class DashboardCategorySale
{
    [JsonPropertyName("category")] public string Category { get; init; } = string.Empty;
    [JsonPropertyName("total")] public decimal Total { get; init; }
    [JsonPropertyName("percent")] public decimal Percent { get; init; }
    public string SummaryText => $"{Percent:N1}% · {DashboardFormatting.Money(Total)}";
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

    [JsonPropertyName("status")]
    public string Status { get; init; } = "completed";

    [JsonPropertyName("is_cancelled")]
    public bool IsCancelled { get; init; }

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

public sealed class SalesHistorySnapshot
{
    [JsonPropertyName("sales")]
    public IReadOnlyList<DashboardRecentSale> Sales { get; init; } = [];

    [JsonPropertyName("page")]
    public int Page { get; init; } = 1;

    [JsonPropertyName("per_page")]
    public int PerPage { get; init; } = 30;

    [JsonPropertyName("total")]
    public int Total { get; init; }

    [JsonPropertyName("has_more")]
    public bool HasMore { get; init; }
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

    public string DueDateText => BrazilianDateFormatting.TryParseDate(DueDate, out var parsed)
        ? $"{(Overdue ? "Vencida" : "Vence")} em {BrazilianDateFormatting.FormatDate(parsed)}"
        : "Vencimento não informado";
}
