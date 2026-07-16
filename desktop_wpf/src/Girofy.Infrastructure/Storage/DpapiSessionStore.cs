using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Microsoft.Extensions.Logging;

namespace Girofy.Infrastructure.Storage;

public sealed class DpapiSessionStore(
    ILogger<DpapiSessionStore> logger) : ISecureSessionStore
{
    private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("Girofy.Windows.Session.v1");
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public async Task<AuthSession?> LoadAsync(CancellationToken cancellationToken)
    {
        if (!File.Exists(AppDataPaths.SessionFilePath))
        {
            return null;
        }

        try
        {
            var protectedPayload = await File.ReadAllBytesAsync(
                AppDataPaths.SessionFilePath,
                cancellationToken);
            var payload = ProtectedData.Unprotect(
                protectedPayload,
                Entropy,
                DataProtectionScope.CurrentUser);
            return JsonSerializer.Deserialize<AuthSession>(payload, JsonOptions);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is CryptographicException
                or JsonException
                or IOException
                or UnauthorizedAccessException)
        {
            logger.LogWarning(exception, "Stored desktop session could not be restored.");
            TryDeleteSessionFile();
            return null;
        }
    }

    public async Task SaveAsync(AuthSession session, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(session);
        AppDataPaths.EnsureDirectory();
        var payload = JsonSerializer.SerializeToUtf8Bytes(session, JsonOptions);
        var protectedPayload = ProtectedData.Protect(
            payload,
            Entropy,
            DataProtectionScope.CurrentUser);
        var temporaryPath = $"{AppDataPaths.SessionFilePath}.{Guid.NewGuid():N}.tmp";

        try
        {
            await File.WriteAllBytesAsync(temporaryPath, protectedPayload, cancellationToken);
            File.Move(temporaryPath, AppDataPaths.SessionFilePath, true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    public Task ClearAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        TryDeleteSessionFile();
        return Task.CompletedTask;
    }

    private static void TryDeleteSessionFile()
    {
        try
        {
            File.Delete(AppDataPaths.SessionFilePath);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }
}
