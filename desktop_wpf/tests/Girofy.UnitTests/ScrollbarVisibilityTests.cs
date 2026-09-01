using System.Xml.Linq;

namespace Girofy.UnitTests;

public sealed class ScrollbarVisibilityTests
{
    [Fact]
    public void Global_theme_hides_scrollbars_without_disabling_scroll_viewers()
    {
        var themePath = FindRepositoryFile(
            "desktop_wpf", "src", "Girofy.Desktop", "Themes", "Colors.xaml");
        var document = XDocument.Load(themePath);
        XNamespace presentation = "http://schemas.microsoft.com/winfx/2006/xaml/presentation";

        var scrollbarStyle = document
            .Descendants(presentation + "Style")
            .Single(element => (string?)element.Attribute("TargetType") == "ScrollBar");
        var setters = scrollbarStyle
            .Elements(presentation + "Setter")
            .ToDictionary(
                element => (string)element.Attribute("Property")!,
                element => (string)element.Attribute("Value")!);

        Assert.Equal("Collapsed", setters["Visibility"]);
        Assert.Equal("False", setters["IsHitTestVisible"]);
        Assert.Equal("0", setters["Width"]);
        Assert.Equal("0", setters["Height"]);
        Assert.Single(scrollbarStyle.Descendants(presentation + "ControlTemplate"));

        var viewsRoot = Path.GetDirectoryName(themePath)!;
        var desktopRoot = Directory.GetParent(viewsRoot)!.FullName;
        var scrollViewers = Directory
            .EnumerateFiles(desktopRoot, "*.xaml", SearchOption.AllDirectories)
            .Select(XDocument.Load)
            .SelectMany(view => view.Descendants(presentation + "ScrollViewer"));

        Assert.NotEmpty(scrollViewers);
        Assert.DoesNotContain(
            scrollViewers,
            element => (string?)element.Attribute("IsEnabled") == "False");
    }

    private static string FindRepositoryFile(params string[] relativeParts)
    {
        foreach (var startPath in new[] { Directory.GetCurrentDirectory(), AppContext.BaseDirectory })
        {
            for (var directory = new DirectoryInfo(startPath); directory is not null; directory = directory.Parent)
            {
                var candidate = Path.Combine([directory.FullName, .. relativeParts]);
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
        }

        throw new FileNotFoundException("O tema global do SkyGest não foi encontrado.");
    }
}
