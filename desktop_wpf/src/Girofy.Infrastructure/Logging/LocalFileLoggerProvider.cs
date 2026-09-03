using Microsoft.Extensions.Logging;
using Girofy.Infrastructure.Runtime;

namespace Girofy.Infrastructure.Logging;

public sealed class LocalFileLoggerProvider : ILoggerProvider
{
    private readonly string _logPath;
    private readonly object _writeLock = new();

    public static string LogDirectoryPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        SkyGestRuntimeEnvironment.DataDirectoryName,
        "logs");

    public static string LogFilePath => Path.Combine(LogDirectoryPath, "desktop.log");

    public LocalFileLoggerProvider()
    {
        Directory.CreateDirectory(LogDirectoryPath);
        _logPath = LogFilePath;
    }

    public ILogger CreateLogger(string categoryName) => new LocalFileLogger(categoryName, WriteLine);

    public void Dispose()
    {
    }

    private void WriteLine(string line)
    {
        lock (_writeLock)
        {
            RotateIfNeeded();
            File.AppendAllText(_logPath, line + Environment.NewLine);
        }
    }

    private void RotateIfNeeded()
    {
        var file = new FileInfo(_logPath);
        if (!file.Exists || file.Length < 2 * 1024 * 1024)
        {
            return;
        }

        var archivedPath = Path.Combine(file.DirectoryName!, "desktop.previous.log");
        File.Delete(archivedPath);
        File.Move(_logPath, archivedPath);
    }

    private sealed class LocalFileLogger(string categoryName, Action<string> writeLine) : ILogger
    {
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => NullScope.Instance;

        public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Information;

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            if (!IsEnabled(logLevel))
            {
                return;
            }

            var message = formatter(state, exception);
            var exceptionName = exception is null ? string.Empty : $" | {exception.GetType().Name}";
            writeLine($"{DateTimeOffset.Now:O} [{logLevel}] {categoryName}: {message}{exceptionName}");

            if (exception is not null)
            {
                writeLine(exception.ToString());
            }
        }
    }

    private sealed class NullScope : IDisposable
    {
        public static NullScope Instance { get; } = new();

        public void Dispose()
        {
        }
    }
}
