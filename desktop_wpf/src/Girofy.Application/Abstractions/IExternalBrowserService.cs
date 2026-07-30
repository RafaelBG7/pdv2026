namespace Girofy.Application.Abstractions;

public interface IExternalBrowserService
{
    void Open(Uri uri);

    Task<bool> OpenAsync(Uri uri, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            Open(uri);
            return Task.FromResult(true);
        }
        catch
        {
            return Task.FromResult(false);
        }
    }
}
