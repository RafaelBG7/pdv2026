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

    Task<CatalogProductList> GetCatalogProductsAsync(
        string accessToken,
        string search,
        int? categoryId,
        string activeFilter,
        string sort,
        int page,
        int perPage,
        CancellationToken cancellationToken);
}
