using Girofy.Application.Models;

namespace Girofy.Application.Abstractions;

public interface IRegistrationHandoffStore
{
    Task SaveAsync(PendingRegistrationHandoff handoff, CancellationToken cancellationToken);
    Task<PendingRegistrationHandoff?> LoadAsync(CancellationToken cancellationToken);
    Task ClearAsync(CancellationToken cancellationToken);
}
