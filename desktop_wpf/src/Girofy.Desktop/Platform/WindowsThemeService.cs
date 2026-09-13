using System.Windows.Media;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;

namespace Girofy.Desktop.Platform;

public sealed class WindowsThemeService(IUserPreferencesStore preferencesStore) : IThemeService
{
    private bool _isAuthenticated;
    private bool _preferredIsDarkMode = true;

    private static readonly IReadOnlyDictionary<string, string> DarkPalette =
        new Dictionary<string, string>
        {
            ["AppBackgroundBrush"] = "#050B16",
            ["AppBackgroundSoftBrush"] = "#050B16",
            ["SidebarBrush"] = "#030D18",
            ["SidebarRaisedBrush"] = "#102B3C",
            ["SurfaceBrush"] = "#0B1424",
            ["SurfaceRaisedBrush"] = "#122033",
            ["SurfaceElevatedBrush"] = "#122033",
            ["SurfaceHoverBrush"] = "#122033",
            ["BorderBrush"] = "#26364D",
            ["BorderStrongBrush"] = "#34506D",
            ["TextPrimaryBrush"] = "#F7FBFF",
            ["TextSecondaryBrush"] = "#9FB0C3",
            ["TextMutedBrush"] = "#9FB0C3",
            ["PrimaryBrush"] = "#8B5CF6",
            ["PrimaryHoverBrush"] = "#A78BFA",
            ["PrimaryPressedBrush"] = "#6D28D9",
            ["AccentBrush"] = "#22D3EE",
            ["InfoBrush"] = "#60A5FA",
            ["SuccessBrush"] = "#22C55E",
            ["WarningBrush"] = "#FBBF24",
            ["ErrorBrush"] = "#FB7185",
            ["AccentSoftBrush"] = "#16394A",
            ["InfoSurfaceBrush"] = "#102A3A",
            ["InfoBorderBrush"] = "#1F6F86",
            ["SuccessSurfaceBrush"] = "#102D27",
            ["SuccessBorderBrush"] = "#257A56",
            ["WarningSurfaceBrush"] = "#322711",
            ["WarningBorderBrush"] = "#8A6818",
            ["ErrorSurfaceBrush"] = "#321D2A",
            ["ErrorBorderBrush"] = "#8B4052",
            ["AlternatingRowBrush"] = "#102034",
            ["TableHeaderBrush"] = "#0F1E32",
            ["SelectionSoftBrush"] = "#30245C",
            ["OverlayBrush"] = "#CC000914",
            ["OverlaySoftBrush"] = "#B8050B16",
            ["LogoTileBrush"] = "#FFFFFF",
            ["OnAccentTextBrush"] = "#FFFFFF",
            ["WarningSoftBrush"] = "#26F59E0B",
            ["ErrorSoftBrush"] = "#26EF4444",
        };

    private static readonly IReadOnlyDictionary<string, string> LightPalette =
        new Dictionary<string, string>
        {
            ["AppBackgroundBrush"] = "#F6F8FF",
            ["AppBackgroundSoftBrush"] = "#F6F8FF",
            ["SidebarBrush"] = "#F6F8FF",
            ["SidebarRaisedBrush"] = "#EEF6FB",
            ["SurfaceBrush"] = "#FFFFFF",
            ["SurfaceRaisedBrush"] = "#EEF6FB",
            ["SurfaceElevatedBrush"] = "#EEF6FB",
            ["SurfaceHoverBrush"] = "#EEF6FB",
            ["BorderBrush"] = "#D8E1EE",
            ["BorderStrongBrush"] = "#B8C7D8",
            ["TextPrimaryBrush"] = "#071126",
            ["TextSecondaryBrush"] = "#637188",
            ["TextMutedBrush"] = "#637188",
            ["PrimaryBrush"] = "#6D28D9",
            ["PrimaryHoverBrush"] = "#5B21B6",
            ["PrimaryPressedBrush"] = "#5B21B6",
            ["AccentBrush"] = "#06B6D4",
            ["InfoBrush"] = "#2563EB",
            ["SuccessBrush"] = "#16A34A",
            ["WarningBrush"] = "#F59E0B",
            ["ErrorBrush"] = "#EF4444",
            ["AccentSoftBrush"] = "#DDF7FB",
            ["InfoSurfaceBrush"] = "#E8F4FF",
            ["InfoBorderBrush"] = "#8BC5EA",
            ["SuccessSurfaceBrush"] = "#E8F8EF",
            ["SuccessBorderBrush"] = "#7DCEA0",
            ["WarningSurfaceBrush"] = "#FFF7DB",
            ["WarningBorderBrush"] = "#E6C45B",
            ["ErrorSurfaceBrush"] = "#FFF0F3",
            ["ErrorBorderBrush"] = "#E7A0AD",
            ["AlternatingRowBrush"] = "#F1F5F9",
            ["TableHeaderBrush"] = "#DFE8F2",
            ["SelectionSoftBrush"] = "#E8DEFF",
            ["OverlayBrush"] = "#66071026",
            ["OverlaySoftBrush"] = "#52071026",
            ["LogoTileBrush"] = "#FFFFFF",
            ["OnAccentTextBrush"] = "#FFFFFF",
            ["WarningSoftBrush"] = "#26D97706",
            ["ErrorSoftBrush"] = "#26DC2626",
        };

