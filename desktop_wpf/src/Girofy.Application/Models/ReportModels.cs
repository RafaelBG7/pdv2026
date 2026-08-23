using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class ReportsSnapshot
{
    [JsonPropertyName("period")]
    public string Period { get; init; } = "daily";

    [JsonPropertyName("period_label")]
    public string PeriodLabel { get; init; } = string.Empty;

    [JsonPropertyName("start_date")]
    public string StartDate { get; init; } = string.Empty;

    [JsonPropertyName("end_date")]
    public string EndDate { get; init; } = string.Empty;

    [JsonPropertyName("chart_metric")]
    public string ChartMetric { get; init; } = "revenue";

    [JsonPropertyName("summary")]
    public ReportSummary Summary { get; init; } = new();

    [JsonPropertyName("payment_totals")]
    public IReadOnlyList<ReportPaymentTotal> PaymentTotals { get; init; } = [];

    [JsonPropertyName("top_products")]
    public IReadOnlyList<ReportTopProduct> TopProducts { get; init; } = [];

    [JsonPropertyName("chart")]
    public ReportChart Chart { get; init; } = new();

    public string PeriodDescription => BuildPeriodDescription(StartDate, EndDate, PeriodLabel, "Período atual");

    internal static string BuildPeriodDescription(string? startDate, string? endDate, string? label, string fallback)
    {
        var hasStart = BrazilianDateFormatting.TryParseDate(startDate, out var start);
        var hasEnd = BrazilianDateFormatting.TryParseDate(endDate, out var end);
        if (hasStart && hasEnd)
        {
            return start == end
                ? BrazilianDateFormatting.FormatDate(start)
                : $"{BrazilianDateFormatting.FormatDate(start)} a {BrazilianDateFormatting.FormatDate(end)}";
        }

        return string.IsNullOrWhiteSpace(label) ? fallback : label;
    }
}

public sealed class ReportSummary
{
    [JsonPropertyName("sales_count")]
    public int SalesCount { get; init; }

    [JsonPropertyName("items_count")]
    public int ItemsCount { get; init; }

    [JsonPropertyName("subtotal")]
    public decimal Subtotal { get; init; }

    [JsonPropertyName("discount")]
    public decimal Discount { get; init; }

    [JsonPropertyName("final")]
    public decimal Final { get; init; }

    [JsonPropertyName("profit")]
    public decimal Profit { get; init; }

    [JsonPropertyName("average_ticket")]
    public decimal AverageTicket { get; init; }

    public string SalesCountText => SalesCount == 1 ? "1 venda" : $"{SalesCount} vendas";

    public string ItemsCountText => ItemsCount == 1 ? "1 item" : $"{ItemsCount} itens";

    public string SubtotalText => DashboardFormatting.Money(Subtotal);

    public string DiscountText => DashboardFormatting.Money(Discount);

    public string FinalText => DashboardFormatting.Money(Final);

    public string ProfitText => DashboardFormatting.Money(Profit);

    public string AverageTicketText => DashboardFormatting.Money(AverageTicket);
}

public sealed class ReportPaymentTotal
{
    [JsonPropertyName("method")]
    public string Method { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;

    [JsonPropertyName("amount")]
    public decimal Amount { get; init; }

    public string AmountText => DashboardFormatting.Money(Amount);
}

public sealed class ReportTopProduct
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
    public decimal Profit { get; init; }

    public string QuantityText => $"{Quantity} un.";

    public string TotalText => DashboardFormatting.Money(Total);

    public string ProfitText => DashboardFormatting.Money(Profit);
}

public sealed class ReportChart
{
    [JsonPropertyName("metric")]
    public string Metric { get; init; } = "revenue";

    [JsonPropertyName("buckets")]
    public IReadOnlyList<ReportChartBucket> Buckets { get; init; } = [];

    [JsonPropertyName("peak")]
    public ReportChartBucket? Peak { get; init; }

    [JsonPropertyName("peak_by_quantity")]
    public ReportChartBucket? PeakByQuantity { get; init; }

    [JsonPropertyName("peak_by_revenue")]
    public ReportChartBucket? PeakByRevenue { get; init; }

    public string MetricLabel => string.Equals(Metric, "quantity", StringComparison.OrdinalIgnoreCase)
        ? "Quantidade"
        : "Faturamento";

    public string PeakText => Peak is null
        ? "Sem pico no período"
        : $"{Peak.Title}: {Peak.SalesCountText} · {Peak.AmountText}";

    public string QuantityPeakText => PeakByQuantity is null
        ? "Sem vendas"
        : $"{PeakByQuantity.Title} · {PeakByQuantity.SalesCountText}";

    public string RevenuePeakText => PeakByRevenue is null
        ? "Sem faturamento"
        : $"{PeakByRevenue.Title} · {PeakByRevenue.AmountText}";
}

