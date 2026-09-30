using Girofy.Application.Models;

namespace Girofy.Application.Abstractions;

public interface IAppSessionContext
{
    AuthSession? Current { get; }

    event EventHandler? Changed;

    void Set(AuthSession session);

    bool TryRefresh(AuthSession previous, AuthSession refreshed);

    void Clear();
}
