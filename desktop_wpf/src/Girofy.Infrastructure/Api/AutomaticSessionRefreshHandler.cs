using System.Net;
using System.Net.Http.Headers;
using Girofy.Application.Abstractions;
using Microsoft.Extensions.Logging;

namespace Girofy.Infrastructure.Api;

public sealed class AutomaticSessionRefreshHandler(
    IAppSessionContext sessionContext,
    SessionRefreshCoordinator refreshCoordinator,
    ILogger<AutomaticSessionRefreshHandler> logger) : DelegatingHandler
{
    private static readonly string[] ExcludedPaths =
    [
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
        "/password-recovery",
    ];

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        if (!IsAuthenticatedRequest(request) || IsExcludedRoute(request.RequestUri))
        {
            return await base.SendAsync(request, cancellationToken);
        }

        var current = sessionContext.Current;
        if (current is not null)
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", current.AccessToken);
            if (await refreshCoordinator.EnsureFreshSessionAsync(
                    current.AccessToken,
                    force: false,
                    cancellationToken))
            {
                current = sessionContext.Current;
                if (current is not null)
                {
                    request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", current.AccessToken);
                }
            }
        }

        var retryRequest = await CloneRequestAsync(request, cancellationToken);
        var accessTokenUsed = request.Headers.Authorization?.Parameter ?? string.Empty;
        var response = await base.SendAsync(request, cancellationToken);
        if (response.StatusCode != HttpStatusCode.Unauthorized)
        {
            retryRequest.Dispose();
            return response;
        }

        response.Dispose();
        if (!await refreshCoordinator.EnsureFreshSessionAsync(
                accessTokenUsed,
                force: true,
                cancellationToken))
        {
            retryRequest.Dispose();
            return new HttpResponseMessage(HttpStatusCode.Unauthorized)
            {
                RequestMessage = request,
                ReasonPhrase = "Session renewal failed",
            };
        }

        current = sessionContext.Current;
        if (current is null)
        {
            retryRequest.Dispose();
            return new HttpResponseMessage(HttpStatusCode.Unauthorized)
            {
                RequestMessage = request,
                ReasonPhrase = "Session unavailable",
            };
        }

        retryRequest.Headers.Authorization = new AuthenticationHeaderValue("Bearer", current.AccessToken);
        logger.LogInformation("Retrying API request once after token refresh.");
        var retryResponse = await base.SendAsync(retryRequest, cancellationToken);
        if (retryResponse.StatusCode == HttpStatusCode.Unauthorized)
        {
            await refreshCoordinator.InvalidateSessionAsync(cancellationToken);
        }

        return retryResponse;
    }

    private static bool IsAuthenticatedRequest(HttpRequestMessage request) =>
        string.Equals(
            request.Headers.Authorization?.Scheme,
            "Bearer",
            StringComparison.OrdinalIgnoreCase);

    private static bool IsExcludedRoute(Uri? requestUri)
    {
        var path = requestUri?.AbsolutePath ?? string.Empty;
        return ExcludedPaths.Any(excluded =>
            path.Contains(excluded, StringComparison.OrdinalIgnoreCase));
    }

    private static async Task<HttpRequestMessage> CloneRequestAsync(
        HttpRequestMessage source,
        CancellationToken cancellationToken)
    {
        var clone = new HttpRequestMessage(source.Method, source.RequestUri)
        {
            Version = source.Version,
            VersionPolicy = source.VersionPolicy,
        };

        foreach (var header in source.Headers)
        {
            clone.Headers.TryAddWithoutValidation(header.Key, header.Value);
        }

        if (source.Content is not null)
        {
            var content = new ByteArrayContent(
                await source.Content.ReadAsByteArrayAsync(cancellationToken));
            foreach (var header in source.Content.Headers)
            {
                content.Headers.TryAddWithoutValidation(header.Key, header.Value);
            }

            clone.Content = content;
        }

        foreach (var option in source.Options)
        {
            clone.Options.Set(new HttpRequestOptionsKey<object?>(option.Key), option.Value);
        }

        return clone;
    }
}
