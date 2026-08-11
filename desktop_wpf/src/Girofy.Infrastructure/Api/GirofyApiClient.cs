using System.Net.Http.Json;
using System.Net.Http.Headers;
using System.Text.Json;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Microsoft.Extensions.Logging;

namespace Girofy.Infrastructure.Api;

public sealed class GirofyApiClient(
    HttpClient httpClient,
    ILogger<GirofyApiClient> logger) : IGirofyApiClient
{
    public async Task<NotificationSnapshot> GetNotificationsAsync(string accessToken, NotificationQuery query, CancellationToken cancellationToken)
    {
        var parameters = new List<string> { $"page={query.Page}", $"page_size={query.PageSize}" };
        if (!string.IsNullOrWhiteSpace(query.Category)) parameters.Add($"category={Uri.EscapeDataString(query.Category)}");
        if (!string.IsNullOrWhiteSpace(query.Severity)) parameters.Add($"severity={Uri.EscapeDataString(query.Severity)}");
        if (!string.IsNullOrWhiteSpace(query.ReadFilter)) parameters.Add($"is_read={Uri.EscapeDataString(query.ReadFilter)}");
        if (!string.IsNullOrWhiteSpace(query.Search)) parameters.Add($"search={Uri.EscapeDataString(query.Search)}");
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, $"api/v1/notifications?{string.Join("&", parameters)}", accessToken);
        using var response = await httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        return await ReadEnvelopeAsync<NotificationSnapshot>(response, cancellationToken);
    }

    public async Task<NotificationUnreadCount> GetNotificationUnreadCountAsync(string accessToken, CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, "api/v1/notifications/unread-count", accessToken);
        using var response = await httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        return await ReadEnvelopeAsync<NotificationUnreadCount>(response, cancellationToken);
    }

    public async Task<NotificationItem> MarkNotificationReadAsync(string accessToken, int notificationId, CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Put, $"api/v1/notifications/{notificationId}/read", accessToken);
        request.Content = JsonContent.Create(new { });
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<NotificationItem>(response, cancellationToken);
    }

    public async Task MarkAllNotificationsReadAsync(string accessToken, CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Put, "api/v1/notifications/read-all", accessToken);
        request.Content = JsonContent.Create(new { });
        using var response = await httpClient.SendAsync(request, cancellationToken);
        await ReadEnvelopeAsync<JsonElement>(response, cancellationToken);
    }

    public async Task DismissNotificationAsync(string accessToken, int notificationId, CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Put, $"api/v1/notifications/{notificationId}/dismiss", accessToken);
        request.Content = JsonContent.Create(new { });
        using var response = await httpClient.SendAsync(request, cancellationToken);
        await ReadEnvelopeAsync<JsonElement>(response, cancellationToken);
    }

    public async Task<NotificationPreferenceSnapshot> GetNotificationPreferencesAsync(string accessToken, CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, "api/v1/notifications/preferences", accessToken);
        using var response = await httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        return await ReadEnvelopeAsync<NotificationPreferenceSnapshot>(response, cancellationToken);
    }

    public async Task<NotificationPreferenceSnapshot> UpdateNotificationPreferencesAsync(string accessToken, UpdateNotificationPreferenceRequest preferences, CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Put, "api/v1/notifications/preferences", accessToken);
        request.Content = JsonContent.Create(preferences);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<NotificationPreferenceSnapshot>(response, cancellationToken);
    }

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

    public async Task<AuthSession> ActivateSubscriptionAsync(
        string identifier,
        string password,
        string activationKey,
        CancellationToken cancellationToken)
    {
        using var response = await httpClient.PostAsJsonAsync(
            "api/v1/subscription/activate",
            new SubscriptionActivationRequest(identifier, password, activationKey),
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

    public async Task<SettingsAccountSnapshot> GetSettingsAccountAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, "api/v1/settings/account", accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<SettingsAccountSnapshot>(response, cancellationToken);
    }

    public async Task<SettingsAccountSnapshot> UpdateSettingsProfileAsync(
        string accessToken,
        UpdateProfileRequest profile,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Put, "api/v1/settings/profile", accessToken);
        request.Content = JsonContent.Create(profile);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<SettingsAccountSnapshot>(response, cancellationToken);
    }

    public async Task<ChangePasswordResult> ChangeSettingsPasswordAsync(
        string accessToken,
        ChangePasswordRequest password,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Put, "api/v1/settings/password", accessToken);
        request.Content = JsonContent.Create(password);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<ChangePasswordResult>(response, cancellationToken);
    }

    public async Task<SettingsAccountSnapshot> UpdateBackupSettingsAsync(
        string accessToken,
        UpdateBackupSettingsRequest backup,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Put, "api/v1/settings/backup", accessToken);
        request.Content = JsonContent.Create(backup);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<SettingsAccountSnapshot>(response, cancellationToken);
    }

    public async Task<SettingsAccountSnapshot> UpdateCompanySettingsAsync(
        string accessToken,
        UpdateCompanySettingsRequest settings,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Put, "api/v1/settings/company", accessToken);
        request.Content = JsonContent.Create(settings);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<SettingsAccountSnapshot>(response, cancellationToken);
    }

    public async Task<ManualBackupResult> RunManualBackupAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/settings/backup/run", accessToken);
        request.Content = JsonContent.Create(new { });
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<ManualBackupResult>(response, cancellationToken);
    }

    public async Task<ExportFile> ExportSettingsDataAsync(
        string accessToken,
        string exportType,
        CancellationToken cancellationToken)
    {
        var safeExportType = Uri.EscapeDataString(exportType.Trim().ToLowerInvariant());
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, $"api/v1/settings/export/{safeExportType}", accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            await ReadEnvelopeAsync<JsonElement>(response, cancellationToken);
        }

        var content = await response.Content.ReadAsByteArrayAsync(cancellationToken);
        var contentType = response.Content.Headers.ContentType?.ToString() ?? "text/csv";
        var fileName = response.Content.Headers.ContentDisposition?.FileNameStar
            ?? response.Content.Headers.ContentDisposition?.FileName
            ?? $"girofy_{safeExportType}.csv";

        return new ExportFile(fileName.Trim('"'), contentType, content);
    }

    public async Task<ProductImportResult> ImportSettingsProductsAsync(
        string accessToken,
        string fileName,
        string contentType,
        byte[] content,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Post,
            "api/v1/settings/import/products",
            accessToken);
        using var form = new MultipartFormDataContent();
        using var fileContent = new ByteArrayContent(content);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue(
            string.IsNullOrWhiteSpace(contentType) ? "application/octet-stream" : contentType);
        form.Add(fileContent, "spreadsheet", fileName);
        request.Content = form;

        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<ProductImportResult>(response, cancellationToken);
    }

    public async Task<SettingsTeamSnapshot> GetSettingsTeamAsync(
        string accessToken,
        string search,
        CancellationToken cancellationToken)
    {
        var path = "api/v1/settings/team";
        if (!string.IsNullOrWhiteSpace(search))
        {
            path += $"?search={Uri.EscapeDataString(search.Trim())}";
        }

        using var request = CreateAuthenticatedRequest(HttpMethod.Get, path, accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<SettingsTeamSnapshot>(response, cancellationToken);
    }

    public async Task<SettingsEmployee> CreateSettingsEmployeeAsync(
        string accessToken,
        CreateEmployeeRequest employee,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/settings/team", accessToken);
        request.Content = JsonContent.Create(employee);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<SettingsEmployee>(response, cancellationToken);
    }

    public async Task<SettingsEmployee> UpdateSettingsEmployeeAsync(
        string accessToken,
        int employeeId,
        UpdateEmployeeRequest employee,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Put,
            $"api/v1/settings/team/{employeeId}",
            accessToken);
        request.Content = JsonContent.Create(employee);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<SettingsEmployee>(response, cancellationToken);
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

    public async Task<SalesHistorySnapshot> GetTodaySalesHistoryAsync(
        string accessToken,
        int page,
        int perPage,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            $"api/v1/sales/today?page={page}&per_page={perPage}",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<SalesHistorySnapshot>(response, cancellationToken);
    }

    public async Task<SaleReceipt> GetSaleDetailAsync(
        string accessToken,
        int saleId,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            $"api/v1/sales/{saleId}",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<SaleReceipt>(response, cancellationToken);
    }

    public async Task<SaleReceipt> CancelSaleAsync(
        string accessToken,
        int saleId,
        string reason,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Post,
            $"api/v1/sales/{saleId}/cancel",
            accessToken);
        request.Content = JsonContent.Create(new CancelSaleRequest(reason));
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<SaleReceipt>(response, cancellationToken);
    }

    public async Task<ReportsSnapshot> GetReportsSummaryAsync(
        string accessToken,
        ReportsQuery query,
        CancellationToken cancellationToken)
    {
        var parameters = new List<string>
        {
            $"period={Uri.EscapeDataString(query.Period)}",
            $"chart_metric={Uri.EscapeDataString(query.ChartMetric)}",
        };
        if (!string.IsNullOrWhiteSpace(query.StartDate))
        {
            parameters.Add($"start_date={Uri.EscapeDataString(query.StartDate.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.EndDate))
        {
            parameters.Add($"end_date={Uri.EscapeDataString(query.EndDate.Trim())}");
        }

        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            $"api/v1/reports/summary?{string.Join('&', parameters)}",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<ReportsSnapshot>(response, cancellationToken);
    }

    public async Task<ProductReportSnapshot> GetProductReportsAsync(
        string accessToken,
        ProductReportsQuery query,
        CancellationToken cancellationToken)
    {
        var parameters = new List<string>
        {
            $"period={Uri.EscapeDataString(query.Period)}",
            $"sort={Uri.EscapeDataString(query.Sort)}",
            $"page={Math.Max(1, query.Page)}",
            $"per_page={Math.Clamp(query.PerPage, 1, 100)}",
        };
        if (!string.IsNullOrWhiteSpace(query.StartDate))
        {
            parameters.Add($"start_date={Uri.EscapeDataString(query.StartDate.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.EndDate))
        {
            parameters.Add($"end_date={Uri.EscapeDataString(query.EndDate.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.Search))
        {
            parameters.Add($"q={Uri.EscapeDataString(query.Search.Trim())}");
        }

        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            $"api/v1/reports/products?{string.Join('&', parameters)}",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<ProductReportSnapshot>(response, cancellationToken);
    }

    public async Task<AuditLogSnapshot> GetAuditLogsAsync(
        string accessToken,
        AuditLogQuery query,
        CancellationToken cancellationToken)
    {
        var parameters = new List<string>
        {
            $"page={Math.Max(1, query.Page)}",
            $"per_page={Math.Clamp(query.PerPage, 1, 100)}",
        };
        if (!string.IsNullOrWhiteSpace(query.Search))
        {
            parameters.Add($"q={Uri.EscapeDataString(query.Search.Trim())}");
        }
        if (query.UserId is > 0)
        {
            parameters.Add($"user_id={query.UserId.Value}");
        }
        if (!string.IsNullOrWhiteSpace(query.Action) &&
            !string.Equals(query.Action, "all", StringComparison.OrdinalIgnoreCase))
        {
            parameters.Add($"action={Uri.EscapeDataString(query.Action.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.EntityType) &&
            !string.Equals(query.EntityType, "all", StringComparison.OrdinalIgnoreCase))
        {
            parameters.Add($"entity_type={Uri.EscapeDataString(query.EntityType.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.HttpMethod) &&
            !string.Equals(query.HttpMethod, "all", StringComparison.OrdinalIgnoreCase))
        {
            parameters.Add($"http_method={Uri.EscapeDataString(query.HttpMethod.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.StartDate))
        {
            parameters.Add($"start_date={Uri.EscapeDataString(query.StartDate.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.EndDate))
        {
            parameters.Add($"end_date={Uri.EscapeDataString(query.EndDate.Trim())}");
        }

        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            $"api/v1/audit/logs?{string.Join('&', parameters)}",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<AuditLogSnapshot>(response, cancellationToken);
    }

    public async Task<PayablesSnapshot> GetPayablesAsync(
        string accessToken,
        PayablesQuery query,
        CancellationToken cancellationToken)
    {
        var parameters = new List<string>
        {
            $"status={Uri.EscapeDataString(query.Status)}",
        };
        if (!string.IsNullOrWhiteSpace(query.Search))
        {
            parameters.Add($"q={Uri.EscapeDataString(query.Search.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.Category) &&
            !string.Equals(query.Category, "all", StringComparison.OrdinalIgnoreCase))
        {
            parameters.Add($"category={Uri.EscapeDataString(query.Category.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.StartDate))
        {
            parameters.Add($"start_date={Uri.EscapeDataString(query.StartDate.Trim())}");
        }
        if (!string.IsNullOrWhiteSpace(query.EndDate))
        {
            parameters.Add($"end_date={Uri.EscapeDataString(query.EndDate.Trim())}");
        }

        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            $"api/v1/payables?{string.Join('&', parameters)}",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<PayablesSnapshot>(response, cancellationToken);
    }

    public async Task<PayableRecord> CreatePayableAsync(
        string accessToken,
        PayableMutationRequest payable,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/payables", accessToken);
        request.Content = JsonContent.Create(payable);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<PayableRecord>(response, cancellationToken);
    }

    public async Task<PayableRecord> PayPayableAsync(
        string accessToken,
        int payableId,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Post,
            $"api/v1/payables/{payableId}/pay",
            accessToken);
        request.Content = JsonContent.Create(new { });
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<PayableRecord>(response, cancellationToken);
    }

    public async Task<PayableRecord> ReopenPayableAsync(
        string accessToken,
        int payableId,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Post,
            $"api/v1/payables/{payableId}/reopen",
            accessToken);
        request.Content = JsonContent.Create(new { });
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<PayableRecord>(response, cancellationToken);
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

    public async Task<CashRegisterDetailSnapshot> GetCashRegisterDetailAsync(
        string accessToken,
        int cashRegisterId,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Get,
            $"api/v1/cash-registers/{cashRegisterId}",
            accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<CashRegisterDetailSnapshot>(response, cancellationToken);
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

    public async Task<CatalogCategory> CreateCatalogCategoryAsync(
        string accessToken,
        CatalogCategoryMutationRequest category,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/catalog/categories", accessToken);
        request.Content = JsonContent.Create(category);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<CatalogCategory>(response, cancellationToken);
    }

    public async Task<CatalogCategory> UpdateCatalogCategoryAsync(
        string accessToken,
        int categoryId,
        CatalogCategoryMutationRequest category,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Put,
            $"api/v1/catalog/categories/{categoryId}",
            accessToken);
        request.Content = JsonContent.Create(category);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<CatalogCategory>(response, cancellationToken);
    }

    public async Task DeleteCatalogCategoryAsync(
        string accessToken,
        int categoryId,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(
            HttpMethod.Delete,
            $"api/v1/catalog/categories/{categoryId}",
            accessToken);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        await ReadEnvelopeAsync<JsonElement>(response, cancellationToken);
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

    public async Task<StockMovementList> GetStockMovementsAsync(
        string accessToken,
        StockMovementQuery query,
        CancellationToken cancellationToken)
    {
        var parameters = new List<string>
        {
            $"page={Math.Max(1, query.Page)}",
            $"per_page={Math.Clamp(query.PerPage, 1, 100)}",
            $"movement_type={Uri.EscapeDataString(query.MovementType)}",
            $"source_type={Uri.EscapeDataString(query.SourceType)}",
        };
        if (!string.IsNullOrWhiteSpace(query.Search))
        {
            parameters.Add($"q={Uri.EscapeDataString(query.Search.Trim())}");
        }
        if (query.CategoryId is > 0)
        {
            parameters.Add($"category_id={query.CategoryId.Value}");
        }

        var path = $"api/v1/stock/movements?{string.Join('&', parameters)}";
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, path, accessToken);
        using var response = await httpClient.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        return await ReadEnvelopeAsync<StockMovementList>(response, cancellationToken);
    }

    public async Task<StockMovementRecord> CreateStockEntryAsync(
        string accessToken,
        StockEntryRequest stockEntry,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/stock/entries", accessToken);
        request.Content = JsonContent.Create(stockEntry);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<StockMovementRecord>(response, cancellationToken);
    }

    public async Task<StockAdjustmentResult> CreateStockAdjustmentAsync(
        string accessToken,
        StockAdjustmentRequest adjustment,
        CancellationToken cancellationToken)
    {
        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "api/v1/stock/adjustments", accessToken);
        request.Content = JsonContent.Create(adjustment);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        return await ReadEnvelopeAsync<StockAdjustmentResult>(response, cancellationToken);
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

    private sealed record CancelSaleRequest(
        [property: global::System.Text.Json.Serialization.JsonPropertyName("reason")] string Reason);

    private sealed class LogoutResult
    {
        [global::System.Text.Json.Serialization.JsonPropertyName("logged_out")]
        public bool LoggedOut { get; init; }
    }
}
