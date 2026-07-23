using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class CashRegisterViewModelTests
{
    [Fact]
    public async Task Initialize_loads_open_register_and_expected_closing_amount()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient
        {
            SummaryResult = OpenSnapshot(42, expectedAmount: 135.50m),
        };
        using var viewModel = new CashRegisterViewModel(apiClient, sessionContext);

        await viewModel.InitializeAsync();

        Assert.True(viewModel.HasOpenRegister);
        Assert.True(viewModel.CanViewFinancials);
        Assert.Equal("access-token", apiClient.LastAccessToken);
        Assert.Equal("135,50", viewModel.ClosingAmountText);
        Assert.Equal("Caixa #42", viewModel.CurrentRegister!.NumberText);
    }

    [Fact]
    public async Task Open_uses_brazilian_money_and_updates_the_snapshot()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient
        {
            SummaryResult = new CashRegisterSnapshot(),
            OpenResult = OpenSnapshot(51, expectedAmount: 1234.56m),
        };
        using var viewModel = new CashRegisterViewModel(apiClient, sessionContext)
        {
            OpeningAmountText = "1.234,56",
        };

        await viewModel.InitializeAsync();
        await viewModel.OpenCommand.ExecuteAsync();

        Assert.Equal(1234.56m, apiClient.LastOpeningAmount);
        Assert.True(viewModel.HasOpenRegister);
        Assert.Equal("Caixa aberto com sucesso.", viewModel.SuccessMessage);
        Assert.Equal("1.234,56", viewModel.ClosingAmountText);
    }

    [Fact]
    public async Task Close_error_keeps_the_register_and_entered_amount()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient
        {
            SummaryResult = OpenSnapshot(61, expectedAmount: 200m),
            CloseException = new GirofyApiException(
                "Faltam R$ 10,00 para fechar o caixa.",
                "cash_register_amount_mismatch",
                422),
        };
        using var viewModel = new CashRegisterViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();
        viewModel.ClosingAmountText = "190,00";

        await viewModel.CloseCommand.ExecuteAsync();

        Assert.True(viewModel.HasOpenRegister);
        Assert.Equal("190,00", viewModel.ClosingAmountText);
        Assert.Equal("Faltam R$ 10,00 para fechar o caixa.", viewModel.ErrorMessage);
        Assert.Equal(61, apiClient.LastCashRegisterId);
        Assert.Equal(190m, apiClient.LastClosingAmount);
    }

    [Fact]
    public async Task Close_success_clears_the_current_register_and_entered_amount()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient
        {
            SummaryResult = OpenSnapshot(62, expectedAmount: 200m),
            CloseResult = new CashRegisterSnapshot
            {
                Permissions = new CashRegisterPermissions { CanViewFinancials = true },
                RecentRegisters =
                [
                    new CashRegisterRecord
                    {
                        Id = 62,
                        Status = "closed",
                        ClosedAt = "2026-07-16T18:00:00Z",
                        ResponsibleUser = "operador",
                        ClosingAmount = 200m,
                    },
                ],
            },
        };
        using var viewModel = new CashRegisterViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();
        viewModel.ClosingAmountText = "200,00";

        await viewModel.CloseCommand.ExecuteAsync();

        Assert.False(viewModel.HasOpenRegister);
        Assert.Empty(viewModel.ClosingAmountText);
        Assert.Equal("Caixa fechado com sucesso.", viewModel.SuccessMessage);
        Assert.Single(viewModel.RecentRegisters);
    }

    [Fact]
    public async Task Loading_selected_register_detail_fetches_timeline()
    {
        var sessionContext = CreateSessionContext();
        var apiClient = new StubApiClient
        {
            SummaryResult = new CashRegisterSnapshot
            {
                Permissions = new CashRegisterPermissions { CanViewFinancials = true },
                RecentRegisters =
                [
                    new CashRegisterRecord
                    {
                        Id = 77,
                        Status = "closed",
                        OpenedAt = "2026-07-16T12:00:00Z",
                        ClosedAt = "2026-07-16T18:00:00Z",
                        ResponsibleUser = "operador",
                        SalesCount = 1,
                        SalesTotal = 25m,
                    },
                ],
            },
            DetailResult = new CashRegisterDetailSnapshot
            {
                Permissions = new CashRegisterPermissions { CanViewFinancials = true },
                CashRegister = new CashRegisterRecord
                {
                    Id = 77,
                    Status = "closed",
                    ResponsibleUser = "operador",
                    SalesCount = 1,
                    SalesTotal = 25m,
                },
                Timeline =
                [
                    new CashRegisterTimelineSale
                    {
                        Id = 301,
                        Number = "#301",
                        Time = "18:03",
                        Seller = "operador",
                        FinalAmount = 25m,
                    },
                ],
            },
        };
        using var viewModel = new CashRegisterViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        viewModel.SelectedRegister = viewModel.RecentRegisters.Single();
        await viewModel.LoadRegisterDetailCommand.ExecuteAsync();

        Assert.Equal(77, apiClient.LastDetailCashRegisterId);
        Assert.True(viewModel.HasDetail);
        Assert.True(viewModel.HasTimeline);
        Assert.Equal("Caixa #77", viewModel.DetailRegister!.NumberText);
        Assert.Equal("#301", viewModel.Timeline.Single().Number);
        Assert.False(viewModel.IsDetailLoading);
    }

    [Fact]
    public async Task Clearing_session_removes_cash_register_data()
    {
        var sessionContext = CreateSessionContext();
        using var viewModel = new CashRegisterViewModel(
            new StubApiClient { SummaryResult = OpenSnapshot(71, expectedAmount: 80m) },
            sessionContext);
        await viewModel.InitializeAsync();

        sessionContext.Clear();

        Assert.False(viewModel.HasOpenRegister);
        Assert.Null(viewModel.Snapshot);
        Assert.False(viewModel.IsAvailable);
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
                Id = 7,
                Username = "operador",
                Permissions = new Dictionary<string, bool>
                {
                    ["can_manage_cash_register"] = true,
                    ["can_view_reports"] = true,
                },
            },
            Company = new CompanyIdentity { Id = 4, Name = "Adega JF" },
        });
        return context;
    }

    private static CashRegisterSnapshot OpenSnapshot(int id, decimal expectedAmount) => new()
    {
        Permissions = new CashRegisterPermissions { CanViewFinancials = true },
        CurrentRegister = new CashRegisterRecord
        {
            Id = id,
            Status = "open",
            OpenedAt = "2026-07-16T12:00:00Z",
            ResponsibleUser = "operador",
            OpeningAmount = expectedAmount,
            ExpectedAmount = expectedAmount,
        },
    };

    private sealed class StubApiClient : IGirofyApiClient
    {
        public CashRegisterSnapshot SummaryResult { get; init; } = new();

        public CashRegisterSnapshot OpenResult { get; init; } = new();

        public CashRegisterSnapshot CloseResult { get; init; } = new();

        public CashRegisterDetailSnapshot DetailResult { get; init; } = new();

        public Exception? CloseException { get; init; }

        public string LastAccessToken { get; private set; } = string.Empty;

        public decimal LastOpeningAmount { get; private set; }

        public int LastCashRegisterId { get; private set; }

        public int LastDetailCashRegisterId { get; private set; }

        public decimal LastClosingAmount { get; private set; }

        public Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            return Task.FromResult(SummaryResult);
        }

        public Task<CashRegisterSnapshot> OpenCashRegisterAsync(
            string accessToken,
            decimal openingAmount,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            LastOpeningAmount = openingAmount;
            return Task.FromResult(OpenResult);
        }

        public Task<CashRegisterSnapshot> CloseCashRegisterAsync(
            string accessToken,
            int cashRegisterId,
            decimal closingAmount,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            LastCashRegisterId = cashRegisterId;
            LastClosingAmount = closingAmount;
            return CloseException is null
                ? Task.FromResult(CloseResult)
                : Task.FromException<CashRegisterSnapshot>(CloseException);
        }

        public Task<CashRegisterDetailSnapshot> GetCashRegisterDetailAsync(
            string accessToken,
            int cashRegisterId,
            CancellationToken cancellationToken)
        {
            LastAccessToken = accessToken;
            LastDetailCashRegisterId = cashRegisterId;
            return Task.FromResult(DetailResult);
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
