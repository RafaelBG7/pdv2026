using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class PayablesViewModelTests
{
    [Fact]
    public async Task Initialize_loads_payables_summary_filters_and_items()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient
        {
            Snapshot = SnapshotWithItems(),
        };
        using var viewModel = new PayablesViewModel(apiClient, sessionContext);

        await viewModel.InitializeAsync();

        Assert.True(viewModel.IsAvailable);
        Assert.True(viewModel.HasItems);
        Assert.Equal("access-token", apiClient.LastAccessToken);
        Assert.Equal("R$ 1.200,50", viewModel.Summary.OpenAmountText);
        Assert.Contains(viewModel.StatusOptions, option => option.Value == "paid");
        Assert.Contains("Aluguel", viewModel.Categories);
        Assert.Single(viewModel.Payables);
        Assert.Equal("Aluguel loja", viewModel.Payables[0].Description);
    }

    [Fact]
    public async Task Create_payable_parses_brazilian_amount_sends_request_and_reloads()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient
        {
            Snapshot = SnapshotWithItems(),
            CreatedPayable = new PayableRecord
            {
                Id = 91,
                Description = "Luz",
                Category = "Luz",
                Amount = 380.75m,
                DueDate = "2026-07-20",
                Status = "open",
                StatusLabel = "Aberta",
            },
        };
        using var viewModel = new PayablesViewModel(apiClient, sessionContext)
        {
            Description = "Luz",
            CategoryText = "Luz",
            AmountText = "380,75",
            DueDateText = "20/07/2026",
            Notes = "Conta mensal",
        };

        await viewModel.CreatePayableCommand.ExecuteAsync();

        Assert.NotNull(apiClient.CreatedRequest);
        Assert.Equal("Luz", apiClient.CreatedRequest!.Description);
        Assert.Equal("Luz", apiClient.CreatedRequest.Category);
        Assert.Equal(380.75m, apiClient.CreatedRequest.Amount);
        Assert.Equal("2026-07-20", apiClient.CreatedRequest.DueDate);
        Assert.Equal("Conta mensal", apiClient.CreatedRequest.Notes);
        Assert.True(viewModel.HasSuccess);
        Assert.Equal(1, apiClient.CreateCalls);
        Assert.Equal(1, apiClient.GetCalls);
    }

    [Fact]
    public async Task Create_payable_rejects_discounted_invalid_amount_before_api_call()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new PayablesViewModel(apiClient, sessionContext)
        {
            Description = "Aluguel",
            AmountText = "0,00",
            DueDateText = "2026-07-20",
        };

        await viewModel.CreatePayableCommand.ExecuteAsync();

        Assert.True(viewModel.HasError);
        Assert.Equal(0, apiClient.CreateCalls);
        Assert.Equal(0, apiClient.GetCalls);
    }

    [Fact]
    public async Task Pay_and_reopen_mark_the_selected_record_and_reload()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient { Snapshot = SnapshotWithItems() };
        using var viewModel = new PayablesViewModel(apiClient, sessionContext);
        var openPayable = new PayableRecord
        {
            Id = 12,
            Description = "Fornecedor",
            Paid = false,
            StatusLabel = "Aberta",
        };
        var paidPayable = new PayableRecord
        {
            Id = 13,
            Description = "Internet",
            Paid = true,
            StatusLabel = "Paga",
        };

        viewModel.PayPayableCommand.Execute(openPayable);
        await WaitUntilAsync(() => apiClient.PaidId == 12);
        viewModel.ReopenPayableCommand.Execute(paidPayable);
        await WaitUntilAsync(() => apiClient.ReopenedId == 13);

        Assert.Equal(12, apiClient.PaidId);
        Assert.Equal(13, apiClient.ReopenedId);
        Assert.True(apiClient.GetCalls >= 2);
    }

    [Fact]
    public async Task Clearing_session_removes_payables_data()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient { Snapshot = SnapshotWithItems() };
        using var viewModel = new PayablesViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        sessionContext.Clear();

        Assert.False(viewModel.IsAvailable);
        Assert.False(viewModel.HasItems);
        Assert.Empty(viewModel.Payables);
        Assert.Empty(viewModel.Categories);
    }

    private static AppSessionContext CreateSessionContext()
    {
        var context = new AppSessionContext();
        context.Set(new AuthSession
        {
            AccessToken = "access-token",
            RefreshToken = "refresh-token",
            User = new UserIdentity
            {
                Id = 4,
                Username = "operador",
                Permissions = new Dictionary<string, bool> { ["can_manage_payables"] = true },
            },
            Company = new CompanyIdentity { Id = 2, Name = "Adega JF" },
        });
        return context;
    }

    private static PayablesSnapshot SnapshotWithItems() => new()
    {
        Items =
        [
            new PayableRecord
            {
                Id = 7,
                Description = "Aluguel loja",
                Category = "Aluguel",
                Amount = 1200.50m,
                DueDate = "2026-07-20",
                Status = "open",
                StatusLabel = "Aberta",
            },
        ],
        Summary = new PayableSummary
        {
            OpenAmount = 1200.50m,
            OverdueAmount = 0m,
            DueSoonAmount = 1200.50m,
            OpenCount = 1,
            PaidCount = 2,
        },
        Categories = ["Aluguel"],
        StatusOptions =
        [
            new CatalogFilterOption("open", "Abertas"),
            new CatalogFilterOption("paid", "Pagas"),
            new CatalogFilterOption("all", "Todas"),
        ],
        SelectedStatus = "open",
    };

    private static async Task WaitUntilAsync(Func<bool> predicate)
    {
        for (var attempt = 0; attempt < 50; attempt++)
        {
            if (predicate())
            {
                return;
            }

            await Task.Delay(10);
        }

        Assert.True(predicate());
    }

    private sealed class StubApiClient : IGirofyApiClient
    {
        public PayablesSnapshot Snapshot { get; init; } = new();

        public PayableRecord CreatedPayable { get; init; } = new()
        {
            Id = 99,
            Description = "Conta criada",
            Category = "Outros",
            Amount = 10m,
            DueDate = "2026-07-20",
        };

        public string LastAccessToken { get; private set; } = string.Empty;

        public int GetCalls { get; private set; }

        public int CreateCalls { get; private set; }

        public PayableMutationRequest? CreatedRequest { get; private set; }

        public int? PaidId { get; private set; }

        public int? ReopenedId { get; private set; }

        public Task<PayablesSnapshot> GetPayablesAsync(
            string accessToken,
            PayablesQuery query,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            GetCalls++;
            return Task.FromResult(Snapshot);
        }

        public Task<PayableRecord> CreatePayableAsync(
            string accessToken,
            PayableMutationRequest request,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            CreateCalls++;
            CreatedRequest = request;
            return Task.FromResult(CreatedPayable);
        }

        public Task<PayableRecord> PayPayableAsync(
            string accessToken,
            int payableId,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            PaidId = payableId;
            return Task.FromResult(new PayableRecord { Id = payableId, Paid = true, StatusLabel = "Paga" });
        }

        public Task<PayableRecord> ReopenPayableAsync(
            string accessToken,
            int payableId,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            ReopenedId = payableId;
            return Task.FromResult(new PayableRecord { Id = payableId, Paid = false, StatusLabel = "Aberta" });
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

        public Task LogoutAsync(string accessToken, CancellationToken cancellationToken) =>
            Task.FromException(new NotSupportedException());

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
}
