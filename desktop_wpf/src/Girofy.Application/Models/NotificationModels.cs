using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class NotificationSnapshot
{
    [JsonPropertyName("items")]
    public IReadOnlyList<NotificationItem> Items { get; init; } = [];
    [JsonPropertyName("page")]
    public int Page { get; init; }
    [JsonPropertyName("page_size")]
    public int PageSize { get; init; }
    [JsonPropertyName("total")]
    public int Total { get; init; }
    [JsonPropertyName("unread_count")]
    public int UnreadCount { get; init; }
}

public sealed class NotificationItem
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("notification_type")] public string NotificationType { get; init; } = string.Empty;
    [JsonPropertyName("category")] public string Category { get; init; } = string.Empty;
    [JsonPropertyName("severity")] public string Severity { get; init; } = "info";
    [JsonPropertyName("title")] public string Title { get; init; } = string.Empty;
    [JsonPropertyName("message")] public string Message { get; init; } = string.Empty;
    [JsonPropertyName("action_url")] public string ActionUrl { get; init; } = string.Empty;
    [JsonPropertyName("is_read")] public bool IsRead { get; init; }
    [JsonPropertyName("created_at")] public string? CreatedAt { get; init; }
    public string SeverityText => Severity switch { "critical" => "Crítica", "warning" => "Atenção", "success" => "Sucesso", _ => "Informação" };
    public string CategoryText => Category switch { "stock" => "Estoque", "payables" => "Contas", "cash_register" => "Caixa", "sales" => "Vendas", "security" => "Segurança", "subscription" => "Assinatura", "backup" => "Backup", _ => "Administração" };
    public string CreatedAtText => DashboardFormatting.DateTimeText(CreatedAt);
    public string ReadText => IsRead ? "Lida" : "Não lida";
}

public sealed record NotificationQuery(
    int Page = 1,
    int PageSize = 20,
    string Category = "",
    string Severity = "",
    string ReadFilter = "",
    string Search = "");

public sealed class NotificationUnreadCount
{
    [JsonPropertyName("unread_count")] public int UnreadCount { get; init; }
}

public sealed class NotificationPreferenceSnapshot
{
    [JsonPropertyName("in_app_enabled")] public bool InAppEnabled { get; init; } = true;
    [JsonPropertyName("email_enabled")] public bool EmailEnabled { get; init; }
    [JsonPropertyName("desktop_enabled")] public bool DesktopEnabled { get; init; } = true;
    [JsonPropertyName("minimum_severity")] public string MinimumSeverity { get; init; } = "info";
    [JsonPropertyName("email_recipients")] public string EmailRecipients { get; init; } = string.Empty;
    [JsonPropertyName("can_manage_recipients")] public bool CanManageRecipients { get; init; }
}

public sealed record UpdateNotificationPreferenceRequest(
    [property: JsonPropertyName("in_app_enabled")] bool InAppEnabled,
    [property: JsonPropertyName("email_enabled")] bool EmailEnabled,
    [property: JsonPropertyName("desktop_enabled")] bool DesktopEnabled,
    [property: JsonPropertyName("minimum_severity")] string MinimumSeverity,
    [property: JsonPropertyName("email_recipients")] string EmailRecipients,
    [property: JsonPropertyName("daily_digest_enabled")] bool DailyDigestEnabled = false,
    [property: JsonPropertyName("daily_digest_time")] string DailyDigestTime = "08:00");
