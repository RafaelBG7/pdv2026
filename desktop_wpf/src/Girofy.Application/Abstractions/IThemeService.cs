namespace Girofy.Application.Abstractions;

public interface IThemeService
{
    bool IsDarkMode { get; }

    Task InitializeAsync(CancellationToken cancellationToken = default);

    Task ToggleAsync(CancellationToken cancellationToken = default);
}
