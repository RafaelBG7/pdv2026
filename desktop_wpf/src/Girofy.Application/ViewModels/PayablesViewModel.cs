using System.Collections.ObjectModel;
using System.Globalization;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class PayablesViewModel : ObservableObject, IDisposable
{
    private static readonly string[] DefaultCategories =
    [
        "Aluguel",
        "Luz",
        "Água",
        "Internet",
        "Fornecedor",
        "Impostos",
        "Outros",
    ];

    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private string _searchText = string.Empty;
    private string _selectedCategory = "Todas";
    private CatalogFilterOption _selectedStatus = new("open", "Abertas");
    private string _startDateText = string.Empty;
    private string _endDateText = string.Empty;
    private string _description = string.Empty;
    private string _categoryText = "Outros";
    private string _amountText = "0,00";
    private string _dueDateText = DateTime.Today.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
    private string _notes = string.Empty;
    private string _errorMessage = string.Empty;
    private string _successMessage = string.Empty;
    private bool _isBusy;
    private bool _isInitialized;
    private PayableSummary _summary = new();

    public PayablesViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        RefreshCommand = new AsyncRelayCommand(RefreshAsync, () => IsAvailable && !IsBusy);
        ApplyFiltersCommand = new AsyncRelayCommand(LoadAsync, () => IsAvailable && !IsBusy);
        CreatePayableCommand = new AsyncRelayCommand(CreatePayableAsync, () => CanManagePayables && !IsBusy);
        ClearFormCommand = new RelayCommand(ClearForm);
        PayPayableCommand = new RelayCommand<PayableRecord>(
            payable => _ = PayAsync(payable, CancellationToken.None),
            payable => CanManagePayables && !IsBusy && payable.CanPay);
        ReopenPayableCommand = new RelayCommand<PayableRecord>(
            payable => _ = ReopenAsync(payable, CancellationToken.None),
            payable => CanManagePayables && !IsBusy && payable.CanReopen);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<PayableRecord> Payables { get; } = [];

    public ObservableCollection<CatalogFilterOption> StatusOptions { get; } = [];

    public ObservableCollection<string> Categories { get; } = [];

    public PayableSummary Summary
    {
        get => _summary;
        private set => SetProperty(ref _summary, value);
    }

    public string SearchText
    {
        get => _searchText;
        set => SetProperty(ref _searchText, value);
    }

    public CatalogFilterOption SelectedStatus
    {
        get => _selectedStatus;
        set => SetProperty(ref _selectedStatus, value);
    }

    public string SelectedCategory
    {
        get => _selectedCategory;
        set => SetProperty(ref _selectedCategory, value);
    }

    public string StartDateText
    {
        get => _startDateText;
        set => SetProperty(ref _startDateText, value);
    }

    public string EndDateText
    {
        get => _endDateText;
        set => SetProperty(ref _endDateText, value);
    }

    public string Description
    {
        get => _description;
        set => SetProperty(ref _description, value);
    }

    public string CategoryText
    {
        get => _categoryText;
        set => SetProperty(ref _categoryText, value);
    }

    public string AmountText
    {
        get => _amountText;
        set => SetProperty(ref _amountText, value);
    }

    public string DueDateText
    {
        get => _dueDateText;
        set => SetProperty(ref _dueDateText, value);
    }

    public string Notes
    {
        get => _notes;
        set => SetProperty(ref _notes, value);
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

    public bool HasSuccess => !string.IsNullOrWhiteSpace(SuccessMessage);

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetProperty(ref _isBusy, value))
            {
                NotifyCommandState();
            }
        }
    }

    public bool CanManagePayables => HasPermission("can_manage_payables");

    public bool IsAvailable => CanManagePayables;

    public bool HasItems => Payables.Count > 0;

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand ApplyFiltersCommand { get; }

    public AsyncRelayCommand CreatePayableCommand { get; }

    public RelayCommand ClearFormCommand { get; }

    public RelayCommand<PayableRecord> PayPayableCommand { get; }

    public RelayCommand<PayableRecord> ReopenPayableCommand { get; }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_sessionContext.Current is null || !IsAvailable)
        {
            Reset();
            return;
        }

        if (_isInitialized)
        {
            return;
        }

        await LoadAsync(cancellationToken);
    }

    private void HandleSessionChanged(object? sender, EventArgs e) => Reset();

    private async Task RefreshAsync(CancellationToken cancellationToken) => await LoadAsync(cancellationToken);

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        if (!IsAvailable)
        {
            Reset();
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var snapshot = await _apiClient.GetPayablesAsync(
                session.AccessToken,
                new PayablesQuery(
                    SearchText,
                    SelectedStatus.Value,
                    SelectedCategory == "Todas" ? "all" : SelectedCategory,
                    NormalizeDate(StartDateText),
                    NormalizeDate(EndDateText)),
                cancellationToken);

            Payables.Clear();
            foreach (var payable in snapshot.Items)
            {
                Payables.Add(payable);
            }

            Summary = snapshot.Summary;
            SyncStatusOptions(snapshot.StatusOptions);
            SyncCategories(snapshot.Categories);
            OnPropertyChanged(nameof(HasItems));
            _isInitialized = true;
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

    private async Task CreatePayableAsync(CancellationToken cancellationToken)
    {
        if (!TryBuildRequest(out var request))
        {
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var payable = await _apiClient.CreatePayableAsync(
                session.AccessToken,
                request,
                cancellationToken);
            SuccessMessage = $"Conta \"{payable.Description}\" cadastrada.";
            ClearForm();
            await LoadCoreAfterMutationAsync(cancellationToken);
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

    private async Task PayAsync(PayableRecord payable, CancellationToken cancellationToken)
    {
        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            await _apiClient.PayPayableAsync(session.AccessToken, payable.Id, cancellationToken);
            SuccessMessage = $"Conta \"{payable.Description}\" marcada como paga.";
            await LoadCoreAfterMutationAsync(cancellationToken);
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

    private async Task ReopenAsync(PayableRecord payable, CancellationToken cancellationToken)
    {
        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            await _apiClient.ReopenPayableAsync(session.AccessToken, payable.Id, cancellationToken);
            SuccessMessage = $"Conta \"{payable.Description}\" reaberta.";
            await LoadCoreAfterMutationAsync(cancellationToken);
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

    private async Task LoadCoreAfterMutationAsync(CancellationToken cancellationToken)
    {
        _isInitialized = false;
        await LoadAsync(cancellationToken);
    }

    private void SyncStatusOptions(IReadOnlyList<CatalogFilterOption> source)
    {
        var selectedValue = SelectedStatus.Value;
        StatusOptions.Clear();
        IReadOnlyList<CatalogFilterOption> options = source.Count > 0
            ? source
            : new CatalogFilterOption[]
            {
                new CatalogFilterOption("open", "Abertas"),
                new CatalogFilterOption("overdue", "Vencidas"),
                new CatalogFilterOption("due_today", "Vencem hoje"),
                new CatalogFilterOption("near_due", "Próximas"),
                new CatalogFilterOption("paid", "Pagas"),
                new CatalogFilterOption("all", "Todas"),
            };

        foreach (var option in options)
        {
            StatusOptions.Add(option);
        }
        SelectedStatus = StatusOptions.FirstOrDefault(option => option.Value == selectedValue)
            ?? StatusOptions.FirstOrDefault(option => option.Value == "open")
            ?? StatusOptions[0];
    }

    private void SyncCategories(IReadOnlyList<string> source)
    {
        var selected = SelectedCategory;
        var categoryNames = source
            .Concat(DefaultCategories)
            .Where(category => !string.IsNullOrWhiteSpace(category))
            .Distinct(StringComparer.CurrentCultureIgnoreCase)
            .OrderBy(category => category, StringComparer.CurrentCultureIgnoreCase)
            .ToList();

        Categories.Clear();
        Categories.Add("Todas");
        foreach (var category in categoryNames)
        {
            Categories.Add(category);
        }
        SelectedCategory = Categories.FirstOrDefault(category =>
            string.Equals(category, selected, StringComparison.CurrentCultureIgnoreCase)) ?? "Todas";
    }

    private bool TryBuildRequest(out PayableMutationRequest request)
    {
        request = new PayableMutationRequest(string.Empty, string.Empty, 0, string.Empty, string.Empty);
        if (string.IsNullOrWhiteSpace(Description))
        {
            ErrorMessage = "Informe a descricao da conta.";
            return false;
        }
        if (!TryParseMoney(AmountText, out var amount) || amount <= 0)
        {
            ErrorMessage = "Informe um valor maior que zero.";
            return false;
        }
        var dueDate = NormalizeDate(DueDateText);
        if (dueDate is null)
        {
            ErrorMessage = "Informe um vencimento valido.";
            return false;
        }

        var category = string.IsNullOrWhiteSpace(CategoryText) ? "Outros" : CategoryText.Trim();
        request = new PayableMutationRequest(
            Description.Trim(),
            category,
            amount,
            dueDate,
            Notes.Trim());
        return true;
    }

    private static string? NormalizeDate(string value)
    {
        var text = value.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        var formats = new[] { "yyyy-MM-dd", "dd/MM/yyyy", "d/M/yyyy" };
        return DateTime.TryParseExact(
            text,
            formats,
            CultureInfo.GetCultureInfo("pt-BR"),
            DateTimeStyles.None,
            out var parsed)
            ? parsed.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture)
            : null;
    }

    private static bool TryParseMoney(string value, out decimal amount)
    {
        var text = value.Trim();
        var styles = NumberStyles.Number | NumberStyles.AllowCurrencySymbol;
        return (decimal.TryParse(text, styles, CultureInfo.GetCultureInfo("pt-BR"), out amount) ||
                decimal.TryParse(text, styles, CultureInfo.InvariantCulture, out amount)) &&
            amount >= 0;
    }

    private bool HasPermission(string permission)
    {
        var permissions = _sessionContext.Current?.User.Permissions;
        return permissions is not null &&
            permissions.TryGetValue(permission, out var allowed) &&
            allowed;
    }

    private AuthSession RequireSession() => _sessionContext.Current
        ?? throw new GirofyApiException(
            "Sua sessao terminou. Entre novamente para continuar.",
            "session_required",
            401);

    private void SetSafeError(Exception exception)
    {
        ErrorMessage = exception switch
        {
            GirofyApiException apiException => apiException.Message,
            TaskCanceledException => "O servidor demorou para responder. Tente novamente.",
            HttpRequestException => "Nao foi possivel consultar as contas agora.",
            _ => "Nao foi possivel carregar contas a pagar. Tente novamente.",
        };
    }

    private void ClearMessages()
    {
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
    }

    private void ClearForm()
    {
        Description = string.Empty;
        CategoryText = "Outros";
        AmountText = "0,00";
        DueDateText = DateTime.Today.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        Notes = string.Empty;
    }

    private void NotifyCommandState()
    {
        OnPropertyChanged(nameof(CanManagePayables));
        OnPropertyChanged(nameof(IsAvailable));
        RefreshCommand.NotifyCanExecuteChanged();
        ApplyFiltersCommand.NotifyCanExecuteChanged();
        CreatePayableCommand.NotifyCanExecuteChanged();
        PayPayableCommand.NotifyCanExecuteChanged();
        ReopenPayableCommand.NotifyCanExecuteChanged();
    }

    private void Reset()
    {
        Payables.Clear();
        StatusOptions.Clear();
        Categories.Clear();
        Summary = new PayableSummary();
        SearchText = string.Empty;
        SelectedCategory = "Todas";
        SelectedStatus = new CatalogFilterOption("open", "Abertas");
        StartDateText = string.Empty;
        EndDateText = string.Empty;
        ClearForm();
        ClearMessages();
        _isInitialized = false;
        OnPropertyChanged(nameof(HasItems));
        NotifyCommandState();
    }

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;
}
