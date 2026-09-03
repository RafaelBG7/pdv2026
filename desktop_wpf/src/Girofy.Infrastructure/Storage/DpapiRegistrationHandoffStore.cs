using System.Security.Cryptography;
using System.Text.Json;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Infrastructure.Runtime;

namespace Girofy.Infrastructure.Storage;

public sealed class DpapiRegistrationHandoffStore : IRegistrationHandoffStore
{
    private static readonly string DirectoryPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        SkyGestRuntimeEnvironment.DataDirectoryName);
    private static readonly string FilePath = Path.Combine(DirectoryPath, "registration-handoff.dat");

    public async Task SaveAsync(PendingRegistrationHandoff handoff, CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(DirectoryPath);
        var plain = JsonSerializer.SerializeToUtf8Bytes(handoff);
        var protectedData = ProtectedData.Protect(plain, null, DataProtectionScope.CurrentUser);
        await File.WriteAllBytesAsync(FilePath, protectedData, cancellationToken);
    }

    public async Task<PendingRegistrationHandoff?> LoadAsync(CancellationToken cancellationToken)
    {
        if (!File.Exists(FilePath)) return null;
        try
        {
            var protectedData = await File.ReadAllBytesAsync(FilePath, cancellationToken);
            var plain = ProtectedData.Unprotect(protectedData, null, DataProtectionScope.CurrentUser);
            return JsonSerializer.Deserialize<PendingRegistrationHandoff>(plain);
        }
        catch (CryptographicException) { return null; }
        catch (JsonException) { return null; }
    }

    public Task ClearAsync(CancellationToken cancellationToken)
    {
        if (File.Exists(FilePath)) File.Delete(FilePath);
        return Task.CompletedTask;
    }
}
