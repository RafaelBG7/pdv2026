using System.Collections.ObjectModel;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class NotificationsViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private CancellationTokenSource? _pollingCancellation;
    private string _category = string.Empty;
    private string _severity = string.Empty;
    private string _readFilter = string.Empty;
    private string _search = string.Empty;
    private string _errorMessage = string.Empty;
    private bool _isBusy;
    private int _unreadCount;
    private int _page = 1;
    private int _total;

    public NotificationsViewModel(IGirofyApiClient apiClient, IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        RefreshCommand = new AsyncRelayCommand(LoadAsync);
        ApplyFiltersCommand = new AsyncRelayCommand(ApplyFiltersAsync);
        MarkAllReadCommand = new AsyncRelayCommand(MarkAllReadAsync);
        MarkReadCommand = new RelayCommand<NotificationItem>(item => _ = MarkReadAsync(item));
        DismissCommand = new RelayCommand<NotificationItem>(item => _ = DismissAsync(item));
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<NotificationItem> Items { get; } = [];
    public string Category { get => _category; set => SetProperty(ref _category, value); }
    public string Severity { get => _severity; set => SetProperty(ref _severity, value); }
    public string ReadFilter { get => _readFilter; set => SetProperty(ref _readFilter, value); }
    public string Search { get => _search; set => SetProperty(ref _search, value); }
    public bool IsBusy { get => _isBusy; private set => SetProperty(ref _isBusy, value); }
    public int UnreadCount { get => _unreadCount; private set { if (SetProperty(ref _unreadCount, value)) { OnPropertyChanged(nameof(HasUnread)); OnPropertyChanged(nameof(UnreadText)); } } }
    public bool HasUnread => UnreadCount > 0;
    public string UnreadText => UnreadCount > 99 ? "99+" : UnreadCount.ToString();
    public bool HasCritical => Items.Any(item => !item.IsRead && item.Severity == "critical");
    public bool HasItems => Items.Count > 0;
    public bool HasNoItems => !IsBusy && !HasItems;
    public string ErrorMessage { get => _errorMessage; private set { if (SetProperty(ref _errorMessage, value)) OnPropertyChanged(nameof(HasError)); } }
    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);
    public int Page { get => _page; private set => SetProperty(ref _page, value); }
    public int Total { get => _total; private set => SetProperty(ref _total, value); }

    public AsyncRelayCommand RefreshCommand { get; }
    public AsyncRelayCommand ApplyFiltersCommand { get; }
    public AsyncRelayCommand MarkAllReadCommand { get; }
    public RelayCommand<NotificationItem> MarkReadCommand { get; }
    public RelayCommand<NotificationItem> DismissCommand { get; }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_sessionContext.Current is null) { Reset(); return; }
        await LoadAsync(cancellationToken);
        StartPolling();
    }

    private async Task ApplyFiltersAsync(CancellationToken cancellationToken) { Page = 1; await LoadAsync(cancellationToken); }

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null) { Reset(); return; }
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            var snapshot = await _apiClient.GetNotificationsAsync(session.AccessToken,
                new NotificationQuery(Page, 20, Category, Severity, ReadFilter, Search), cancellationToken);
            if (_sessionContext.Current?.AccessToken != session.AccessToken) return;
            Items.Clear();
            foreach (var item in snapshot.Items) Items.Add(item);
            UnreadCount = snapshot.UnreadCount;
            Total = snapshot.Total;
            OnPropertyChanged(nameof(HasItems)); OnPropertyChanged(nameof(HasNoItems)); OnPropertyChanged(nameof(HasCritical));
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
        catch (GirofyApiException exception) when (exception.StatusCode == 401) { ErrorMessage = "Sua sessão terminou. Entre novamente."; }
        catch (TaskCanceledException) { ErrorMessage = "O servidor demorou para responder."; }
        catch (HttpRequestException) { ErrorMessage = "Não foi possível atualizar as notificações."; }
        catch { ErrorMessage = "Não foi possível carregar as notificações."; }
        finally { IsBusy = false; OnPropertyChanged(nameof(HasNoItems)); }
    }

    private async Task MarkReadAsync(NotificationItem item)
    {
        var session = _sessionContext.Current; if (session is null || item.IsRead) return;
        try { await _apiClient.MarkNotificationReadAsync(session.AccessToken, item.Id, CancellationToken.None); await LoadAsync(CancellationToken.None); }
        catch { ErrorMessage = "Não foi possível marcar a notificação como lida."; }
    }

    private async Task DismissAsync(NotificationItem item)
    {
        var session = _sessionContext.Current; if (session is null) return;
        try { await _apiClient.DismissNotificationAsync(session.AccessToken, item.Id, CancellationToken.None); await LoadAsync(CancellationToken.None); }
        catch { ErrorMessage = "Não foi possível dispensar a notificação."; }
    }

    private async Task MarkAllReadAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current; if (session is null) return;
        await _apiClient.MarkAllNotificationsReadAsync(session.AccessToken, cancellationToken);
        await LoadAsync(cancellationToken);
    }

    private void StartPolling()
    {
        _pollingCancellation?.Cancel(); _pollingCancellation?.Dispose();
        _pollingCancellation = new CancellationTokenSource();
        _ = PollAsync(_pollingCancellation.Token);
    }

    private async Task PollAsync(CancellationToken cancellationToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(60));
        try { while (await timer.WaitForNextTickAsync(cancellationToken)) await LoadAsync(cancellationToken); }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
    }

    private void HandleSessionChanged(object? sender, EventArgs e)
    {
        _pollingCancellation?.Cancel();
        if (_sessionContext.Current is null) Reset(); else _ = InitializeAsync();
    }

    private void Reset()
    {
        Items.Clear(); UnreadCount = 0; Total = 0; Page = 1; ErrorMessage = string.Empty; IsBusy = false;
        OnPropertyChanged(nameof(HasItems)); OnPropertyChanged(nameof(HasNoItems)); OnPropertyChanged(nameof(HasCritical));
    }

    public void Dispose() { _pollingCancellation?.Cancel(); _pollingCancellation?.Dispose(); _sessionContext.Changed -= HandleSessionChanged; }
}
