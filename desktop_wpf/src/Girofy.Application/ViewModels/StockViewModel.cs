using System.Collections.ObjectModel;
using System.Globalization;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class StockViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private string _searchText = string.Empty;
    private string _productSearchText = string.Empty;
    private string _errorMessage = string.Empty;
    private string _successMessage = string.Empty;
    private bool _isBusy;
    private bool _isInitialized;
    private bool _isMovementsTabSelected = true;
    private int _page = 1;
    private int _totalPages;
    private CatalogCategory? _selectedCategory;
    private CatalogFilterOption _selectedMovementType;
    private CatalogFilterOption _selectedSourceType;
    private CatalogFilterOption _selectedResponsibleUser;
    private DateTime? _startDate;
    private DateTime? _endDate;
    private bool _movementsLoaded;
    private bool _costsVisible;
    private StockMovementRecord? _selectedMovement;
    private StockMovementSummary _summary = new();
    private CatalogProduct? _entryProduct;
    private string _entryQuantityText = "1";
    private string _entryUnitCostText = "0,00";
    private string _entryReason = "Entrada manual";
    private string _entryNotes = string.Empty;
    private bool _entryUpdateCost = true;
    private CatalogProduct? _adjustmentProduct;
    private CatalogFilterOption _selectedAdjustmentMode;
    private CatalogFilterOption _selectedAdjustmentDirection;
    private string _adjustmentTargetStockText = "0";
    private string _adjustmentQuantityText = "1";
    private string _adjustmentReason = "Ajuste manual";
    private string _adjustmentNotes = string.Empty;

    public StockViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        _selectedMovementType = new CatalogFilterOption("all", "Todos");
        _selectedSourceType = new CatalogFilterOption("all", "Todas");
        _selectedResponsibleUser = new CatalogFilterOption("all", "Todos");
        AdjustmentModes =
        [
            new("target", "Definir estoque final"),
            new("delta", "Somar ou baixar quantidade"),
        ];
        AdjustmentDirections =
        [
            new("in", "Entrada"),
            new("out", "Saída"),
        ];
        _selectedAdjustmentMode = AdjustmentModes[0];
        _selectedAdjustmentDirection = AdjustmentDirections[0];
        SearchCommand = new AsyncRelayCommand(SearchAsync);
        RefreshCommand = new AsyncRelayCommand(RefreshAsync);
        ClearFiltersCommand = new AsyncRelayCommand(ClearFiltersAsync);
        SearchProductsCommand = new AsyncRelayCommand(SearchProductsAsync);
        PreviousPageCommand = new AsyncRelayCommand(PreviousPageAsync);
        NextPageCommand = new AsyncRelayCommand(NextPageAsync);
        RegisterEntryCommand = new AsyncRelayCommand(RegisterEntryAsync, () => CanManageStock && !IsBusy);
        RegisterAdjustmentCommand = new AsyncRelayCommand(RegisterAdjustmentAsync, () => CanManageStock && !IsBusy);
        ShowMovementsTabCommand = new RelayCommand(ShowMovementsTab);
        ShowManualEntriesTabCommand = new RelayCommand(ShowManualEntriesTab);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<StockMovementRecord> Movements { get; } = [];

    public ObservableCollection<CatalogCategory> Categories { get; } = [];

    public ObservableCollection<CatalogProduct> ProductOptions { get; } = [];

    public ObservableCollection<CatalogFilterOption> MovementTypes { get; } = [];

    public ObservableCollection<CatalogFilterOption> SourceTypes { get; } = [];

    public ObservableCollection<CatalogFilterOption> ResponsibleUsers { get; } = [];

    public IReadOnlyList<CatalogFilterOption> AdjustmentModes { get; }

    public IReadOnlyList<CatalogFilterOption> AdjustmentDirections { get; }

    public string SearchText
    {
        get => _searchText;
        set => SetProperty(ref _searchText, value);
    }

    public string ProductSearchText
    {
        get => _productSearchText;
        set => SetProperty(ref _productSearchText, value);
    }

    public CatalogCategory? SelectedCategory
    {
        get => _selectedCategory;
        set => SetProperty(ref _selectedCategory, value);
    }

    public CatalogFilterOption SelectedMovementType
    {
        get => _selectedMovementType;
        set => SetProperty(ref _selectedMovementType, value);
    }

    public CatalogFilterOption SelectedSourceType
    {
        get => _selectedSourceType;
        set => SetProperty(ref _selectedSourceType, value);
    }

    public CatalogFilterOption SelectedResponsibleUser
    {
        get => _selectedResponsibleUser;
        set => SetProperty(ref _selectedResponsibleUser, value);
    }

    public DateTime? StartDate
    {
        get => _startDate;
        set => SetProperty(ref _startDate, value);
    }

    public DateTime? EndDate
    {
        get => _endDate;
        set => SetProperty(ref _endDate, value);
    }

    public StockMovementRecord? SelectedMovement
    {
        get => _selectedMovement;
        set
        {
            if (SetProperty(ref _selectedMovement, value))
            {
                OnPropertyChanged(nameof(HasSelectedMovement));
            }
        }
    }

    public bool HasSelectedMovement => SelectedMovement is not null;

    public bool CostsVisible
    {
        get => _costsVisible;
        private set => SetProperty(ref _costsVisible, value);
    }

    public bool HasMovements => Movements.Count > 0;

    public bool ShowEmptyState => _movementsLoaded && !IsBusy && !HasError && !HasMovements;

    public string EmptyStateText => HasActiveFilters
        ? "Nenhuma movimentação encontrada para os filtros selecionados."
        : "Nenhuma movimentação de estoque encontrada.";

    public bool HasActiveFilters =>
        !string.IsNullOrWhiteSpace(SearchText) ||
        SelectedCategory is { Id: > 0 } ||
        SelectedMovementType.Value != "all" ||
        SelectedSourceType.Value != "all" ||
        SelectedResponsibleUser.Value != "all" ||
        StartDate.HasValue ||
        EndDate.HasValue;

    public StockMovementSummary Summary
    {
        get => _summary;
        private set => SetProperty(ref _summary, value);
    }

    public CatalogProduct? EntryProduct
    {
        get => _entryProduct;
        set => SetProperty(ref _entryProduct, value);
    }

    public string EntryQuantityText
    {
        get => _entryQuantityText;
        set => SetProperty(ref _entryQuantityText, value);
    }

    public string EntryUnitCostText
    {
        get => _entryUnitCostText;
        set => SetProperty(ref _entryUnitCostText, value);
    }

    public string EntryReason
    {
        get => _entryReason;
        set => SetProperty(ref _entryReason, value);
    }

    public string EntryNotes
    {
        get => _entryNotes;
        set => SetProperty(ref _entryNotes, value);
    }

    public bool EntryUpdateCost
    {
        get => _entryUpdateCost;
        set => SetProperty(ref _entryUpdateCost, value);
    }

    public CatalogProduct? AdjustmentProduct
    {
        get => _adjustmentProduct;
        set => SetProperty(ref _adjustmentProduct, value);
    }

    public CatalogFilterOption SelectedAdjustmentMode
    {
        get => _selectedAdjustmentMode;
        set
        {
            if (SetProperty(ref _selectedAdjustmentMode, value))
            {
                OnPropertyChanged(nameof(IsTargetAdjustment));
                OnPropertyChanged(nameof(IsDeltaAdjustment));
            }
        }
    }

    public bool IsTargetAdjustment => SelectedAdjustmentMode.Value == "target";

    public bool IsDeltaAdjustment => !IsTargetAdjustment;

    public CatalogFilterOption SelectedAdjustmentDirection
    {
        get => _selectedAdjustmentDirection;
        set => SetProperty(ref _selectedAdjustmentDirection, value);
    }

    public string AdjustmentTargetStockText
    {
        get => _adjustmentTargetStockText;
        set => SetProperty(ref _adjustmentTargetStockText, value);
    }

    public string AdjustmentQuantityText
    {
        get => _adjustmentQuantityText;
        set => SetProperty(ref _adjustmentQuantityText, value);
    }

    public string AdjustmentReason
    {
        get => _adjustmentReason;
        set => SetProperty(ref _adjustmentReason, value);
    }

    public string AdjustmentNotes
    {
        get => _adjustmentNotes;
        set => SetProperty(ref _adjustmentNotes, value);
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

    public bool IsMovementsTabSelected
    {
        get => _isMovementsTabSelected;
        private set
        {
            if (SetProperty(ref _isMovementsTabSelected, value))
            {
                OnPropertyChanged(nameof(IsManualEntriesTabSelected));
            }
        }
    }

    public bool IsManualEntriesTabSelected => !IsMovementsTabSelected;

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetProperty(ref _isBusy, value))
            {
                NotifyCommandState();
                NotifyMovementState();
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

    public bool CanViewStock => HasPermission("can_view_stock_movements") || CanManageStock;

    public bool CanManageStock => HasPermission("can_manage_stock");

    public bool IsAvailable => CanViewStock;

    public AsyncRelayCommand SearchCommand { get; }

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand ClearFiltersCommand { get; }

    public AsyncRelayCommand SearchProductsCommand { get; }

    public AsyncRelayCommand PreviousPageCommand { get; }

    public AsyncRelayCommand NextPageCommand { get; }

    public AsyncRelayCommand RegisterEntryCommand { get; }

    public AsyncRelayCommand RegisterAdjustmentCommand { get; }

    public RelayCommand ShowMovementsTabCommand { get; }

    public RelayCommand ShowManualEntriesTabCommand { get; }

    private void ShowMovementsTab() => IsMovementsTabSelected = true;

    private void ShowManualEntriesTab() => IsMovementsTabSelected = false;

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
        await LoadMovementsAsync(cancellationToken);
    }

    private async Task RefreshAsync(CancellationToken cancellationToken) => await LoadAsync(cancellationToken);

    private async Task ClearFiltersAsync(CancellationToken cancellationToken)
    {
        SearchText = string.Empty;
        SelectedCategory = Categories.FirstOrDefault();
        SelectedMovementType = MovementTypes.FirstOrDefault() ?? new CatalogFilterOption("all", "Todos");
        SelectedSourceType = SourceTypes.FirstOrDefault() ?? new CatalogFilterOption("all", "Todas");
        SelectedResponsibleUser = ResponsibleUsers.FirstOrDefault() ?? new CatalogFilterOption("all", "Todos");
        StartDate = null;
        EndDate = null;
        Page = 1;
        SelectedMovement = null;
        await LoadMovementsAsync(cancellationToken);
    }

    private async Task SearchProductsAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var result = await _apiClient.GetCatalogProductsAsync(
                session.AccessToken,
                ProductSearchText,
                null,
                "active",
                "name",
                1,
                40,
                cancellationToken);

            ProductOptions.Clear();
            foreach (var product in result.Items.OrderBy(product => product.Name, StringComparer.CurrentCultureIgnoreCase))
            {
                ProductOptions.Add(product);
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

    private async Task PreviousPageAsync(CancellationToken cancellationToken)
    {
        if (!CanGoPrevious)
        {
            return;
        }

        Page--;
        await LoadMovementsAsync(cancellationToken);
    }

    private async Task NextPageAsync(CancellationToken cancellationToken)
    {
        if (!CanGoNext)
        {
            return;
        }

        Page++;
        await LoadMovementsAsync(cancellationToken);
    }

    private async Task RegisterEntryAsync(CancellationToken cancellationToken)
    {
        if (!TryBuildEntryRequest(out var request))
        {
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var movement = await _apiClient.CreateStockEntryAsync(
                session.AccessToken,
                request,
                cancellationToken);
            SuccessMessage = $"Entrada registrada em {movement.ProductName}.";
            EntryQuantityText = "1";
            await ReloadAfterMutationAsync(cancellationToken);
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

    private async Task RegisterAdjustmentAsync(CancellationToken cancellationToken)
    {
        if (!TryBuildAdjustmentRequest(out var request))
        {
            return;
        }

        var session = RequireSession();
        IsBusy = true;
        ClearMessages();
        try
        {
            var result = await _apiClient.CreateStockAdjustmentAsync(
                session.AccessToken,
                request,
                cancellationToken);
            SuccessMessage = result.Changed && result.Movement is not null
                ? $"Estoque ajustado em {result.Movement.ProductName}."
                : result.Message;
            await ReloadAfterMutationAsync(cancellationToken);
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

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        if (!CanViewStock)
        {
            Reset();
            return;
        }

        IsBusy = true;
        ClearMessages();
        try
        {
            await LoadCategoriesAsync(cancellationToken);
            await LoadProductsCoreAsync(cancellationToken);
            await LoadMovementsCoreAsync(cancellationToken);
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

    private async Task LoadMovementsAsync(CancellationToken cancellationToken)
    {
        if (StartDate.HasValue && EndDate.HasValue && StartDate.Value.Date > EndDate.Value.Date)
        {
            ErrorMessage = "A data inicial não pode ser posterior à data final.";
            return;
        }

        IsBusy = true;
        _movementsLoaded = false;
        NotifyMovementState();
        ClearMessages();
        try
        {
            await LoadMovementsCoreAsync(cancellationToken);
        }
        catch (Exception exception)
        {
            SetSafeError(exception);
        }
        finally
        {
            _movementsLoaded = true;
            IsBusy = false;
            NotifyMovementState();
        }
    }

    private async Task ReloadAfterMutationAsync(CancellationToken cancellationToken)
    {
        await LoadProductsCoreAsync(cancellationToken);
        await LoadMovementsCoreAsync(cancellationToken);
    }

    private async Task LoadCategoriesAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        var selectedId = SelectedCategory?.Id ?? 0;
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
        SelectedCategory = Categories.FirstOrDefault(category => category.Id == selectedId)
            ?? Categories.FirstOrDefault();
    }

    private async Task LoadProductsCoreAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        var result = await _apiClient.GetCatalogProductsAsync(
            session.AccessToken,
            ProductSearchText,
            null,
            "active",
            "name",
            1,
            40,
            cancellationToken);

        var entryProductId = EntryProduct?.Id;
        var adjustmentProductId = AdjustmentProduct?.Id;
        ProductOptions.Clear();
        foreach (var product in result.Items.OrderBy(product => product.Name, StringComparer.CurrentCultureIgnoreCase))
        {
            ProductOptions.Add(product);
        }
        EntryProduct = ProductOptions.FirstOrDefault(product => product.Id == entryProductId)
            ?? ProductOptions.FirstOrDefault();
        AdjustmentProduct = ProductOptions.FirstOrDefault(product => product.Id == adjustmentProductId)
            ?? ProductOptions.FirstOrDefault();
    }

    private async Task LoadMovementsCoreAsync(CancellationToken cancellationToken)
    {
        var session = RequireSession();
        var result = await _apiClient.GetStockMovementsAsync(
            session.AccessToken,
            new StockMovementQuery(
                SearchText,
                SelectedCategory is { Id: > 0 } ? SelectedCategory.Id : null,
                SelectedMovementType.Value,
                SelectedSourceType.Value,
                int.TryParse(SelectedResponsibleUser.Value, out var responsibleUserId)
                    ? responsibleUserId
                    : null,
                StartDate,
                EndDate,
                Page,
                30),
            cancellationToken);

        Movements.Clear();
        SelectedMovement = null;
        foreach (var movement in result.Items)
        {
            Movements.Add(movement);
        }
        Summary = result.Summary;
        SyncFilterOptions(MovementTypes, result.MovementTypes, "Todos", ref _selectedMovementType);
        SyncFilterOptions(SourceTypes, result.SourceTypes, "Todas", ref _selectedSourceType);
        SyncFilterOptions(ResponsibleUsers, result.ResponsibleUsers, "Todos", ref _selectedResponsibleUser);
        OnPropertyChanged(nameof(SelectedMovementType));
        OnPropertyChanged(nameof(SelectedSourceType));
        OnPropertyChanged(nameof(SelectedResponsibleUser));
        CostsVisible = result.CostsVisible;
        Page = result.Pagination.Page;
        TotalPages = result.Pagination.TotalPages;
        _movementsLoaded = true;
        NotifyMovementState();
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
        foreach (var option in source)
        {
            target.Add(option);
        }
        selected = target.FirstOrDefault(option => option.Value == selectedValue) ?? target[0];
    }

    private bool TryBuildEntryRequest(out StockEntryRequest request)
    {
        request = new StockEntryRequest(0, 0, 0, string.Empty, string.Empty, false);
        if (EntryProduct is null)
        {
            ErrorMessage = "Selecione o produto da entrada.";
            return false;
        }
        if (!TryParsePositiveInteger(EntryQuantityText, out var quantity))
        {
            ErrorMessage = "Informe uma quantidade de entrada válida.";
            return false;
        }
        if (!TryParseMoney(EntryUnitCostText, out var unitCost))
        {
            ErrorMessage = "Informe um custo unitário válido.";
            return false;
        }
        if (string.IsNullOrWhiteSpace(EntryReason))
        {
            ErrorMessage = "Informe o motivo da entrada.";
            return false;
        }

        request = new StockEntryRequest(
            EntryProduct.Id,
            quantity,
            unitCost,
            EntryReason.Trim(),
            EntryNotes.Trim(),
            EntryUpdateCost);
        return true;
    }

    private bool TryBuildAdjustmentRequest(out StockAdjustmentRequest request)
    {
        request = new StockAdjustmentRequest(0, "target", 0, "in", 0, string.Empty, string.Empty);
        if (AdjustmentProduct is null)
        {
            ErrorMessage = "Selecione o produto do ajuste.";
            return false;
        }
        if (string.IsNullOrWhiteSpace(AdjustmentReason))
        {
            ErrorMessage = "Informe o motivo do ajuste.";
            return false;
        }
        if (!TryParseInteger(AdjustmentTargetStockText, out var targetStock))
        {
            ErrorMessage = "Informe um estoque final válido.";
            return false;
        }
        if (!TryParsePositiveInteger(AdjustmentQuantityText, out var quantity))
        {
            ErrorMessage = "Informe uma quantidade de ajuste válida.";
            return false;
        }

        request = new StockAdjustmentRequest(
            AdjustmentProduct.Id,
            SelectedAdjustmentMode.Value,
            targetStock,
            SelectedAdjustmentDirection.Value,
            quantity,
            AdjustmentReason.Trim(),
            AdjustmentNotes.Trim());
        return true;
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

    private static bool TryParseMoney(string value, out decimal amount)
    {
        var text = value.Trim();
        var styles = NumberStyles.Number | NumberStyles.AllowCurrencySymbol;
        return (decimal.TryParse(text, styles, CultureInfo.GetCultureInfo("pt-BR"), out amount) ||
                decimal.TryParse(text, styles, CultureInfo.InvariantCulture, out amount)) &&
            amount >= 0;
    }

    private static bool TryParseInteger(string value, out int amount) =>
        int.TryParse(value.Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out amount);

    private static bool TryParsePositiveInteger(string value, out int amount) =>
        TryParseInteger(value, out amount) && amount > 0;

    private void SetSafeError(Exception exception)
    {
        ErrorMessage = exception switch
        {
            GirofyApiException apiException => apiException.Message,
            TaskCanceledException => "O servidor demorou para responder. Tente novamente.",
            HttpRequestException => "Não foi possível consultar o estoque agora.",
            _ => "Não foi possível carregar o estoque. Tente novamente.",
        };
    }

    private void ClearMessages()
    {
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
    }

    private void NotifyMovementState()
    {
        OnPropertyChanged(nameof(HasMovements));
        OnPropertyChanged(nameof(ShowEmptyState));
        OnPropertyChanged(nameof(EmptyStateText));
        OnPropertyChanged(nameof(HasActiveFilters));
    }

    private void NotifyCommandState()
    {
        OnPropertyChanged(nameof(CanGoPrevious));
        OnPropertyChanged(nameof(CanGoNext));
        OnPropertyChanged(nameof(CanViewStock));
        OnPropertyChanged(nameof(CanManageStock));
        OnPropertyChanged(nameof(IsAvailable));
        RegisterEntryCommand.NotifyCanExecuteChanged();
        RegisterAdjustmentCommand.NotifyCanExecuteChanged();
    }

    private void Reset()
    {
        Movements.Clear();
        Categories.Clear();
        ProductOptions.Clear();
        MovementTypes.Clear();
        SourceTypes.Clear();
        ResponsibleUsers.Clear();
        Summary = new StockMovementSummary();
        SearchText = string.Empty;
        ProductSearchText = string.Empty;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        Page = 1;
        TotalPages = 0;
        StartDate = null;
        EndDate = null;
        SelectedMovement = null;
        CostsVisible = false;
        _movementsLoaded = false;
        EntryProduct = null;
        AdjustmentProduct = null;
        IsMovementsTabSelected = true;
        _isInitialized = false;
        NotifyCommandState();
    }

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;
}
