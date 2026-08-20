namespace Girofy.Application.Abstractions;

public interface IThemeService
{
    bool IsDarkMode { get; }

    event EventHandler? Changed;

    Task InitializeAsync(CancellationToken cancellationToken = default);

    Task ToggleAsync(CancellationToken cancellationToken = default);

    void Apply();
}
