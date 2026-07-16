using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class HealthStatus
{
    [JsonPropertyName("status")]
    public string Status { get; init; } = string.Empty;

    [JsonPropertyName("service")]
    public string Service { get; init; } = string.Empty;

    [JsonPropertyName("api_version")]
    public string ApiVersion { get; init; } = string.Empty;
}
