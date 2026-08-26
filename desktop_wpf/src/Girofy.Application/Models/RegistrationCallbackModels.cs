using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public sealed record PendingRegistrationHandoff(string State, string CodeVerifier);

public sealed class RegistrationCallbackResult
{
    [JsonPropertyName("identifier")]
    public string Identifier { get; init; } = string.Empty;

    [JsonPropertyName("subscription_activation_required")]
    public bool SubscriptionActivationRequired { get; init; }
}
