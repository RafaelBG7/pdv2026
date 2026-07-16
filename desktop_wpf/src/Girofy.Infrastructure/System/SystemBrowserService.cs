using System.Diagnostics;
using Girofy.Application.Abstractions;

namespace Girofy.Infrastructure.System;

public sealed class SystemBrowserService : IExternalBrowserService
{
    public void Open(Uri uri)
    {
        Process.Start(new ProcessStartInfo(uri.AbsoluteUri)
        {
            UseShellExecute = true,
        });
    }
}
