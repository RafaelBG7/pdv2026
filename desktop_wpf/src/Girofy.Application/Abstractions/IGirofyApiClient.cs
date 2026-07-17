using Girofy.Application.Models;

namespace Girofy.Application.Abstractions;

public interface IGirofyApiClient
{
    Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken);

    Task<AuthSession> LoginAsync(
        string identifier,
        string password,
        CancellationToken cancellationToken);

    Task<AuthSession> RefreshSessionAsync(
        string refreshToken,
        CancellationToken cancellationToken);

    Task<AuthIdentity> GetCurrentIdentityAsync(
        string accessToken,
        CancellationToken cancellationToken);

    Task LogoutAsync(
        string accessToken,
        CancellationToken cancellationToken);

    Task<DashboardSnapshot> GetDashboardSummaryAsync(
        string accessToken,
        CancellationToken cancellationToken);

    Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(
        string accessToken,
        CancellationToken cancellationToken);

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

    Task<SaleReceipt> CreateSaleAsync(
        string accessToken,
        string idempotencyKey,
        IReadOnlyList<SaleLineRequest> items,
        decimal discountAmount,
        IReadOnlyList<SalePaymentRequest> payments,
        CancellationToken cancellationToken);
}
