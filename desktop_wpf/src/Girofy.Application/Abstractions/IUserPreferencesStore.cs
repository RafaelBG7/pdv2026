using Girofy.Application.Models;

namespace Girofy.Application.Abstractions;

public interface IUserPreferencesStore
{
    Task<UserPreferences> LoadAsync(CancellationToken cancellationToken);

    Task SaveAsync(UserPreferences preferences, CancellationToken cancellationToken);
}
