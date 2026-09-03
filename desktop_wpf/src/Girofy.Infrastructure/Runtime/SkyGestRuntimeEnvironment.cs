namespace Girofy.Infrastructure.Runtime;

public static class SkyGestRuntimeEnvironment
{
    public const string HomologationMarkerFileName = "SkyGest.Homologation";

    public static bool IsHomologation =>
        string.Equals(
            System.Environment.GetEnvironmentVariable("SKYGEST_ENVIRONMENT"),
            "Homologation",
            StringComparison.OrdinalIgnoreCase)
        || File.Exists(Path.Combine(AppContext.BaseDirectory, HomologationMarkerFileName));

    public static string DataDirectoryName => IsHomologation ? "Girofy-Homologation" : "Girofy";
}
