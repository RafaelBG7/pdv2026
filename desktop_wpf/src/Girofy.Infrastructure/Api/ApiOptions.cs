using Microsoft.Extensions.Configuration;

namespace Girofy.Infrastructure.Api;

public sealed class ApiOptions
{
    private const string LegacyProductionHost = "skygest.com.br";
    private const string CanonicalProductionHost = "www.skygest.com.br";

    public string BaseUrl { get; init; } = string.Empty;

    public bool AllowInsecureHttp { get; init; }

    public int TimeoutSeconds { get; init; } = 10;

    public static ApiOptions FromConfiguration(IConfiguration configuration)
    {
        var section = configuration.GetSection("Api");
        var baseUrl = Environment.GetEnvironmentVariable("GIROFY_API_BASE_URL") ?? section["BaseUrl"];
        var allowHttpValue = Environment.GetEnvironmentVariable("GIROFY_ALLOW_INSECURE_HTTP") ?? section["AllowInsecureHttp"];
        var timeoutValue = Environment.GetEnvironmentVariable("GIROFY_API_TIMEOUT_SECONDS") ?? section["TimeoutSeconds"];

        return new ApiOptions
        {
            BaseUrl = baseUrl?.Trim() ?? string.Empty,
            AllowInsecureHttp = bool.TryParse(allowHttpValue, out var allowHttp) && allowHttp,
            TimeoutSeconds = int.TryParse(timeoutValue, out var timeout) ? Math.Clamp(timeout, 3, 60) : 10,
        };
    }

    public Uri GetValidatedBaseUri()
    {
        if (!Uri.TryCreate(BaseUrl, UriKind.Absolute, out var baseUri))
        {
            throw new InvalidOperationException("A URL da API SkyGest não foi configurada corretamente.");
        }

        if (baseUri.Scheme != Uri.UriSchemeHttps && baseUri.Scheme != Uri.UriSchemeHttp)
        {
            throw new InvalidOperationException("A API SkyGest deve usar HTTP ou HTTPS.");
        }

        if (baseUri.Scheme == Uri.UriSchemeHttp && !AllowInsecureHttp)
        {
            throw new InvalidOperationException("Conexões HTTP precisam ser habilitadas explicitamente.");
        }

        if (string.Equals(baseUri.Host, LegacyProductionHost, StringComparison.OrdinalIgnoreCase))
        {
            var canonicalUri = new UriBuilder(baseUri)
            {
                Host = CanonicalProductionHost,
            };
            baseUri = canonicalUri.Uri;
        }

        return new Uri($"{baseUri.ToString().TrimEnd('/')}/", UriKind.Absolute);
    }
}
