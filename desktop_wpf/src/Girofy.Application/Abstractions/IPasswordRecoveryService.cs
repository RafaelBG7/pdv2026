namespace Girofy.Application.Abstractions;

public interface IPasswordRecoveryService
{
    Task RequestAsync(string identifier, CancellationToken cancellationToken = default);
}
