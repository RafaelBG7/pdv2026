using System.IO;
using System.IO.Pipes;
using System.Globalization;
using System.Threading;
using System.Windows;
using System.Windows.Threading;
using Girofy.Application.Abstractions;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;
using Girofy.Desktop.Platform;
using Girofy.Infrastructure.Api;
using Girofy.Infrastructure.Logging;
using Girofy.Infrastructure.Runtime;
using Girofy.Infrastructure.Storage;
using Girofy.Infrastructure.System;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Girofy.Desktop;

public partial class App : System.Windows.Application
{
    // Identificadores legados preservados para impedir duas instâncias durante upgrades.
    private static readonly string SingleInstanceMutexName = SkyGestRuntimeEnvironment.IsHomologation
        ? @"Local\Girofy.Desktop.Homologation.SingleInstance"
        : @"Local\Girofy.Desktop.SingleInstance";
    private static readonly string ActivationPipeName = SkyGestRuntimeEnvironment.IsHomologation
        ? "Girofy.Desktop.Homologation.Activation"
        : "Girofy.Desktop.Activation";
    private readonly Mutex _singleInstanceMutex = new(false, SingleInstanceMutexName);
    private readonly bool _ownsSingleInstance;
    private readonly IHost? _host;
    private ILogger<App>? _logger;

    public App()
    {
        var brazilianCulture = CultureInfo.GetCultureInfo("pt-BR");
        CultureInfo.DefaultThreadCurrentCulture = brazilianCulture;
        CultureInfo.DefaultThreadCurrentUICulture = brazilianCulture;

        _ownsSingleInstance = TryAcquireSingleInstance(_singleInstanceMutex);
        if (!_ownsSingleInstance)
        {
            return;
        }

        _host = Host.CreateDefaultBuilder()
            .ConfigureAppConfiguration((_, configuration) =>
            {
                configuration.SetBasePath(AppContext.BaseDirectory);
                configuration.AddInMemoryCollection(new Dictionary<string, string?>
                {
                    ["Api:BaseUrl"] = "https://www.skygest.com.br",
                    ["Api:AllowInsecureHttp"] = "false",
                    ["Api:TimeoutSeconds"] = "10",
                });
                configuration.AddJsonFile("appsettings.json", optional: true, reloadOnChange: false);
                if (SkyGestRuntimeEnvironment.IsHomologation)
                {
                    configuration.AddJsonFile("appsettings.Homologation.json", optional: false, reloadOnChange: false);
                }
                configuration.AddEnvironmentVariables();
            })
            .ConfigureLogging(logging =>
            {
                logging.ClearProviders();
                logging.AddProvider(new LocalFileLoggerProvider());
            })
            .ConfigureServices((context, services) =>
            {
                var apiOptions = ApiOptions.FromConfiguration(context.Configuration);
                var serverUri = apiOptions.GetValidatedBaseUri();
                var productVersion = typeof(App).Assembly.GetName().Version?.ToString(3) ?? "unknown";
                var userAgent = $"SkyGest-Windows/{productVersion}";

                services.AddSingleton(apiOptions);
                services.AddSingleton<IExternalBrowserService, SystemBrowserService>();
                services.AddSingleton<IFileSaveService, WindowsFileSaveService>();
                services.AddSingleton<IFilePickerService, WindowsFilePickerService>();
                services.AddSingleton<ISecureSessionStore, DpapiSessionStore>();
                services.AddSingleton<IRegistrationHandoffStore, DpapiRegistrationHandoffStore>();
                services.AddSingleton<IUserPreferencesStore, JsonUserPreferencesStore>();
                services.AddSingleton<IThemeService, WindowsThemeService>();
                services.AddSingleton<IAccessibilityService, AccessibilityService>();
                services.AddSingleton<WindowsAccessibilityResourceAdapter>();
                services.AddSingleton<IAppSessionContext, AppSessionContext>();
                services.AddSingleton<SessionRefreshCoordinator>();
                services.AddTransient<AutomaticSessionRefreshHandler>();
                services.AddHttpClient(ApiHttpClientNames.SessionRefresh, client =>
                {
                    client.BaseAddress = serverUri;
                    client.Timeout = TimeSpan.FromSeconds(apiOptions.TimeoutSeconds);
                    client.DefaultRequestHeaders.UserAgent.ParseAdd(userAgent);
                });
                services.AddHttpClient<IGirofyApiClient, GirofyApiClient>(client =>
                {
                    client.BaseAddress = serverUri;
                    client.Timeout = TimeSpan.FromSeconds(apiOptions.TimeoutSeconds);
                    client.DefaultRequestHeaders.UserAgent.ParseAdd(userAgent);
                }).AddHttpMessageHandler<AutomaticSessionRefreshHandler>();
                services.AddHttpClient<IPasswordRecoveryService, PasswordRecoveryService>(client =>
                {
                    client.BaseAddress = serverUri;
                    client.Timeout = TimeSpan.FromSeconds(apiOptions.TimeoutSeconds);
                    client.DefaultRequestHeaders.UserAgent.ParseAdd(userAgent);
                });
                services.AddTransient<ForgotPasswordViewModel>();
                services.AddSingleton(provider => new LoginViewModel(
                    provider.GetRequiredService<IGirofyApiClient>(),
                    provider.GetRequiredService<ISecureSessionStore>(),
                    provider.GetRequiredService<IUserPreferencesStore>(),
                    provider.GetRequiredService<IExternalBrowserService>(),
                    provider.GetRequiredService<IAppSessionContext>(),
                    provider.GetRequiredService<ForgotPasswordViewModel>(),
                    provider.GetRequiredService<IRegistrationHandoffStore>(),
                    new Uri(serverUri, "login?auth_tab=register")));
                services.AddSingleton<CatalogViewModel>();
                services.AddSingleton<DashboardViewModel>();
                services.AddSingleton<CashRegisterViewModel>();
                services.AddSingleton<SalesViewModel>();
                services.AddSingleton<StockViewModel>();
                services.AddSingleton<PayablesViewModel>();
                services.AddSingleton<ReportsViewModel>();
                services.AddSingleton<AuditViewModel>();
                services.AddSingleton<NotificationsViewModel>();
                services.AddSingleton(provider => new SettingsViewModel(
                    provider.GetRequiredService<IGirofyApiClient>(),
                    provider.GetRequiredService<IAppSessionContext>(),
                    provider.GetRequiredService<IExternalBrowserService>(),
                    provider.GetRequiredService<IFileSaveService>(),
                    provider.GetRequiredService<IFilePickerService>(),
                    new Uri(serverUri, "configuracoes"),
                    provider.GetRequiredService<IThemeService>(),
                    provider.GetRequiredService<IAccessibilityService>()));
                services.AddSingleton(provider => new ConnectionViewModel(
                    provider.GetRequiredService<IGirofyApiClient>(),
                    provider.GetRequiredService<IExternalBrowserService>(),
                    serverUri,
                    provider.GetRequiredService<LoginViewModel>(),
                    provider.GetRequiredService<CatalogViewModel>(),
                    provider.GetRequiredService<DashboardViewModel>(),
                    provider.GetRequiredService<CashRegisterViewModel>(),
                    provider.GetRequiredService<SalesViewModel>(),
                    provider.GetRequiredService<StockViewModel>(),
                    provider.GetRequiredService<PayablesViewModel>(),
                    provider.GetRequiredService<ReportsViewModel>(),
                    provider.GetRequiredService<AuditViewModel>(),
                    provider.GetRequiredService<NotificationsViewModel>(),
                    provider.GetRequiredService<SettingsViewModel>()));
                services.AddSingleton<MainWindow>();
            })
            .Build();

        DispatcherUnhandledException += HandleDispatcherException;
        AppDomain.CurrentDomain.UnhandledException += HandleDomainException;
        TaskScheduler.UnobservedTaskException += HandleUnobservedTaskException;
    }

    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        if (!_ownsSingleInstance || _host is null)
        {
            await ForwardActivationAsync(e.Args);
            Shutdown();
            return;
        }

