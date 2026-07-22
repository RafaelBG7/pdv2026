using System.Globalization;
using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed record SaleLineRequest(
    [property: JsonPropertyName("product_id")] int ProductId,
    [property: JsonPropertyName("quantity")] int Quantity);

public sealed record SalePaymentRequest(
    [property: JsonPropertyName("method")] string Method,
    [property: JsonPropertyName("amount")] decimal Amount);

public sealed class SaleReceipt
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("idempotency_key")]
    public string IdempotencyKey { get; init; } = string.Empty;

    [JsonPropertyName("already_processed")]
    public bool AlreadyProcessed { get; init; }

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; init; } = string.Empty;

    [JsonPropertyName("cash_register_id")]
    public int CashRegisterId { get; init; }

    [JsonPropertyName("payment_status")]
    public string PaymentStatus { get; init; } = string.Empty;

    [JsonPropertyName("subtotal")]
    public decimal Subtotal { get; init; }

    [JsonPropertyName("discount_amount")]
    public decimal DiscountAmount { get; init; }

    [JsonPropertyName("final_amount")]
    public decimal FinalAmount { get; init; }

    [JsonPropertyName("paid_amount")]
    public decimal PaidAmount { get; init; }

    [JsonPropertyName("change_amount")]
    public decimal ChangeAmount { get; init; }

    [JsonPropertyName("stock_warnings")]
    public IReadOnlyList<string> StockWarnings { get; init; } = [];

    [JsonPropertyName("items")]
    public IReadOnlyList<SaleReceiptItem> Items { get; init; } = [];

    [JsonPropertyName("payments")]
    public IReadOnlyList<SaleReceiptPayment> Payments { get; init; } = [];

    public string SaleNumberText => $"Venda #{Id}";

    public string SubtotalText => FormatMoney(Subtotal);

    public string DiscountAmountText => FormatMoney(DiscountAmount);

    public string FinalAmountText => FormatMoney(FinalAmount);

    public string PaidAmountText => FormatMoney(PaidAmount);

    public string ChangeAmountText => FormatMoney(ChangeAmount);

    public string CashRegisterText => $"Caixa #{CashRegisterId}";

    public bool HasStockWarnings => StockWarnings.Count > 0;

    private static string FormatMoney(decimal value) =>
        $"R$ {value.ToString("N2", BrazilianCulture)}";
}

public sealed class SaleReceiptItem
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    [JsonPropertyName("product_id")]
    public int ProductId { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("quantity")]
    public int Quantity { get; init; }

    [JsonPropertyName("unit_price")]
    public decimal UnitPrice { get; init; }

    [JsonPropertyName("subtotal")]
    public decimal Subtotal { get; init; }

    [JsonPropertyName("profit_amount")]
    public decimal ProfitAmount { get; init; }

    public string QuantityText => $"{Quantity} un.";

    public string UnitPriceText => $"R$ {UnitPrice.ToString("N2", BrazilianCulture)}";

    public string SubtotalText => $"R$ {Subtotal.ToString("N2", BrazilianCulture)}";

    public string ProfitAmountText => $"R$ {ProfitAmount.ToString("N2", BrazilianCulture)}";
}

public sealed class SaleReceiptPayment
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    [JsonPropertyName("method")]
    public string Method { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;

    [JsonPropertyName("amount")]
    public decimal Amount { get; init; }

    public string AmountText => $"R$ {Amount.ToString("N2", BrazilianCulture)}";
}
