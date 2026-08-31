using System.Windows.Media.Imaging;

namespace Girofy.UnitTests;

public sealed class ApplicationIconTests
{
    [Fact]
    public void SkyGest_icon_can_be_decoded_by_wpf()
    {
        var iconPath = FindApplicationIcon();

        var decoder = BitmapDecoder.Create(
            new Uri(iconPath, UriKind.Absolute),
            BitmapCreateOptions.PreservePixelFormat,
            BitmapCacheOption.OnLoad);

        Assert.NotEmpty(decoder.Frames);
        Assert.Contains(decoder.Frames, frame => frame.PixelWidth >= 256 && frame.PixelHeight >= 256);
    }

    private static string FindApplicationIcon()
    {
        foreach (var startPath in new[] { Directory.GetCurrentDirectory(), AppContext.BaseDirectory })
        {
            for (var directory = new DirectoryInfo(startPath); directory is not null; directory = directory.Parent)
            {
                var candidate = Path.Combine(
                    directory.FullName,
                    "desktop_wpf",
                    "src",
                    "Girofy.Desktop",
                    "Resources",
                    "SkyGest.ico");

                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
        }

        throw new FileNotFoundException("O ícone do SkyGest não foi encontrado para validação.");
    }
}
