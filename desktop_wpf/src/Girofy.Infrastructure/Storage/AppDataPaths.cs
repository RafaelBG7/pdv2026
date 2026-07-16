namespace Girofy.Infrastructure.Storage;

internal static class AppDataPaths
{
    public static string DirectoryPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Girofy");

    public static string SessionFilePath => Path.Combine(DirectoryPath, "auth.dat");

    public static string PreferencesFilePath => Path.Combine(DirectoryPath, "preferences.json");

    public static void EnsureDirectory() => Directory.CreateDirectory(DirectoryPath);
}
