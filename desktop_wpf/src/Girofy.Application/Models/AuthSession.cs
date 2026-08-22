using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed class AuthSession
{
    [JsonPropertyName("access_token")]
    public string AccessToken { get; init; } = string.Empty;

    [JsonPropertyName("refresh_token")]
    public string RefreshToken { get; init; } = string.Empty;

    [JsonPropertyName("token_type")]
    public string TokenType { get; init; } = "Bearer";

    [JsonPropertyName("expires_in")]
    public int ExpiresIn { get; init; }

    [JsonPropertyName("access_expires_at_utc")]
    public DateTimeOffset? AccessExpiresAtUtc { get; init; }

    [JsonPropertyName("refresh_expires_at")]
    public string RefreshExpiresAt { get; init; } = string.Empty;

    [JsonPropertyName("user")]
    public UserIdentity User { get; init; } = new();

    [JsonPropertyName("company")]
    public CompanyIdentity? Company { get; init; }

    public AuthSession WithCalculatedAccessExpiration(DateTimeOffset now) => new()
    {
        AccessToken = AccessToken,
        RefreshToken = RefreshToken,
        TokenType = TokenType,
        ExpiresIn = ExpiresIn,
        AccessExpiresAtUtc = ExpiresIn > 0 ? now.AddSeconds(ExpiresIn) : null,
        RefreshExpiresAt = RefreshExpiresAt,
        User = User,
        Company = Company,
    };
}

public sealed class AuthIdentity
{
    [JsonPropertyName("user")]
    public UserIdentity User { get; init; } = new();

    [JsonPropertyName("company")]
    public CompanyIdentity? Company { get; init; }
}

public sealed record SubscriptionActivationRequest(
    [property: JsonPropertyName("identifier")] string Identifier,
    [property: JsonPropertyName("password")] string Password,
    [property: JsonPropertyName("activation_key")] string ActivationKey);

public sealed class UserIdentity
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("username")]
    public string Username { get; init; } = string.Empty;

    [JsonPropertyName("first_name")]
    public string FirstName { get; init; } = string.Empty;

    [JsonPropertyName("last_name")]
    public string LastName { get; init; } = string.Empty;

    [JsonPropertyName("full_name")]
    public string FullName { get; init; } = string.Empty;

    [JsonPropertyName("email")]
    public string Email { get; init; } = string.Empty;

    [JsonPropertyName("phone")]
    public string Phone { get; init; } = string.Empty;

    [JsonPropertyName("role")]
    public string Role { get; init; } = string.Empty;

    [JsonPropertyName("role_label")]
    public string RoleLabel { get; init; } = string.Empty;

    [JsonPropertyName("permissions")]
    public IReadOnlyDictionary<string, bool> Permissions { get; init; } =
        new Dictionary<string, bool>();
}

public sealed class CompanyIdentity
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("active")]
    public bool Active { get; init; }

    [JsonPropertyName("subscription_plan")]
    public string SubscriptionPlan { get; init; } = string.Empty;

    [JsonPropertyName("subscription_renews_at")]
    public string? SubscriptionRenewsAt { get; init; }

    [JsonPropertyName("subscription_valid")]
    public bool SubscriptionValid { get; init; }
}
