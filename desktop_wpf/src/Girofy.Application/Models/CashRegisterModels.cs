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

    [JsonPropertyName("opening_amount")]
    public decimal? OpeningAmount { get; init; }

    [JsonPropertyName("closing_amount")]
    public decimal? ClosingAmount { get; init; }

    [JsonPropertyName("sales_total")]
    public decimal? SalesTotal { get; init; }

    [JsonPropertyName("expected_amount")]
    public decimal? ExpectedAmount { get; init; }

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
