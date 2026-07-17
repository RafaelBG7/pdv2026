using System.Net.Http.Json;
using System.Net.Http.Headers;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Microsoft.Extensions.Logging;

namespace Girofy.Infrastructure.Api;

public sealed class GirofyApiClient(
    HttpClient httpClient,
    ILogger<GirofyApiClient> logger) : IGirofyApiClient
{
    public async Task<HealthStatus> GetHealthAsync(CancellationToken cancellationToken)
    {
        using var response = await httpClient.GetAsync(
            "api/v1/health",
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            logger.LogWarning("API health check returned HTTP {StatusCode}.", (int)response.StatusCode);
            throw new HttpRequestException("O servidor Girofy respondeu com erro.", null, response.StatusCode);
        }

        var payload = await response.Content.ReadFromJsonAsync<ApiEnvelope<HealthStatus>>(
            cancellationToken: cancellationToken);

        if (payload is not { Success: true, Data: not null } ||
            !string.Equals(payload.Data.Status, "ok", StringComparison.OrdinalIgnoreCase))
        {
            logger.LogWarning("API health check returned an invalid response envelope.");
            throw new InvalidOperationException("A resposta da API Girofy é inválida.");
        }

        return payload.Data;
    }

    public async Task<AuthSession> LoginAsync(
        string identifier,
        string password,
        CancellationToken cancellationToken)
    {
        using var response = await httpClient.PostAsJsonAsync(
            "api/v1/auth/login",
            new LoginRequest(identifier, password),
            cancellationToken);
        return await ReadEnvelopeAsync<AuthSession>(response, cancellationToken);
    }

    public async Task<AuthSession> RefreshSessionAsync(
        string refreshToken,
        CancellationToken cancellationToken)
    {
        using var response = await httpClient.PostAsJsonAsync(
            "api/v1/auth/refresh",
            new RefreshRequest(refreshToken),
            cancellationToken);
        return await ReadEnvelopeAsync<AuthSession>(response, cancellationToken);
    }

    public async Task<AuthIdentity> GetCurrentIdentityAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, "api/v1/auth/me", accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<AuthIdentity>(response, cancellationToken);
    }

    public async Task LogoutAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/auth/logout", accessToken);
        request.Content = JsonContent.Create(new { });
        using var response = await httpClient.SendAsync(request, cancellationToken);
        await ReadEnvelopeAsync<LogoutResult>(response, cancellationToken);
    }

    public async Task<DashboardSnapshot> GetDashboardSummaryAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            "api/v1/dashboard/summary",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<DashboardSnapshot>(response, cancellationToken);
    }

    public async Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            "api/v1/cash-registers/summary",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<CashRegisterSnapshot>(response, cancellationToken);
    }

    public async Task<CashRegisterSnapshot> OpenCashRegisterAsync(
        string accessToken,
        decimal openingAmount,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Post,
            "api/v1/cash-registers/open",
            accessToken);
        request.Content = JsonContent.Create(new OpenCashRegisterRequest(openingAmount));
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<CashRegisterSnapshot>(response, cancellationToken);
    }

    public async Task<CashRegisterSnapshot> CloseCashRegisterAsync(
        string accessToken,
        int cashRegisterId,
        decimal closingAmount,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Post,
            "api/v1/cash-registers/close",
            accessToken);
        request.Content = JsonContent.Create(new CloseCashRegisterRequest(
            cashRegisterId,
            closingAmount));
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<CashRegisterSnapshot>(response, cancellationToken);
    }

    public async Task<CatalogCategoryList> GetCatalogCategoriesAsync(
        string accessToken,
        string search,
        CancellationToken cancellationToken)
    {
        var path = "api/v1/catalog/categories";
        if (!string.IsNullOrWhiteSpace(search))
        {
            path += $"?q={Uri.EscapeDataString(search.Trim())}";
        }

        using var request = CreateAuthenticatedRequest(HttpMethod.Get, path, accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<CatalogCategoryList>(response, cancellationToken);
    }

    public async Task<CatalogProductList> GetCatalogProductsAsync(
        string accessToken,
        string search,
        int? categoryId,
        string activeFilter,
        string sort,
        int page,
        int perPage,
        CancellationToken cancellationToken)
    {
        var query = new List<string>
        {
            $"page={Math.Max(1, page)}",
            $"per_page={Math.Clamp(perPage, 1, 100)}",
            $"active={Uri.EscapeDataString(activeFilter)}",
            $"sort={Uri.EscapeDataString(sort)}",
        };
        if (!string.IsNullOrWhiteSpace(search))
        {
            query.Add($"q={Uri.EscapeDataString(search.Trim())}");
        }
        if (categoryId is > 0)
        {
            query.Add($"category_id={categoryId.Value}");
        }

        var path = $"api/v1/catalog/products?{string.Join('&', query)}";
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, path, accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<CatalogProductList>(response, cancellationToken);
    }

    public async Task<CatalogProduct> CreateCatalogProductAsync(
        string accessToken,
        CatalogProductMutationRequest product,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/catalog/products", accessToken);
        request.Content = JsonContent.Create(product);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<CatalogProduct>(response, cancellationToken);
    }

    public async Task<CatalogProduct> UpdateCatalogProductAsync(
        string accessToken,
        int productId,
        CatalogProductMutationRequest product,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Put,
            $"api/v1/catalog/products/{productId}",
            accessToken);
        request.Content = JsonContent.Create(product);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<CatalogProduct>(response, cancellationToken);
    }

    public async Task<SaleReceipt> CreateSaleAsync(
        string accessToken,
        string idempotencyKey,
        IReadOnlyList<SaleLineRequest> items,
        decimal discountAmount,
        IReadOnlyList<SalePaymentRequest> payments,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/sales", accessToken);
        request.Headers.Add("Idempotency-Key", idempotencyKey);
        request.Content = JsonContent.Create(new CreateSaleRequest(
            idempotencyKey,
            items,
            discountAmount,
            payments));
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<SaleReceipt>(response, cancellationToken);
    }

    private static HttpRequestMessage CreateAuthenticatedRequest(
        HttpMethod method,
        string path,
        string accessToken)
    {
        var request = new HttpRequestMessage(method, path);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        return request;
    }

    private async Task<T> ReadEnvelopeAsync<T>(
        HttpResponseMessage response,
        CancellationToken cancellationToken)
    {
        ApiEnvelope<T>? payload = null;
        try
        {
            payload = await response.Content.ReadFromJsonAsync<ApiEnvelope<T>>(
                cancellationToken: cancellationToken);
        }
        catch (global::System.Text.Json.JsonException exception)
        {
            logger.LogWarning(
                exception,
                "API returned invalid JSON with HTTP {StatusCode}.",
                (int)response.StatusCode);
        }

        if (response.IsSuccessStatusCode && payload is { Success: true, Data: not null })
        {
            return payload.Data;
        }

        var firstError = payload?.Errors.FirstOrDefault();
        var message = payload?.Message
            ?? firstError?.Message
            ?? "O servidor Girofy não conseguiu concluir a solicitação.";
        var code = firstError?.Code ?? "api_request_failed";
        logger.LogWarning(
            "API request failed with HTTP {StatusCode} and code {ErrorCode}.",
            (int)response.StatusCode,
            code);
        throw new GirofyApiException(message, code, (int)response.StatusCode);
    }

    private sealed record LoginRequest(
        [property: global::System.Text.Json.Serialization.JsonPropertyName("identifier")] string Identifier,
        [property: global::System.Text.Json.Serialization.JsonPropertyName("password")] string Password);

    private sealed record RefreshRequest(
        [property: global::System.Text.Json.Serialization.JsonPropertyName("refresh_token")] string RefreshToken);

    private sealed record OpenCashRegisterRequest(
        [property: global::System.Text.Json.Serialization.JsonPropertyName("opening_amount")] decimal OpeningAmount);

    private sealed record CloseCashRegisterRequest(
        [property: global::System.Text.Json.Serialization.JsonPropertyName("cash_register_id")] int CashRegisterId,
        [property: global::System.Text.Json.Serialization.JsonPropertyName("closing_amount")] decimal ClosingAmount);

    private sealed record CreateSaleRequest(
        [property: global::System.Text.Json.Serialization.JsonPropertyName("idempotency_key")] string IdempotencyKey,
        [property: global::System.Text.Json.Serialization.JsonPropertyName("items")] IReadOnlyList<SaleLineRequest> Items,
        [property: global::System.Text.Json.Serialization.JsonPropertyName("discount_amount")] decimal DiscountAmount,
        [property: global::System.Text.Json.Serialization.JsonPropertyName("payments")] IReadOnlyList<SalePaymentRequest> Payments);

    private sealed class LogoutResult
    {
        [global::System.Text.Json.Serialization.JsonPropertyName("logged_out")]
        public bool LoggedOut { get; init; }
    }
}
