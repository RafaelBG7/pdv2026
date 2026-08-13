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
            DetailResult = new CashRegisterDetailSnapshot
            {
                CashRegister = new CashRegisterRecord { Id = 42, Status = "open" },
                Timeline =
                [
                    new CashRegisterTimelineSale
                    {
                        Id = 201,
                        Number = "#201",
                        BalanceBeforeSale = 100m,
                        BalanceAfterSale = 135.50m,
                    },
                ],
            },
        };
        using var viewModel = new CashRegisterViewModel(apiClient, sessionContext);

        await viewModel.InitializeAsync();

        Assert.True(viewModel.HasOpenRegister);
        Assert.True(viewModel.CanViewFinancials);
        Assert.Equal("access-token", apiClient.LastAccessToken);
        Assert.Equal("135,50", viewModel.ClosingAmountText);
        Assert.Equal("Caixa #42", viewModel.CurrentRegister!.NumberText);
        Assert.Equal(42, apiClient.LastDetailCashRegisterId);
        Assert.True(viewModel.HasCurrentTimeline);
        Assert.Equal("R$ 100,00", viewModel.CurrentTimeline.Single().BalanceBeforeSaleText);
        Assert.Equal("R$ 135,50", viewModel.CurrentTimeline.Single().BalanceAfterSaleText);
        Assert.True(viewModel.IsCurrentRegisterTabSelected);
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
        Assert.True(viewModel.IsPreviousRegistersTabSelected);
    }

    [Fact]
    public async Task Internal_navigation_separates_current_and_previous_registers()
    {
        var apiClient = new StubApiClient
        {
            SummaryResult = new CashRegisterSnapshot
            {
                RecentRegisters =
                [
                    new CashRegisterRecord { Id = 77, Status = "closed" },
                ],
            },
        };
        using var viewModel = new CashRegisterViewModel(apiClient, CreateSessionContext());
        await viewModel.InitializeAsync();

        Assert.True(viewModel.IsCurrentRegisterTabSelected);
        Assert.True(viewModel.HasRecentRegisters);

        viewModel.ShowPreviousRegistersTabCommand.Execute(null);

        Assert.True(viewModel.IsPreviousRegistersTabSelected);
        Assert.False(viewModel.IsCurrentRegisterTabSelected);

        viewModel.ShowCurrentRegisterTabCommand.Execute(null);

        Assert.True(viewModel.IsCurrentRegisterTabSelected);
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
    public async Task Collapsing_selected_register_clears_selection_and_detail()
    {
        var apiClient = new StubApiClient
        {
            SummaryResult = new CashRegisterSnapshot
            {
                RecentRegisters =
                [
                    new CashRegisterRecord { Id = 77, Status = "closed" },
                ],
            },
            DetailResult = new CashRegisterDetailSnapshot
            {
                CashRegister = new CashRegisterRecord { Id = 77, Status = "closed" },
            },
        };
        using var viewModel = new CashRegisterViewModel(apiClient, CreateSessionContext());
        await viewModel.InitializeAsync();
        viewModel.SelectedRegister = viewModel.RecentRegisters.Single();
        await viewModel.LoadSelectedRegisterDetailAsync();

        viewModel.CollapseSelectedRegisterDetail();

        Assert.Null(viewModel.SelectedRegister);
        Assert.Null(viewModel.DetailSnapshot);
        Assert.False(viewModel.HasDetail);
        Assert.False(viewModel.IsDetailLoading);
    }

    [Fact]
    public async Task Latest_selected_register_wins_when_detail_responses_finish_out_of_order()
    {
        var firstResponse = new TaskCompletionSource<CashRegisterDetailSnapshot>();
        var secondResponse = new TaskCompletionSource<CashRegisterDetailSnapshot>();
        var apiClient = new StubApiClient
        {
            SummaryResult = new CashRegisterSnapshot
            {
                RecentRegisters =
                [
                    new CashRegisterRecord { Id = 10, Status = "closed" },
                    new CashRegisterRecord { Id = 20, Status = "closed" },
                ],
            },
            DetailHandler = (id, _) => id == 10 ? firstResponse.Task : secondResponse.Task,
        };
        using var viewModel = new CashRegisterViewModel(apiClient, CreateSessionContext());
        await viewModel.InitializeAsync();

        viewModel.SelectedRegister = viewModel.RecentRegisters[0];
        var firstLoad = viewModel.LoadSelectedRegisterDetailAsync();
        viewModel.SelectedRegister = viewModel.RecentRegisters[1];
        var secondLoad = viewModel.LoadSelectedRegisterDetailAsync();

        secondResponse.SetResult(new CashRegisterDetailSnapshot
        {
            CashRegister = new CashRegisterRecord { Id = 20, Status = "closed" },
        });
        await secondLoad;
        firstResponse.SetResult(new CashRegisterDetailSnapshot
        {
            CashRegister = new CashRegisterRecord { Id = 10, Status = "closed" },
        });
        await firstLoad;

        Assert.Equal(20, viewModel.DetailRegister?.Id);
        Assert.False(viewModel.IsDetailLoading);
    }

    [Fact]
    public async Task Selecting_another_register_cancels_the_previous_detail_request()
    {
        var firstRequestCancelled = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var apiClient = new StubApiClient
        {
            SummaryResult = new CashRegisterSnapshot
            {
                RecentRegisters =
                [
                    new CashRegisterRecord { Id = 10, Status = "closed" },
                    new CashRegisterRecord { Id = 20, Status = "closed" },
                ],
            },
            DetailHandler = async (id, cancellationToken) =>
            {
                if (id == 10)
                {
                    using var registration = cancellationToken.Register(
                        () => firstRequestCancelled.TrySetResult(true));
                    await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
                }

                return new CashRegisterDetailSnapshot
                {
                    CashRegister = new CashRegisterRecord { Id = id, Status = "closed" },
                };
            },
        };
        using var viewModel = new CashRegisterViewModel(apiClient, CreateSessionContext());
        await viewModel.InitializeAsync();

        viewModel.SelectedRegister = viewModel.RecentRegisters[0];
        var firstLoad = viewModel.LoadSelectedRegisterDetailAsync();
        await Task.Yield();
        viewModel.SelectedRegister = viewModel.RecentRegisters[1];
        await viewModel.LoadSelectedRegisterDetailAsync();
        await firstLoad.WaitAsync(TimeSpan.FromSeconds(5));

        Assert.True(await firstRequestCancelled.Task.WaitAsync(TimeSpan.FromSeconds(5)));
        Assert.Equal(20, viewModel.DetailRegister?.Id);
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

        public Func<int, CancellationToken, Task<CashRegisterDetailSnapshot>>? DetailHandler { get; init; }

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
            return DetailHandler?.Invoke(cashRegisterId, cancellationToken) ??
                Task.FromResult(DetailResult);
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
