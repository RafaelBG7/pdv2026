using System.Collections.ObjectModel;
using System.Globalization;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class AuditViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private string _searchText = string.Empty;
    private string _startDateText = string.Empty;
    private string _endDateText = string.Empty;
    private string _errorMessage = string.Empty;
    private bool _isBusy;
    private bool _isInitialized;
    private int _page = 1;
    private int _totalPages;
    private AuditUserOption _selectedUser = new() { Id = 0, Label = "Todos" };
    private CatalogFilterOption _selectedAction = new("all", "Todas");
    private CatalogFilterOption _selectedEntity = new("all", "Todos");
    private CatalogFilterOption _selectedMethod = new("all", "Todos");
    private AuditLogSummary _summary = new();

    public AuditViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        SearchCommand = new AsyncRelayCommand(SearchAsync, () => IsAvailable && !IsBusy);
        RefreshCommand = new AsyncRelayCommand(RefreshAsync, () => IsAvailable && !IsBusy);
        ClearFiltersCommand = new AsyncRelayCommand(ClearFiltersAsync, () => IsAvailable && !IsBusy);
        PreviousPageCommand = new AsyncRelayCommand(PreviousPageAsync, () => CanGoPrevious);
        NextPageCommand = new AsyncRelayCommand(NextPageAsync, () => CanGoNext);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<AuditLogRecord> Logs { get; } = [];

    public ObservableCollection<AuditUserOption> Users { get; } = [];

    public ObservableCollection<CatalogFilterOption> Actions { get; } = [];

    public ObservableCollection<CatalogFilterOption> Entities { get; } = [];

    public ObservableCollection<CatalogFilterOption> Methods { get; } = [];

    public AuditLogSummary Summary
    {
        get => _summary;
        private set => SetProperty(ref _summary, value);
    }

    public string SearchText
    {
        get => _searchText;
        set => SetProperty(ref _searchText, value);
    }

    public AuditUserOption SelectedUser
    {
        get => _selectedUser;
        set => SetProperty(ref _selectedUser, value);
    }

    public CatalogFilterOption SelectedAction
    {
        get => _selectedAction;
        set => SetProperty(ref _selectedAction, value);
    }

    public CatalogFilterOption SelectedEntity
    {
        get => _selectedEntity;
        set => SetProperty(ref _selectedEntity, value);
    }

    public CatalogFilterOption SelectedMethod
    {
        get => _selectedMethod;
        set => SetProperty(ref _selectedMethod, value);
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

    public int Page
    {
        get => _page;
        private set
        {
            if (SetProperty(ref _page, value))
            {
                OnPropertyChanged(nameof(PageSummary));
                OnPropertyChanged(nameof(CanGoPrevious));
                OnPropertyChanged(nameof(CanGoNext));
            }
        }
    }

    public int TotalPages
    {
        get => _totalPages;
        private set
        {
            if (SetProperty(ref _totalPages, value))
            {
                OnPropertyChanged(nameof(PageSummary));
                OnPropertyChanged(nameof(CanGoNext));
            }
        }
    }

    public string PageSummary => TotalPages == 0 ? "Página 0 de 0" : $"Página {Page} de {TotalPages}";

    public bool CanGoPrevious => Page > 1 && !IsBusy;

    public bool CanGoNext => Page < TotalPages && !IsBusy;

    public bool CanViewAuditLogs => HasPermission("can_view_audit_logs");

    public bool IsAvailable => CanViewAuditLogs;

    public bool HasItems => Logs.Count > 0;

    public AsyncRelayCommand SearchCommand { get; }

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand ClearFiltersCommand { get; }

    public AsyncRelayCommand PreviousPageCommand { get; }

    public AsyncRelayCommand NextPageCommand { get; }

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

    private async Task SearchAsync(CancellationToken cancellationToken)
    {
        Page = 1;
        await LoadAsync(cancellationToken);
    }

    private async Task RefreshAsync(CancellationToken cancellationToken) => await LoadAsync(cancellationToken);

    private async Task ClearFiltersAsync(CancellationToken cancellationToken)
    {
        SearchText = string.Empty;
        StartDateText = string.Empty;
        EndDateText = string.Empty;
        SelectedUser = Users.FirstOrDefault() ?? new AuditUserOption { Id = 0, Label = "Todos" };
        SelectedAction = Actions.FirstOrDefault() ?? new CatalogFilterOption("all", "Todas");
        SelectedEntity = Entities.FirstOrDefault() ?? new CatalogFilterOption("all", "Todos");
        SelectedMethod = Methods.FirstOrDefault() ?? new CatalogFilterOption("all", "Todos");
        Page = 1;
        await LoadAsync(cancellationToken);
    }

    private async Task PreviousPageAsync(CancellationToken cancellationToken)
    {
        if (!CanGoPrevious)
        {
            return;
        }

        Page--;
        await LoadAsync(cancellationToken);
    }

    private async Task NextPageAsync(CancellationToken cancellationToken)
    {
        if (!CanGoNext)
        {
            return;
        }

        Page++;
        await LoadAsync(cancellationToken);
    }

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
            var result = await _apiClient.GetAuditLogsAsync(
                session.AccessToken,
                new AuditLogQuery(
                    SearchText,
                    SelectedUser.Id > 0 ? SelectedUser.Id : null,
                    SelectedAction.Value,
                    SelectedEntity.Value,
                    SelectedMethod.Value,
                    NormalizeDate(StartDateText),
                    NormalizeDate(EndDateText),
                    Page,
                    30),
                cancellationToken);

            Logs.Clear();
            foreach (var log in result.Items)
            {
                Logs.Add(log);
            }

            Summary = result.Summary;
            SyncUsers(result.Users);
            SyncFilterOptions(Actions, result.ActionOptions, "Todas", ref _selectedAction);
            SyncFilterOptions(Entities, result.EntityOptions, "Todos", ref _selectedEntity);
            SyncFilterOptions(Methods, result.MethodOptions, "Todos", ref _selectedMethod);
            OnPropertyChanged(nameof(SelectedAction));
            OnPropertyChanged(nameof(SelectedEntity));
            OnPropertyChanged(nameof(SelectedMethod));
            Page = result.Pagination.Page;
            TotalPages = result.Pagination.TotalPages;
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

    private void SyncUsers(IReadOnlyList<AuditUserOption> users)
    {
        var selectedId = SelectedUser.Id;
        Users.Clear();
        Users.Add(new AuditUserOption { Id = 0, Label = "Todos" });
        foreach (var user in users.OrderBy(user => user.Label, StringComparer.CurrentCultureIgnoreCase))
        {
            Users.Add(user);
        }
        SelectedUser = Users.FirstOrDefault(user => user.Id == selectedId) ?? Users[0];
    }

    private static void SyncFilterOptions(
        ObservableCollection<CatalogFilterOption> target,
        IReadOnlyList<CatalogFilterOption> source,
        string allLabel,
        ref CatalogFilterOption selected)
    {
        var selectedValue = selected.Value;
        target.Clear();
        target.Add(new CatalogFilterOption("all", allLabel));
        foreach (var option in source.OrderBy(option => option.Label, StringComparer.CurrentCultureIgnoreCase))
        {
            target.Add(option);
        }
        selected = target.FirstOrDefault(option => option.Value == selectedValue) ?? target[0];
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
            "Sua sessão terminou. Entre novamente para continuar.",
            "session_required",
            401);

    private static string NormalizeDate(string value)
    {
        var text = value.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            return string.Empty;
        }

        if (DateTime.TryParse(text, CultureInfo.GetCultureInfo("pt-BR"), DateTimeStyles.None, out var date) ||
            DateTime.TryParse(text, CultureInfo.InvariantCulture, DateTimeStyles.None, out date))
        {
            return date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        }

        return text;
    }

    private void SetSafeError(Exception exception)
    {
        ErrorMessage = exception switch
        {
            GirofyApiException apiException => apiException.Message,
            TaskCanceledException => "O servidor demorou para responder. Tente novamente.",
            HttpRequestException => "Não foi possível consultar a auditoria agora.",
            _ => "Não foi possível carregar a auditoria. Tente novamente.",
        };
    }

    private void ClearMessages() => ErrorMessage = string.Empty;

    private void NotifyCommandState()
    {
        OnPropertyChanged(nameof(CanGoPrevious));
        OnPropertyChanged(nameof(CanGoNext));
        OnPropertyChanged(nameof(CanViewAuditLogs));
        OnPropertyChanged(nameof(IsAvailable));
        SearchCommand.NotifyCanExecuteChanged();
        RefreshCommand.NotifyCanExecuteChanged();
        ClearFiltersCommand.NotifyCanExecuteChanged();
        PreviousPageCommand.NotifyCanExecuteChanged();
        NextPageCommand.NotifyCanExecuteChanged();
    }

    private void Reset()
    {
        Logs.Clear();
        OnPropertyChanged(nameof(HasItems));
        Users.Clear();
        Actions.Clear();
        Entities.Clear();
        Methods.Clear();
        Summary = new AuditLogSummary();
        SearchText = string.Empty;
        StartDateText = string.Empty;
        EndDateText = string.Empty;
        ErrorMessage = string.Empty;
        _selectedUser = new AuditUserOption { Id = 0, Label = "Todos" };
        _selectedAction = new CatalogFilterOption("all", "Todas");
        _selectedEntity = new CatalogFilterOption("all", "Todos");
        _selectedMethod = new CatalogFilterOption("all", "Todos");
        OnPropertyChanged(nameof(SelectedUser));
        OnPropertyChanged(nameof(SelectedAction));
        OnPropertyChanged(nameof(SelectedEntity));
        OnPropertyChanged(nameof(SelectedMethod));
        Page = 1;
        TotalPages = 0;
        _isInitialized = false;
        NotifyCommandState();
    }

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;
}
