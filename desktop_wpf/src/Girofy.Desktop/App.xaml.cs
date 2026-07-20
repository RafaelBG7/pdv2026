using System.Windows;
using System.Windows.Threading;
using Girofy.Application.Abstractions;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;
using Girofy.Desktop.Platform;
using Girofy.Infrastructure.Api;
using Girofy.Infrastructure.Logging;
using Girofy.Infrastructure.Storage;
using Girofy.Infrastructure.System;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Girofy.Desktop;

public partial class App : System.Windows.Application
{
    private readonly IHost _host;
    private ILogger<App>? _logger;

    public App()
    {
        _host = Host.CreateDefaultBuilder()
            .ConfigureAppConfiguration((_, configuration) =>
            {
                configuration.SetBasePath(AppContext.BaseDirectory);
                configuration.AddJsonFile("appsettings.json", optional: false, reloadOnChange: false);
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

                services.AddSingleton(apiOptions);
                services.AddSingleton<IExternalBrowserService, SystemBrowserService>();
                services.AddSingleton<IFileSaveService, WindowsFileSaveService>();
                services.AddSingleton<IFilePickerService, WindowsFilePickerService>();
                services.AddSingleton<ISecureSessionStore, DpapiSessionStore>();
                services.AddSingleton<IUserPreferencesStore, JsonUserPreferencesStore>();
                services.AddSingleton<IAppSessionContext, AppSessionContext>();
                services.AddHttpClient<IGirofyApiClient, GirofyApiClient>(client =>
                {
                    client.BaseAddress = serverUri;
                    client.Timeout = TimeSpan.FromSeconds(apiOptions.TimeoutSeconds);
                    client.DefaultRequestHeaders.UserAgent.ParseAdd("Girofy-Windows/0.1");
                });
                services.AddSingleton(provider => new LoginViewModel(
                    provider.GetRequiredService<IGirofyApiClient>(),
                    provider.GetRequiredService<ISecureSessionStore>(),
                    provider.GetRequiredService<IUserPreferencesStore>(),
                    provider.GetRequiredService<IExternalBrowserService>(),
                    provider.GetRequiredService<IAppSessionContext>(),
                    new Uri(serverUri, "forgot-password")));
                services.AddSingleton<CatalogViewModel>();
                services.AddSingleton<DashboardViewModel>();
                services.AddSingleton<CashRegisterViewModel>();
                services.AddSingleton<SalesViewModel>();
                services.AddSingleton<StockViewModel>();
                services.AddSingleton<PayablesViewModel>();
                services.AddSingleton<ReportsViewModel>();
                services.AddSingleton<AuditViewModel>();
                services.AddSingleton(provider => new SettingsViewModel(
                    provider.GetRequiredService<IGirofyApiClient>(),
                    provider.GetRequiredService<IAppSessionContext>(),
                    provider.GetRequiredService<IExternalBrowserService>(),
                    provider.GetRequiredService<IFileSaveService>(),
                    provider.GetRequiredService<IFilePickerService>(),
                    new Uri(serverUri, "configuracoes")));
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
        await _host.StartAsync();
        _logger = _host.Services.GetRequiredService<ILogger<App>>();
        _logger.LogInformation("Girofy Windows started.");
        _host.Services.GetRequiredService<MainWindow>().Show();
    }

    protected override async void OnExit(ExitEventArgs e)
    {
        _logger?.LogInformation("Girofy Windows stopped.");
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(3));
        await _host.StopAsync(timeout.Token);
        _host.Dispose();
        base.OnExit(e);
    }

    private void HandleDispatcherException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        _logger?.LogError(e.Exception, "Unhandled desktop UI error.");
        MessageBox.Show(
            "O Girofy encontrou uma falha inesperada. Tente novamente.",
            "Girofy",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
        e.Handled = true;
    }

    private void HandleDomainException(object? sender, UnhandledExceptionEventArgs e)
    {
        _logger?.LogCritical(e.ExceptionObject as Exception, "Unhandled desktop process error.");
    }

    private void HandleUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        _logger?.LogError(e.Exception, "Unobserved desktop task error.");
        e.SetObserved();
    }
}