        try
        {
            await _host.StartAsync();
            _logger = _host.Services.GetRequiredService<ILogger<App>>();
            try
            {
                await _host.Services.GetRequiredService<IThemeService>().InitializeAsync();
                await _host.Services.GetRequiredService<IAccessibilityService>().InitializeAsync();
                _host.Services.GetRequiredService<WindowsAccessibilityResourceAdapter>().Apply();
            }
            catch (Exception themeException)
            {
                _logger.LogWarning(themeException, "Saved desktop theme could not be applied; using the default theme.");
            }
            _logger.LogInformation("SkyGest Windows started.");
            var mainWindow = _host.Services.GetRequiredService<MainWindow>();
            if (SkyGestRuntimeEnvironment.IsHomologation)
            {
                mainWindow.Title = "SkyGest Homologação";
            }
            mainWindow.Show();
            _ = ListenForActivationsAsync();
            var callback = e.Args.FirstOrDefault(argument => Uri.TryCreate(argument, UriKind.Absolute, out var uri)
                && string.Equals(uri.Scheme, "girofy", StringComparison.OrdinalIgnoreCase));
            if (callback is not null)
            {
                await _host.Services.GetRequiredService<LoginViewModel>()
                    .HandleRegistrationCallbackAsync(new Uri(callback));
            }
        }
        catch (Exception exception)
        {
            WriteEmergencyLog(exception, "Falha ao iniciar o SkyGest Windows.");
            _logger?.LogCritical(exception, "Desktop startup failed.");
            MessageBox.Show(
                BuildUnexpectedErrorMessage(),
                "SkyGest",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            Shutdown(1);
        }
    }

