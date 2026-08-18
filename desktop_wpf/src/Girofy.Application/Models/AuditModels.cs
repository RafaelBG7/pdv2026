using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class AuditLogSnapshot
{
    [JsonPropertyName("items")]
    public IReadOnlyList<AuditLogRecord> Items { get; init; } = [];

    [JsonPropertyName("pagination")]
    public CatalogPagination Pagination { get; init; } = new();

    [JsonPropertyName("summary")]
    public AuditLogSummary Summary { get; init; } = new();

    [JsonPropertyName("users")]
    public IReadOnlyList<AuditUserOption> Users { get; init; } = [];

    [JsonPropertyName("action_options")]
    public IReadOnlyList<CatalogFilterOption> ActionOptions { get; init; } = [];

    [JsonPropertyName("entity_options")]
    public IReadOnlyList<CatalogFilterOption> EntityOptions { get; init; } = [];

    [JsonPropertyName("method_options")]
    public IReadOnlyList<CatalogFilterOption> MethodOptions { get; init; } = [];
}

public sealed class AuditLogSummary
{
    [JsonPropertyName("count")]
    public int Count { get; init; }

    [JsonPropertyName("users")]
    public int Users { get; init; }

    [JsonPropertyName("actions")]
    public int Actions { get; init; }

    public string CountText => Count == 1 ? "1 evento" : $"{Count} eventos";

    public string UsersText => Users == 1 ? "1 usuário" : $"{Users} usuários";

    public string ActionsText => Actions == 1 ? "1 ação" : $"{Actions} ações";
}

public sealed class AuditLogRecord
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("created_at")]
    public string? CreatedAt { get; init; }

    [JsonPropertyName("user_id")]
    public int? UserId { get; init; }

    [JsonPropertyName("user_name")]
    public string UserName { get; init; } = string.Empty;

    [JsonPropertyName("user_role")]
    public string UserRole { get; init; } = string.Empty;

    [JsonPropertyName("action")]
    public string Action { get; init; } = string.Empty;

    [JsonPropertyName("action_label")]
    public string ActionLabel { get; init; } = string.Empty;

    [JsonPropertyName("entity_type")]
    public string EntityType { get; init; } = string.Empty;

    [JsonPropertyName("entity_label")]
    public string EntityLabel { get; init; } = string.Empty;

    [JsonPropertyName("entity_id")]
    public int? EntityId { get; init; }

    [JsonPropertyName("description")]
    public string Description { get; init; } = string.Empty;

    [JsonPropertyName("old_values")]
    public string OldValues { get; init; } = string.Empty;

    [JsonPropertyName("new_values")]
    public string NewValues { get; init; } = string.Empty;

    [JsonPropertyName("ip_address")]
    public string IpAddress { get; init; } = string.Empty;

    [JsonPropertyName("user_agent")]
    public string UserAgent { get; init; } = string.Empty;

    [JsonPropertyName("request_id")]
    public string RequestId { get; init; } = string.Empty;

    [JsonPropertyName("route")]
    public string Route { get; init; } = string.Empty;

    [JsonPropertyName("http_method")]
    public string HttpMethod { get; init; } = string.Empty;

    public string CreatedAtText => DashboardFormatting.DateTimeText(CreatedAt);

    public string CreatedDateText => DashboardFormatting.LocalDateTime(CreatedAt)?.ToString("dd/MM/yyyy") ?? "-";

    public string CreatedTimeText => DashboardFormatting.LocalDateTime(CreatedAt)?.ToString("HH:mm") ?? "";

    public string UserNameText => string.IsNullOrWhiteSpace(UserName) ? "Sistema" : UserName;

    public string ActionText => string.IsNullOrWhiteSpace(ActionLabel) ? Action : ActionLabel;

    public string EntityText => string.IsNullOrWhiteSpace(EntityLabel) ? EntityType : EntityLabel;

    public string EntityIdText => EntityId.HasValue ? $"#{EntityId.Value}" : "-";

    public string MethodText => string.IsNullOrWhiteSpace(HttpMethod) ? "-" : HttpMethod;

    public string IpText => string.IsNullOrWhiteSpace(IpAddress) ? "-" : IpAddress;

    public string RequestText => string.IsNullOrWhiteSpace(RequestId) ? "-" : RequestId;

    public string RouteText => string.IsNullOrWhiteSpace(Route) ? "-" : Route;

    public string OldValuesText => string.IsNullOrWhiteSpace(OldValues) ? "Sem dados anteriores" : OldValues;

    public string NewValuesText => string.IsNullOrWhiteSpace(NewValues) ? "Sem dados novos" : NewValues;
}

public sealed class AuditUserOption
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("username")]
    public string Username { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;
}

public sealed record AuditLogQuery(
    string Search,
    int? UserId,
    string Action,
    string EntityType,
    string HttpMethod,
    string StartDate,
    string EndDate,
    int Page,
    int PerPage);
