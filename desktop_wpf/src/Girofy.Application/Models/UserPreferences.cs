namespace Girofy.Application.Models;

public sealed class UserPreferences
{
    public bool RememberUsername { get; init; }

    public string RememberedIdentifier { get; init; } = string.Empty;

    public string Theme { get; init; } = "dark";

    public AccessibilityPreferences Accessibility { get; init; } = new();
}

public sealed record AccessibilityPreferences
{
    public string TextSize { get; init; } = "standard";

    public bool ReinforcedText { get; init; }

    public string Contrast { get; init; } = "standard";

    public bool? ReduceMotion { get; init; }

    public static AccessibilityPreferences Default { get; } = new();
}
