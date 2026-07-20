using System.Globalization;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class CashRegisterViewModel : ObservableObject, IDisposable
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private CashRegisterSnapshot? _snapshot;
    private CashRegisterRecord? _selectedRegister;
    private CashRegisterDetailSnapshot? _detailSnapshot;
    private string _openingAmountText = "0,00";
    private string _closingAmountText = string.Empty;
    private string _errorMessage = string.Empty;
    private string _successMessage = string.Empty;
    private bool _isBusy;

    public CashRegisterViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        RefreshCommand = new AsyncRelayCommand(LoadAsync);
        OpenCommand = new AsyncRelayCommand(OpenAsync);
        CloseCommand = new AsyncRelayCommand(CloseAsync);
        LoadRegisterDetailCommand = new AsyncRelayCommand(
            LoadSelectedRegisterDetailAsync,
            () => SelectedRegister is not null);
        ClearRegisterDetailCommand = new AsyncRelayCommand(ClearRegisterDetailAsync);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public CashRegisterSnapshot? Snapshot
    {
        get => _snapshot;
        private set
        {
            if (!SetProperty(ref _snapshot, value))
            {
                return;
            }
            OnPropertyChanged(nameof(CurrentRegister));
            OnPropertyChanged(nameof(RecentRegisters));
            OnPropertyChanged(nameof(HasOpenRegister));
            OnPropertyChanged(nameof(HasNoOpenRegister));
            OnPropertyChanged(nameof(CanViewFinancials));
            if (SelectedRegister is not null &&
                RecentRegisters.All(item => item.Id != SelectedRegister.Id) &&
                CurrentRegister?.Id != SelectedRegister.Id)
            {
                SelectedRegister = null;
            }
        }
    }

    public CashRegisterRecord? CurrentRegister => Snapshot?.CurrentRegister;

    public IReadOnlyList<CashRegisterRecord> RecentRegisters => Snapshot?.RecentRegisters ?? [];

    public CashRegisterRecord? SelectedRegister
    {
        get => _selectedRegister;
        set
        {
            if (SetProperty(ref _selectedRegister, value))
            {
                LoadRegisterDetailCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public CashRegisterDetailSnapshot? DetailSnapshot
    {
        get => _detailSnapshot;
        private set
        {
            if (!SetProperty(ref _detailSnapshot, value))
            {
                return;
            }
            OnPropertyChanged(nameof(DetailRegister));
            OnPropertyChanged(nameof(Timeline));
            OnPropertyChanged(nameof(HasDetail));
            OnPropertyChanged(nameof(HasTimeline));
            OnPropertyChanged(nameof(HasNoTimeline));
        }
    }

    public CashRegisterRecord? DetailRegister => DetailSnapshot?.CashRegister;

    public IReadOnlyList<CashRegisterTimelineSale> Timeline => DetailSnapshot?.Timeline ?? [];

    public bool HasDetail => DetailSnapshot?.CashRegister is not null;

    public bool HasTimeline => Timeline.Count > 0;

    public bool HasNoTimeline => HasDetail && !HasTimeline;

    public bool HasOpenRegister => CurrentRegister is not null;

    public bool HasNoOpenRegister => !HasOpenRegister;

    public bool CanViewFinancials => Snapshot?.Permissions.CanViewFinancials ?? false;

    public bool IsAvailable
    {
        get
        {
            var permissions = _sessionContext.Current?.User.Permissions;
            return permissions is not null &&
                permissions.TryGetValue("can_manage_cash_register", out var allowed) &&
                allowed;
        }
    }

    public string OpeningAmountText
    {
        get => _openingAmountText;
        set => SetProperty(ref _openingAmountText, value);
    }

    public string ClosingAmountText
    {
        get => _closingAmountText;
        set => SetProperty(ref _closingAmountText, value);
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

    public string SuccessMessage
    {
        get => _successMessage;
        private set
        {
            if (SetProperty(ref _successMessage, value))
            {
                OnPropertyChanged(nameof(HasSuccess));
            }
        }
    }

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    public bool HasSuccess => !string.IsNullOrWhiteSpace(SuccessMessage);

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand OpenCommand { get; }

    public AsyncRelayCommand CloseCommand { get; }

    public AsyncRelayCommand LoadRegisterDetailCommand { get; }

    public AsyncRelayCommand ClearRegisterDetailCommand { get; }

    public Task InitializeAsync(CancellationToken cancellationToken = default) =>
        LoadAsync(cancellationToken);

    private void HandleSessionChanged(object? sender, EventArgs e)
    {
        Reset();
        OnPropertyChanged(nameof(IsAvailable));
    }

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !IsAvailable)
        {
            Reset();
            return;
        }

        IsBusy = true;
        ClearMessages();
        try
        {
            var snapshot = await _apiClient.GetCashRegisterSummaryAsync(
                session.AccessToken,
                cancellationToken);
            ApplySnapshotIfCurrent(session, snapshot);
            DetailSnapshot = null;
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task OpenAsync(CancellationToken cancellationToken)
    {
        if (HasOpenRegister)
        {
            ErrorMessage = "Já existe um caixa aberto.";
            return;
        }
        if (!TryParseMoney(OpeningAmountText, out var openingAmount))
        {
            ErrorMessage = "Informe um valor inicial válido, como 100,00.";
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var snapshot = await _apiClient.OpenCashRegisterAsync(
                session.AccessToken,
                openingAmount,
                cancellationToken);
            ApplySnapshotIfCurrent(session, snapshot);
            OpeningAmountText = "0,00";
            ClosingAmountText = snapshot.CurrentRegister?.ExpectedAmount is decimal expected
                ? expected.ToString("N2", BrazilianCulture)
                : string.Empty;
            SuccessMessage = "Caixa aberto com sucesso.";
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task CloseAsync(CancellationToken cancellationToken)
    {
        var current = CurrentRegister;
        if (current is null)
        {
            ErrorMessage = "Não há caixa aberto para fechar.";
            return;
        }
        if (!TryParseMoney(ClosingAmountText, out var closingAmount))
        {
            ErrorMessage = "Informe o valor contado no caixa, como 125,00.";
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var snapshot = await _apiClient.CloseCashRegisterAsync(
                session.AccessToken,
                current.Id,
                closingAmount,
                cancellationToken);
            ApplySnapshotIfCurrent(session, snapshot);
            ClosingAmountText = string.Empty;
            SuccessMessage = "Caixa fechado com sucesso.";
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LoadSelectedRegisterDetailAsync(CancellationToken cancellationToken)
    {
        var selected = SelectedRegister;
        if (selected is null)
        {
            ErrorMessage = "Selecione um caixa para ver os detalhes.";
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var detail = await _apiClient.GetCashRegisterDetailAsync(
                session.AccessToken,
                selected.Id,
                cancellationToken);
            if (string.Equals(
                _sessionContext.Current?.AccessToken,
                session.AccessToken,
                StringComparison.Ordinal))
            {
                DetailSnapshot = detail;
                SuccessMessage = $"Detalhes do caixa #{selected.Id} carregados.";
            }
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            IsBusy = false;
        }
    }

    private Task ClearRegisterDetailAsync(CancellationToken cancellationToken)
    {
        DetailSnapshot = null;
        SuccessMessage = string.Empty;
        return Task.CompletedTask;
    }

    private AuthSession RequireSession() => _sessionContext.Current
        ?? throw new GirofyApiException(
            "Sua sessão terminou. Entre novamente para continuar.",
            "session_required",
            401);

    private void ApplySnapshotIfCurrent(AuthSession session, CashRegisterSnapshot snapshot)
    {
        if (!string.Equals(
            _sessionContext.Current?.AccessToken,
            session.AccessToken,
            StringComparison.Ordinal))
        {
            return;
        }
        Snapshot = snapshot;
        if (snapshot.CurrentRegister?.ExpectedAmount is decimal expected &&
            string.IsNullOrWhiteSpace(ClosingAmountText))
        {
            ClosingAmountText = expected.ToString("N2", BrazilianCulture);
        }
    }

    private static bool TryParseMoney(string text, out decimal value)
    {
        var normalized = (text ?? string.Empty).Trim();
        var culture = normalized.Contains(',') ? BrazilianCulture : CultureInfo.InvariantCulture;
        return decimal.TryParse(
            normalized,
            NumberStyles.Number,
            culture,
            out value) && value >= 0;
    }

    private void SetSafeError(Exception exception)
    {
        ErrorMessage = exception switch
        {
            GirofyApiException apiException => apiException.Message,
            TaskCanceledException => "O servidor demorou para responder. Tente novamente.",
            HttpRequestException => "Não foi possível consultar o caixa agora.",
            _ => "Não foi possível concluir a operação do caixa. Tente novamente.",
        };
    }

    private void ClearMessages()
    {
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
    }

    private void Reset()
    {
        Snapshot = null;
        SelectedRegister = null;
        DetailSnapshot = null;
        OpeningAmountText = "0,00";
        ClosingAmountText = string.Empty;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        IsBusy = false;
    }

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;
}
