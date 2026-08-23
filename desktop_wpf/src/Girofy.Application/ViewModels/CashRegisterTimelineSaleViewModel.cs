using Girofy.Application.Models;
using Girofy.Application.Mvvm;
using System.Globalization;

namespace Girofy.Application.ViewModels;

public sealed class CashRegisterTimelineSaleViewModel : ObservableObject
{
    private readonly Func<CashRegisterTimelineSaleViewModel, CancellationToken, Task> _loadDetail;
    private SaleReceipt? _detail;
    private bool _isExpanded;
    private bool _isLoading;
    private string _errorMessage = string.Empty;

    public CashRegisterTimelineSaleViewModel(
        CashRegisterTimelineSale summary,
        bool canViewFinancials,
        Func<CashRegisterTimelineSaleViewModel, CancellationToken, Task> loadDetail)
    {
        Summary = summary;
        CanViewFinancials = canViewFinancials;
        _loadDetail = loadDetail;
        RetryCommand = new AsyncRelayCommand(LoadAsync);
    }

    public CashRegisterTimelineSale Summary { get; }

    public int Id => Summary.Id;

    public string Number => Summary.Number;

    public string HeaderText => Summary.HeaderText;

    public string PaymentsText => Summary.PaymentsText;

    public string FinalAmountText => Detail?.FinalAmountText ?? Summary.FinalAmountText;

    public string BalanceBeforeSaleText => Summary.BalanceBeforeSaleText;

    public string BalanceAfterSaleText => Summary.BalanceAfterSaleText;

    public string SaleNumberText => string.IsNullOrWhiteSpace(Summary.Number)
        ? $"Venda #{Summary.Id}"
        : $"Venda {Summary.Number}";

    public string DateTimeText
    {
        get
        {
            if (!string.IsNullOrWhiteSpace(Summary.CreatedAt))
            {
                return BrazilianDateFormatting.FormatTimestamp(Summary.CreatedAt);
            }

            var date = BrazilianDateFormatting.NormalizeDateInput(Summary.Date);
            var time = NormalizeTime(Summary.Time);
            return date is null
                ? (string.IsNullOrWhiteSpace(time) ? "Data não informada" : time)
                : string.IsNullOrWhiteSpace(time) ? date : $"{date} às {time}";
        }
    }

    public string SellerText => string.IsNullOrWhiteSpace(Summary.Seller)
        ? "Não informado"
        : Summary.Seller;

    private static string NormalizeTime(string? value) =>
        TimeOnly.TryParseExact(
            value,
            ["HH:mm", "HH:mm:ss"],
            CultureInfo.InvariantCulture,
            DateTimeStyles.None,
            out var time)
                ? time.ToString("HH:mm", CultureInfo.InvariantCulture)
                : value?.Trim() ?? string.Empty;

    public SaleReceipt? Detail
    {
        get => _detail;
        private set
        {
            if (!SetProperty(ref _detail, value))
            {
                return;
            }

            OnPropertyChanged(nameof(HasDetail));
            OnPropertyChanged(nameof(Items));
            OnPropertyChanged(nameof(Payments));
            OnPropertyChanged(nameof(FinalAmountText));
            OnPropertyChanged(nameof(StatusText));
            OnPropertyChanged(nameof(IsCancelled));
            OnPropertyChanged(nameof(HasCancellationDetails));
            OnPropertyChanged(nameof(CancelledByText));
            OnPropertyChanged(nameof(CancelledAtText));
            OnPropertyChanged(nameof(CancellationReasonText));
            OnPropertyChanged(nameof(SubtotalText));
            OnPropertyChanged(nameof(DiscountAmountText));
            OnPropertyChanged(nameof(PaidAmountText));
            OnPropertyChanged(nameof(ChangeAmountText));
            OnPropertyChanged(nameof(HasChange));
            OnPropertyChanged(nameof(HasProfit));
            OnPropertyChanged(nameof(ProfitAmountText));
        }
    }

    public IReadOnlyList<SaleReceiptItem> Items => Detail?.Items ?? [];

    public IReadOnlyList<SaleReceiptPayment> Payments => Detail?.Payments ?? [];

    public bool HasDetail => Detail is not null;

    public bool IsExpanded
    {
        get => _isExpanded;
        set => SetProperty(ref _isExpanded, value);
    }

    public bool IsLoading
    {
        get => _isLoading;
        private set => SetProperty(ref _isLoading, value);
    }

    public string ErrorMessage
    {
        get => _errorMessage;
        private set
        {
            if (SetProperty(ref _errorMessage, value))
            {
                OnPropertyChanged(nameof(HasError));
            }
        }
    }

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    public bool CanViewFinancials { get; }

    public string StatusText => Detail?.StatusText ?? Summary.StatusText.ToUpperInvariant();

    public bool IsCancelled => Detail?.IsCancelled ?? Summary.IsCancelled;

    public string SubtotalText => Detail?.SubtotalText ?? "—";

    public string DiscountAmountText => Detail?.DiscountAmountText ?? Summary.DiscountAmountText;

    public string PaidAmountText => Detail?.PaidAmountText ?? "—";

    public string ChangeAmountText => Detail?.ChangeAmountText ?? "—";

    public bool HasChange => Detail?.ChangeAmount > 0;

    public bool HasProfit => CanViewFinancials && Detail is not null;

    public string ProfitAmountText => DashboardFormatting.Money(
        Detail?.Items.Sum(item => item.ProfitAmount) ?? 0m);

    public bool HasCancellationDetails => IsCancelled &&
        (!string.IsNullOrWhiteSpace(Detail?.CancelledByUserName) ||
         !string.IsNullOrWhiteSpace(Detail?.CancelledAt) ||
         !string.IsNullOrWhiteSpace(Detail?.CancellationReason));

    public string CancelledByText => string.IsNullOrWhiteSpace(Detail?.CancelledByUserName)
        ? "Não informado"
        : Detail.CancelledByUserName;

    public string CancelledAtText => Detail?.CancelledAtText ?? string.Empty;

    public string CancellationReasonText => string.IsNullOrWhiteSpace(Detail?.CancellationReason)
        ? "Não informado"
        : Detail.CancellationReason;

    public AsyncRelayCommand RetryCommand { get; }

    public Task EnsureDetailLoadedAsync(CancellationToken cancellationToken = default) =>
        HasDetail || IsLoading ? Task.CompletedTask : LoadAsync(cancellationToken);

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        IsLoading = true;
        ErrorMessage = string.Empty;
        try
        {
            await _loadDetail(this, cancellationToken);
        }
        finally
        {
            IsLoading = false;
        }
    }

    internal void ApplyDetail(SaleReceipt detail)
    {
        Detail = detail;
        ErrorMessage = string.Empty;
    }

    internal void ApplyError(string message)
    {
        Detail = null;
        ErrorMessage = message;
    }
}
