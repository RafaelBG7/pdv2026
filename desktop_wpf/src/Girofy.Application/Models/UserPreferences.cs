namespace Girofy.Application.Models;

public sealed class UserPreferences
{
    public bool RememberUsername { get; init; }

    public string RememberedIdentifier { get; init; } = string.Empty;

    public string Theme { get; init; } = "dark";
}
