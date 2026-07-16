using Girofy.Application.Abstractions;
using Girofy.Application.Models;

namespace Girofy.Application.Services;

public sealed class AppSessionContext : IAppSessionContext
{
    public AuthSession? Current { get; private set; }

    public event EventHandler? Changed;

    public void Set(AuthSession session)
    {
        Current = session;
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public void Clear()
    {
        Current = null;
        Changed?.Invoke(this, EventArgs.Empty);
    }
}
