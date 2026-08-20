using Girofy.Application.Models;

namespace Girofy.Application.Abstractions;

public interface IAccessibilityService
{
    AccessibilityPreferences Current { get; }

    event EventHandler? Changed;

    Task InitializeAsync(CancellationToken cancellationToken = default);

    void Preview(AccessibilityPreferences preferences);

    Task SaveAsync(AccessibilityPreferences preferences, CancellationToken cancellationToken = default);

    Task ResetAsync(CancellationToken cancellationToken = default);
}
