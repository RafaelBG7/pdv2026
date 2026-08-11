using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class CashRegisterSnapshot
{
    [JsonPropertyName("permissions")]
    public CashRegisterPermissions Permissions { get; init; } = new();

    [JsonPropertyName("current_register")]
    public CashRegisterRecord? CurrentRegister { get; init; }

    [JsonPropertyName("recent_registers")]
    public IReadOnlyList<CashRegisterRecord> RecentRegisters { get; init; } = [];
}

public sealed class CashRegisterPermissions
{
    [JsonPropertyName("can_view_financials")]
    public bool CanViewFinancials { get; init; }
}

public sealed class CashRegisterDetailSnapshot
{
    [JsonPropertyName("permissions")]
    public CashRegisterPermissions Permissions { get; init; } = new();

    [JsonPropertyName("cash_register")]
    public CashRegisterRecord? CashRegister { get; init; }

    [JsonPropertyName("timeline")]
    public IReadOnlyList<CashRegisterTimelineSale> Timeline { get; init; } = [];

    public bool HasTimeline => Timeline.Count > 0;
}

public sealed class CashRegisterRecord
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("status")]
    public string Status { get; init; } = string.Empty;

    [JsonPropertyName("opened_at")]
    public string? OpenedAt { get; init; }

    [JsonPropertyName("closed_at")]
    public string? ClosedAt { get; init; }

    [JsonPropertyName("responsible_user")]
    public string ResponsibleUser { get; init; } = string.Empty;

    [JsonPropertyName("sales_count")]
    public int SalesCount { get; init; }

    [JsonPropertyName("cancelled_sales_count")]
    public int CancelledSalesCount { get; init; }

    [JsonPropertyName("opening_amount")]
    public decimal? OpeningAmount { get; init; }

    [JsonPropertyName("closing_amount")]
    public decimal? ClosingAmount { get; init; }

    [JsonPropertyName("sales_total")]
    public decimal? SalesTotal { get; init; }

    [JsonPropertyName("cancelled_sales_total")]
    public decimal? CancelledSalesTotal { get; init; }

    [JsonPropertyName("valid_sales_total")]
    public decimal? ValidSalesTotal { get; init; }

    [JsonPropertyName("expected_amount")]
    public decimal? ExpectedAmount { get; init; }

    [JsonPropertyName("adjusted_expected_amount")]
    public decimal? AdjustedExpectedAmount { get; init; }

    [JsonPropertyName("difference")]
    public decimal? Difference { get; init; }

    [JsonPropertyName("payment_totals")]
    public IReadOnlyList<CashRegisterPaymentTotal> PaymentTotals { get; init; } = [];

    public bool IsOpen => string.Equals(Status, "open", StringComparison.OrdinalIgnoreCase);

    public string NumberText => $"Caixa #{Id}";

    public string StatusText => IsOpen ? "Aberto" : "Fechado";

    public string OpenedAtText => DashboardFormatting.DateTimeText(OpenedAt);

    public string ClosedAtText => ClosedAt is null
        ? "Em andamento"
        : DashboardFormatting.DateTimeText(ClosedAt);

    public string SalesCountText => SalesCount == 1 ? "1 venda" : $"{SalesCount} vendas";

    public string OpeningAmountText => DashboardFormatting.OptionalMoney(OpeningAmount);

    public string ClosingAmountText => DashboardFormatting.OptionalMoney(ClosingAmount);

    public string SalesTotalText => DashboardFormatting.OptionalMoney(SalesTotal);

    public string ExpectedAmountText => DashboardFormatting.OptionalMoney(ExpectedAmount);

    public string DifferenceText => DashboardFormatting.OptionalMoney(Difference);

    public bool HasCancellationAdjustment => CancelledSalesCount > 0;

    public string CancellationAdjustmentText =>
        $"{CancelledSalesCount} venda(s) cancelada(s) · {DashboardFormatting.OptionalMoney(CancelledSalesTotal)} · total válido {DashboardFormatting.OptionalMoney(ValidSalesTotal)}";
}

