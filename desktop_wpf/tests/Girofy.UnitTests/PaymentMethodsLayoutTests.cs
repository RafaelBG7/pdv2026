using System.Xml.Linq;

namespace Girofy.UnitTests;

public sealed class PaymentMethodsLayoutTests
{
    [Fact]
    public void Checkout_displays_all_payment_methods_in_operational_order()
    {
        var salesViewPath = FindRepositoryFile(
            "desktop_wpf", "src", "Girofy.Desktop", "Views", "SalesView.xaml");
        var document = XDocument.Load(salesViewPath);
        XNamespace presentation = "http://schemas.microsoft.com/winfx/2006/xaml/presentation";
        XNamespace xaml = "http://schemas.microsoft.com/winfx/2006/xaml";

        var panel = document
            .Descendants(presentation + "Border")
            .Single(element => (string?)element.Attribute(xaml + "Name") == "PaymentMethodsPanel");
        var fields = panel
            .Descendants(presentation + "TextBox")
            .Select(field => new
            {
                Name = (string?)field.Attribute(xaml + "Name"),
                Method = (string?)field.Attribute("Tag"),
            })
            .ToArray();

        Assert.Equal(
            new[] { "money", "debit", "credit", "pix" },
            fields.Select(field => field.Method!).ToArray());
        Assert.Equal(
            new[] { "MoneyInput", "DebitInput", "CreditInput", "PixInput" },
            fields.Select(field => field.Name!).ToArray());

        var labels = panel
            .Descendants(presentation + "TextBlock")
            .Select(element => (string?)element.Attribute("Text"))
            .Where(text => text is "DINHEIRO" or "DÉBITO" or "CRÉDITO" or "PIX")
            .ToArray();
        Assert.Equal(
            new[] { "DINHEIRO", "DÉBITO", "CRÉDITO", "PIX" },
            labels.Select(text => text!).ToArray());
    }

    [Fact]
    public void Checkout_payment_methods_are_always_vertical_and_visible()
    {
        var salesViewPath = FindRepositoryFile(
            "desktop_wpf", "src", "Girofy.Desktop", "Views", "SalesView.xaml");
        var document = XDocument.Load(salesViewPath);
        XNamespace presentation = "http://schemas.microsoft.com/winfx/2006/xaml/presentation";
        XNamespace xaml = "http://schemas.microsoft.com/winfx/2006/xaml";

        var grid = document
            .Descendants(presentation + "Grid")
            .Single(element => (string?)element.Attribute(xaml + "Name") == "PaymentMethodsGrid");

        var methodPanels = grid
            .Elements(presentation + "StackPanel")
            .ToArray();

        Assert.Equal(4, methodPanels.Length);
        Assert.Equal(
            new[] { 0, 2, 4, 6 },
            methodPanels.Select(panel => (int?)panel.Attribute("Grid.Row") ?? 0).ToArray());
        Assert.All(methodPanels, panel => Assert.Null(panel.Attribute("Grid.Column")));
        Assert.Null(grid.Attribute("SizeChanged"));
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

        throw new FileNotFoundException("A tela de vendas do SkyGest não foi encontrada.");
    }
}
