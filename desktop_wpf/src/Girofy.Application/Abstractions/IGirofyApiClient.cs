using Girofy.Application.Models;

namespace Girofy.Application.Abstractions;

public interface IGirofyApiClient
{
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
