using Girofy.Application.Models;

namespace Girofy.Application.Abstractions;

public interface ISecureSessionStore
{
    Task<AuthSession?> LoadAsync(CancellationToken cancellationToken);

    Task SaveAsync(AuthSession session, CancellationToken cancellationToken);

    Task ClearAsync(CancellationToken cancellationToken);
}
