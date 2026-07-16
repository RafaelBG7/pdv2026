using System.Collections.ObjectModel;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class CatalogViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private string _searchText = string.Empty;
    private string _errorMessage = string.Empty;
    private bool _isBusy;
    private bool _isProductsView = true;
    private CatalogCategory? _selectedCategory;
    private CatalogFilterOption _selectedActiveFilter;
    private CatalogFilterOption _selectedSort;
    private int _page = 1;
    private int _totalPages;
    private int _totalProducts;
    private bool _isInitialized;

    public CatalogViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        ActiveFilters =
        [
            new("all", "Todos"),
            new("active", "Ativos"),
            new("inactive", "Inativos"),
        ];
        SortOptions =
        [
            new("name", "Nome A-Z"),
            new("name_desc", "Nome Z-A"),
            new("price", "Menor preço"),
            new("price_desc", "Maior preço"),
            new("stock", "Menor estoque"),
            new("stock_desc", "Maior estoque"),
        ];
        _selectedActiveFilter = ActiveFilters[0];
        _selectedSort = SortOptions[0];
        SearchCommand = new AsyncRelayCommand(SearchAsync);
        RefreshCommand = new AsyncRelayCommand(RefreshAsync);
        PreviousPageCommand = new AsyncRelayCommand(PreviousPageAsync);
        NextPageCommand = new AsyncRelayCommand(NextPageAsync);
        ShowProductsCommand = new RelayCommand(() => IsProductsView = true);
        ShowCategoriesCommand = new RelayCommand(() => IsProductsView = false);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<CatalogProduct> Products { get; } = [];

    public ObservableCollection<CatalogCategory> Categories { get; } = [];

    public IReadOnlyList<CatalogFilterOption> ActiveFilters { get; }

    public IReadOnlyList<CatalogFilterOption> SortOptions { get; }

    public string SearchText
    {
        get => _searchText;
        set => SetProperty(ref _searchText, value);
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
        private set => SetProperty(ref _isBusy, value);
    }

    public bool IsProductsView
    {
        get => _isProductsView;
        private set
        {
            if (SetProperty(ref _isProductsView, value))
            {
                OnPropertyChanged(nameof(IsCategoriesView));
            }
        }
    }

    public bool IsCategoriesView => !IsProductsView;

    public CatalogCategory? SelectedCategory
    {
        get => _selectedCategory;
        set => SetProperty(ref _selectedCategory, value);
    }

    public CatalogFilterOption SelectedActiveFilter
    {
        get => _selectedActiveFilter;
        set => SetProperty(ref _selectedActiveFilter, value);
    }

    public CatalogFilterOption SelectedSort
    {
        get => _selectedSort;
        set => SetProperty(ref _selectedSort, value);
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

    public int TotalProducts
    {
        get => _totalProducts;
        private set
        {
            if (SetProperty(ref _totalProducts, value))
            {
                OnPropertyChanged(nameof(ProductSummary));
            }
        }
    }

    public string ProductSummary => TotalProducts == 1
        ? "1 produto encontrado"
        : $"{TotalProducts} produtos encontrados";

    public string PageSummary => TotalPages == 0
        ? "Página 0 de 0"
        : $"Página {Page} de {TotalPages}";

    public bool CanGoPrevious => Page > 1 && !IsBusy;

    public bool CanGoNext => Page < TotalPages && !IsBusy;

    public AsyncRelayCommand SearchCommand { get; }

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand PreviousPageCommand { get; }

    public AsyncRelayCommand NextPageCommand { get; }

    public RelayCommand ShowProductsCommand { get; }

    public RelayCommand ShowCategoriesCommand { get; }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_sessionContext.Current is null)
        {
            Reset();
            return;
        }

        if (_isInitialized)
        {
            return;
        }

        await LoadCatalogAsync(cancellationToken);
    }

    private void HandleSessionChanged(object? sender, EventArgs e)
    {
        if (_sessionContext.Current is null)
        {
            Reset();
            return;
        }

        Reset();
    }

    private async Task SearchAsync(CancellationToken cancellationToken)
    {
        Page = 1;
        await LoadProductsAsync(cancellationToken);
    }

    private async Task RefreshAsync(CancellationToken cancellationToken) =>
        await LoadCatalogAsync(cancellationToken);

    private async Task PreviousPageAsync(CancellationToken cancellationToken)
    {
        if (!CanGoPrevious)
        {
            return;
        }
        Page--;
        await LoadProductsAsync(cancellationToken);
    }

    private async Task NextPageAsync(CancellationToken cancellationToken)
    {
        if (!CanGoNext)
        {
            return;
        }
        Page++;
        await LoadProductsAsync(cancellationToken);
    }

    private async Task LoadCatalogAsync(CancellationToken cancellationToken)
    {
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            await LoadCategoriesCoreAsync(cancellationToken);
            await LoadProductsCoreAsync(cancellationToken);
            _isInitialized = true;
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            IsBusy = false;
            NotifyNavigationState();
        }
    }

    private async Task LoadProductsAsync(CancellationToken cancellationToken)
    {
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            await LoadProductsCoreAsync(cancellationToken);
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            IsBusy = false;
            NotifyNavigationState();
        }
    }

    private async Task LoadCategoriesCoreAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        var selectedCategoryId = SelectedCategory?.Id ?? 0;
        var result = await _apiClient.GetCatalogCategoriesAsync(
            session.AccessToken,
            string.Empty,
            cancellationToken);

        Categories.Clear();
        Categories.Add(new CatalogCategory { Id = 0, Name = "Todas", ProductCount = result.Total });
        foreach (var category in result.Items)
        {
            Categories.Add(category);
        }
        SelectedCategory = Categories.FirstOrDefault(category => category.Id == selectedCategoryId)
            ?? Categories.FirstOrDefault();
    }

    private async Task LoadProductsCoreAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        var result = await _apiClient.GetCatalogProductsAsync(
            session.AccessToken,
            SearchText,
            SelectedCategory is { Id: > 0 } ? SelectedCategory.Id : null,
            SelectedActiveFilter.Value,
            SelectedSort.Value,
            Page,
            50,
            cancellationToken);

        Products.Clear();
        foreach (var product in result.Items)
        {
            Products.Add(product);
        }
        Page = result.Pagination.Page;
        TotalPages = result.Pagination.TotalPages;
        TotalProducts = result.Pagination.Total;
    }

    private AuthSession RequireSession() => _sessionContext.Current
        ?? throw new GirofyApiException(
            "Sua sessão terminou. Entre novamente para continuar.",
            "session_required",
            401);

    private void SetSafeError(Exception exception)
    {
        ErrorMessage = exception switch
        {
            GirofyApiException apiException => apiException.Message,
            TaskCanceledException => "O servidor demorou para responder. Tente novamente.",
            HttpRequestException => "Não foi possível consultar o catálogo agora.",
            _ => "Não foi possível carregar os produtos. Tente novamente.",
        };
    }

    private void NotifyNavigationState()
    {
        OnPropertyChanged(nameof(CanGoPrevious));
        OnPropertyChanged(nameof(CanGoNext));
    }

    private void Reset()
    {
        Products.Clear();
        Categories.Clear();
        SearchText = string.Empty;
        ErrorMessage = string.Empty;
        Page = 1;
        TotalPages = 0;
        TotalProducts = 0;
        _isInitialized = false;
    }

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;
}
