using System.Windows.Media;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;

namespace Girofy.Desktop.Platform;

public sealed class WindowsThemeService(IUserPreferencesStore preferencesStore) : IThemeService
{
    private static readonly IReadOnlyDictionary<string, string> DarkPalette =
        new Dictionary<string, string>
        {
            ["AppBackgroundBrush"] = "#050B16",
            ["AppBackgroundSoftBrush"] = "#081421",
            ["SidebarBrush"] = "#041421",
            ["SidebarRaisedBrush"] = "#082033",
            ["SurfaceBrush"] = "#0B1424",
            ["SurfaceRaisedBrush"] = "#122033",
            ["SurfaceElevatedBrush"] = "#182B45",
            ["SurfaceHoverBrush"] = "#1B314E",
            ["BorderBrush"] = "#26364D",
            ["BorderStrongBrush"] = "#34506D",
            ["TextPrimaryBrush"] = "#F7FBFF",
            ["TextSecondaryBrush"] = "#B8C7D9",
            ["TextMutedBrush"] = "#8293AA",
            ["AccentSoftBrush"] = "#16394A",
            ["InfoSurfaceBrush"] = "#102A3A",
            ["InfoBorderBrush"] = "#1F6F86",
            ["SuccessSurfaceBrush"] = "#102D27",
            ["SuccessBorderBrush"] = "#257A56",
            ["WarningSurfaceBrush"] = "#322711",
            ["WarningBorderBrush"] = "#8A6818",
            ["ErrorSurfaceBrush"] = "#321D2A",
            ["ErrorBorderBrush"] = "#8B4052",
        };

    private static readonly IReadOnlyDictionary<string, string> LightPalette =
        new Dictionary<string, string>
        {
            ["AppBackgroundBrush"] = "#F4F7FB",
            ["AppBackgroundSoftBrush"] = "#EEF3F8",
            ["SidebarBrush"] = "#F7FAFC",
            ["SidebarRaisedBrush"] = "#E8F3FA",
            ["SurfaceBrush"] = "#FFFFFF",
            ["SurfaceRaisedBrush"] = "#F8FAFC",
            ["SurfaceElevatedBrush"] = "#EDF3F8",
            ["SurfaceHoverBrush"] = "#E5EEF6",
            ["BorderBrush"] = "#D7E0EA",
            ["BorderStrongBrush"] = "#B8C7D8",
            ["TextPrimaryBrush"] = "#172033",
            ["TextSecondaryBrush"] = "#52627A",
            ["TextMutedBrush"] = "#78879A",
            ["AccentSoftBrush"] = "#DDF7FB",
            ["InfoSurfaceBrush"] = "#E8F4FF",
            ["InfoBorderBrush"] = "#8BC5EA",
            ["SuccessSurfaceBrush"] = "#E8F8EF",
            ["SuccessBorderBrush"] = "#7DCEA0",
            ["WarningSurfaceBrush"] = "#FFF7DB",
            ["WarningBorderBrush"] = "#E6C45B",
            ["ErrorSurfaceBrush"] = "#FFF0F3",
            ["ErrorBorderBrush"] = "#E7A0AD",
        };

    public bool IsDarkMode { get; private set; } = true;

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        var preferences = await preferencesStore.LoadAsync(cancellationToken);
        IsDarkMode = !string.Equals(preferences.Theme, "light", StringComparison.OrdinalIgnoreCase);
        if (!IsDarkMode)
        {
            ApplyPalette();
        }
    }

    public async Task ToggleAsync(CancellationToken cancellationToken = default)
    {
        IsDarkMode = !IsDarkMode;
        ApplyPalette();

        var current = await preferencesStore.LoadAsync(cancellationToken);
        await preferencesStore.SaveAsync(
            new UserPreferences
            {
                RememberUsername = current.RememberUsername,
                RememberedIdentifier = current.RememberedIdentifier,
                Theme = IsDarkMode ? "dark" : "light",
            },
            cancellationToken);
    }

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
            ? ["#122033", "#0B1424", "#0B3142"]
            : ["#FFFFFF", "#F7FAFC", "#E5F7FB"]);
        ApplyGradient("SidebarGradientBrush", IsDarkMode
            ? ["#041421", "#061525", "#120A2A"]
            : ["#F7FAFC", "#F1F7FA", "#F4EFFF"]);
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