    protected override async void OnExit(ExitEventArgs e)
    {
        try
        {
            if (_host is not null)
            {
                _logger?.LogInformation("SkyGest Windows stopped.");
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(3));
                await _host.StopAsync(timeout.Token);
                _host.Dispose();
            }
        }
        finally
        {
            if (_ownsSingleInstance)
            {
                _singleInstanceMutex.ReleaseMutex();
            }
            _singleInstanceMutex.Dispose();
            base.OnExit(e);
        }
    }

    private static bool TryAcquireSingleInstance(Mutex mutex)
    {
        try
        {
            return mutex.WaitOne(TimeSpan.Zero, false);
        }
        catch (AbandonedMutexException)
        {
            return true;
        }
    }

    private async Task ListenForActivationsAsync()
    {
        while (_ownsSingleInstance)
        {
            try
            {
                await using var pipe = new NamedPipeServerStream(
                    ActivationPipeName, PipeDirection.In, 1, PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
                await pipe.WaitForConnectionAsync();
                using var reader = new StreamReader(pipe);
                var argument = await reader.ReadLineAsync();
                if (Uri.TryCreate(argument, UriKind.Absolute, out var callback)
                    && string.Equals(callback.Scheme, "girofy", StringComparison.OrdinalIgnoreCase)
                    && _host is not null)
                {
                    await Dispatcher.InvokeAsync(async () =>
                    {
                        var window = _host.Services.GetRequiredService<MainWindow>();
                        window.Show();
                        window.Activate();
                        await _host.Services.GetRequiredService<LoginViewModel>()
                            .HandleRegistrationCallbackAsync(callback);
                    });
                }
            }
            catch (Exception exception)
            {
                _logger?.LogWarning(exception, "Desktop activation callback could not be processed.");
            }
        }
    }

    private static async Task ForwardActivationAsync(string[] arguments)
    {
        var callback = arguments.FirstOrDefault(argument => Uri.TryCreate(argument, UriKind.Absolute, out var uri)
            && string.Equals(uri.Scheme, "girofy", StringComparison.OrdinalIgnoreCase));
        if (callback is null) return;
        try
        {
            await using var pipe = new NamedPipeClientStream(".", ActivationPipeName, PipeDirection.Out, PipeOptions.Asynchronous);
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(2));
            await pipe.ConnectAsync(timeout.Token);
            await using var writer = new StreamWriter(pipe) { AutoFlush = true };
            await writer.WriteLineAsync(callback);
        }
        catch
        {
            // The browser fallback remains available when the running instance cannot be reached.
        }
    }

    private void HandleDispatcherException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        WriteEmergencyLog(e.Exception, "Falha inesperada na interface do SkyGest Windows.");
        _logger?.LogError(e.Exception, "Unhandled desktop UI error.");

        if (!HasVisibleWindow())
        {
            MessageBox.Show(
                BuildUnexpectedErrorMessage(),
                "SkyGest",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }

        e.Handled = true;
    }

    private bool HasVisibleWindow()
    {
        foreach (Window window in Windows)
        {
            if (window.IsVisible)
            {
                return true;
            }
        }

        return false;
    }

    private void HandleDomainException(object? sender, UnhandledExceptionEventArgs e)
    {
        var exception = e.ExceptionObject as Exception;
        WriteEmergencyLog(exception, "Falha inesperada no processo do SkyGest Windows.");
        _logger?.LogCritical(exception, "Unhandled desktop process error.");
    }

    private void HandleUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        WriteEmergencyLog(e.Exception, "Falha inesperada em tarefa assíncrona do SkyGest Windows.");
        _logger?.LogError(e.Exception, "Unobserved desktop task error.");
        e.SetObserved();
    }

    private static string BuildUnexpectedErrorMessage() =>
        "O SkyGest encontrou uma falha inesperada. Tente novamente." +
        Environment.NewLine +
        Environment.NewLine +
        "Detalhes técnicos foram salvos em:" +
        Environment.NewLine +
        LocalFileLoggerProvider.LogFilePath;

    private static void WriteEmergencyLog(Exception? exception, string message)
    {
        try
        {
            Directory.CreateDirectory(LocalFileLoggerProvider.LogDirectoryPath);
            File.AppendAllText(
                LocalFileLoggerProvider.LogFilePath,
                $"{DateTimeOffset.Now:O} [Critical] {message}{Environment.NewLine}{exception}{Environment.NewLine}");
        }
        catch
        {
            // O app nao pode quebrar novamente tentando registrar a propria falha.
        }
    }
}
