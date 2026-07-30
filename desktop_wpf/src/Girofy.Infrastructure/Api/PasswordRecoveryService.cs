using System.Net;
using System.Net.Http.Json;
using Girofy.Application.Abstractions;
using Microsoft.Extensions.Logging;

namespace Girofy.Infrastructure.Api;

public sealed class PasswordRecoveryService(
    HttpClient httpClient,
    ILogger<PasswordRecoveryService> logger) : IPasswordRecoveryService
{
    public async Task RequestAsync(
        string identifier,
        CancellationToken cancellationToken = default)
    {
        logger.LogInformation("Starting a password recovery request.");
        using var response = await httpClient.PostAsJsonAsync(
            "api/v1/auth/password-recovery/request",
            new { identifier },
            cancellationToken);
        if (response.StatusCode == HttpStatusCode.TooManyRequests)
        {
            logger.LogWarning("Password recovery was rate limited.");
            throw new HttpRequestException("Rate limited.", null, response.StatusCode);
        }
        if (!response.IsSuccessStatusCode)
        {
            logger.LogWarning(
                "Password recovery returned HTTP {StatusCode}.",
                (int)response.StatusCode);
            throw new HttpRequestException("Password recovery failed.", null, response.StatusCode);
        }
        logger.LogInformation("Password recovery request completed.");
    }
}
