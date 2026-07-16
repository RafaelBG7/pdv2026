namespace Girofy.Application.Abstractions;

public interface IExternalBrowserService
{
    void Open(Uri uri);
}
