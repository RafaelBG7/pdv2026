using System.Collections.ObjectModel;
using System.Globalization;
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
    private CatalogProduct? _selectedProduct;
    private CatalogCategory? _editorCategory;
    private bool _isProductEditorOpen;
    private bool _isEditingProduct;
    private bool _editorActive = true;
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
        OpenNewProductCommand = new RelayCommand(OpenNewProduct, () => CanManageProducts && !IsBusy);
        OpenEditProductCommand = new RelayCommand(OpenSelectedProduct, () => CanManageProducts && SelectedProduct is not null && !IsBusy);
        CloseProductEditorCommand = new RelayCommand(CloseProductEditor);
        SaveProductCommand = new AsyncRelayCommand(SaveProductAsync, () => CanManageProducts && IsProductEditorOpen && !IsBusy);
        OpenNewCategoryCommand = new RelayCommand(OpenNewCategory, () => CanManageCategories && !IsBusy);
        OpenEditCategoryCommand = new RelayCommand(OpenSelectedCategory, () => CanManageCategories && SelectedCategoryRow is not null && !IsBusy);
        CloseCategoryEditorCommand = new RelayCommand(CloseCategoryEditor);
        SaveCategoryCommand = new AsyncRelayCommand(SaveCategoryAsync, () => CanManageCategories && IsCategoryEditorOpen && !IsBusy);
        DeleteCategoryCommand = new AsyncRelayCommand(DeleteCategoryAsync, () => CanManageCategories && SelectedCategoryRow is not null && !IsBusy);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<CatalogProduct> Products { get; } = [];

    public ObservableCollection<CatalogCategory> Categories { get; } = [];

    public ObservableCollection<CatalogCategory> CategoryRows { get; } = [];

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
                OpenEditProductCommand.NotifyCanExecuteChanged();
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
            }
        }
    }

    public bool IsEditingProduct
    {
        get => _isEditingProduct;
        private set => SetProperty(ref _isEditingProduct, value);
    }

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

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand PreviousPageCommand { get; }

    public AsyncRelayCommand NextPageCommand { get; }

    public RelayCommand ShowProductsCommand { get; }

    public RelayCommand ShowCategoriesCommand { get; }

    public RelayCommand OpenNewProductCommand { get; }

    public RelayCommand OpenEditProductCommand { get; }

    public RelayCommand CloseProductEditorCommand { get; }

    public AsyncRelayCommand SaveProductCommand { get; }

    public RelayCommand OpenNewCategoryCommand { get; }

    public RelayCommand OpenEditCategoryCommand { get; }

    public RelayCommand CloseCategoryEditorCommand { get; }

    public AsyncRelayCommand SaveCategoryCommand { get; }

    public AsyncRelayCommand DeleteCategoryCommand { get; }

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
        EditorCategory = Categories.FirstOrDefault();
        EditorCostPrice = "0,00";
        EditorSalePrice = "0,00";
        EditorStockQuantity = "0";
        EditorMinStockQuantity = "0";
        EditorStockReason = "Cadastro inicial";
        EditorActive = true;
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
            ? Categories.FirstOrDefault(category => category.Id == product.Category.Id)
            : Categories.FirstOrDefault();
        EditorCostPrice = FormatMoney(product.CostPrice ?? 0);
        EditorSalePrice = FormatMoney(product.SalePrice);
        EditorStockQuantity = product.StockQuantity.ToString(CultureInfo.InvariantCulture);
        EditorMinStockQuantity = product.MinStockQuantity.ToString(CultureInfo.InvariantCulture);
        EditorStockReason = "Ajuste pelo aplicativo Windows";
        EditorActive = product.Active;
        ErrorMessage = string.Empty;
        IsProductEditorOpen = true;
    }

    private void CloseProductEditor()
    {
        IsProductEditorOpen = false;
        ErrorMessage = string.Empty;
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

        Categories.Clear();
        CategoryRows.Clear();
        Categories.Add(new CatalogCategory { Id = 0, Name = "Todas", ProductCount = result.Total });
        foreach (var category in result.Items)
        {
            Categories.Add(category);
            CategoryRows.Add(category);
        }
        SelectedCategory = Categories.FirstOrDefault(category => category.Id == selectedCategoryId)
            ?? Categories.FirstOrDefault();
        SelectedCategoryRow = CategoryRows.FirstOrDefault(category => category.Id == selectedCategoryRowId);
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
        SelectedProduct = Products.FirstOrDefault(product => product.Id == SelectedProduct?.Id);
        Page = result.Pagination.Page;
        TotalPages = result.Pagination.TotalPages;
        TotalProducts = result.Pagination.Total;
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

        request = new CatalogProductMutationRequest(
            name,
            EditorBarcode.Trim(),
            EditorCategory is { Id: > 0 } ? EditorCategory.Id : null,
            costPrice,
            salePrice,
            stockQuantity,
            minStockQuantity,
            EditorActive,
            string.IsNullOrWhiteSpace(EditorStockReason)
                ? "Atualização pelo aplicativo Windows"
                : EditorStockReason.Trim());
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
        value.ToString("N2", CultureInfo.GetCultureInfo("pt-BR"));

    private static bool TryParseMoney(string value, out decimal amount)
    {
        var text = value.Trim();
        var brazilianCulture = CultureInfo.GetCultureInfo("pt-BR");
        var styles = NumberStyles.Number | NumberStyles.AllowCurrencySymbol;
        if (!decimal.TryParse(text, styles, brazilianCulture, out amount) &&
            !decimal.TryParse(text, styles, CultureInfo.InvariantCulture, out amount))
        {
            return false;
        }

        return amount >= 0;
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
        OpenNewCategoryCommand.NotifyCanExecuteChanged();
        OpenEditCategoryCommand.NotifyCanExecuteChanged();
        SaveCategoryCommand.NotifyCanExecuteChanged();
        DeleteCategoryCommand.NotifyCanExecuteChanged();
    }

    private void Reset()
    {
        Products.Clear();
        Categories.Clear();
        CategoryRows.Clear();
        SearchText = string.Empty;
        ErrorMessage = string.Empty;
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

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;
}
