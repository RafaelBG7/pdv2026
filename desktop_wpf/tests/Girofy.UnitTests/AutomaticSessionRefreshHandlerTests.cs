using System.Collections.Concurrent;
using System.Net;
using System.Text;
using System.Text.Json;
using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Infrastructure.Api;
using Microsoft.Extensions.Logging.Abstractions;

namespace Girofy.UnitTests;

public sealed class AutomaticSessionRefreshHandlerTests
{
    [Fact]
    public async Task Valid_access_token_does_not_refresh()
    {
        var fixture = CreateFixture(_ => JsonResponse(HttpStatusCode.OK, new { ok = true }));

        using var response = await fixture.Client.SendAsync(AuthenticatedGet());

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(0, fixture.RefreshHandler.CallCount);
        Assert.Equal(1, fixture.ApiHandler.CallCount);
    }

    [Fact]
    public async Task Unauthorized_request_refreshes_and_retries_once()
    {
        var fixture = CreateFixture(request =>
            request.Headers.Authorization?.Parameter == "access-new"
                ? JsonResponse(HttpStatusCode.OK, new { ok = true })
                : JsonResponse(HttpStatusCode.Unauthorized, new { success = false }));

        using var response = await fixture.Client.SendAsync(AuthenticatedGet());

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(1, fixture.RefreshHandler.CallCount);
        Assert.Equal(2, fixture.ApiHandler.CallCount);
        Assert.Equal("refresh-new", fixture.Store.SavedSession?.RefreshToken);
        Assert.Equal("access-new", fixture.Context.Current?.AccessToken);
    }

    [Fact]
    public async Task Rejected_refresh_clears_session_without_looping()
    {
        var fixture = CreateFixture(
            _ => JsonResponse(HttpStatusCode.Unauthorized, new { success = false }),
            refreshResponse: _ => JsonResponse(HttpStatusCode.Unauthorized, new { success = false }));

        using var response = await fixture.Client.SendAsync(AuthenticatedGet());

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(1, fixture.RefreshHandler.CallCount);
        Assert.Equal(1, fixture.ApiHandler.CallCount);
        Assert.Null(fixture.Context.Current);
        Assert.Equal(1, fixture.Store.ClearCount);
    }

    [Fact]
    public async Task Second_unauthorized_response_ends_session_without_another_refresh()
    {
        var fixture = CreateFixture(
            _ => JsonResponse(HttpStatusCode.Unauthorized, new { success = false }));

        using var response = await fixture.Client.SendAsync(AuthenticatedGet());

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(1, fixture.RefreshHandler.CallCount);
        Assert.Equal(2, fixture.ApiHandler.CallCount);
        Assert.Null(fixture.Context.Current);
        Assert.Equal(1, fixture.Store.ClearCount);
    }

