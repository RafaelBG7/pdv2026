using System.Text.Json;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Microsoft.Extensions.Logging;

namespace Girofy.Infrastructure.Storage;

public sealed class JsonUserPreferencesStore(
    ILogger<JsonUserPreferencesStore> logger) : IUserPreferencesStore
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
    };

    public async Task<UserPreferences> LoadAsync(CancellationToken cancellationToken)
    {
        if (!File.Exists(AppDataPaths.PreferencesFilePath))
        {
            return new UserPreferences();
        }

        try
        {
            await using var stream = File.OpenRead(AppDataPaths.PreferencesFilePath);
            return await JsonSerializer.DeserializeAsync<UserPreferences>(
                stream,
                JsonOptions,
                cancellationToken) ?? new UserPreferences();
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is JsonException
                or IOException
                or UnauthorizedAccessException)
        {
            logger.LogWarning(exception, "Desktop preferences could not be loaded.");
            return new UserPreferences();
        }
    }

    public async Task SaveAsync(
        UserPreferences preferences,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(preferences);
        AppDataPaths.EnsureDirectory();
        var temporaryPath = $"{AppDataPaths.PreferencesFilePath}.{Guid.NewGuid():N}.tmp";

        try
        {
            await using (var stream = File.Create(temporaryPath))
            {
                await JsonSerializer.SerializeAsync(
                    stream,
                    preferences,
                    JsonOptions,
                    cancellationToken);
            }
            File.Move(temporaryPath, AppDataPaths.PreferencesFilePath, true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }
}
