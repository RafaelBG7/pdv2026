using Girofy.Application.Models;

namespace Girofy.Application.Abstractions;

public interface IGirofyApiClient
{
    Task<NotificationSnapshot> GetNotificationsAsync(string accessToken, NotificationQuery query, CancellationToken cancellationToken) =>
        Task.FromException<NotificationSnapshot>(new NotSupportedException());
    Task<NotificationUnreadCount> GetNotificationUnreadCountAsync(string accessToken, CancellationToken cancellationToken) =>
        Task.FromException<NotificationUnreadCount>(new NotSupportedException());
    Task<NotificationItem> MarkNotificationReadAsync(string accessToken, int notificationId, CancellationToken cancellationToken) =>
        Task.FromException<NotificationItem>(new NotSupportedException());
    Task MarkAllNotificationsReadAsync(string accessToken, CancellationToken cancellationToken) =>
        Task.FromException(new NotSupportedException());
    Task DismissNotificationAsync(string accessToken, int notificationId, CancellationToken cancellationToken) =>
        Task.FromException(new NotSupportedException());
    Task<NotificationPreferenceSnapshot> GetNotificationPreferencesAsync(string accessToken, CancellationToken cancellationToken) =>
        Task.FromException<NotificationPreferenceSnapshot>(new NotSupportedException());
    Task<NotificationPreferenceSnapshot> UpdateNotificationPreferencesAsync(string accessToken, UpdateNotificationPreferenceRequest preferences, CancellationToken cancellationToken) =>
        Task.FromException<NotificationPreferenceSnapshot>(new NotSupportedException());
    Task<EmailAlertSettingsSnapshot> GetEmailAlertSettingsAsync(string accessToken, CancellationToken cancellationToken) =>
        Task.FromException<EmailAlertSettingsSnapshot>(new NotSupportedException());
    Task<EmailAlertSettingsSnapshot> UpdateEmailAlertSettingsAsync(string accessToken, UpdateEmailAlertSettingsRequest settings, CancellationToken cancellationToken) =>
        Task.FromException<EmailAlertSettingsSnapshot>(new NotSupportedException());
    Task<EmailAlertTestResult> TestEmailAlertSettingsAsync(string accessToken, TestEmailAlertSettingsRequest request, CancellationToken cancellationToken) =>
        Task.FromException<EmailAlertTestResult>(new NotSupportedException());

    Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken);

    Task<AuthSession> LoginAsync(
        string identifier,
        string password,
        CancellationToken cancellationToken);

    Task<AuthSession> ActivateSubscriptionAsync(
        string identifier,
        string password,
        string activationKey,
        CancellationToken cancellationToken) =>
        Task.FromException<AuthSession>(new NotSupportedException());

    Task<AuthSession> RefreshSessionAsync(
        string refreshToken,
        CancellationToken cancellationToken);

    Task<AuthIdentity> GetCurrentIdentityAsync(
        string accessToken,
        CancellationToken cancellationToken);

    Task LogoutAsync(
        string accessToken,
        CancellationToken cancellationToken);

    Task<SettingsAccountSnapshot> GetSettingsAccountAsync(
        string accessToken,
        CancellationToken cancellationToken) =>
        Task.FromException<SettingsAccountSnapshot>(new NotSupportedException());

    Task<SettingsAccountSnapshot> UpdateSettingsProfileAsync(
        string accessToken,
        UpdateProfileRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<SettingsAccountSnapshot>(new NotSupportedException());

    Task<ChangePasswordResult> ChangeSettingsPasswordAsync(
        string accessToken,
        ChangePasswordRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<ChangePasswordResult>(new NotSupportedException());

    Task<SettingsAccountSnapshot> UpdateBackupSettingsAsync(
        string accessToken,
        UpdateBackupSettingsRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<SettingsAccountSnapshot>(new NotSupportedException());

    Task<SettingsAccountSnapshot> UpdateCompanySettingsAsync(
        string accessToken,
        UpdateCompanySettingsRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<SettingsAccountSnapshot>(new NotSupportedException());

    Task<ManualBackupResult> RunManualBackupAsync(
        string accessToken,
        CancellationToken cancellationToken) =>
        Task.FromException<ManualBackupResult>(new NotSupportedException());

    Task<ExportFile> ExportSettingsDataAsync(
        string accessToken,
        string exportType,
        CancellationToken cancellationToken) =>
        Task.FromException<ExportFile>(new NotSupportedException());

    Task<ProductImportResult> ImportSettingsProductsAsync(
        string accessToken,
        string fileName,
        string contentType,
        byte[] content,
        CancellationToken cancellationToken) =>
        Task.FromException<ProductImportResult>(new NotSupportedException());

    Task<SettingsTeamSnapshot> GetSettingsTeamAsync(
        string accessToken,
        string search,
        CancellationToken cancellationToken) =>
        Task.FromException<SettingsTeamSnapshot>(new NotSupportedException());

    Task<SettingsEmployee> CreateSettingsEmployeeAsync(
        string accessToken,
        CreateEmployeeRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<SettingsEmployee>(new NotSupportedException());

    Task<SettingsEmployee> UpdateSettingsEmployeeAsync(
        string accessToken,
        int employeeId,
        UpdateEmployeeRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<SettingsEmployee>(new NotSupportedException());

    Task<DashboardSnapshot> GetDashboardSummaryAsync(
        string accessToken,
        CancellationToken cancellationToken);

    Task<SalesHistorySnapshot> GetTodaySalesHistoryAsync(
        string accessToken,
        int page,
        int perPage,
        CancellationToken cancellationToken) =>
        Task.FromException<SalesHistorySnapshot>(new NotSupportedException());

    Task<SaleReceipt> GetSaleDetailAsync(
        string accessToken,
        int saleId,
        CancellationToken cancellationToken) =>
        Task.FromException<SaleReceipt>(new NotSupportedException());

    Task<SaleReceipt> CancelSaleAsync(
        string accessToken,
        int saleId,
        string reason,
        CancellationToken cancellationToken) =>
        Task.FromException<SaleReceipt>(new NotSupportedException());

    Task<ReportsSnapshot> GetReportsSummaryAsync(
        string accessToken,
        ReportsQuery query,
        CancellationToken cancellationToken) =>
        Task.FromException<ReportsSnapshot>(new NotSupportedException());

    Task<ProductReportSnapshot> GetProductReportsAsync(
        string accessToken,
        ProductReportsQuery query,
        CancellationToken cancellationToken) =>
        Task.FromException<ProductReportSnapshot>(new NotSupportedException());

    Task<AuditLogSnapshot> GetAuditLogsAsync(
        string accessToken,
        AuditLogQuery query,
        CancellationToken cancellationToken) =>
        Task.FromException<AuditLogSnapshot>(new NotSupportedException());

    Task<PayablesSnapshot> GetPayablesAsync(
        string accessToken,
        PayablesQuery query,
        CancellationToken cancellationToken) =>
        Task.FromException<PayablesSnapshot>(new NotSupportedException());

    Task<IReadOnlyList<string>> GetPayableCategoriesAsync(
        string accessToken,
        CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<string>>([]);

    Task<PayableRecord> CreatePayableAsync(
        string accessToken,
        PayableMutationRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<PayableRecord>(new NotSupportedException());

    Task<PayableRecord> PayPayableAsync(
        string accessToken,
        int payableId,
        CancellationToken cancellationToken) =>
        Task.FromException<PayableRecord>(new NotSupportedException());

    Task<PayableRecord> ReopenPayableAsync(
        string accessToken,
        int payableId,
        CancellationToken cancellationToken) =>
        Task.FromException<PayableRecord>(new NotSupportedException());

    Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(
        string accessToken,
        CancellationToken cancellationToken);

    Task<CashRegisterDetailSnapshot> GetCashRegisterDetailAsync(
        string accessToken,
        int cashRegisterId,
        CancellationToken cancellationToken) =>
        Task.FromException<CashRegisterDetailSnapshot>(new NotSupportedException());

    Task<CashRegisterSnapshot> OpenCashRegisterAsync(
        string accessToken,
        decimal openingAmount,
        CancellationToken cancellationToken);

    Task<CashRegisterSnapshot> CloseCashRegisterAsync(
        string accessToken,
        int cashRegisterId,
        decimal closingAmount,
        CancellationToken cancellationToken);

    Task<CatalogCategoryList> GetCatalogCategoriesAsync(
        string accessToken,
        string search,
        CancellationToken cancellationToken);

    Task<CatalogCategory> CreateCatalogCategoryAsync(
        string accessToken,
        CatalogCategoryMutationRequest category,
        CancellationToken cancellationToken) =>
        Task.FromException<CatalogCategory>(new NotSupportedException());

    Task<CatalogCategory> UpdateCatalogCategoryAsync(
        string accessToken,
        int categoryId,
        CatalogCategoryMutationRequest category,
        CancellationToken cancellationToken) =>
        Task.FromException<CatalogCategory>(new NotSupportedException());

    Task DeleteCatalogCategoryAsync(
        string accessToken,
        int categoryId,
        CancellationToken cancellationToken) =>
        Task.FromException(new NotSupportedException());

    Task<CatalogProductList> GetCatalogProductsAsync(
        string accessToken,
        string search,
        int? categoryId,
        string activeFilter,
        string sort,
        int page,
        int perPage,
        CancellationToken cancellationToken);

    Task<CatalogProductList> GetCatalogProductsAsync(
        string accessToken,
        string search,
        int? categoryId,
        string activeFilter,
        string stockFilter,
        decimal? minPrice,
        decimal? maxPrice,
        string sort,
        int page,
        int perPage,
        CancellationToken cancellationToken) =>
        GetCatalogProductsAsync(
            accessToken,
            search,
            categoryId,
            activeFilter,
            sort,
            page,
            perPage,
            cancellationToken);

    Task<CatalogProduct?> GetCatalogProductByBarcodeAsync(
        string accessToken,
        string barcode,
        CancellationToken cancellationToken) =>
        Task.FromException<CatalogProduct?>(new NotSupportedException());

    Task<CatalogProduct> CreateCatalogProductAsync(
        string accessToken,
        CatalogProductMutationRequest product,
        CancellationToken cancellationToken) =>
        Task.FromException<CatalogProduct>(new NotSupportedException());

    Task<CatalogProduct> UpdateCatalogProductAsync(
        string accessToken,
        int productId,
        CatalogProductMutationRequest product,
        CancellationToken cancellationToken) =>
        Task.FromException<CatalogProduct>(new NotSupportedException());

    Task DeleteCatalogProductAsync(
        string accessToken,
        int productId,
        CancellationToken cancellationToken) =>
        Task.FromException(new NotSupportedException());

    Task<StockMovementList> GetStockMovementsAsync(
        string accessToken,
        StockMovementQuery query,
        CancellationToken cancellationToken) =>
        Task.FromException<StockMovementList>(new NotSupportedException());

    Task<StockMovementRecord> CreateStockEntryAsync(
        string accessToken,
        StockEntryRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<StockMovementRecord>(new NotSupportedException());

    Task<StockAdjustmentResult> CreateStockAdjustmentAsync(
        string accessToken,
        StockAdjustmentRequest request,
        CancellationToken cancellationToken) =>
        Task.FromException<StockAdjustmentResult>(new NotSupportedException());

    Task<SaleReceipt> CreateSaleAsync(
        string accessToken,
        string idempotencyKey,
        IReadOnlyList<SaleLineRequest> items,
        decimal discountAmount,
        IReadOnlyList<SalePaymentRequest> payments,
        CancellationToken cancellationToken);
}