public sealed class ReportChartBucket
{
    [JsonPropertyName("key")]
    public string Key { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;

    [JsonPropertyName("title")]
    public string Title { get; init; } = string.Empty;

    [JsonPropertyName("sales_count")]
    public int SalesCount { get; init; }

    [JsonPropertyName("total")]
    public decimal Total { get; init; }

    [JsonPropertyName("percent")]
    public decimal Percent { get; init; }

    [JsonPropertyName("is_peak")]
    public bool IsPeak { get; init; }

    public string SalesCountText => SalesCount == 1 ? "1 venda" : $"{SalesCount} vendas";

    public string AmountText => DashboardFormatting.Money(Total);

    public string TooltipText => $"{Title}\n{SalesCountText} · {AmountText}";

    public double BarWidth => Math.Max(6.0, (double)Percent * 2.3);

    public double ChartHeight => Math.Max(4.0, (double)Percent * 2.15);

    public bool ShowAxisLabel => Key.Length != 2 ||
        !int.TryParse(Key, out var hour) ||
        hour % 3 == 0;
}

public sealed record ReportsQuery(
    string Period,
    string ChartMetric,
    string? StartDate,
    string? EndDate);

public sealed class ProductReportSnapshot
{
    [JsonPropertyName("period")]
    public string Period { get; init; } = "daily";

    [JsonPropertyName("period_label")]
    public string PeriodLabel { get; init; } = string.Empty;

    [JsonPropertyName("start_date")]
    public string StartDate { get; init; } = string.Empty;

    [JsonPropertyName("end_date")]
    public string EndDate { get; init; } = string.Empty;

    [JsonPropertyName("search")]
    public string Search { get; init; } = string.Empty;

    [JsonPropertyName("category_id")]
    public int CategoryId { get; init; }

    [JsonPropertyName("product_id")]
    public int ProductId { get; init; }

    [JsonPropertyName("summary")]
    public ProductReportSummary Summary { get; init; } = new();

    [JsonPropertyName("items")]
    public IReadOnlyList<ProductReportItem> Items { get; init; } = [];

    [JsonPropertyName("pagination")]
    public ReportPagination Pagination { get; init; } = new();

    [JsonPropertyName("sort")]
    public string Sort { get; init; } = "quantity_desc";

    [JsonPropertyName("sort_options")]
    public IReadOnlyList<ReportOption> SortOptions { get; init; } = [];

    public string PeriodDescription => ReportsSnapshot.BuildPeriodDescription(
        StartDate,
        EndDate,
        PeriodLabel,
        "Produtos no período atual");
}

public sealed class ProductReportSummary
{
    [JsonPropertyName("products")]
    public int Products { get; init; }

    [JsonPropertyName("quantity")]
    public int Quantity { get; init; }

    [JsonPropertyName("revenue")]
    public decimal Revenue { get; init; }

    [JsonPropertyName("cost")]
    public decimal Cost { get; init; }

    [JsonPropertyName("profit")]
    public decimal Profit { get; init; }

    [JsonPropertyName("average_ticket")]
    public decimal AverageTicket { get; init; }

    public string ProductsText => Products == 1 ? "1 produto" : $"{Products} produtos";

    public string QuantityText => $"{Quantity} un.";

    public string RevenueText => DashboardFormatting.Money(Revenue);

    public string CostText => DashboardFormatting.Money(Cost);

    public string ProfitText => DashboardFormatting.Money(Profit);

    public string AverageTicketText => DashboardFormatting.Money(AverageTicket);
}

public sealed class ProductReportItem
{
    [JsonPropertyName("product_id")]
    public int ProductId { get; init; }

    [JsonPropertyName("product_name")]
    public string ProductName { get; init; } = string.Empty;

    [JsonPropertyName("barcode")]
    public string Barcode { get; init; } = string.Empty;

    [JsonPropertyName("category_id")]
    public int? CategoryId { get; init; }

    [JsonPropertyName("category_name")]
    public string CategoryName { get; init; } = "Sem categoria";

    [JsonPropertyName("quantity")]
    public int Quantity { get; init; }

    [JsonPropertyName("revenue")]
    public decimal Revenue { get; init; }

    [JsonPropertyName("cost")]
    public decimal Cost { get; init; }

    [JsonPropertyName("profit")]
    public decimal Profit { get; init; }

    [JsonPropertyName("average_ticket")]
    public decimal AverageTicket { get; init; }

    [JsonPropertyName("stock")]
    public int Stock { get; init; }

    [JsonPropertyName("active")]
    public bool Active { get; init; }

    public string BarcodeText => string.IsNullOrWhiteSpace(Barcode) ? "Sem código" : Barcode;

    public string QuantityText => $"{Quantity} un.";

    public string RevenueText => DashboardFormatting.Money(Revenue);

    public string CostText => DashboardFormatting.Money(Cost);

    public string ProfitText => DashboardFormatting.Money(Profit);

    public string AverageTicketText => DashboardFormatting.Money(AverageTicket);

    public string StockText => $"{Stock} un.";

    public string StatusText => Active ? "Ativo" : "Inativo";
}

public sealed class ReportPagination
{
    [JsonPropertyName("page")]
    public int Page { get; init; } = 1;

    [JsonPropertyName("per_page")]
    public int PerPage { get; init; } = 25;

    [JsonPropertyName("total")]
    public int Total { get; init; }

    [JsonPropertyName("pages")]
    public int Pages { get; init; } = 1;

    [JsonPropertyName("has_next")]
    public bool HasNext { get; init; }

    [JsonPropertyName("has_prev")]
    public bool HasPrevious { get; init; }

    public string PageText => Pages <= 0
        ? "Página 1 de 1"
        : $"Página {Page} de {Pages}";
}

public sealed class ReportOption
{
    [JsonPropertyName("value")]
    public string Value { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;
}

public sealed record ProductReportsQuery(
    string Period,
    string? StartDate,
    string? EndDate,
    string Search,
    string Sort,
    int Page,
    int PerPage);
