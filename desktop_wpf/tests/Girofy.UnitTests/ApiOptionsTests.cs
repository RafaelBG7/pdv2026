using Girofy.Infrastructure.Api;

namespace Girofy.UnitTests;

public sealed class ApiOptionsTests
{
    [Fact]
    public void GetValidatedBaseUri_uses_canonical_production_host()
    {
        var options = CreateOptions("https://www.skygest.com.br");

        var result = options.GetValidatedBaseUri();

        Assert.Equal("https://www.skygest.com.br/", result.AbsoluteUri);
    }

    [Fact]
    public void GetValidatedBaseUri_replaces_legacy_production_host()
    {
        var options = CreateOptions("https://skygest.com.br");

        var result = options.GetValidatedBaseUri();

        Assert.Equal("https://www.skygest.com.br/", result.AbsoluteUri);
    }

    [Fact]
    public void GetValidatedBaseUri_preserves_homologation_host()
    {
        var options = CreateOptions("https://hml.skygest.com.br");

        var result = options.GetValidatedBaseUri();

        Assert.Equal("https://hml.skygest.com.br/", result.AbsoluteUri);
    }

    private static ApiOptions CreateOptions(string baseUrl)
    {
        return new ApiOptions
        {
            BaseUrl = baseUrl,
            AllowInsecureHttp = false,
        };
    }
}