    [Fact]
    public async Task Concurrent_unauthorized_requests_share_one_rotating_refresh()
    {
        var oldRequests = 0;
        var allOldRequestsStarted = new TaskCompletionSource(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var fixture = CreateFixture(
            _ => throw new InvalidOperationException("Async response expected."),
            refreshDelay: TimeSpan.FromMilliseconds(80),
            apiResponseAsync: async request =>
            {
                if (request.Headers.Authorization?.Parameter == "access-new")
                {
                    return JsonResponse(HttpStatusCode.OK, new { ok = true });
                }

                if (Interlocked.Increment(ref oldRequests) == 6)
                {
                    allOldRequestsStarted.SetResult();
                }

                await allOldRequestsStarted.Task;
                return JsonResponse(HttpStatusCode.Unauthorized, new { success = false });
            });

        var responses = await Task.WhenAll(
            Enumerable.Range(0, 6).Select(_ => fixture.Client.SendAsync(AuthenticatedGet())));

        Assert.All(responses, response => Assert.Equal(HttpStatusCode.OK, response.StatusCode));
        Assert.Equal(1, fixture.RefreshHandler.CallCount);
        Assert.Equal(12, fixture.ApiHandler.CallCount);
        foreach (var response in responses) response.Dispose();
    }

    [Fact]
    public async Task Retry_preserves_body_headers_and_idempotency_key()
    {
        var observedBodies = new ConcurrentQueue<string>();
        var observedKeys = new ConcurrentQueue<string?>();
        var fixture = CreateFixture(request =>
        {
            observedBodies.Enqueue(request.Content?.ReadAsStringAsync().GetAwaiter().GetResult() ?? string.Empty);
            observedKeys.Enqueue(request.Headers.TryGetValues("Idempotency-Key", out var values)
                ? values.Single()
                : null);
            return request.Headers.Authorization?.Parameter == "access-new"
                ? JsonResponse(HttpStatusCode.OK, new { ok = true })
                : JsonResponse(HttpStatusCode.Unauthorized, new { success = false });
        });
        using var request = new HttpRequestMessage(HttpMethod.Post, "api/v1/sales")
        {
            Content = new StringContent("{\"idempotency_key\":\"sale-123\"}", Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new("Bearer", "access-old");
        request.Headers.Add("Idempotency-Key", "sale-123");

        using var response = await fixture.Client.SendAsync(request);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(2, observedBodies.Count);
        Assert.All(observedBodies, body => Assert.Contains("sale-123", body));
        Assert.All(observedKeys, key => Assert.Equal("sale-123", key));
    }

    [Fact]
    public async Task Refresh_endpoint_is_never_intercepted()
    {
        var fixture = CreateFixture(_ => JsonResponse(HttpStatusCode.Unauthorized, new { success = false }));
        using var request = new HttpRequestMessage(HttpMethod.Post, "api/v1/auth/refresh")
        {
            Content = new StringContent("{}", Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new("Bearer", "access-old");

        using var response = await fixture.Client.SendAsync(request);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(0, fixture.RefreshHandler.CallCount);
        Assert.Equal(1, fixture.ApiHandler.CallCount);
    }

    [Fact]
    public async Task Near_expiration_refreshes_before_sending_original_request()
    {
        var fixture = CreateFixture(request =>
            request.Headers.Authorization?.Parameter == "access-new"
                ? JsonResponse(HttpStatusCode.OK, new { ok = true })
                : JsonResponse(HttpStatusCode.Unauthorized, new { success = false }),
            accessExpiresAt: DateTimeOffset.UtcNow.AddSeconds(20));

        using var response = await fixture.Client.SendAsync(AuthenticatedGet());

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(1, fixture.RefreshHandler.CallCount);
        Assert.Equal(1, fixture.ApiHandler.CallCount);
    }

    private static Fixture CreateFixture(
        Func<HttpRequestMessage, HttpResponseMessage> apiResponse,
        Func<HttpRequestMessage, HttpResponseMessage>? refreshResponse = null,
        TimeSpan? refreshDelay = null,
        DateTimeOffset? accessExpiresAt = null,
        Func<HttpRequestMessage, Task<HttpResponseMessage>>? apiResponseAsync = null)
    {
        var context = new AppSessionContext();
        context.Set(CreateSession("access-old", "refresh-old", accessExpiresAt));
        var store = new StubSessionStore();
        var refreshHandler = new StubHandler(async request =>
        {
            if (refreshDelay is { } delay) await Task.Delay(delay);
            return refreshResponse?.Invoke(request) ?? RefreshSuccessResponse();
        });
        var factory = new StubHttpClientFactory(refreshHandler);
        var coordinator = new SessionRefreshCoordinator(
            factory,
            context,
            store,
            NullLogger<SessionRefreshCoordinator>.Instance);
        var apiHandler = new StubHandler(
            apiResponseAsync ?? (request => Task.FromResult(apiResponse(request))));
        var automaticHandler = new AutomaticSessionRefreshHandler(
            context,
            coordinator,
            NullLogger<AutomaticSessionRefreshHandler>.Instance)
        {
            InnerHandler = apiHandler,
        };
        var client = new HttpClient(automaticHandler) { BaseAddress = new Uri("https://girofy.test/") };
        return new Fixture(client, apiHandler, refreshHandler, context, store);
    }

    private static HttpRequestMessage AuthenticatedGet()
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "api/v1/catalog/products");
        request.Headers.Authorization = new("Bearer", "access-old");
        return request;
    }

    private static AuthSession CreateSession(
        string accessToken,
        string refreshToken,
        DateTimeOffset? accessExpiresAt = null) => new()
    {
        AccessToken = accessToken,
        RefreshToken = refreshToken,
        ExpiresIn = 900,
        AccessExpiresAtUtc = accessExpiresAt,
        User = new UserIdentity { Username = "operator" },
    };

    private static HttpResponseMessage RefreshSuccessResponse() => JsonResponse(
        HttpStatusCode.OK,
        new
        {
            success = true,
            data = new
            {
                access_token = "access-new",
                refresh_token = "refresh-new",
                token_type = "Bearer",
                expires_in = 900,
                refresh_expires_at = DateTimeOffset.UtcNow.AddDays(30).ToString("O"),
                user = new { username = "operator" },
                company = (object?)null,
            },
            errors = Array.Empty<object>(),
        });

    private static HttpResponseMessage JsonResponse(HttpStatusCode status, object payload) => new(status)
    {
        Content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json"),
    };

    private sealed record Fixture(
        HttpClient Client,
        StubHandler ApiHandler,
        StubHandler RefreshHandler,
        AppSessionContext Context,
        StubSessionStore Store);

    private sealed class StubHandler(Func<HttpRequestMessage, Task<HttpResponseMessage>> response) : HttpMessageHandler
    {
        private int _callCount;
        public int CallCount => _callCount;

        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            Interlocked.Increment(ref _callCount);
            return await response(request);
        }
    }

    private sealed class StubHttpClientFactory(HttpMessageHandler handler) : IHttpClientFactory
    {
        public HttpClient CreateClient(string name) => new(handler, disposeHandler: false)
        {
            BaseAddress = new Uri("https://girofy.test/"),
        };
    }

    private sealed class StubSessionStore : ISecureSessionStore
    {
        public AuthSession? SavedSession { get; private set; }
        public int ClearCount { get; private set; }

        public Task<AuthSession?> LoadAsync(CancellationToken cancellationToken) =>
            Task.FromResult(SavedSession);

        public Task SaveAsync(AuthSession session, CancellationToken cancellationToken)
        {
            SavedSession = session;
            return Task.CompletedTask;
        }

        public Task ClearAsync(CancellationToken cancellationToken)
        {
            ClearCount++;
            SavedSession = null;
            return Task.CompletedTask;
        }
    }
}