    public bool IsDarkMode { get; private set; } = true;

    public event EventHandler? Changed;

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        var preferences = await preferencesStore.LoadAsync(cancellationToken);
        _preferredIsDarkMode = !string.Equals(preferences.Theme, "light", StringComparison.OrdinalIgnoreCase);
        IsDarkMode = _isAuthenticated ? _preferredIsDarkMode : true;
        ApplyPalette();

        Changed?.Invoke(this, EventArgs.Empty);
    }

    public async Task ToggleAsync(CancellationToken cancellationToken = default)
    {
        if (!_isAuthenticated)
        {
            return;
        }

        IsDarkMode = !IsDarkMode;
        _preferredIsDarkMode = IsDarkMode;
        ApplyPalette();

        var current = await preferencesStore.LoadAsync(cancellationToken);
        await preferencesStore.SaveAsync(
            new UserPreferences
            {
                RememberUsername = current.RememberUsername,
                RememberedIdentifier = current.RememberedIdentifier,
                Theme = IsDarkMode ? "dark" : "light",
                Accessibility = current.Accessibility,
            },
            cancellationToken);
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public void SetAuthenticationState(bool isAuthenticated)
    {
        _isAuthenticated = isAuthenticated;
        var requestedDarkMode = isAuthenticated ? _preferredIsDarkMode : true;
        if (IsDarkMode == requestedDarkMode)
        {
            return;
        }

        IsDarkMode = requestedDarkMode;
        ApplyPalette();
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public void Apply() => ApplyPalette();

    private void ApplyPalette()
    {
        var resources = System.Windows.Application.Current.Resources;
        var palette = IsDarkMode ? DarkPalette : LightPalette;
        foreach (var (key, value) in palette)
        {
            var color = (Color)ColorConverter.ConvertFromString(value);
            ReplaceOrUpdateSolidBrush(resources, key, color);
        }

        ApplyGradient("HeroGradientBrush", IsDarkMode
            ? ["#0B1424", "#0B1424", "#122033"]
            : ["#FFFFFF", "#FFFFFF", "#EEF6FB"]);
        ApplyGradient("SidebarGradientBrush", IsDarkMode
            ? ["#030D18", "#030D18", "#050B16"]
            : ["#F6F8FF", "#F6F8FF", "#EEF6FB"]);
        ApplyGradient("PrimaryGradientBrush", IsDarkMode
            ? ["#8B5CF6", "#22D3EE"]
            : ["#6D28D9", "#06B6D4"]);
    }

    private static void ApplyGradient(string key, IReadOnlyList<string> colors)
    {
        var resources = System.Windows.Application.Current.Resources;
        if (resources[key] is not LinearGradientBrush current)
        {
            return;
        }

        var brush = current.IsFrozen ? current.Clone() : current;
        for (var index = 0; index < brush.GradientStops.Count && index < colors.Count; index++)
        {
            brush.GradientStops[index].Color = (Color)ColorConverter.ConvertFromString(colors[index]);
        }

        if (!ReferenceEquals(brush, current))
        {
            resources[key] = brush;
        }
    }

    private static void ReplaceOrUpdateSolidBrush(
        System.Windows.ResourceDictionary resources,
        string key,
        Color color)
    {
        if (resources[key] is not SolidColorBrush current)
        {
            resources[key] = new SolidColorBrush(color);
            return;
        }

        if (current.IsFrozen)
        {
            resources[key] = new SolidColorBrush(color);
            return;
        }

        current.Color = color;
    }
}