public sealed class CashRegisterPaymentTotal
{
    [JsonPropertyName("method")]
    public string Method { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;

    [JsonPropertyName("amount")]
    public decimal Amount { get; init; }

    public string AmountText => DashboardFormatting.Money(Amount);
}

public sealed class CashRegisterTimelineSale
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("number")]
    public string Number { get; init; } = string.Empty;

    [JsonPropertyName("created_at")]
    public string? CreatedAt { get; init; }

    [JsonPropertyName("date")]
    public string Date { get; init; } = string.Empty;

    [JsonPropertyName("time")]
    public string Time { get; init; } = string.Empty;

    [JsonPropertyName("seller")]
    public string Seller { get; init; } = string.Empty;

    [JsonPropertyName("payment_status")]
    public string PaymentStatus { get; init; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; init; } = "completed";

    [JsonPropertyName("is_cancelled")]
    public bool IsCancelled { get; init; }

    [JsonPropertyName("cancelled_at")]
    public string? CancelledAt { get; init; }

    [JsonPropertyName("cancelled_by_user_id")]
    public int? CancelledByUserId { get; init; }

    [JsonPropertyName("cancellation_reason")]
    public string CancellationReason { get; init; } = string.Empty;

    [JsonPropertyName("payments_text")]
    public string PaymentsText { get; init; } = string.Empty;

    [JsonPropertyName("total_amount")]
    public decimal? TotalAmount { get; init; }

    [JsonPropertyName("discount_amount")]
    public decimal? DiscountAmount { get; init; }

    [JsonPropertyName("final_amount")]
    public decimal? FinalAmount { get; init; }

    [JsonPropertyName("balance_before_sale")]
    public decimal? BalanceBeforeSale { get; init; }

    [JsonPropertyName("balance_after_sale")]
    public decimal? BalanceAfterSale { get; init; }

    [JsonPropertyName("payments")]
    public IReadOnlyList<CashRegisterTimelinePayment> Payments { get; init; } = [];

    [JsonPropertyName("items")]
    public IReadOnlyList<CashRegisterTimelineItem> Items { get; init; } = [];

    public string HeaderText => $"{Time} · Venda {Number} · {Seller}";

    public string FinalAmountText => DashboardFormatting.OptionalMoney(FinalAmount);

    public string DiscountAmountText => DashboardFormatting.OptionalMoney(DiscountAmount);

    public string BalanceBeforeSaleText => DashboardFormatting.OptionalMoney(BalanceBeforeSale);

    public string BalanceAfterSaleText => DashboardFormatting.OptionalMoney(BalanceAfterSale);

    public string StatusText => IsCancelled
        ? "Cancelada"
        : string.Equals(PaymentStatus, "paid", StringComparison.OrdinalIgnoreCase)
            ? "Pago"
            : PaymentStatus;

    public bool HasItems => Items.Count > 0;

    public bool HasPayments => Payments.Count > 0;
}

public sealed class CashRegisterTimelinePayment
{
    [JsonPropertyName("method")]
    public string Method { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;

    [JsonPropertyName("amount")]
    public decimal? Amount { get; init; }

    public string AmountText => DashboardFormatting.OptionalMoney(Amount);
}

public sealed class CashRegisterTimelineItem
{
    [JsonPropertyName("product_id")]
    public int ProductId { get; init; }

    [JsonPropertyName("product_name")]
    public string ProductName { get; init; } = string.Empty;

    [JsonPropertyName("quantity")]
    public int Quantity { get; init; }

    [JsonPropertyName("unit_price")]
    public decimal? UnitPrice { get; init; }

    [JsonPropertyName("total_price")]
    public decimal? TotalPrice { get; init; }

    public string QuantityText => Quantity == 1 ? "1 un." : $"{Quantity} un.";

    public string UnitPriceText => DashboardFormatting.OptionalMoney(UnitPrice);

    public string TotalPriceText => DashboardFormatting.OptionalMoney(TotalPrice);
}
