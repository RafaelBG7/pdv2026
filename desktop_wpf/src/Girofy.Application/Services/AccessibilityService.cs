using Girofy.Application.Abstractions;
using Girofy.Application.Models;

namespace Girofy.Application.Services;

public sealed class AccessibilityService(IUserPreferencesStore preferencesStore) : IAccessibilityService
{
    public AccessibilityPreferences Current { get; private set; } = AccessibilityPreferences.Default;

    public event EventHandler? Changed;

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        var preferences = await preferencesStore.LoadAsync(cancellationToken);
        Current = Normalize(preferences.Accessibility);
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public void Preview(AccessibilityPreferences preferences)
    {
        Current = Normalize(preferences);
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public async Task SaveAsync(
        AccessibilityPreferences preferences,
        CancellationToken cancellationToken = default)
    {
        Current = Normalize(preferences);
        var current = await preferencesStore.LoadAsync(cancellationToken);
        await preferencesStore.SaveAsync(CopyWithAccessibility(current, Current), cancellationToken);
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public Task ResetAsync(CancellationToken cancellationToken = default) =>
        SaveAsync(AccessibilityPreferences.Default, cancellationToken);

    private static AccessibilityPreferences Normalize(AccessibilityPreferences? preferences)
    {
        preferences ??= AccessibilityPreferences.Default;
        var textSize = preferences.TextSize is "medium" or "large" or "xlarge"
            ? preferences.TextSize
            : "standard";
        var contrast = preferences.Contrast is "high" or "very_high"
            ? preferences.Contrast
            : "standard";
        return preferences with { TextSize = textSize, Contrast = contrast };
    }

    private static UserPreferences CopyWithAccessibility(
        UserPreferences current,
        AccessibilityPreferences accessibility) =>
        new()
        {
            RememberUsername = current.RememberUsername,
            RememberedIdentifier = current.RememberedIdentifier,
            Theme = current.Theme,
            Accessibility = accessibility,
        };
}
