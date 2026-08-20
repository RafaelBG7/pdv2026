using System.Text;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class SettingsViewModelTests
{
    private static AppSessionContext CreateAdminSessionContext()
    {
        var context = new AppSessionContext();
        context.Set(new AuthSession
        {
            AccessToken = "access-token",
            RefreshToken = "refresh-token",
            User = new UserIdentity { Id = 10, Username = "adegajf", Role = "admin", RoleLabel = "Admin" },
            Company = new CompanyIdentity
            {
                Id = 20, Name = "Adega JF", Active = true,
                SubscriptionPlan = "Pro", SubscriptionValid = true,
            },
        });
        return context;
    }

    [Fact]
    public async Task Notification_preferences_are_loaded_and_saved_by_native_settings()
    {
        var apiClient = new ExportApiClient();
        var sessionContext = CreateAdminSessionContext();
        var viewModel = new SettingsViewModel(
            apiClient, sessionContext, new StubBrowserService(), new CapturingFileSaveService(),
            new CapturingFilePickerService(), new Uri("https://girofy.example/configuracoes"));

        await viewModel.InitializeAsync();

        Assert.True(viewModel.NotificationInAppEnabled);
        Assert.Equal("warning", viewModel.NotificationMinimumSeverity);
        Assert.Equal("22:00", viewModel.NotificationQuietHoursStart);
        viewModel.NotificationEmailEnabled = true;
        viewModel.NotificationDailyDigestEnabled = true;
        viewModel.NotificationDailyDigestTime = "07:30";
        await viewModel.SaveNotificationPreferencesCommand.ExecuteAsync();

        Assert.NotNull(apiClient.NotificationPreferenceRequest);
        Assert.True(apiClient.NotificationPreferenceRequest!.EmailEnabled);
        Assert.True(apiClient.NotificationPreferenceRequest.DailyDigestEnabled);
        Assert.Equal("07:30", apiClient.NotificationPreferenceRequest.DailyDigestTime);
        Assert.Contains("salvas com sucesso", viewModel.SuccessMessage);
    }

    [Fact]
    public async Task ToggleThemeAsync_changes_theme_and_updates_button_text()
    {
        var themeService = new StubThemeService();
        var viewModel = new SettingsViewModel(
            new ExportApiClient(),
            new AppSessionContext(),
            new StubBrowserService(),
            new CapturingFileSaveService(),
            new CapturingFilePickerService(),
            new Uri("https://girofy.example/configuracoes"),
            themeService);

        Assert.Equal("Usar tema claro", viewModel.ThemeToggleText);
        Assert.True(viewModel.IsDarkMode);

        await viewModel.ToggleThemeCommand.ExecuteAsync();

        Assert.False(themeService.IsDarkMode);
        Assert.False(viewModel.IsDarkMode);
        Assert.Equal("Usar tema escuro", viewModel.ThemeToggleText);
    }

    [Fact]
    public async Task ExportDataAsync_downloads_selected_csv_and_prompts_to_save_for_admin()
    {
        var apiClient = new ExportApiClient();
        var fileSaveService = new CapturingFileSaveService();
        var sessionContext = new AppSessionContext();
        sessionContext.Set(new AuthSession
        {
            AccessToken = "access-token",
            RefreshToken = "refresh-token",
            User = new UserIdentity
            {
                Id = 10,
                Username = "adegajf",
                Role = "admin",
                RoleLabel = "Admin",
            },
            Company = new CompanyIdentity
            {
                Id = 20,
                Name = "Adega JF",
                Active = true,
                SubscriptionPlan = "Pro",
                SubscriptionValid = true,
            },
        });
        var viewModel = new SettingsViewModel(
            apiClient,
            sessionContext,
            new StubBrowserService(),
            fileSaveService,
            new CapturingFilePickerService(),
            new Uri("https://girofy.example/configuracoes"));

        await viewModel.InitializeAsync();
        viewModel.SelectedExportType = "vendas";
        await viewModel.ExportDataCommand.ExecuteAsync();

        Assert.Equal("access-token", apiClient.ExportAccessToken);
        Assert.Equal("vendas", apiClient.ExportType);
        Assert.Equal("girofy_vendas.csv", fileSaveService.SuggestedFileName);
        Assert.Equal("id;total", Encoding.UTF8.GetString(fileSaveService.Content));
        Assert.Contains("Exportação salva", viewModel.SuccessMessage);
        Assert.Empty(viewModel.ErrorMessage);
    }

    [Fact]
    public async Task ImportProductsAsync_uploads_selected_spreadsheet_for_admin()
    {
        var apiClient = new ExportApiClient();
        var filePickerService = new CapturingFilePickerService
        {
            File = new PickedFile(
                "produtos.csv",
                "text/csv",
                Encoding.UTF8.GetBytes("produto;categoria\nSkol;Cerveja")),
        };
        var sessionContext = new AppSessionContext();
        sessionContext.Set(new AuthSession
        {
            AccessToken = "access-token",
            RefreshToken = "refresh-token",
            User = new UserIdentity
            {
                Id = 10,
                Username = "adegajf",
                Role = "admin",
                RoleLabel = "Admin",
            },
            Company = new CompanyIdentity
            {
                Id = 20,
                Name = "Adega JF",
                Active = true,
                SubscriptionPlan = "Pro",
                SubscriptionValid = true,
            },
        });
        var viewModel = new SettingsViewModel(
            apiClient,
            sessionContext,
            new StubBrowserService(),
            new CapturingFileSaveService(),
            filePickerService,
            new Uri("https://girofy.example/configuracoes"));

        await viewModel.InitializeAsync();
        await viewModel.ImportProductsCommand.ExecuteAsync();

        Assert.Equal("access-token", apiClient.ImportAccessToken);
        Assert.Equal("produtos.csv", apiClient.ImportFileName);
        Assert.Equal("text/csv", apiClient.ImportContentType);
        Assert.Equal("produto;categoria\nSkol;Cerveja", Encoding.UTF8.GetString(apiClient.ImportContent));
        Assert.Contains("Importação concluída", viewModel.SuccessMessage);
        Assert.Empty(viewModel.ErrorMessage);
    }

    [Fact]
    public async Task SaveCompanySettingsAsync_updates_operational_rules_for_admin()
    {
        var apiClient = new ExportApiClient();
        var sessionContext = new AppSessionContext();
        sessionContext.Set(new AuthSession
        {
            AccessToken = "access-token",
            RefreshToken = "refresh-token",
            User = new UserIdentity
            {
                Id = 10,
                Username = "adegajf",
                Role = "admin",
                RoleLabel = "Admin",
            },
            Company = new CompanyIdentity
            {
                Id = 20,
                Name = "Adega JF",
                Active = true,
                SubscriptionPlan = "Pro",
                SubscriptionValid = true,
            },
        });
        var viewModel = new SettingsViewModel(
            apiClient,
            sessionContext,
            new StubBrowserService(),
            new CapturingFileSaveService(),
            new CapturingFilePickerService(),
            new Uri("https://girofy.example/configuracoes"));

        await viewModel.InitializeAsync();
        viewModel.AllowNegativeStock = true;
        viewModel.PixFeeEnabled = true;
        viewModel.PixFeePercent = "1,25";
        viewModel.DebitFeeEnabled = true;
        viewModel.DebitFeePercent = "2.5";
        viewModel.CreditFeeEnabled = false;
        viewModel.CreditFeePercent = "0";

        await viewModel.SaveCompanySettingsCommand.ExecuteAsync();

        Assert.Equal("access-token", apiClient.CompanySettingsAccessToken);
        Assert.NotNull(apiClient.CompanySettingsRequest);
        var request = apiClient.CompanySettingsRequest!;
        Assert.True(request.AllowNegativeStock);
        Assert.True(request.PixFeeEnabled);
        Assert.Equal(1.25m, request.PixFeePercent);
        Assert.True(request.DebitFeeEnabled);
        Assert.Equal(2.5m, request.DebitFeePercent);
        Assert.False(request.CreditFeeEnabled);
        Assert.True(viewModel.AllowNegativeStock);
        Assert.Contains("salvas", viewModel.SuccessMessage);
        Assert.Empty(viewModel.ErrorMessage);
    }

    private sealed class ExportApiClient : IGirofyApiClient
    {
        public string ExportAccessToken { get; private set; } = string.Empty;

        public string ExportType { get; private set; } = string.Empty;

        public string ImportAccessToken { get; private set; } = string.Empty;

        public string ImportFileName { get; private set; } = string.Empty;

        public string ImportContentType { get; private set; } = string.Empty;

        public byte[] ImportContent { get; private set; } = [];

        public string CompanySettingsAccessToken { get; private set; } = string.Empty;

        public UpdateCompanySettingsRequest? CompanySettingsRequest { get; private set; }

        public UpdateNotificationPreferenceRequest? NotificationPreferenceRequest { get; private set; }

        public UpdateEmailAlertSettingsRequest? EmailAlertSettingsRequest { get; private set; }

        public Task<EmailAlertSettingsSnapshot> GetEmailAlertSettingsAsync(
            string accessToken,
            CancellationToken cancellationToken) => Task.FromResult(CreateEmailAlertSnapshot());

        public Task<EmailAlertSettingsSnapshot> UpdateEmailAlertSettingsAsync(
            string accessToken,
            UpdateEmailAlertSettingsRequest settings,
            CancellationToken cancellationToken)
        {
            EmailAlertSettingsRequest = settings;
            return Task.FromResult(new EmailAlertSettingsSnapshot
            {
                CompanyName = "Adega JF",
                SmtpConfigured = true,
                Items = settings.Items.Select(item => new EmailAlertSettingItem
                {
                    AlertType = item.AlertType,
                    Label = item.AlertType,
                    Enabled = item.Enabled,
                    Recipients = item.Recipients.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries),
                }).ToArray(),
            });
        }

        private static EmailAlertSettingsSnapshot CreateEmailAlertSnapshot() => new()
        {
            CompanyName = "Adega JF",
            SmtpConfigured = true,
            Items =
            [
                new EmailAlertSettingItem
                {
                    AlertType = "product_out_of_stock", Label = "Produto esgotado",
                    Description = "Quando chegar a zero.", Enabled = true,
                    Recipients = ["alertas@girofy.test"],
                },
            ],
        };

        public Task<NotificationPreferenceSnapshot> GetNotificationPreferencesAsync(
            string accessToken,
            CancellationToken cancellationToken) => Task.FromResult(new NotificationPreferenceSnapshot
            {
                InAppEnabled = true,
                DesktopEnabled = true,
                MinimumSeverity = "warning",
                CanManageRecipients = true,
                EmailRecipients = "alertas@girofy.test",
                QuietHoursStart = "22:00",
                QuietHoursEnd = "07:00",
                DailyDigestTime = "08:00",
            });

        public Task<NotificationPreferenceSnapshot> UpdateNotificationPreferencesAsync(
            string accessToken,
            UpdateNotificationPreferenceRequest preferences,
            CancellationToken cancellationToken)
        {
            NotificationPreferenceRequest = preferences;
            return Task.FromResult(new NotificationPreferenceSnapshot
            {
                InAppEnabled = preferences.InAppEnabled,
                EmailEnabled = preferences.EmailEnabled,
                DesktopEnabled = preferences.DesktopEnabled,
                MinimumSeverity = preferences.MinimumSeverity,
                EmailRecipients = preferences.EmailRecipients,
                CanManageRecipients = true,
                QuietHoursStart = preferences.QuietHoursStart,
                QuietHoursEnd = preferences.QuietHoursEnd,
                DailyDigestEnabled = preferences.DailyDigestEnabled,
                DailyDigestTime = preferences.DailyDigestTime,
            });
        }

        public Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken) =>
            Task.FromException<HealthStatus>(new NotSupportedException());

        public Task<AuthSession> LoginAsync(
            string identifier,
            string password,
            CancellationToken cancellationToken) =>
            Task.FromException<AuthSession>(new NotSupportedException());

        public Task<AuthSession> RefreshSessionAsync(
            string refreshToken,
            CancellationToken cancellationToken) =>
            Task.FromException<AuthSession>(new NotSupportedException());

        public Task<AuthIdentity> GetCurrentIdentityAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException<AuthIdentity>(new NotSupportedException());

        public Task LogoutAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException(new NotSupportedException());

        public Task<SettingsAccountSnapshot> GetSettingsAccountAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromResult(new SettingsAccountSnapshot
            {
                User = new UserIdentity
                {
                    Id = 10,
                    Username = "adegajf",
                    Role = "admin",
                    RoleLabel = "Admin",
                },
                Company = new CompanyIdentity
                {
                    Id = 20,
                    Name = "Adega JF",
                    Active = true,
                    SubscriptionPlan = "Pro",
                    SubscriptionValid = true,
                },
                Profile = new SettingsProfile
                {
                    Username = "adegajf",
                    RoleLabel = "Admin",
                },
                CompanySettings = new SettingsCompanyOptions
                {
                    AllowNegativeStock = false,
                    BackupFrequency = "manual",
                    PixFeeEnabled = false,
                    PixFeePercent = 0,
                    DebitFeeEnabled = false,
                    DebitFeePercent = 0,
                    CreditFeeEnabled = false,
                    CreditFeePercent = 0,
                },
            });

        public Task<SettingsAccountSnapshot> UpdateCompanySettingsAsync(
            string accessToken,
            UpdateCompanySettingsRequest request,
            CancellationToken cancellationToken)
        {
            CompanySettingsAccessToken = accessToken;
            CompanySettingsRequest = request;
            return Task.FromResult(new SettingsAccountSnapshot
            {
                User = new UserIdentity
                {
                    Id = 10,
                    Username = "adegajf",
                    Role = "admin",
                    RoleLabel = "Admin",
                },
                Company = new CompanyIdentity
                {
                    Id = 20,
                    Name = "Adega JF",
                    Active = true,
                    SubscriptionPlan = "Pro",
                    SubscriptionValid = true,
                },
                Profile = new SettingsProfile
                {
                    Username = "adegajf",
                    RoleLabel = "Admin",
                },
                CompanySettings = new SettingsCompanyOptions
                {
                    AllowNegativeStock = request.AllowNegativeStock,
                    BackupFrequency = "manual",
                    PixFeeEnabled = request.PixFeeEnabled,
                    PixFeePercent = request.PixFeePercent,
                    DebitFeeEnabled = request.DebitFeeEnabled,
                    DebitFeePercent = request.DebitFeePercent,
                    CreditFeeEnabled = request.CreditFeeEnabled,
                    CreditFeePercent = request.CreditFeePercent,
                },
            });
        }

        public Task<SettingsTeamSnapshot> GetSettingsTeamAsync(
            string accessToken,
            string search,
            CancellationToken cancellationToken) =>
            Task.FromResult(new SettingsTeamSnapshot());

        public Task<ExportFile> ExportSettingsDataAsync(
            string accessToken,
            string exportType,
            CancellationToken cancellationToken)
        {
            ExportAccessToken = accessToken;
            ExportType = exportType;
            return Task.FromResult(new ExportFile(
                "girofy_vendas.csv",
                "text/csv",
                Encoding.UTF8.GetBytes("id;total")));
        }

        public Task<ProductImportResult> ImportSettingsProductsAsync(
            string accessToken,
            string fileName,
            string contentType,
            byte[] content,
            CancellationToken cancellationToken)
        {
            ImportAccessToken = accessToken;
            ImportFileName = fileName;
            ImportContentType = contentType;
            ImportContent = content;
            return Task.FromResult(new ProductImportResult
            {
                Created = 1,
                Updated = 2,
                Skipped = 0,
                Movements = 1,
                TotalRows = 3,
            });
        }

        public Task<DashboardSnapshot> GetDashboardSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException<DashboardSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> OpenCashRegisterAsync(
            string accessToken,
            decimal openingAmount,
            CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

        public Task<CashRegisterSnapshot> CloseCashRegisterAsync(
            string accessToken,
            int cashRegisterId,
            decimal closingAmount,
            CancellationToken cancellationToken) =>
            Task.FromException<CashRegisterSnapshot>(new NotSupportedException());

        public Task<CatalogCategoryList> GetCatalogCategoriesAsync(
            string accessToken,
            string search,
            CancellationToken cancellationToken) =>
            Task.FromException<CatalogCategoryList>(new NotSupportedException());

        public Task<CatalogProductList> GetCatalogProductsAsync(
            string accessToken,
            string search,
            int? categoryId,
            string activeFilter,
            string sort,
            int page,
            int perPage,
            CancellationToken cancellationToken) =>
            Task.FromException<CatalogProductList>(new NotSupportedException());

        public Task<SaleReceipt> CreateSaleAsync(
            string accessToken,
            string idempotencyKey,
            IReadOnlyList<SaleLineRequest> items,
            decimal discountAmount,
            IReadOnlyList<SalePaymentRequest> payments,
            CancellationToken cancellationToken) =>
            Task.FromException<SaleReceipt>(new NotSupportedException());
    }

    private sealed class CapturingFileSaveService : IFileSaveService
    {
        public string SuggestedFileName { get; private set; } = string.Empty;

        public byte[] Content { get; private set; } = [];

        public Task<string?> SaveFileAsync(
            string suggestedFileName,
            string filter,
            byte[] content,
            CancellationToken cancellationToken)
        {
            SuggestedFileName = suggestedFileName;
            Content = content;
            return Task.FromResult<string?>("C:\\Exports\\girofy_vendas.csv");
        }
    }

    private sealed class CapturingFilePickerService : IFilePickerService
    {
        public PickedFile? File { get; set; }

        public Task<PickedFile?> PickFileAsync(
            string filter,
            CancellationToken cancellationToken) =>
            Task.FromResult(File);
    }

    private sealed class StubBrowserService : IExternalBrowserService
    {
        public void Open(Uri uri)
        {
        }
    }

    private sealed class StubThemeService : IThemeService
    {
        public bool IsDarkMode { get; private set; } = true;

        public event EventHandler? Changed;

        public Task InitializeAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;

        public Task ToggleAsync(CancellationToken cancellationToken = default)
        {
            IsDarkMode = !IsDarkMode;
            Changed?.Invoke(this, EventArgs.Empty);
            return Task.CompletedTask;
        }

        public void Apply()
        {
        }
    }
}
