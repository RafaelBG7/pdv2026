using Girofy.Application.Abstractions;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class SalesViewModelTests
{
    [Fact]
    public async Task Search_orders_products_and_adds_the_selected_quantity()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "coca",
        };

        await viewModel.SearchCommand.ExecuteAsync();

        Assert.Equal(["Coca Cola 2L", "Coca Zero 2L"], viewModel.SearchResults.Select(item => item.Name));
        Assert.Equal("Coca Cola 2L", viewModel.SelectedSearchProduct?.Name);

        viewModel.QuantityText = "2";
        viewModel.AddProductCommand.Execute(null);

        Assert.Single(viewModel.CartItems);
        Assert.Equal(2, viewModel.CartItems[0].Quantity);
        Assert.Equal(24m, viewModel.Subtotal);
        Assert.Equal("R$ 24,00", viewModel.SubtotalText);
        Assert.Equal(string.Empty, viewModel.SearchText);
        Assert.Empty(viewModel.SearchResults);
    }

    [Fact]
    public async Task Quantity_popup_opens_for_selected_product_and_closes_without_adding()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "coca",
        };

        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.QuantityText = "8";
        viewModel.OpenQuantityPopupCommand.Execute(null);

        Assert.True(viewModel.IsQuantityPopupOpen);
        Assert.Equal("1", viewModel.QuantityText);
        Assert.Equal("Coca Cola 2L", viewModel.SelectedSearchProduct?.Name);

        viewModel.CloseQuantityPopupCommand.Execute(null);

        Assert.False(viewModel.IsQuantityPopupOpen);
        Assert.Null(viewModel.SelectedSearchProduct);
        Assert.Empty(viewModel.CartItems);
    }

    [Fact]
    public async Task Exact_barcode_opens_quantity_and_consecutive_scans_merge_the_cart_line()
    {
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, SessionContext());

        Assert.True(await viewModel.SelectExactBarcodeAsync(" 789 ", showNotFound: true));
        Assert.True(viewModel.IsQuantityPopupOpen);
        Assert.Equal("Coca Cola 2L", viewModel.SelectedSearchProduct?.Name);

        viewModel.QuantityText = "2";
        viewModel.AddProductCommand.Execute(null);
        Assert.True(await viewModel.SelectExactBarcodeAsync("789", showNotFound: true));
        viewModel.QuantityText = "1";
        viewModel.AddProductCommand.Execute(null);

        Assert.Single(viewModel.CartItems);
        Assert.Equal(3, viewModel.CartItems[0].Quantity);
    }

    [Fact]
    public async Task Barcode_lookup_reports_missing_and_inactive_products()
    {
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, SessionContext());

        Assert.False(await viewModel.SelectExactBarcodeAsync("missing", showNotFound: true));
        Assert.Contains("não encontrado", viewModel.ErrorMessage, StringComparison.OrdinalIgnoreCase);

        Assert.False(await viewModel.SelectExactBarcodeAsync("inactive", showNotFound: true));
        Assert.Contains("inativo", viewModel.ErrorMessage, StringComparison.OrdinalIgnoreCase);
        Assert.Empty(viewModel.CartItems);
    }

    [Fact]
    public async Task Typing_searches_products_live_and_orders_suggestions()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext);

        viewModel.SearchText = "coca";

        await WaitUntilAsync(() => viewModel.SearchResults.Count == 2);

        Assert.Equal(["Coca Cola 2L", "Coca Zero 2L"], viewModel.SearchResults.Select(item => item.Name));
        Assert.Equal("Coca Cola 2L", viewModel.SelectedSearchProduct?.Name);
        Assert.False(viewModel.HasError);
    }

    [Fact]
    public async Task Search_keeps_up_to_twenty_ranked_results_for_dense_picker()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient
        {
            CatalogProducts = Enumerable.Range(1, 30)
                .Select(index => new CatalogProduct
                {
                    Id = index,
                    Name = $"Coca Cola opção {index:00}",
                    Barcode = $"789{index:000}",
                    SalePrice = index,
                    StockQuantity = index,
                    Active = true,
                })
                .ToArray(),
        };
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "coca",
        };

        await viewModel.SearchCommand.ExecuteAsync();

        Assert.Equal(20, viewModel.SearchResults.Count);
        Assert.Equal(30, apiClient.LastCatalogPerPage);
        Assert.Equal("Coca Cola opção 01", viewModel.SelectedSearchProduct?.Name);
    }

    [Fact]
    public async Task Initialize_loads_today_sales_history()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient
        {
            DashboardRecentSales =
            [
                new DashboardRecentSale
                {
                    Id = 18,
                    CreatedAt = "2026-07-21T09:15:00-03:00",
                    FinalAmount = 11m,
                    UserName = "operador",
                    PaymentMethods = ["Dinheiro"],
                },
                new DashboardRecentSale
                {
                    Id = 19,
                    CreatedAt = "2026-07-21T10:30:00-03:00",
                    FinalAmount = 22m,
                    UserName = "operador",
                    PaymentMethods = ["Pix", "Débito"],
                },
            ],
        };
        using var viewModel = new SalesViewModel(apiClient, sessionContext);

        await viewModel.InitializeAsync();

        Assert.True(viewModel.HasTodaySales);
        Assert.False(viewModel.HasNoTodaySales);
        Assert.Equal([18, 19], viewModel.TodaySales.Select(sale => sale.Id));
        Assert.Equal("Pix + Débito", viewModel.TodaySales[1].PaymentText);
    }

    [Fact]
    public async Task Toggle_today_sale_expands_and_loads_detail()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient
        {
            DashboardRecentSales =
            [
                new DashboardRecentSale
                {
                    Id = 18,
                    CreatedAt = "2026-07-21T09:15:00-03:00",
                    FinalAmount = 11m,
                    UserName = "operador",
                    PaymentMethods = ["Dinheiro"],
                    PaymentStatus = "paid",
                },
            ],
        };
        apiClient.SaleDetails[18] = new SaleReceipt
        {
            Id = 18,
            CashRegisterId = 5,
            Subtotal = 11m,
            DiscountAmount = 1m,
            FinalAmount = 10m,
            PaidAmount = 10m,
            ChangeAmount = 0m,
            Items =
            [
                new SaleReceiptItem
                {
                    ProductId = 3,
                    Name = "Heineken 269ml",
                    Quantity = 2,
                    UnitPrice = 5.5m,
                    Subtotal = 11m,
                    ProfitAmount = 6m,
                },
            ],
            Payments =
            [
                new SaleReceiptPayment { Method = "money", Label = "Dinheiro", Amount = 10m },
            ],
        };

        using var viewModel = new SalesViewModel(apiClient, sessionContext);
        await viewModel.InitializeAsync();

        var sale = viewModel.TodaySales.Single();
        viewModel.ToggleTodaySaleCommand.Execute(sale);
        await WaitUntilAsync(() => sale.Detail is not null);

        Assert.True(sale.IsExpanded);
        Assert.Equal("Ocultar", sale.ExpandHint);
        Assert.Equal("Dinheiro: R$ 10,00", sale.DetailPaymentsText);
        Assert.Equal("R$ 6,00", sale.Detail?.Items.Single().ProfitAmountText);
    }

    [Fact]
    public async Task Refresh_history_reloads_and_preserves_a_safe_empty_state()
    {
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, SessionContext());

        await viewModel.InitializeAsync();
        await viewModel.RefreshHistoryCommand.ExecuteAsync();

        Assert.Equal(2, apiClient.HistoryCalls);
        Assert.True(viewModel.ShowHistoryEmptyState);
        Assert.False(viewModel.IsHistoryLoading);
    }

    [Fact]
    public async Task History_loads_thirty_sales_then_appends_the_next_page()
    {
        var apiClient = new StubApiClient
        {
            DashboardRecentSales = Enumerable.Range(1, 40)
                .Select(id => new DashboardRecentSale { Id = id, FinalAmount = id })
                .ToArray(),
        };
        using var viewModel = new SalesViewModel(apiClient, SessionContext());

        await viewModel.InitializeAsync();

        Assert.Equal(30, viewModel.TodaySales.Count);
        Assert.True(viewModel.HasMoreSales);
        await viewModel.LoadMoreHistoryCommand.ExecuteAsync();
        Assert.Equal(40, viewModel.TodaySales.Count);
        Assert.False(viewModel.HasMoreSales);
        Assert.Equal([1, 2], apiClient.RequestedHistoryPages);
    }

    [Fact]
    public async Task History_network_failure_has_a_friendly_message()
    {
        var apiClient = new StubApiClient
        {
            HistoryException = new HttpRequestException("offline"),
        };
        using var viewModel = new SalesViewModel(apiClient, SessionContext());

        await viewModel.InitializeAsync();

        Assert.Contains("Verifique sua conexão", viewModel.HistoryErrorMessage);
        Assert.False(viewModel.ShowHistoryEmptyState);
    }

    [Fact]
    public async Task Historical_sale_reuses_the_existing_receipt()
    {
        var apiClient = new StubApiClient
        {
            DashboardRecentSales =
            [
                new DashboardRecentSale { Id = 18, FinalAmount = 10m },
            ],
        };
        apiClient.SaleDetails[18] = new SaleReceipt
        {
            Id = 18,
            FinalAmount = 10m,
            Items = [new SaleReceiptItem { Name = "Produto", Quantity = 1, Subtotal = 10m }],
            Payments = [new SaleReceiptPayment { Label = "Pix", Amount = 10m }],
        };
        using var viewModel = new SalesViewModel(apiClient, SessionContext());
        await viewModel.InitializeAsync();

        viewModel.ViewHistoricalReceiptCommand.Execute(viewModel.TodaySales.Single());
        await WaitUntilAsync(() => viewModel.IsHistoricalReceipt);

        Assert.Equal(18, viewModel.Receipt?.Id);
        Assert.Equal("Comprovante da venda", viewModel.ReceiptTitle);
        Assert.Single(viewModel.Receipt!.Items);
        Assert.Single(viewModel.Receipt.Payments);

        viewModel.CloseHistoricalReceiptCommand.Execute(null);
        Assert.Null(viewModel.Receipt);
    }

    [Fact]
    public async Task Failure_preserves_the_order_and_retry_reuses_the_idempotency_key()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient { FailFirstSaleAttempt = true };
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "789",
        };
        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.SelectedSearchProduct = viewModel.SearchResults.Single(item => item.Barcode == "789");
        viewModel.QuantityText = "2";
        viewModel.AddProductCommand.Execute(null);
        viewModel.DiscountText = "2,00";
        viewModel.MoneyText = "10,00";
        viewModel.FillPixCommand.Execute(null);

        Assert.Equal(22m, viewModel.Total);
        Assert.Equal("12,00", viewModel.PixText);

        await viewModel.FinalizeCommand.ExecuteAsync();

        Assert.True(viewModel.HasError);
        Assert.Contains("preservado", viewModel.ErrorMessage, StringComparison.OrdinalIgnoreCase);
        Assert.Single(viewModel.CartItems);
        Assert.Equal("2,00", viewModel.DiscountText);
        Assert.Equal("10,00", viewModel.MoneyText);
        Assert.Equal("12,00", viewModel.PixText);
        Assert.Single(apiClient.IdempotencyKeys);

        await viewModel.FinalizeCommand.ExecuteAsync();

        Assert.True(viewModel.HasReceipt);
        Assert.Equal(42, viewModel.Receipt?.Id);
        Assert.Empty(viewModel.CartItems);
        Assert.Equal(2, apiClient.IdempotencyKeys.Count);
        Assert.Equal(apiClient.IdempotencyKeys[0], apiClient.IdempotencyKeys[1]);
        Assert.Equal(2m, apiClient.LastDiscountAmount);
        Assert.Equal([10m, 12m], apiClient.LastPayments.Select(payment => payment.Amount));
    }

    [Fact]
    public async Task Discount_above_subtotal_is_rejected_before_the_api_call()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "789",
        };
        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.AddProductCommand.Execute(null);
        viewModel.DiscountText = "20,00";
        viewModel.MoneyText = "20,00";

        await viewModel.FinalizeCommand.ExecuteAsync();

        Assert.True(viewModel.HasError);
        Assert.Empty(apiClient.IdempotencyKeys);
        Assert.Single(viewModel.CartItems);
    }

    [Fact]
    public async Task Discount_popup_applies_value_and_shows_percentage()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "789",
        };

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.AddProductCommand.Execute(null);

        viewModel.OpenDiscountPopupCommand.Execute(null);
        Assert.True(viewModel.IsDiscountPopupVisible);

        viewModel.DraftDiscountText = "3,00";

        Assert.Equal(3m, viewModel.DraftDiscountAmount);
        Assert.Equal("25,00%", viewModel.DraftDiscountPercentText);
        Assert.Equal("R$ 9,00", viewModel.DraftTotalAfterDiscountText);

        viewModel.ApplyDiscountCommand.Execute(null);

        Assert.False(viewModel.IsDiscountPopupVisible);
        Assert.Equal("3,00", viewModel.DiscountText);
        Assert.Equal(3m, viewModel.DiscountAmount);
        Assert.Equal("25,00%", viewModel.DiscountPercentText);
        Assert.Equal("R$ 9,00", viewModel.TotalText);
    }

    [Fact]
    public async Task Discount_popup_rejects_value_above_subtotal_without_closing()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "789",
        };

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.AddProductCommand.Execute(null);
        viewModel.OpenDiscountPopupCommand.Execute(null);
        viewModel.DraftDiscountText = "20,00";

        viewModel.ApplyDiscountCommand.Execute(null);

        Assert.True(viewModel.HasError);
        Assert.True(viewModel.IsDiscountPopupVisible);
        Assert.Equal("0,00", viewModel.DiscountText);
        Assert.Equal("R$ 12,00", viewModel.TotalText);
    }

    [Fact]
    public async Task Sale_popup_moves_between_product_and_payment_steps()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "coca",
        };

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();

        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.True(viewModel.IsProductStepOpen);
        Assert.False(viewModel.IsPaymentStepVisible);

        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.AddProductCommand.Execute(null);
        viewModel.OpenPaymentStepCommand.Execute(null);

        Assert.True(viewModel.IsPaymentStepVisible);
        Assert.Equal("12,00", viewModel.MoneyText);

        viewModel.MoneyText = "5,00";
        viewModel.AutoCompletePaymentIfEmpty("pix");

        Assert.Equal("5,00", viewModel.MoneyText);
        Assert.Equal("7,00", viewModel.PixText);

        viewModel.AutoCompletePaymentIfEmpty("money");

        Assert.Equal("5,00", viewModel.MoneyText);

        viewModel.BackToProductsCommand.Execute(null);

        Assert.True(viewModel.IsProductStepOpen);

        viewModel.OpenPaymentStepCommand.Execute(null);
        await viewModel.FinalizeCommand.ExecuteAsync();

        Assert.True(viewModel.HasReceipt);
        Assert.False(viewModel.IsSaleEditorOpen);
        Assert.False(viewModel.IsPaymentStepVisible);
    }

    [Fact]
    public async Task Closing_empty_sale_discards_immediately_and_reopens_empty()
    {
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, SessionContext());

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        viewModel.SearchText = "temporary";
        viewModel.CloseSaleEditorCommand.Execute(null);

        Assert.False(viewModel.IsSaleEditorOpen);
        Assert.False(viewModel.IsDiscardConfirmationOpen);
        Assert.Empty(viewModel.SearchText);
        Assert.Empty(apiClient.IdempotencyKeys);

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.Empty(viewModel.CartItems);
        Assert.Equal("R$ 0,00", viewModel.TotalText);
    }

    [Fact]
    public async Task Escape_closes_empty_sale_and_reopening_starts_with_a_clean_draft()
    {
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, SessionContext());

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        viewModel.HandleSaleEscapeCommand.Execute(null);

        Assert.False(viewModel.IsSaleEditorOpen);
        Assert.Empty(viewModel.CartItems);
        Assert.Empty(viewModel.SearchText);

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();

        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.True(viewModel.IsProductStepOpen);
        Assert.Equal("R$ 0,00", viewModel.SubtotalText);
        Assert.Equal("R$ 0,00", viewModel.TotalText);
    }

    [Fact]
    public async Task Escape_closes_only_the_highest_sale_layer()
    {
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, SessionContext())
        {
            SearchText = "coca",
        };
        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        await viewModel.SearchCommand.ExecuteAsync();
        Assert.True(viewModel.HasSearchResults);

        viewModel.HandleSaleEscapeCommand.Execute(null);

        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.False(viewModel.HasSearchResults);
        Assert.Empty(viewModel.SearchText);

        Assert.True(await viewModel.SelectExactBarcodeAsync("789", showNotFound: true));
        Assert.True(viewModel.IsQuantityPopupOpen);

        viewModel.HandleSaleEscapeCommand.Execute(null);

        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.False(viewModel.IsQuantityPopupOpen);

        viewModel.HandleSaleEscapeCommand.Execute(null);

        Assert.False(viewModel.IsSaleEditorOpen);
    }

    [Fact]
    public async Task Escape_and_close_button_share_the_same_discard_confirmation_flow()
    {
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, SessionContext());
        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        Assert.True(await viewModel.SelectExactBarcodeAsync("789", showNotFound: true));
        viewModel.AddProductCommand.Execute(null);

        viewModel.HandleSaleEscapeCommand.Execute(null);

        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.True(viewModel.IsDiscardConfirmationOpen);
        Assert.Single(viewModel.CartItems);

        viewModel.HandleSaleEscapeCommand.Execute(null);
        Assert.False(viewModel.IsDiscardConfirmationOpen);
        Assert.Single(viewModel.CartItems);

        viewModel.CloseSaleEditorCommand.Execute(null);
        Assert.True(viewModel.IsDiscardConfirmationOpen);
        viewModel.ConfirmDiscardSaleCommand.Execute(null);

        Assert.False(viewModel.IsSaleEditorOpen);
        Assert.Empty(viewModel.CartItems);
        Assert.Equal("0,00", viewModel.DiscountText);
        Assert.Equal("0,00", viewModel.MoneyText);
        Assert.Equal("0,00", viewModel.PixText);
        Assert.Empty(viewModel.SearchText);
    }

    [Fact]
    public async Task Closing_sale_with_items_requires_confirmation_and_discard_clears_all_draft_state()
    {
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, SessionContext());
        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        Assert.True(await viewModel.SelectExactBarcodeAsync("789", showNotFound: true));
        viewModel.QuantityText = "2";
        viewModel.AddProductCommand.Execute(null);
        viewModel.DiscountText = "2,00";
        viewModel.MoneyText = "5,00";
        viewModel.PixText = "17,00";

        viewModel.CloseSaleEditorCommand.Execute(null);

        Assert.True(viewModel.IsDiscardConfirmationOpen);
        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.Single(viewModel.CartItems);

        viewModel.ContinueSaleCommand.Execute(null);
        Assert.False(viewModel.IsDiscardConfirmationOpen);
        Assert.Single(viewModel.CartItems);

        viewModel.CloseSaleEditorCommand.Execute(null);
        viewModel.ConfirmDiscardSaleCommand.Execute(null);

        Assert.False(viewModel.IsSaleEditorOpen);
        Assert.Empty(viewModel.CartItems);
        Assert.Empty(viewModel.SearchText);
        Assert.Equal("1", viewModel.QuantityText);
        Assert.Equal("0,00", viewModel.DiscountText);
        Assert.Equal("0,00", viewModel.MoneyText);
        Assert.Equal("0,00", viewModel.PixText);
        Assert.Equal("0,00", viewModel.DebitText);
        Assert.Equal("0,00", viewModel.CreditText);
        Assert.Empty(apiClient.IdempotencyKeys);

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.Empty(viewModel.CartItems);
    }

    [Fact]
    public async Task Discard_after_failed_finalize_creates_a_new_idempotency_key_for_next_sale()
    {
        var apiClient = new StubApiClient { FailFirstSaleAttempt = true };
        using var viewModel = new SalesViewModel(apiClient, SessionContext());
        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        Assert.True(await viewModel.SelectExactBarcodeAsync("789", showNotFound: true));
        viewModel.AddProductCommand.Execute(null);
        viewModel.MoneyText = "12,00";

        await viewModel.FinalizeCommand.ExecuteAsync();
        Assert.Single(apiClient.IdempotencyKeys);

        viewModel.CloseSaleEditorCommand.Execute(null);
        viewModel.ConfirmDiscardSaleCommand.Execute(null);
        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        Assert.True(await viewModel.SelectExactBarcodeAsync("789", showNotFound: true));
        viewModel.AddProductCommand.Execute(null);
        viewModel.MoneyText = "12,00";
        await viewModel.FinalizeCommand.ExecuteAsync();

        Assert.Equal(2, apiClient.IdempotencyKeys.Count);
        Assert.NotEqual(apiClient.IdempotencyKeys[0], apiClient.IdempotencyKeys[1]);
    }

    [Fact]
    public async Task Payment_autocomplete_moves_untouched_value_and_keeps_manual_amounts()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient();
        using var viewModel = new SalesViewModel(apiClient, sessionContext)
        {
            SearchText = "789",
        };

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        await viewModel.SearchCommand.ExecuteAsync();
        viewModel.AddProductCommand.Execute(null);
        viewModel.OpenPaymentStepCommand.Execute(null);

        Assert.Equal("12,00", viewModel.MoneyText);

        viewModel.AutoCompletePaymentIfEmpty("debit");

        Assert.Equal("0,00", viewModel.MoneyText);
        Assert.Equal("12,00", viewModel.DebitText);

        viewModel.DebitText = "3,00";
        viewModel.AutoCompletePaymentIfEmpty("pix");

        Assert.Equal("3,00", viewModel.DebitText);
        Assert.Equal("9,00", viewModel.PixText);
        Assert.Equal("0,00", viewModel.MoneyText);

        viewModel.AutoCompletePaymentIfEmpty("credit");

        Assert.Equal("3,00", viewModel.DebitText);
        Assert.Equal("0,00", viewModel.PixText);
        Assert.Equal("9,00", viewModel.CreditText);
    }

    [Fact]
    public async Task Opening_sale_with_closed_cash_prompts_before_editor()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient
        {
            CashRegisterSnapshot = new CashRegisterSnapshot(),
        };
        using var viewModel = new SalesViewModel(apiClient, sessionContext);

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();

        Assert.False(viewModel.IsSaleEditorOpen);
        Assert.True(viewModel.IsOpenCashPromptOpen);
        Assert.Contains("caixa", viewModel.ErrorMessage, StringComparison.OrdinalIgnoreCase);
        Assert.Equal("0,00", viewModel.OpeningCashText);
    }

    [Fact]
    public async Task Confirm_cash_prompt_opens_register_and_sale_editor()
    {
        var sessionContext = SessionContext();
        var apiClient = new StubApiClient
        {
            CashRegisterSnapshot = new CashRegisterSnapshot(),
        };
        using var viewModel = new SalesViewModel(apiClient, sessionContext);

        await viewModel.OpenSaleEditorCommand.ExecuteAsync();
        viewModel.OpeningCashText = "12,50";

        await viewModel.ConfirmOpenCashBeforeSaleCommand.ExecuteAsync();

        Assert.Equal(12.50m, apiClient.LastOpeningAmount);
        Assert.Equal(1, apiClient.OpenCashRegisterCalls);
        Assert.True(viewModel.IsSaleEditorOpen);
        Assert.False(viewModel.IsOpenCashPromptOpen);
        Assert.True(viewModel.IsProductStepOpen);
    }

    private static async Task WaitUntilAsync(Func<bool> predicate)
    {
        for (var attempt = 0; attempt < 30; attempt++)
        {
            if (predicate())
            {
                return;
            }

            await Task.Delay(50);
        }
    }

    private static AppSessionContext SessionContext()
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
                Permissions = new Dictionary<string, bool> { ["can_manage_sales"] = true },
            },
            Company = new CompanyIdentity { Id = 2, Name = "Adega JF" },
        });
        return context;
    }

    private static CashRegisterSnapshot CreateOpenCashRegisterSnapshot(decimal openingAmount = 0) =>
        new()
        {
            CurrentRegister = new CashRegisterRecord
            {
                Id = 12,
                Status = "open",
                OpenedAt = "2026-07-22T10:00:00-03:00",
                ResponsibleUser = "operador",
                OpeningAmount = openingAmount,
            },
        };

    private sealed class StubApiClient : IGirofyApiClient
    {
        private int _saleAttempts;

        public bool FailFirstSaleAttempt { get; init; }

        public List<string> IdempotencyKeys { get; } = [];

        public decimal LastDiscountAmount { get; private set; }

        public IReadOnlyList<SalePaymentRequest> LastPayments { get; private set; } = [];

        public IReadOnlyList<DashboardRecentSale> DashboardRecentSales { get; init; } = [];

        public IReadOnlyList<CatalogProduct>? CatalogProducts { get; init; }

        public int LastCatalogPerPage { get; private set; }

        public Exception? HistoryException { get; init; }

        public int HistoryCalls { get; private set; }

        public List<int> RequestedHistoryPages { get; } = [];

        public Dictionary<int, SaleReceipt> SaleDetails { get; } = [];

        public CashRegisterSnapshot CashRegisterSnapshot { get; set; } = CreateOpenCashRegisterSnapshot();

        public int OpenCashRegisterCalls { get; private set; }

        public decimal? LastOpeningAmount { get; private set; }

        public Task<CatalogProductList> GetCatalogProductsAsync(
            string accessToken,
            string search,
            int? categoryId,
            string activeFilter,
            string sort,
            int page,
            int perPage,
            CancellationToken cancellationToken)
        {
            LastCatalogPerPage = perPage;
            var products = CatalogProducts ??
            [
                new CatalogProduct
                {
                    Id = 10,
                    Name = "Coca Zero 2L",
                    Barcode = "790",
                    SalePrice = 13m,
                    StockQuantity = 5,
                    Active = true,
                },
                new CatalogProduct
                {
                    Id = 9,
                    Name = "Coca Cola 2L",
                    Barcode = "789",
                    SalePrice = 12m,
                    StockQuantity = 8,
                    Active = true,
                },
            ];
            return Task.FromResult(new CatalogProductList
            {
                Items = products,
                Pagination = new CatalogPagination
                {
                    Page = 1,
                    PerPage = 30,
                    Total = products.Count,
                    TotalPages = 1,
                },
            });
        }

        public Task<CatalogProduct?> GetCatalogProductByBarcodeAsync(
            string accessToken,
            string barcode,
            CancellationToken cancellationToken)
        {
            if (string.Equals(barcode, "inactive", StringComparison.OrdinalIgnoreCase))
            {
                return Task.FromResult<CatalogProduct?>(new CatalogProduct
                {
                    Id = 99,
                    Name = "Produto inativo",
                    Barcode = "inactive",
                    Active = false,
                });
            }

            var products = CatalogProducts ??
            [
                new CatalogProduct { Id = 10, Name = "Coca Zero 2L", Barcode = "790", SalePrice = 13m, StockQuantity = 5, Active = true },
                new CatalogProduct { Id = 9, Name = "Coca Cola 2L", Barcode = "789", SalePrice = 12m, StockQuantity = 8, Active = true },
            ];
            return Task.FromResult<CatalogProduct?>(products.SingleOrDefault(
                product => string.Equals(product.Barcode, barcode, StringComparison.Ordinal)));
        }

        public Task<SaleReceipt> CreateSaleAsync(
            string accessToken,
            string idempotencyKey,
            IReadOnlyList<SaleLineRequest> items,
            decimal discountAmount,
            IReadOnlyList<SalePaymentRequest> payments,
            CancellationToken cancellationToken)
        {
            _saleAttempts++;
            IdempotencyKeys.Add(idempotencyKey);
            LastDiscountAmount = discountAmount;
            LastPayments = payments;
            if (FailFirstSaleAttempt && _saleAttempts == 1)
            {
                return Task.FromException<SaleReceipt>(new HttpRequestException("offline"));
            }

            return Task.FromResult(new SaleReceipt
            {
                Id = 42,
                IdempotencyKey = idempotencyKey,
                CashRegisterId = 8,
                Subtotal = 24m,
                DiscountAmount = 2m,
                FinalAmount = 22m,
                PaidAmount = 22m,
                Payments =
                [
                    new SaleReceiptPayment { Method = "money", Label = "Dinheiro", Amount = 10m },
                    new SaleReceiptPayment { Method = "pix", Label = "Pix", Amount = 12m },
                ],
            });
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
            Task.FromResult(new DashboardSnapshot
            {
                RecentSales = DashboardRecentSales,
            });

        public Task<SalesHistorySnapshot> GetTodaySalesHistoryAsync(
            string accessToken,
            int page,
            int perPage,
            CancellationToken cancellationToken)
        {
            HistoryCalls++;
            RequestedHistoryPages.Add(page);
            var pageSales = DashboardRecentSales
                .Skip((page - 1) * perPage)
                .Take(perPage)
                .ToArray();
            return HistoryException is null
                ? Task.FromResult(new SalesHistorySnapshot
            {
                Sales = pageSales,
                Page = page,
                PerPage = perPage,
                Total = DashboardRecentSales.Count,
                HasMore = page * perPage < DashboardRecentSales.Count,
            })
                : Task.FromException<SalesHistorySnapshot>(HistoryException);
        }

        public Task<SaleReceipt> GetSaleDetailAsync(
            string accessToken,
            int saleId,
            CancellationToken cancellationToken) =>
            SaleDetails.TryGetValue(saleId, out var receipt)
                ? Task.FromResult(receipt)
                : Task.FromException<SaleReceipt>(new InvalidOperationException("Venda não encontrada."));

        public Task<CashRegisterSnapshot> GetCashRegisterSummaryAsync(
            string accessToken,
            CancellationToken cancellationToken) =>
            Task.FromResult(CashRegisterSnapshot);

        public Task<CashRegisterSnapshot> OpenCashRegisterAsync(
            string accessToken,
            decimal openingAmount,
            CancellationToken cancellationToken)
        {
            OpenCashRegisterCalls++;
            LastOpeningAmount = openingAmount;
            CashRegisterSnapshot = CreateOpenCashRegisterSnapshot(openingAmount);
            return Task.FromResult(CashRegisterSnapshot);
        }

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
    }
}
