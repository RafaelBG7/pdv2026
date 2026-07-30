using System.Diagnostics;
using Girofy.Application.Abstractions;
using Microsoft.Extensions.Logging;

namespace Girofy.Infrastructure.System;

public sealed class SystemBrowserService(ILogger<SystemBrowserService> logger) : IExternalBrowserService
{
    public void Open(Uri uri)
    {
        Process.Start(new ProcessStartInfo(uri.AbsoluteUri)
        {
            UseShellExecute = true,
        });
    }

    public Task<bool> OpenAsync(Uri uri, CancellationToken cancellationToken = default)
    {
        if (!uri.IsAbsoluteUri ||
            (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps))
        {
            logger.LogWarning("Blocked an invalid external browser URI.");
            return Task.FromResult(false);
        }

        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            Open(uri);
            logger.LogInformation("Opened an external Girofy web page.");
            return Task.FromResult(true);
        }
        catch (Exception exception)
        {
            logger.LogWarning(exception, "Failed to open an external Girofy web page.");
            return Task.FromResult(false);
        }
    }
}
