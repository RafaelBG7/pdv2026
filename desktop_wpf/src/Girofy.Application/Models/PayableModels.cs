using System.Globalization;
using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class PayablesSnapshot
{
    [JsonPropertyName("items")]
    public IReadOnlyList<PayableRecord> Items { get; init; } = [];

    [JsonPropertyName("summary")]
    public PayableSummary Summary { get; init; } = new();

    [JsonPropertyName("categories")]
    public IReadOnlyList<string> Categories { get; init; } = [];

    [JsonPropertyName("status_options")]
    public IReadOnlyList<CatalogFilterOption> StatusOptions { get; init; } = [];

    [JsonPropertyName("selected_status")]
    public string SelectedStatus { get; init; } = "open";
}

public sealed class PayableSummary
{
    [JsonPropertyName("open_amount")]
    [JsonNumberHandling(JsonNumberHandling.AllowReadingFromString)]
    public decimal OpenAmount { get; init; }

    [JsonPropertyName("overdue_amount")]
    [JsonNumberHandling(JsonNumberHandling.AllowReadingFromString)]
    public decimal OverdueAmount { get; init; }

    [JsonPropertyName("due_soon_amount")]
    [JsonNumberHandling(JsonNumberHandling.AllowReadingFromString)]
    public decimal DueSoonAmount { get; init; }

    [JsonPropertyName("open_count")]
    public int OpenCount { get; init; }

    [JsonPropertyName("paid_count")]
    public int PaidCount { get; init; }

    public string OpenAmountText => DashboardFormatting.Money(OpenAmount);

    public string OverdueAmountText => DashboardFormatting.Money(OverdueAmount);

    public string DueSoonAmountText => DashboardFormatting.Money(DueSoonAmount);

    public string OpenCountText => OpenCount == 1 ? "1 aberta" : $"{OpenCount} abertas";

    public string PaidCountText => PaidCount == 1 ? "1 paga" : $"{PaidCount} pagas";
}

public sealed class PayableRecord
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("description")]
    public string Description { get; init; } = string.Empty;

    [JsonPropertyName("category")]
    public string Category { get; init; } = "Outros";

    [JsonPropertyName("amount")]
    [JsonNumberHandling(JsonNumberHandling.AllowReadingFromString)]
    public decimal Amount { get; init; }

    [JsonPropertyName("due_date")]
    public string? DueDate { get; init; }

    [JsonPropertyName("paid")]
    public bool Paid { get; init; }

    [JsonPropertyName("paid_at")]
    public string? PaidAt { get; init; }

    [JsonPropertyName("notes")]
    public string Notes { get; init; } = string.Empty;

    [JsonPropertyName("created_at")]
    public string? CreatedAt { get; init; }

    [JsonPropertyName("status")]
    public string Status { get; init; } = "open";

    [JsonPropertyName("status_label")]
    public string StatusLabel { get; init; } = "Aberta";

    public string AmountText => DashboardFormatting.Money(Amount);

    public string DueDateText => FormatDate(DueDate);

    public string PaidAtText => DashboardFormatting.DateTimeText(PaidAt);

    public string CreatedAtText => DashboardFormatting.DateTimeText(CreatedAt);

    public string NotesText => string.IsNullOrWhiteSpace(Notes) ? "Sem observações" : Notes;

    public bool CanPay => !Paid;

    public bool CanReopen => Paid;

    private static string FormatDate(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "Sem vencimento";
        }

        return DateOnly.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var parsed)
            ? parsed.ToString("dd/MM/yyyy", BrazilianCulture)
            : value;
    }
}

public sealed record PayablesQuery(
    string Search,
    string Status,
    string Category,
    string? StartDate,
    string? EndDate);

public sealed record PayableMutationRequest(
    [property: JsonPropertyName("description")] string Description,
    [property: JsonPropertyName("category")] string Category,
    [property: JsonPropertyName("amount")] decimal Amount,
    [property: JsonPropertyName("due_date")] string DueDate,
    [property: JsonPropertyName("notes")] string Notes);
