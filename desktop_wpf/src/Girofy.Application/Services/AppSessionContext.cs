using Girofy.Application.Abstractions;
using Girofy.Application.Models;

namespace Girofy.Application.Services;

public sealed class AppSessionContext : IAppSessionContext
{
    private long _authenticationVersion;

    public AuthSession? Current { get; private set; }

    public event EventHandler? Changed;

    public void Set(AuthSession session)
    {
        session.AuthenticationVersion = ++_authenticationVersion;
        Current = session;
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public bool TryRefresh(AuthSession previous, AuthSession refreshed)
    {
        if (!ReferenceEquals(Current, previous))
        {
            return false;
        }

        refreshed.AuthenticationVersion = previous.AuthenticationVersion;
        Current = refreshed;
        Changed?.Invoke(this, EventArgs.Empty);
        return true;
    }

    public void Clear()
    {
        ++_authenticationVersion;
        Current = null;
        Changed?.Invoke(this, EventArgs.Empty);
    }
}
