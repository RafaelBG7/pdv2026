using System.Windows;
using System.Windows.Media;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;

namespace Girofy.Desktop.Platform;

public sealed class WindowsAccessibilityResourceAdapter : IDisposable
{
    private readonly IAccessibilityService _accessibilityService;
    private readonly IThemeService _themeService;

    public WindowsAccessibilityResourceAdapter(
        IAccessibilityService accessibilityService,
        IThemeService themeService)
    {
        _accessibilityService = accessibilityService;
        _themeService = themeService;
        _accessibilityService.Changed += HandleChanged;
        _themeService.Changed += HandleChanged;
    }

    public bool EffectiveReduceMotion =>
        _accessibilityService.Current.ReduceMotion ?? !SystemParameters.ClientAreaAnimation;

    public void Apply()
    {
        if (System.Windows.Application.Current is null)
        {
            return;
        }

        var resources = System.Windows.Application.Current.Resources;
        var preferences = _accessibilityService.Current;
        var scale = preferences.TextSize switch
        {
            "medium" => 1.10,
            "large" => 1.20,
            "xlarge" => 1.30,
            _ => 1.00,
        };

        SetFontTokens(resources, scale, preferences.ReinforcedText);
        resources["AccessibilityReduceMotion"] = EffectiveReduceMotion;
        resources["AnimationFastDuration"] = new Duration(
            EffectiveReduceMotion ? TimeSpan.Zero : TimeSpan.FromMilliseconds(120));
        resources["AnimationNormalDuration"] = new Duration(
            EffectiveReduceMotion ? TimeSpan.Zero : TimeSpan.FromMilliseconds(220));

        _themeService.Apply();
        ApplyContrast(resources, preferences.Contrast, _themeService.IsDarkMode);
    }

    public void Dispose()
    {
        _accessibilityService.Changed -= HandleChanged;
        _themeService.Changed -= HandleChanged;
    }

    private void HandleChanged(object? sender, EventArgs e) => Apply();

    private static void SetFontTokens(
        ResourceDictionary resources,
        double scale,
        bool reinforced)
    {
        resources["FontSizeTiny"] = 10d * scale;
        resources["FontSizeSmall"] = 11d * scale;
        resources["FontSizeCaption"] = 12d * scale;
        resources["FontSizeBody"] = 13d * scale;
        resources["FontSizeLabel"] = 14d * scale;
        resources["FontSizeInput"] = 15d * scale;
        resources["FontSizeSubtitle"] = 16d * scale;
        resources["FontSizeSection"] = 18d * scale;
        resources["FontSizeCardTitle"] = 21d * scale;
        resources["FontSizeTitle"] = 24d * scale;
        resources["FontSizePageTitle"] = 28d * scale;
        resources["FontSizeHero"] = 32d * scale;
        resources["FontWeightBody"] = reinforced ? FontWeights.Medium : FontWeights.Normal;
        resources["FontWeightLabel"] = reinforced ? FontWeights.SemiBold : FontWeights.Medium;
        resources["FontWeightStrong"] = reinforced ? FontWeights.Bold : FontWeights.SemiBold;
    }

    private static void ApplyContrast(
        ResourceDictionary resources,
        string contrast,
        bool dark)
    {
        if (contrast == "standard")
        {
            resources["AccessibilityBorderThickness"] = new Thickness(1);
            return;
        }

        var veryHigh = contrast == "very_high";
        resources["AccessibilityBorderThickness"] = new Thickness(veryHigh ? 2 : 1.5);
        SetBrush(resources, "TextPrimaryBrush", dark ? "#FFFFFF" : "#000000");
        SetBrush(resources, "TextSecondaryBrush", dark ? "#E5EDF8" : "#172033");
        SetBrush(resources, "TextMutedBrush", dark ? "#C6D4E6" : "#334155");
        SetBrush(resources, "BorderBrush", dark
            ? (veryHigh ? "#F7FBFF" : "#7F94AF")
            : (veryHigh ? "#111827" : "#64748B"));
        SetBrush(resources, "BorderStrongBrush", dark ? "#FFFFFF" : "#000000");
        SetBrush(resources, "SurfaceBrush", dark ? "#020617" : "#FFFFFF");
        SetBrush(resources, "SurfaceRaisedBrush", dark ? "#0B1220" : "#F8FAFC");
        SetBrush(resources, "SurfaceHoverBrush", dark ? "#23324A" : "#DCE7F2");
        SetBrush(resources, "SelectionSoftBrush", dark ? "#4C1D95" : "#DDD6FE");
        SetBrush(resources, "OverlayBrush", dark ? "#E6000000" : "#99000000");
    }

    private static void SetBrush(ResourceDictionary resources, string key, string colorValue)
    {
        var color = (Color)ColorConverter.ConvertFromString(colorValue);
        resources[key] = new SolidColorBrush(color);
    }
}
