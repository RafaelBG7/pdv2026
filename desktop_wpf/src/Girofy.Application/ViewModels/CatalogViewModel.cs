using System.Collections.ObjectModel;
using System.Globalization;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Formatting;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class CatalogViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private string _searchText = string.Empty;
    private string _categorySearchText = string.Empty;
    private string _errorMessage = string.Empty;
    private string _successMessage = string.Empty;
    private bool _isBusy;
    private bool _isProductsView = true;
    private CatalogCategory? _selectedCategory;
    private CatalogFilterOption _selectedActiveFilter;
    private CatalogFilterOption _selectedStockFilter;
    private CatalogFilterOption _selectedSort;
    private string _minPriceText = "0,00";
    private string _maxPriceText = "0,00";
    private bool _isMinPriceFilterActive;
    private bool _isMaxPriceFilterActive;
    private decimal? _appliedMinPrice;
    private decimal? _appliedMaxPrice;
    private int _page = 1;
    private int _totalPages;
    private int _totalProducts;
    private bool _isInitialized;
    private bool _suppressCategoryFilter;
    private CatalogProduct? _selectedProduct;
    private CatalogCategory? _editorCategory;
    private bool _isProductEditorOpen;
    private bool _isEditingProduct;
    private bool _isDeleteConfirmationOpen;
    private bool _isDeleting;
    private string _deleteConfirmationError = string.Empty;
    private bool _editorActive = true;
    private bool _editorIsKit;
    private CatalogProduct? _editorKitComponent;
    private string _editorKitComponentQuantity = "0";
    private string _editorKitComponentSearchText = string.Empty;
    private CatalogProduct? _selectedKitComponentSuggestion;
    private bool _isSearchingKitComponents;
    private bool _isKitComponentSuggestionsOpen;
    private string _kitComponentSearchMessage = string.Empty;
    private CancellationTokenSource? _kitComponentSearchCts;
    private int _kitComponentSearchVersion;
    private bool _suppressKitComponentSearch;
    private string _editorTitle = "Novo produto";
    private string _editorName = string.Empty;
    private string _editorBarcode = string.Empty;
    private string _editorCostPrice = "0,00";
    private string _editorSalePrice = "0,00";
    private string _editorStockQuantity = "0";
    private string _editorMinStockQuantity = "0";
    private string _editorStockReason = string.Empty;
    private CatalogCategory? _selectedCategoryRow;
    private bool _isCategoryEditorOpen;
    private bool _isEditingCategory;
    private string _categoryEditorTitle = "Nova categoria";
    private string _categoryEditorName = string.Empty;

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
        StockFilters =
        [
            new("all", "Todos"),
            new("available", "Com estoque"),
            new("low", "Estoque baixo"),
            new("out", "Sem estoque"),
        ];
        SortOptions =
        [
            new("name", "Nome A-Z"),
            new("name_desc", "Nome Z-A"),
            new("price", "Menor preço"),
            new("price_desc", "Maior preço"),
            new("stock", "Menor estoque"),
            new("stock_desc", "Maior estoque"),
            new("created_desc", "Mais recentes"),
            new("created_asc", "Mais antigos"),
        ];
        _selectedActiveFilter = ActiveFilters[0];
        _selectedStockFilter = StockFilters[0];
        _selectedSort = SortOptions[0];
        SearchCommand = new AsyncRelayCommand(SearchAsync);
        SearchCategoriesCommand = new AsyncRelayCommand(SearchCategoriesAsync);
        ClearCategorySearchCommand = new AsyncRelayCommand(ClearCategorySearchAsync);
        ClearProductFiltersCommand = new AsyncRelayCommand(ClearProductFiltersAsync);
        RefreshCommand = new AsyncRelayCommand(RefreshAsync);
        PreviousPageCommand = new AsyncRelayCommand(PreviousPageAsync);
        NextPageCommand = new AsyncRelayCommand(NextPageAsync);
        ShowProductsCommand = new RelayCommand(() => IsProductsView = true);
        ShowCategoriesCommand = new RelayCommand(() => IsProductsView = false);
        OpenNewProductCommand = new RelayCommand(OpenNewProduct, () => CanManageProducts && !IsBusy);
        OpenEditProductCommand = new RelayCommand(OpenSelectedProduct, () => CanManageProducts && SelectedProduct is not null && !IsBusy);
        CloseProductEditorCommand = new RelayCommand(CloseProductEditor);
        SaveProductCommand = new AsyncRelayCommand(SaveProductAsync, () => CanManageProducts && IsProductEditorOpen && !IsBusy);
        OpenDeleteProductConfirmationCommand = new RelayCommand(OpenDeleteProductConfirmation, CanRequestProductDeletion);
        CancelDeleteProductCommand = new RelayCommand(CancelDeleteProductConfirmation, () => IsDeleteConfirmationOpen && !IsDeleting);
        DeleteProductCommand = new AsyncRelayCommand(DeleteProductAsync, () => CanRequestProductDeletion() && IsDeleteConfirmationOpen && !IsDeleting);
        OpenNewCategoryCommand = new RelayCommand(OpenNewCategory, () => CanManageCategories && !IsBusy);
        OpenEditCategoryCommand = new RelayCommand(OpenSelectedCategory, () => CanManageCategories && SelectedCategoryRow is not null && !IsBusy);
        CloseCategoryEditorCommand = new RelayCommand(CloseCategoryEditor);
        SaveCategoryCommand = new AsyncRelayCommand(SaveCategoryAsync, () => CanManageCategories && IsCategoryEditorOpen && !IsBusy);
        DeleteCategoryCommand = new AsyncRelayCommand(DeleteCategoryAsync, () => CanManageCategories && SelectedCategoryRow is not null && !IsBusy);
        SelectKitComponentCommand = new RelayCommand<CatalogProduct>(SelectKitComponent);
        ClearKitComponentCommand = new RelayCommand(ClearKitComponentSelection);
        RetryKitComponentSearchCommand = new AsyncRelayCommand(RetryKitComponentSearchAsync, () => EditorIsKit && !IsSearchingKitComponents);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<CatalogProduct> Products { get; } = [];

    public ObservableCollection<CatalogCategory> Categories { get; } = [];

    public ObservableCollection<CatalogCategory> ProductCategories { get; } = [];

    public ObservableCollection<CatalogCategory> CategoryRows { get; } = [];

    public ObservableCollection<CatalogProduct> KitComponentSuggestions { get; } = [];

    public IReadOnlyList<CatalogFilterOption> ActiveFilters { get; }

    public IReadOnlyList<CatalogFilterOption> StockFilters { get; }

    public IReadOnlyList<CatalogFilterOption> SortOptions { get; }

    public string SearchText
    {
        get => _searchText;
        set => SetProperty(ref _searchText, value);
    }

    public string CategorySearchText
    {
        get => _categorySearchText;
        set => SetProperty(ref _categorySearchText, value);
    }

    public string CategorySummary => CategoryRows.Count == 1
        ? "1 categoria encontrada"
        : $"{CategoryRows.Count} categorias encontradas";

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
                NotifyNavigationState();
            }
        }
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
        set
        {
            if (SetProperty(ref _selectedCategory, value)
                && _isInitialized
                && !_suppressCategoryFilter)
            {
                _ = ApplyCategoryFilterAsync();
            }
        }
    }

    public CatalogFilterOption SelectedActiveFilter
    {
        get => _selectedActiveFilter;
        set => SetProperty(ref _selectedActiveFilter, value);
    }

    public CatalogFilterOption SelectedStockFilter
    {
        get => _selectedStockFilter;
        set => SetProperty(ref _selectedStockFilter, value);
    }

    public string MinPriceText
    {
        get => _minPriceText;
        set => SetProperty(ref _minPriceText, value);
    }

    public string MaxPriceText
    {
        get => _maxPriceText;
        set => SetProperty(ref _maxPriceText, value);
    }

    public bool IsMinPriceFilterActive
    {
        get => _isMinPriceFilterActive;
        set => SetProperty(ref _isMinPriceFilterActive, value);
    }

    public bool IsMaxPriceFilterActive
    {
        get => _isMaxPriceFilterActive;
        set => SetProperty(ref _isMaxPriceFilterActive, value);
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

    public bool CanManageProducts => _sessionContext.Current?.User.Permissions.TryGetValue(
        "can_manage_products",
        out var canManageProducts) == true && canManageProducts;

    public bool CanManageCategories => _sessionContext.Current?.User.Permissions.TryGetValue(
        "can_manage_categories",
        out var canManageCategories) == true && canManageCategories;

    public CatalogProduct? SelectedProduct
    {
        get => _selectedProduct;
        set
        {
            if (SetProperty(ref _selectedProduct, value))
            {
                OnPropertyChanged(nameof(DeleteConfirmationProductName));
                OpenEditProductCommand.NotifyCanExecuteChanged();
                OpenDeleteProductConfirmationCommand.NotifyCanExecuteChanged();
                DeleteProductCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public bool IsProductEditorOpen
    {
        get => _isProductEditorOpen;
        private set
        {
            if (SetProperty(ref _isProductEditorOpen, value))
            {
                SaveProductCommand.NotifyCanExecuteChanged();
                DeleteProductCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public bool IsEditingProduct
    {
        get => _isEditingProduct;
        private set
        {
            if (SetProperty(ref _isEditingProduct, value))
            {
                DeleteProductCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public bool IsDeleteConfirmationOpen
    {
        get => _isDeleteConfirmationOpen;
        private set
        {
            if (SetProperty(ref _isDeleteConfirmationOpen, value))
            {
                OpenDeleteProductConfirmationCommand.NotifyCanExecuteChanged();
                CancelDeleteProductCommand.NotifyCanExecuteChanged();
                DeleteProductCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public bool IsDeleting
    {
        get => _isDeleting;
        private set
        {
            if (SetProperty(ref _isDeleting, value))
            {
                OnPropertyChanged(nameof(DeleteProductButtonText));
                OpenDeleteProductConfirmationCommand.NotifyCanExecuteChanged();
                CancelDeleteProductCommand.NotifyCanExecuteChanged();
                DeleteProductCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public string DeleteProductButtonText => IsDeleting ? "Excluindo..." : "Excluir produto";

    public string DeleteConfirmationProductName => SelectedProduct?.Name ?? string.Empty;

    public string DeleteConfirmationError
    {
        get => _deleteConfirmationError;
        private set
        {
            if (SetProperty(ref _deleteConfirmationError, value))
            {
                OnPropertyChanged(nameof(HasDeleteConfirmationError));
            }
        }
    }

    public bool HasDeleteConfirmationError => !string.IsNullOrWhiteSpace(DeleteConfirmationError);

    public string EditorTitle
    {
        get => _editorTitle;
        private set => SetProperty(ref _editorTitle, value);
    }

    public string EditorName
    {
        get => _editorName;
        set => SetProperty(ref _editorName, value);
    }

    public string EditorBarcode
    {
        get => _editorBarcode;
        set => SetProperty(ref _editorBarcode, value);
    }

    public void CommitEditorBarcodeInput()
    {
        EditorBarcode = (EditorBarcode ?? string.Empty).Trim();
    }

    public CatalogCategory? EditorCategory
    {
        get => _editorCategory;
        set => SetProperty(ref _editorCategory, value);
    }

    public string EditorCostPrice
    {
        get => _editorCostPrice;
        set => SetProperty(ref _editorCostPrice, value);
    }

    public string EditorSalePrice
    {
        get => _editorSalePrice;
        set => SetProperty(ref _editorSalePrice, value);
    }

    public string EditorStockQuantity
    {
        get => _editorStockQuantity;
        set => SetProperty(ref _editorStockQuantity, value);
    }

    public string EditorMinStockQuantity
    {
        get => _editorMinStockQuantity;
        set => SetProperty(ref _editorMinStockQuantity, value);
    }

    public string EditorStockReason
    {
        get => _editorStockReason;
        set => SetProperty(ref _editorStockReason, value);
    }

    public bool EditorActive
    {
        get => _editorActive;
        set => SetProperty(ref _editorActive, value);
    }

    public bool EditorIsKit
    {
        get => _editorIsKit;
        set
        {
            if (SetProperty(ref _editorIsKit, value) && !value)
            {
                ClearKitComponentSelection();
                EditorKitComponentQuantity = "0";
            }
        }
    }

    public CatalogProduct? EditorKitComponent
    {
        get => _editorKitComponent;
        set
        {
            if (SetProperty(ref _editorKitComponent, value))
            {
                OnPropertyChanged(nameof(HasSelectedKitComponent));
            }
        }
    }

    public string EditorKitComponentSearchText
    {
        get => _editorKitComponentSearchText;
        set
        {
            if (!SetProperty(ref _editorKitComponentSearchText, value))
            {
                return;
            }

            if (_suppressKitComponentSearch)
            {
                return;
            }

            if (EditorKitComponent is not null
                && !string.Equals(value.Trim(), EditorKitComponent.Name, StringComparison.CurrentCultureIgnoreCase))
            {
                EditorKitComponent = null;
            }

            QueueKitComponentSearch();
        }
    }

    public CatalogProduct? SelectedKitComponentSuggestion
    {
        get => _selectedKitComponentSuggestion;
        set => SetProperty(ref _selectedKitComponentSuggestion, value);
    }

    public bool IsSearchingKitComponents
    {
        get => _isSearchingKitComponents;
        private set
        {
            if (SetProperty(ref _isSearchingKitComponents, value))
            {
                RetryKitComponentSearchCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public bool IsKitComponentSuggestionsOpen
    {
        get => _isKitComponentSuggestionsOpen;
        private set => SetProperty(ref _isKitComponentSuggestionsOpen, value);
    }

    public string KitComponentSearchMessage
    {
        get => _kitComponentSearchMessage;
        private set
        {
            if (SetProperty(ref _kitComponentSearchMessage, value))
            {
                OnPropertyChanged(nameof(HasKitComponentSearchMessage));
            }
        }
    }

    public bool HasKitComponentSearchMessage => !string.IsNullOrWhiteSpace(KitComponentSearchMessage);

    public bool HasSelectedKitComponent => EditorKitComponent is not null;

    public string EditorKitComponentQuantity
    {
        get => _editorKitComponentQuantity;
        set => SetProperty(ref _editorKitComponentQuantity, value);
    }

    public CatalogCategory? SelectedCategoryRow
    {
        get => _selectedCategoryRow;
        set
        {
            if (SetProperty(ref _selectedCategoryRow, value))
            {
                OpenEditCategoryCommand.NotifyCanExecuteChanged();
                DeleteCategoryCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public bool IsCategoryEditorOpen
    {
        get => _isCategoryEditorOpen;
        private set
        {
            if (SetProperty(ref _isCategoryEditorOpen, value))
            {
                SaveCategoryCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public bool IsEditingCategory
    {
        get => _isEditingCategory;
        private set => SetProperty(ref _isEditingCategory, value);
    }

    public string CategoryEditorTitle
    {
        get => _categoryEditorTitle;
        private set => SetProperty(ref _categoryEditorTitle, value);
    }

    public string CategoryEditorName
    {
        get => _categoryEditorName;
        set => SetProperty(ref _categoryEditorName, value);
    }

    public AsyncRelayCommand SearchCommand { get; }

    public AsyncRelayCommand SearchCategoriesCommand { get; }

    public AsyncRelayCommand ClearCategorySearchCommand { get; }

    public AsyncRelayCommand ClearProductFiltersCommand { get; }

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand PreviousPageCommand { get; }

    public AsyncRelayCommand NextPageCommand { get; }

    public RelayCommand ShowProductsCommand { get; }

    public RelayCommand ShowCategoriesCommand { get; }

    public RelayCommand OpenNewProductCommand { get; }

    public RelayCommand OpenEditProductCommand { get; }

    public RelayCommand CloseProductEditorCommand { get; }

    public AsyncRelayCommand SaveProductCommand { get; }

    public RelayCommand OpenDeleteProductConfirmationCommand { get; }

    public RelayCommand CancelDeleteProductCommand { get; }

    public AsyncRelayCommand DeleteProductCommand { get; }

    public RelayCommand OpenNewCategoryCommand { get; }

    public RelayCommand OpenEditCategoryCommand { get; }

    public RelayCommand CloseCategoryEditorCommand { get; }

    public AsyncRelayCommand SaveCategoryCommand { get; }

    public AsyncRelayCommand DeleteCategoryCommand { get; }

    public RelayCommand<CatalogProduct> SelectKitComponentCommand { get; }

    public RelayCommand ClearKitComponentCommand { get; }

    public AsyncRelayCommand RetryKitComponentSearchCommand { get; }

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
        if (!TryParseOptionalMoney(MinPriceText, IsMinPriceFilterActive, out var minPrice))
        {
            ErrorMessage = "Informe um preço mínimo válido.";
            return;
        }
        if (!TryParseOptionalMoney(MaxPriceText, IsMaxPriceFilterActive, out var maxPrice))
        {
            ErrorMessage = "Informe um preço máximo válido.";
            return;
        }
        if (minPrice is not null && maxPrice is not null && minPrice > maxPrice)
        {
            ErrorMessage = "O preço mínimo não pode ser maior que o preço máximo.";
            return;
        }
        _appliedMinPrice = minPrice;
        _appliedMaxPrice = maxPrice;
        Page = 1;
        await LoadProductsAsync(cancellationToken);
    }

    private async Task ClearProductFiltersAsync(CancellationToken cancellationToken)
    {
        SearchText = string.Empty;
        SelectedActiveFilter = ActiveFilters[0];
        SelectedStockFilter = StockFilters[0];
        SelectedSort = SortOptions[0];
        MinPriceText = "0,00";
        MaxPriceText = "0,00";
        IsMinPriceFilterActive = false;
        IsMaxPriceFilterActive = false;
        _appliedMinPrice = null;
        _appliedMaxPrice = null;
        _suppressCategoryFilter = true;
        SelectedCategory = Categories.FirstOrDefault();
        _suppressCategoryFilter = false;
        Page = 1;
        await LoadProductsAsync(cancellationToken);
    }

    private Task SearchCategoriesAsync(CancellationToken cancellationToken) =>
        LoadCategoryRowsAsync(cancellationToken);

    private async Task ClearCategorySearchAsync(CancellationToken cancellationToken)
    {
        CategorySearchText = string.Empty;
        await LoadCategoryRowsAsync(cancellationToken);
    }

    private async Task ApplyCategoryFilterAsync()
    {
        Page = 1;
        await LoadProductsAsync(CancellationToken.None);
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

    private void OpenNewProduct()
    {
        if (!CanManageProducts)
        {
            return;
        }

        EditorTitle = "Novo produto";
        IsEditingProduct = false;
        SelectedProduct = null;
        EditorName = string.Empty;
        EditorBarcode = string.Empty;
        EditorCategory = ProductCategories.FirstOrDefault();
        EditorCostPrice = "0,00";
        EditorSalePrice = "0,00";
        EditorStockQuantity = "0";
        EditorMinStockQuantity = "0";
        EditorStockReason = "Cadastro inicial";
        EditorActive = true;
        EditorIsKit = false;
        ClearKitComponentSelection();
        EditorKitComponentQuantity = "0";
        ErrorMessage = string.Empty;
        IsProductEditorOpen = true;
    }

    private void OpenSelectedProduct()
    {
        if (!CanManageProducts || SelectedProduct is null)
        {
            return;
        }

        var product = SelectedProduct;
        EditorTitle = $"Editar {product.Name}";
        IsEditingProduct = true;
        EditorName = product.Name;
        EditorBarcode = product.Barcode;
        EditorCategory = product.Category is { Id: > 0 }
            ? ProductCategories.FirstOrDefault(category => category.Id == product.Category.Id)
            : ProductCategories.FirstOrDefault();
        EditorCostPrice = FormatMoney(product.CostPrice ?? 0);
        EditorSalePrice = FormatMoney(product.SalePrice);
        EditorStockQuantity = product.StockQuantity.ToString(CultureInfo.InvariantCulture);
        EditorMinStockQuantity = product.MinStockQuantity.ToString(CultureInfo.InvariantCulture);
        EditorStockReason = "Ajuste pelo aplicativo Windows";
        EditorActive = product.Active;
        EditorIsKit = product.IsKit;
        SetKitComponentSelection(product.KitComponent is null
            ? null
            : new CatalogProduct
            {
                Id = product.KitComponent.Id,
                Name = product.KitComponent.Name,
                Active = true,
            });
        EditorKitComponentQuantity = product.KitComponentQuantity.ToString(CultureInfo.InvariantCulture);
        ErrorMessage = string.Empty;
        IsProductEditorOpen = true;
    }

    private void CloseProductEditor()
    {
        CancelDeleteProductConfirmation();
        CancelKitComponentSearch();
        IsKitComponentSuggestionsOpen = false;
        IsProductEditorOpen = false;
        ErrorMessage = string.Empty;
    }

    private bool CanRequestProductDeletion() =>
        CanManageProducts && IsEditingProduct && SelectedProduct is not null && !IsBusy && !IsDeleting;

    private void OpenDeleteProductConfirmation()
    {
        if (!CanRequestProductDeletion())
        {
            return;
        }

        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        DeleteConfirmationError = string.Empty;
        OnPropertyChanged(nameof(DeleteConfirmationProductName));
        IsDeleteConfirmationOpen = true;
    }

    private void CancelDeleteProductConfirmation()
    {
        if (IsDeleting)
        {
            return;
        }

        IsDeleteConfirmationOpen = false;
        DeleteConfirmationError = string.Empty;
    }

    private async Task SaveProductAsync(CancellationToken cancellationToken)
    {
        if (!TryBuildProductRequest(out var request))
        {
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            var savedProduct = IsEditingProduct && SelectedProduct is not null
                ? await _apiClient.UpdateCatalogProductAsync(
                    session.AccessToken,
                    SelectedProduct.Id,
                    request,
                    cancellationToken)
                : await _apiClient.CreateCatalogProductAsync(
                    session.AccessToken,
                    request,
                    cancellationToken);

            await LoadCatalogAsync(cancellationToken);
            SelectedProduct = Products.FirstOrDefault(product => product.Id == savedProduct.Id);
            IsProductEditorOpen = false;
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

    private async Task DeleteProductAsync(CancellationToken cancellationToken)
    {
        if (!CanManageProducts || !IsEditingProduct || SelectedProduct is null)
        {
            return;
        }

        var session = RequireSession();
        var deletedProductId = SelectedProduct.Id;
        var deletedProductName = SelectedProduct.Name;
        IsDeleting = true;
        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        DeleteConfirmationError = string.Empty;
        try
        {
            await _apiClient.DeleteCatalogProductAsync(
                session.AccessToken,
                deletedProductId,
                cancellationToken);
            IsDeleteConfirmationOpen = false;
            IsProductEditorOpen = false;
            SelectedProduct = null;
            await LoadCatalogAsync(cancellationToken);
            SuccessMessage = $"Produto \"{deletedProductName}\" excluído com sucesso.";
        }
        catch (Exception exception)
        {
            DeleteConfirmationError = GetDeleteProductError(exception);
        }
        finally
        {
            IsBusy = false;
            IsDeleting = false;
            NotifyNavigationState();
        }
    }

    private static string GetDeleteProductError(Exception exception) => exception switch
    {
        GirofyApiException { StatusCode: 409 } =>
            "Este produto possui histórico de vendas ou é usado como base de kit. Inative-o em vez de excluir.",
        GirofyApiException { StatusCode: 403 } =>
            "Você não possui permissão para excluir este produto.",
        GirofyApiException { StatusCode: 404 } =>
            "Este produto não foi encontrado. Atualize a lista e tente novamente.",
        GirofyApiException apiException => apiException.Message,
        TaskCanceledException => "O servidor demorou para responder. Tente novamente.",
        HttpRequestException => "Não foi possível conectar ao servidor. Verifique sua internet e tente novamente.",
        _ => "Não foi possível excluir o produto agora. Tente novamente.",
    };

    private void OpenNewCategory()
    {
        if (!CanManageCategories)
        {
            return;
        }

        CategoryEditorTitle = "Nova categoria";
        IsEditingCategory = false;
        SelectedCategoryRow = null;
        CategoryEditorName = string.Empty;
        ErrorMessage = string.Empty;
        IsCategoryEditorOpen = true;
    }

    private void OpenSelectedCategory()
    {
        if (!CanManageCategories || SelectedCategoryRow is null)
        {
            return;
        }

        CategoryEditorTitle = $"Editar {SelectedCategoryRow.Name}";
        IsEditingCategory = true;
        CategoryEditorName = SelectedCategoryRow.Name;
        ErrorMessage = string.Empty;
        IsCategoryEditorOpen = true;
    }

    private void CloseCategoryEditor()
    {
        IsCategoryEditorOpen = false;
        ErrorMessage = string.Empty;
    }

    private async Task SaveCategoryAsync(CancellationToken cancellationToken)
    {
        if (!TryBuildCategoryRequest(out var request))
        {
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            var savedCategory = IsEditingCategory && SelectedCategoryRow is not null
                ? await _apiClient.UpdateCatalogCategoryAsync(
                    session.AccessToken,
                    SelectedCategoryRow.Id,
                    request,
                    cancellationToken)
                : await _apiClient.CreateCatalogCategoryAsync(
                    session.AccessToken,
                    request,
                    cancellationToken);

            await LoadCatalogAsync(cancellationToken);
            SelectedCategoryRow = CategoryRows.FirstOrDefault(category => category.Id == savedCategory.Id);
            IsCategoryEditorOpen = false;
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

    private async Task DeleteCategoryAsync(CancellationToken cancellationToken)
    {
        if (!CanManageCategories || SelectedCategoryRow is null)
        {
            return;
        }

        var session = RequireSession();
        var deletedCategoryId = SelectedCategoryRow.Id;
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            await _apiClient.DeleteCatalogCategoryAsync(
                session.AccessToken,
                deletedCategoryId,
                cancellationToken);
            if (SelectedCategory?.Id == deletedCategoryId)
            {
                SelectedCategory = Categories.FirstOrDefault();
            }
            await LoadCatalogAsync(cancellationToken);
            IsCategoryEditorOpen = false;
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
        var selectedCategoryRowId = SelectedCategoryRow?.Id ?? 0;
        var result = await _apiClient.GetCatalogCategoriesAsync(
            session.AccessToken,
            string.Empty,
            cancellationToken);

        _suppressCategoryFilter = true;
        try
        {
            Categories.Clear();
            ProductCategories.Clear();
            Categories.Add(new CatalogCategory { Id = 0, Name = "Todas", ProductCount = result.Total });
            foreach (var category in result.Items)
            {
                Categories.Add(category);
                ProductCategories.Add(category);
            }
            SelectedCategory = Categories.FirstOrDefault(category => category.Id == selectedCategoryId)
                ?? Categories.FirstOrDefault();

            var categoryRows = string.IsNullOrWhiteSpace(CategorySearchText)
                ? result
                : await _apiClient.GetCatalogCategoriesAsync(
                    session.AccessToken,
                    CategorySearchText,
                    cancellationToken);
            ApplyCategoryRows(categoryRows.Items, selectedCategoryRowId);
        }
        finally
        {
            _suppressCategoryFilter = false;
        }
    }

    private async Task LoadCategoryRowsAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        var selectedCategoryRowId = SelectedCategoryRow?.Id ?? 0;
        IsBusy = true;
        ErrorMessage = string.Empty;
        try
        {
            var result = await _apiClient.GetCatalogCategoriesAsync(
                session.AccessToken,
                CategorySearchText,
                cancellationToken);
            ApplyCategoryRows(result.Items, selectedCategoryRowId);
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

    private void ApplyCategoryRows(
        IReadOnlyList<CatalogCategory> categories,
        int selectedCategoryRowId)
    {
        CategoryRows.Clear();
        foreach (var category in categories)
        {
            CategoryRows.Add(category);
        }
        SelectedCategoryRow = CategoryRows.FirstOrDefault(category => category.Id == selectedCategoryRowId);
        OnPropertyChanged(nameof(CategorySummary));
    }

    private async Task LoadProductsCoreAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        var result = await _apiClient.GetCatalogProductsAsync(
            session.AccessToken,
            SearchText,
            SelectedCategory is { Id: > 0 } ? SelectedCategory.Id : null,
            SelectedActiveFilter.Value,
            SelectedStockFilter.Value,
            _appliedMinPrice,
            _appliedMaxPrice,
            SelectedSort.Value,
            Page,
            50,
            cancellationToken);

        Products.Clear();
        foreach (var product in result.Items)
        {
            Products.Add(product);
        }
        SelectedProduct = Products.FirstOrDefault(product => product.Id == SelectedProduct?.Id);
        Page = result.Pagination.Page;
        TotalPages = result.Pagination.TotalPages;
        TotalProducts = result.Pagination.Total;
    }

    private void QueueKitComponentSearch()
    {
        CancelKitComponentSearch();
        KitComponentSuggestions.Clear();
        SelectedKitComponentSuggestion = null;
        KitComponentSearchMessage = string.Empty;

        var term = EditorKitComponentSearchText.Trim();
        if (!EditorIsKit || term.Length < 1 || EditorKitComponent is not null)
        {
            IsKitComponentSuggestionsOpen = false;
            return;
        }

        IsKitComponentSuggestionsOpen = true;
        var cts = new CancellationTokenSource();
        _kitComponentSearchCts = cts;
        var version = ++_kitComponentSearchVersion;
        _ = SearchKitComponentsAfterDelayAsync(term, version, cts);
    }

    private async Task SearchKitComponentsAfterDelayAsync(
        string term,
        int version,
        CancellationTokenSource cts)
    {
        try
        {
            await Task.Delay(220, cts.Token);
            await SearchKitComponentsAsync(term, version, cts.Token);
        }
        catch (OperationCanceledException)
        {
        }
        finally
        {
            if (ReferenceEquals(_kitComponentSearchCts, cts))
            {
                _kitComponentSearchCts = null;
            }
            cts.Dispose();
        }
    }

    private async Task SearchKitComponentsAsync(string term, int version, CancellationToken cancellationToken)
    {
        var session = RequireSession();
        IsSearchingKitComponents = true;
        KitComponentSearchMessage = string.Empty;
        try
        {
            var result = await _apiClient.GetCatalogProductsAsync(
                session.AccessToken,
                term,
                null,
                "active",
                "name",
                1,
                20,
                cancellationToken);

            if (version != _kitComponentSearchVersion
                || !string.Equals(EditorKitComponentSearchText.Trim(), term, StringComparison.Ordinal)
                || !EditorIsKit)
            {
                return;
            }

            KitComponentSuggestions.Clear();
            foreach (var product in result.Items.Where(product => product.Active && product.Id != SelectedProduct?.Id))
            {
                KitComponentSuggestions.Add(product);
            }
            SelectedKitComponentSuggestion = KitComponentSuggestions.FirstOrDefault();
            KitComponentSearchMessage = KitComponentSuggestions.Count == 0
                ? "Nenhum produto ativo encontrado."
                : string.Empty;
            IsKitComponentSuggestionsOpen = true;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception)
        {
            if (version != _kitComponentSearchVersion)
            {
                return;
            }
            KitComponentSuggestions.Clear();
            SelectedKitComponentSuggestion = null;
            KitComponentSearchMessage = "Não foi possível pesquisar. Tente novamente.";
            IsKitComponentSuggestionsOpen = true;
        }
        finally
        {
            if (version == _kitComponentSearchVersion)
            {
                IsSearchingKitComponents = false;
            }
        }
    }

    private async Task RetryKitComponentSearchAsync(CancellationToken cancellationToken)
    {
        var term = EditorKitComponentSearchText.Trim();
        if (!EditorIsKit || term.Length < 1)
        {
            return;
        }

        CancelKitComponentSearch();
        var version = ++_kitComponentSearchVersion;
        await SearchKitComponentsAsync(term, version, cancellationToken);
    }

    private void SelectKitComponent(CatalogProduct product)
    {
        if (product.Id == SelectedProduct?.Id)
        {
            KitComponentSearchMessage = "Um produto não pode ser componente dele mesmo.";
            return;
        }
        SetKitComponentSelection(product);
    }

    private void SetKitComponentSelection(CatalogProduct? product)
    {
        CancelKitComponentSearch();
        _suppressKitComponentSearch = true;
        try
        {
            EditorKitComponent = product;
            EditorKitComponentSearchText = product?.Name ?? string.Empty;
        }
        finally
        {
            _suppressKitComponentSearch = false;
        }
        KitComponentSuggestions.Clear();
        SelectedKitComponentSuggestion = null;
        KitComponentSearchMessage = string.Empty;
        IsKitComponentSuggestionsOpen = false;
    }

    private void ClearKitComponentSelection()
    {
        SetKitComponentSelection(null);
    }

    public void CloseKitComponentSuggestions()
    {
        CancelKitComponentSearch();
        IsKitComponentSuggestionsOpen = false;
    }

    public void MoveKitComponentSuggestionSelection(int offset)
    {
        if (KitComponentSuggestions.Count == 0)
        {
            return;
        }
        var currentIndex = SelectedKitComponentSuggestion is null
            ? -1
            : KitComponentSuggestions.IndexOf(SelectedKitComponentSuggestion);
        var nextIndex = Math.Clamp(currentIndex + offset, 0, KitComponentSuggestions.Count - 1);
        SelectedKitComponentSuggestion = KitComponentSuggestions[nextIndex];
    }

    public void ConfirmSelectedKitComponentSuggestion()
    {
        if (SelectedKitComponentSuggestion is not null)
        {
            SelectKitComponent(SelectedKitComponentSuggestion);
        }
    }

    private void CancelKitComponentSearch()
    {
        _kitComponentSearchVersion++;
        _kitComponentSearchCts?.Cancel();
        _kitComponentSearchCts = null;
        IsSearchingKitComponents = false;
    }

    private bool TryBuildProductRequest(out CatalogProductMutationRequest request)
    {
        request = new CatalogProductMutationRequest(
            string.Empty,
            string.Empty,
            null,
            0,
            0,
            0,
            0,
            true,
            string.Empty);

        var name = EditorName.Trim();
        if (string.IsNullOrWhiteSpace(name))
        {
            ErrorMessage = "Informe o nome do produto.";
            return false;
        }

        if (!TryParseMoney(EditorCostPrice, out var costPrice))
        {
            ErrorMessage = "Informe um custo válido.";
            return false;
        }

        if (!TryParseMoney(EditorSalePrice, out var salePrice))
        {
            ErrorMessage = "Informe um valor de venda válido.";
            return false;
        }

        if (!TryParseInteger(EditorStockQuantity, out var stockQuantity))
        {
            ErrorMessage = "Informe um estoque válido.";
            return false;
        }

        if (!TryParseInteger(EditorMinStockQuantity, out var minStockQuantity) || minStockQuantity < 0)
        {
            ErrorMessage = "Informe um estoque mínimo válido.";
            return false;
        }

        var kitComponentQuantity = 0;
        if (EditorIsKit && (EditorKitComponent is null
            || !TryParseInteger(EditorKitComponentQuantity, out kitComponentQuantity)
            || kitComponentQuantity < 1))
        {
            ErrorMessage = "Informe o produto base e a quantidade consumida pelo kit.";
            return false;
        }
        if (EditorIsKit && EditorKitComponent?.Id == SelectedProduct?.Id)
        {
            ErrorMessage = "Um produto não pode ser componente dele mesmo.";
            return false;
        }

        request = new CatalogProductMutationRequest(
            name,
            (EditorBarcode ?? string.Empty).Trim(),
            EditorCategory is { Id: > 0 } ? EditorCategory.Id : null,
            costPrice,
            salePrice,
            stockQuantity,
            minStockQuantity,
            EditorActive,
            string.IsNullOrWhiteSpace(EditorStockReason)
                ? "Atualização pelo aplicativo Windows"
                : EditorStockReason.Trim(),
            EditorIsKit,
            EditorIsKit ? EditorKitComponent?.Id : null,
            EditorIsKit ? kitComponentQuantity : 0);
        return true;
    }

    private bool TryBuildCategoryRequest(out CatalogCategoryMutationRequest request)
    {
        request = new CatalogCategoryMutationRequest(string.Empty);
        var name = CategoryEditorName.Trim();
        if (string.IsNullOrWhiteSpace(name))
        {
            ErrorMessage = "Informe o nome da categoria.";
            return false;
        }

        request = new CatalogCategoryMutationRequest(name);
        return true;
    }

    private static string FormatMoney(decimal value) =>
        BrazilianMoneyFormatter.Format(value);

    private static bool TryParseMoney(string value, out decimal amount) =>
        BrazilianMoneyFormatter.TryParse(value, out amount);

    private static bool TryParseOptionalMoney(string value, bool isActive, out decimal? amount)
    {
        amount = null;
        if (!isActive)
        {
            return true;
        }
        if (!TryParseMoney(value, out var parsed))
        {
            return false;
        }
        amount = parsed;
        return true;
    }

    private static bool TryParseInteger(string value, out int amount) =>
        int.TryParse(value.Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out amount);

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
            _ => "Não foi possível carregar o catálogo. Tente novamente.",
        };
    }

    private void NotifyNavigationState()
    {
        OnPropertyChanged(nameof(CanGoPrevious));
        OnPropertyChanged(nameof(CanGoNext));
        OnPropertyChanged(nameof(CanManageProducts));
        OnPropertyChanged(nameof(CanManageCategories));
        OpenNewProductCommand.NotifyCanExecuteChanged();
        OpenEditProductCommand.NotifyCanExecuteChanged();
        SaveProductCommand.NotifyCanExecuteChanged();
        OpenDeleteProductConfirmationCommand.NotifyCanExecuteChanged();
        CancelDeleteProductCommand.NotifyCanExecuteChanged();
        DeleteProductCommand.NotifyCanExecuteChanged();
        OpenNewCategoryCommand.NotifyCanExecuteChanged();
        OpenEditCategoryCommand.NotifyCanExecuteChanged();
        SaveCategoryCommand.NotifyCanExecuteChanged();
        DeleteCategoryCommand.NotifyCanExecuteChanged();
    }

    private void Reset()
    {
        Products.Clear();
        Categories.Clear();
        ProductCategories.Clear();
        CategoryRows.Clear();
        OnPropertyChanged(nameof(CategorySummary));
        CancelKitComponentSearch();
        KitComponentSuggestions.Clear();
        SetKitComponentSelection(null);
        SearchText = string.Empty;
        MinPriceText = "0,00";
        MaxPriceText = "0,00";
        IsMinPriceFilterActive = false;
        IsMaxPriceFilterActive = false;
        _appliedMinPrice = null;
        _appliedMaxPrice = null;
        SelectedActiveFilter = ActiveFilters[0];
        SelectedStockFilter = StockFilters[0];
        SelectedSort = SortOptions[0];
        CategorySearchText = string.Empty;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        IsDeleteConfirmationOpen = false;
        IsDeleting = false;
        DeleteConfirmationError = string.Empty;
        Page = 1;
        TotalPages = 0;
        TotalProducts = 0;
        SelectedProduct = null;
        SelectedCategory = null;
        SelectedCategoryRow = null;
        IsProductEditorOpen = false;
        IsEditingProduct = false;
        IsCategoryEditorOpen = false;
        IsEditingCategory = false;
        _isInitialized = false;
        NotifyNavigationState();
    }

    public void Dispose()
    {
        CancelKitComponentSearch();
        _sessionContext.Changed -= HandleSessionChanged;
    }
}
