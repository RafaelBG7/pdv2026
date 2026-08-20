using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;

namespace Girofy.UnitTests;

public sealed class AccessibilityServiceTests
{
    [Fact]
    public async Task Loads_defaults_when_no_accessibility_preference_exists()
    {
        var service = new AccessibilityService(new MemoryPreferencesStore());

        await service.InitializeAsync();

        Assert.Equal("standard", service.Current.TextSize);
        Assert.Equal("standard", service.Current.Contrast);
        Assert.False(service.Current.ReinforcedText);
        Assert.Null(service.Current.ReduceMotion);
    }

    [Fact]
    public async Task Saves_and_reloads_accessibility_without_losing_other_preferences()
    {
        var store = new MemoryPreferencesStore
        {
            Value = new UserPreferences
            {
                RememberUsername = true,
                RememberedIdentifier = "operador",
                Theme = "light",
            },
        };
        var service = new AccessibilityService(store);

        await service.SaveAsync(new AccessibilityPreferences
        {
            TextSize = "large",
            Contrast = "high",
            ReinforcedText = true,
            ReduceMotion = true,
        });

        Assert.Equal("large", store.Value.Accessibility.TextSize);
        Assert.Equal("high", store.Value.Accessibility.Contrast);
        Assert.True(store.Value.Accessibility.ReinforcedText);
        Assert.True(store.Value.Accessibility.ReduceMotion);
        Assert.True(store.Value.RememberUsername);
        Assert.Equal("operador", store.Value.RememberedIdentifier);
        Assert.Equal("light", store.Value.Theme);

        var reloaded = new AccessibilityService(store);
        await reloaded.InitializeAsync();
        Assert.Equal(service.Current, reloaded.Current);
    }

    [Fact]
    public async Task Preview_notifies_without_persisting_and_reset_restores_defaults()
    {
        var store = new MemoryPreferencesStore();
        var service = new AccessibilityService(store);
        var changed = 0;
        service.Changed += (_, _) => changed++;

        service.Preview(new AccessibilityPreferences
        {
            TextSize = "xlarge",
            Contrast = "very_high",
            ReduceMotion = true,
        });

        Assert.Equal("standard", store.Value.Accessibility.TextSize);
        Assert.Equal("xlarge", service.Current.TextSize);

        await service.SaveAsync(service.Current);
        await service.ResetAsync();

        Assert.Equal(3, changed);
        Assert.Equal(AccessibilityPreferences.Default, service.Current);
        Assert.Equal(AccessibilityPreferences.Default, store.Value.Accessibility);
    }

    [Fact]
    public async Task Invalid_values_are_normalized_to_safe_scales()
    {
        var store = new MemoryPreferencesStore();
        var service = new AccessibilityService(store);

        await service.SaveAsync(new AccessibilityPreferences
        {
            TextSize = "500-percent",
            Contrast = "unknown",
        });

        Assert.Equal("standard", service.Current.TextSize);
        Assert.Equal("standard", service.Current.Contrast);
    }

    private sealed class MemoryPreferencesStore : IUserPreferencesStore
    {
        public UserPreferences Value { get; set; } = new();

        public Task<UserPreferences> LoadAsync(CancellationToken cancellationToken) =>
            Task.FromResult(Value);

        public Task SaveAsync(UserPreferences preferences, CancellationToken cancellationToken)
        {
            Value = preferences;
            return Task.CompletedTask;
        }
    }
}
