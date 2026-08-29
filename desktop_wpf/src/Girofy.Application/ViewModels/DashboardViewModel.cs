using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class DashboardViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private DashboardSnapshot? _snapshot;
    private string _errorMessage = string.Empty;
    private bool _isBusy;
    private DashboardPeriodOption _selectedPeriod;
    private DateTime? _customStartDate = DateTime.Today;
    private DateTime? _customEndDate = DateTime.Today;

    public DashboardViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        RefreshCommand = new AsyncRelayCommand(LoadAsync);
        ApplyPeriodCommand = new AsyncRelayCommand(LoadAsync);
        Periods =
        [
            new("today", "Hoje"), new("7d", "7 dias"), new("30d", "30 dias"),
            new("month", "Este mês"), new("previous_month", "Mês anterior"),
            new("3m", "3 meses"), new("6m", "6 meses"), new("year", "Este ano"),
            new("custom", "Personalizado")
        ];
        _selectedPeriod = Periods[0];
        _sessionContext.Changed += HandleSessionChanged;
    }

    public DashboardSnapshot? Snapshot
    {
        get => _snapshot;
        private set
        {
            if (SetProperty(ref _snapshot, value))
            {
                OnPropertyChanged(nameof(HasData));
                OnPropertyChanged(nameof(EmptyMessage));
            }
        }
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

    public bool HasData => Snapshot is not null;

    public string EmptyMessage => IsBusy
        ? "Carregando a operação da sua adega..."
        : "O dashboard ainda não foi carregado.";

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetProperty(ref _isBusy, value))
            {
                OnPropertyChanged(nameof(EmptyMessage));
            }
        }
    }

    public AsyncRelayCommand RefreshCommand { get; }
    public AsyncRelayCommand ApplyPeriodCommand { get; }
    public IReadOnlyList<DashboardPeriodOption> Periods { get; }
    public DashboardPeriodOption SelectedPeriod
    {
        get => _selectedPeriod;
        set
        {
            if (SetProperty(ref _selectedPeriod, value)) OnPropertyChanged(nameof(IsCustomPeriod));
        }
    }
    public bool IsCustomPeriod => SelectedPeriod.Key == "custom";
    public DateTime? CustomStartDate { get => _customStartDate; set => SetProperty(ref _customStartDate, value); }
    public DateTime? CustomEndDate { get => _customEndDate; set => SetProperty(ref _customEndDate, value); }

    public Task InitializeAsync(CancellationToken cancellationToken = default) =>
        LoadAsync(cancellationToken);

    private async void HandleSessionChanged(object? sender, EventArgs e)
    {
        if (_sessionContext.Current is null)
        {
            Reset();
            return;
        }

        try
        {
            await LoadAsync(CancellationToken.None);
        }
        catch
        {
            // LoadAsync converts failures into a safe UI message.
        }
    }

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null)
        {
            Reset();
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            var snapshot = await _apiClient.GetDashboardSummaryAsync(
                session.AccessToken,
                SelectedPeriod.Key,
                SelectedPeriod.Key == "custom" ? CustomStartDate?.ToString("yyyy-MM-dd") : null,
                SelectedPeriod.Key == "custom" ? CustomEndDate?.ToString("yyyy-MM-dd") : null,
                cancellationToken);
            if (string.Equals(
                _sessionContext.Current?.AccessToken,
                session.AccessToken,
                StringComparison.Ordinal))
            {
                Snapshot = snapshot;
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (TaskCanceledException)
        {
            ErrorMessage = "O servidor demorou para carregar o dashboard.";
        }
        catch (HttpRequestException)
        {
            ErrorMessage = "Não foi possível consultar a operação agora.";
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível carregar o dashboard. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void Reset()
    {
        Snapshot = null;
        ErrorMessage = string.Empty;
        IsBusy = false;
    }

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;
}

public sealed record DashboardPeriodOption(string Key, string Label);
