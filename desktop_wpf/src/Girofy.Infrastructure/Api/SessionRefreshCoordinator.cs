using System.Net;
using System.Net.Http.Json;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Microsoft.Extensions.Logging;

namespace Girofy.Infrastructure.Api;

public sealed class SessionRefreshCoordinator(
    IHttpClientFactory httpClientFactory,
    IAppSessionContext sessionContext,
    ISecureSessionStore sessionStore,
    ILogger<SessionRefreshCoordinator> logger)
{
    private readonly SemaphoreSlim _refreshLock = new(1, 1);

    public async Task<bool> EnsureFreshSessionAsync(
        string observedAccessToken,
        bool force,
        CancellationToken cancellationToken)
    {
        var current = sessionContext.Current;
        if (current is null || string.IsNullOrWhiteSpace(current.RefreshToken))
        {
            return false;
        }

        if (!force && !IsNearExpiration(current))
        {
            return true;
        }

        await _refreshLock.WaitAsync(cancellationToken);
        try
        {
            current = sessionContext.Current;
            if (current is null || string.IsNullOrWhiteSpace(current.RefreshToken))
            {
                return false;
            }

            if (!string.Equals(current.AccessToken, observedAccessToken, StringComparison.Ordinal))
            {
                return true;
            }

            if (!force && !IsNearExpiration(current))
            {
                return true;
            }

            logger.LogInformation("Access token expired or near expiration; attempting refresh.");
            using var client = httpClientFactory.CreateClient(ApiHttpClientNames.SessionRefresh);
            using var response = await client.PostAsJsonAsync(
                "api/v1/auth/refresh",
                new RefreshRequest(current.RefreshToken),
                cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
                {
                    await InvalidateSessionInsideLockAsync(cancellationToken);
                }

                logger.LogWarning(
                    "Session refresh was rejected with HTTP {StatusCode}.",
                    (int)response.StatusCode);
                return false;
            }

            var envelope = await response.Content.ReadFromJsonAsync<ApiEnvelope<AuthSession>>(
                cancellationToken: cancellationToken);
            if (envelope is not { Success: true, Data: not null } ||
                string.IsNullOrWhiteSpace(envelope.Data.AccessToken) ||
                string.IsNullOrWhiteSpace(envelope.Data.RefreshToken))
            {
                logger.LogWarning("Session refresh returned an invalid response envelope.");
                return false;
            }

            var refreshed = envelope.Data.WithCalculatedAccessExpiration(DateTimeOffset.UtcNow);
            await sessionStore.SaveAsync(refreshed, cancellationToken);
            sessionContext.Set(refreshed);
            logger.LogInformation("Session refresh completed successfully.");
            return true;
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (HttpRequestException exception)
        {
            logger.LogWarning(exception, "Session refresh could not reach the API.");
            return false;
        }
        catch (global::System.Text.Json.JsonException exception)
        {
            logger.LogWarning(exception, "Session refresh returned invalid JSON.");
            return false;
        }
        finally
        {
            _refreshLock.Release();
        }
    }

    public async Task InvalidateSessionAsync(CancellationToken cancellationToken)
    {
        await _refreshLock.WaitAsync(cancellationToken);
        try
        {
            await InvalidateSessionInsideLockAsync(cancellationToken);
        }
        finally
        {
            _refreshLock.Release();
        }
    }

    private async Task InvalidateSessionInsideLockAsync(CancellationToken cancellationToken)
    {
        if (sessionContext.Current is null)
        {
            return;
        }

        await sessionStore.ClearAsync(cancellationToken);
        sessionContext.Clear();
        logger.LogWarning("Refresh rejected; local session was cleared.");
    }

    private static bool IsNearExpiration(AuthSession session) =>
        session.AccessExpiresAtUtc is { } expiresAt &&
        expiresAt <= DateTimeOffset.UtcNow.AddSeconds(60);

    private sealed record RefreshRequest(
        [property: global::System.Text.Json.Serialization.JsonPropertyName("refresh_token")]
        string RefreshToken);
}

public static class ApiHttpClientNames
{
    public const string SessionRefresh = "Girofy.SessionRefresh";
}
