using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class ApiEnvelope<T>
{
    [JsonPropertyName("success")]
    public bool Success { get; init; }

    [JsonPropertyName("data")]
    public T? Data { get; init; }

    [JsonPropertyName("message")]
    public string? Message { get; init; }

    [JsonPropertyName("errors")]
    public IReadOnlyList<ApiError> Errors { get; init; } = [];
}

public sealed class ApiError
{
    [JsonPropertyName("field")]
    public string? Field { get; init; }

    [JsonPropertyName("code")]
    public string? Code { get; init; }

    [JsonPropertyName("message")]
    public string? Message { get; init; }
}
