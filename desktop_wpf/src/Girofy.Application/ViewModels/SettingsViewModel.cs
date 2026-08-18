using System.Collections.ObjectModel;
using System.Globalization;
using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class SettingsViewModel : ObservableObject, IDisposable
{
    private readonly IGirofyApiClient _apiClient;
    private readonly IAppSessionContext _sessionContext;
    private readonly IThemeService _themeService;
    private readonly IExternalBrowserService _browserService;
    private readonly IFileSaveService _fileSaveService;
    private readonly IFilePickerService _filePickerService;
    private readonly Uri _webSettingsUri;
    private SettingsAccountSnapshot? _snapshot;
    private string _firstName = string.Empty;
    private string _lastName = string.Empty;
    private string _phone = string.Empty;
    private string _currentPassword = string.Empty;
    private string _newPassword = string.Empty;
    private string _confirmPassword = string.Empty;
    private bool _allowNegativeStock;
    private bool _pixFeeEnabled;
    private string _pixFeePercent = "0,00";
    private bool _debitFeeEnabled;
    private string _debitFeePercent = "0,00";
    private bool _creditFeeEnabled;
    private string _creditFeePercent = "0,00";
    private string _backupFrequency = "manual";
    private string _selectedExportType = "produtos";
    private string _teamSearch = string.Empty;
    private SettingsEmployee? _selectedEmployee;
    private string _employeeFirstName = string.Empty;
    private string _employeeLastName = string.Empty;
    private string _employeeCpf = string.Empty;
    private string _employeeEmail = string.Empty;
    private string _employeePhone = string.Empty;
    private string _employeeRole = "operator";
    private bool _employeeIsActive = true;
    private string _newEmployeeUsername = string.Empty;
    private string _newEmployeePassword = string.Empty;
    private string _newEmployeeFirstName = string.Empty;
    private string _newEmployeeLastName = string.Empty;
    private string _newEmployeeCpf = string.Empty;
    private string _newEmployeeEmail = string.Empty;
    private string _newEmployeePhone = string.Empty;
    private string _newEmployeeRole = "operator";
    private string _errorMessage = string.Empty;
    private string _successMessage = string.Empty;
    private bool _isBusy;

    public SettingsViewModel(
        IGirofyApiClient apiClient,
        IAppSessionContext sessionContext,
        IExternalBrowserService browserService,
        IFileSaveService fileSaveService,
        IFilePickerService filePickerService,
        Uri webSettingsUri,
        IThemeService? themeService = null)
    {
        _apiClient = apiClient;
        _sessionContext = sessionContext;
        _themeService = themeService ?? NullThemeService.Instance;
        _browserService = browserService;
        _fileSaveService = fileSaveService;
        _filePickerService = filePickerService;
        _webSettingsUri = webSettingsUri;
        RefreshCommand = new AsyncRelayCommand(LoadAsync);
        SaveProfileCommand = new AsyncRelayCommand(SaveProfileAsync);
        ChangePasswordCommand = new AsyncRelayCommand(ChangePasswordAsync);
        SaveCompanySettingsCommand = new AsyncRelayCommand(SaveCompanySettingsAsync, () => CanManageTeam && !IsBusy);
        SaveBackupSettingsCommand = new AsyncRelayCommand(SaveBackupSettingsAsync, () => CanManageTeam && !IsBusy);
        RunManualBackupCommand = new AsyncRelayCommand(RunManualBackupAsync, () => CanManageTeam && !IsBusy);
        ExportDataCommand = new AsyncRelayCommand(ExportDataAsync, () => CanExportData && !IsBusy);
        ImportProductsCommand = new AsyncRelayCommand(ImportProductsAsync, () => CanImportProducts && !IsBusy);
        RefreshTeamCommand = new AsyncRelayCommand(RefreshTeamAsync, () => CanManageTeam && !IsBusy);
        CreateEmployeeCommand = new AsyncRelayCommand(CreateEmployeeAsync, () => CanManageTeam && !IsBusy);
        SaveEmployeeCommand = new AsyncRelayCommand(SaveEmployeeAsync, () => CanManageTeam && HasSelectedEmployee && !IsBusy);
        ClearNewEmployeeCommand = new RelayCommand(ClearNewEmployeeForm);
        OpenWebSettingsCommand = new RelayCommand(() => _browserService.Open(_webSettingsUri));
        ToggleThemeCommand = new AsyncRelayCommand(ToggleThemeAsync);
        _sessionContext.Changed += HandleSessionChanged;
    }

    public ObservableCollection<SettingsEmployee> Employees { get; } = [];

    public ObservableCollection<SettingsEmployeeRoleOption> RoleOptions { get; } = [];

    public ObservableCollection<BackupFrequencyOption> BackupFrequencyOptions { get; } =
    [
        new("manual", "Somente manual"),
        new("daily", "Diário"),
        new("weekly", "Semanal"),
        new("monthly", "Mensal"),
    ];

    public ObservableCollection<ExportDataTypeOption> ExportTypeOptions { get; } =
    [
        new("produtos", "Produtos"),
        new("vendas", "Vendas"),
        new("caixas", "Caixas"),
        new("contas", "Contas a pagar"),
    ];

    public SettingsAccountSnapshot? Snapshot
    {
        get => _snapshot;
        private set
        {
            if (SetProperty(ref _snapshot, value))
            {
                OnPropertyChanged(nameof(HasData));
                OnPropertyChanged(nameof(CompanyName));
                OnPropertyChanged(nameof(PlanText));
                OnPropertyChanged(nameof(SubscriptionText));
                OnPropertyChanged(nameof(RoleText));
                OnPropertyChanged(nameof(EmailText));
                OnPropertyChanged(nameof(UsernameText));
                OnPropertyChanged(nameof(NegativeStockText));
                OnPropertyChanged(nameof(FeeText));
                OnPropertyChanged(nameof(BackupFrequencyText));
                OnPropertyChanged(nameof(BackupLastAtText));
                OnPropertyChanged(nameof(BackupStatusText));
                OnPropertyChanged(nameof(CanManageTeam));
                OnPropertyChanged(nameof(CanExportData));
                OnPropertyChanged(nameof(CanImportProducts));
                OnPropertyChanged(nameof(TeamVisibility));
                OnPropertyChanged(nameof(CompanySettingsVisibility));
                OnPropertyChanged(nameof(BackupVisibility));
                OnPropertyChanged(nameof(ExportVisibility));
                OnPropertyChanged(nameof(ImportVisibility));
                NotifyAdministrativeCommands();
            }
        }
    }

    public string FirstName
    {
        get => _firstName;
        set => SetProperty(ref _firstName, value);
    }

    public string LastName
    {
        get => _lastName;
        set => SetProperty(ref _lastName, value);
    }

    public string Phone
    {
        get => _phone;
        set => SetProperty(ref _phone, value);
    }

    public string CurrentPassword
    {
        get => _currentPassword;
        set => SetProperty(ref _currentPassword, value);
    }

    public string NewPassword
    {
        get => _newPassword;
        set => SetProperty(ref _newPassword, value);
    }

    public string ConfirmPassword
    {
        get => _confirmPassword;
        set => SetProperty(ref _confirmPassword, value);
    }

    public bool AllowNegativeStock
    {
        get => _allowNegativeStock;
        set
        {
            if (SetProperty(ref _allowNegativeStock, value))
            {
                OnPropertyChanged(nameof(NegativeStockText));
            }
        }
    }

    public bool PixFeeEnabled
    {
        get => _pixFeeEnabled;
        set
        {
            if (SetProperty(ref _pixFeeEnabled, value))
            {
                OnPropertyChanged(nameof(FeeText));
            }
        }
    }

    public string PixFeePercent
    {
        get => _pixFeePercent;
        set
        {
            if (SetProperty(ref _pixFeePercent, value))
            {
                OnPropertyChanged(nameof(FeeText));
            }
        }
    }

    public bool DebitFeeEnabled
    {
        get => _debitFeeEnabled;
        set
        {
            if (SetProperty(ref _debitFeeEnabled, value))
            {
                OnPropertyChanged(nameof(FeeText));
            }
        }
    }

    public string DebitFeePercent
    {
        get => _debitFeePercent;
        set
        {
            if (SetProperty(ref _debitFeePercent, value))
            {
                OnPropertyChanged(nameof(FeeText));
            }
        }
    }

    public bool CreditFeeEnabled
    {
        get => _creditFeeEnabled;
        set
        {
            if (SetProperty(ref _creditFeeEnabled, value))
            {
                OnPropertyChanged(nameof(FeeText));
            }
        }
    }

    public string CreditFeePercent
    {
        get => _creditFeePercent;
        set
        {
            if (SetProperty(ref _creditFeePercent, value))
            {
                OnPropertyChanged(nameof(FeeText));
            }
        }
    }

    public string BackupFrequency
    {
        get => _backupFrequency;
        set
        {
            if (SetProperty(ref _backupFrequency, value))
            {
                OnPropertyChanged(nameof(BackupFrequencyText));
            }
        }
    }

    public string SelectedExportType
    {
        get => _selectedExportType;
        set => SetProperty(ref _selectedExportType, string.IsNullOrWhiteSpace(value) ? "produtos" : value);
    }

    public string TeamSearch
    {
        get => _teamSearch;
        set => SetProperty(ref _teamSearch, value);
    }

    public SettingsEmployee? SelectedEmployee
    {
        get => _selectedEmployee;
        set
        {
            if (SetProperty(ref _selectedEmployee, value))
            {
                ApplySelectedEmployee(value);
                OnPropertyChanged(nameof(HasSelectedEmployee));
                SaveEmployeeCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public string EmployeeFirstName
    {
        get => _employeeFirstName;
        set => SetProperty(ref _employeeFirstName, value);
    }

    public string EmployeeLastName
    {
        get => _employeeLastName;
        set => SetProperty(ref _employeeLastName, value);
    }

    public string EmployeeCpf
    {
        get => _employeeCpf;
        set => SetProperty(ref _employeeCpf, value);
    }

    public string EmployeeEmail
    {
        get => _employeeEmail;
        set => SetProperty(ref _employeeEmail, value);
    }

    public string EmployeePhone
    {
        get => _employeePhone;
        set => SetProperty(ref _employeePhone, value);
    }

    public string EmployeeRole
    {
        get => _employeeRole;
        set => SetProperty(ref _employeeRole, value);
    }

    public bool EmployeeIsActive
    {
        get => _employeeIsActive;
        set => SetProperty(ref _employeeIsActive, value);
    }

    public string NewEmployeeUsername
    {
        get => _newEmployeeUsername;
        set => SetProperty(ref _newEmployeeUsername, value);
    }

    public string NewEmployeePassword
    {
        get => _newEmployeePassword;
        set => SetProperty(ref _newEmployeePassword, value);
    }

    public string NewEmployeeFirstName
    {
        get => _newEmployeeFirstName;
        set => SetProperty(ref _newEmployeeFirstName, value);
    }

    public string NewEmployeeLastName
    {
        get => _newEmployeeLastName;
        set => SetProperty(ref _newEmployeeLastName, value);
    }

    public string NewEmployeeCpf
    {
        get => _newEmployeeCpf;
        set => SetProperty(ref _newEmployeeCpf, value);
    }

    public string NewEmployeeEmail
    {
        get => _newEmployeeEmail;
        set => SetProperty(ref _newEmployeeEmail, value);
    }

    public string NewEmployeePhone
    {
        get => _newEmployeePhone;
        set => SetProperty(ref _newEmployeePhone, value);
    }

    public string NewEmployeeRole
    {
        get => _newEmployeeRole;
        set => SetProperty(ref _newEmployeeRole, value);
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

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetProperty(ref _isBusy, value))
            {
                NotifyAdministrativeCommands();
            }
        }
    }

    public bool HasData => Snapshot is not null;

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    public bool HasSuccess => !string.IsNullOrWhiteSpace(SuccessMessage);

    public bool CanManageTeam =>
        Snapshot?.User.Role is "admin" or "manager" or "master" ||
        (Snapshot?.User.Permissions.TryGetValue("can_manage_settings", out var canManageSettings) == true &&
            canManageSettings);

    public bool CanExportData => Snapshot?.User.Role is "admin" or "master" && Snapshot?.Company is not null;

    public bool CanImportProducts => Snapshot?.User.Role is "admin" or "manager" or "master" && Snapshot?.Company is not null;

    public bool HasSelectedEmployee => SelectedEmployee is not null;

    public string TeamVisibility => CanManageTeam ? "Visible" : "Collapsed";

    public string CompanySettingsVisibility => CanManageTeam ? "Visible" : "Collapsed";

    public string BackupVisibility => CanManageTeam ? "Visible" : "Collapsed";

    public string ExportVisibility => CanExportData ? "Visible" : "Collapsed";

    public string ImportVisibility => CanImportProducts ? "Visible" : "Collapsed";

    public string UsernameText => Snapshot?.Profile.Username ?? "-";

    public string EmailText => string.IsNullOrWhiteSpace(Snapshot?.Profile.Email)
        ? "E-mail não informado"
        : Snapshot.Profile.Email;

    public string RoleText => Snapshot?.Profile.RoleLabel ?? "-";

    public string CompanyName => Snapshot?.Company?.Name ?? "Adega não selecionada";

    public string PlanText => Snapshot?.Company is null
        ? "Plano não disponível"
        : $"{Snapshot.Company.SubscriptionPlan} · {(Snapshot.Company.SubscriptionValid ? "Ativo" : "Pendente")}";

    public string SubscriptionText => string.IsNullOrWhiteSpace(Snapshot?.Company?.SubscriptionRenewsAt)
        ? "Renovação não informada"
        : $"Renova em {Snapshot.Company.SubscriptionRenewsAt}";

    public string NegativeStockText => AllowNegativeStock
        ? "Venda sem estoque permitida"
        : "Venda sem estoque bloqueada";

    public string FeeText
    {
        get
        {
            if (Snapshot?.CompanySettings is null)
            {
                return "Taxas não configuradas";
            }

            return $"Pix {FormatFee(PixFeeEnabled, ParsePercentOrZero(PixFeePercent))} · Débito {FormatFee(DebitFeeEnabled, ParsePercentOrZero(DebitFeePercent))} · Crédito {FormatFee(CreditFeeEnabled, ParsePercentOrZero(CreditFeePercent))}";
        }
    }

    public string BackupFrequencyText =>
        BackupFrequencyOptions.FirstOrDefault(option => string.Equals(
            option.Value,
            Snapshot?.CompanySettings?.BackupFrequency ?? BackupFrequency,
            StringComparison.OrdinalIgnoreCase))?.Label ?? "Somente manual";

    public string BackupLastAtText
    {
        get
        {
            var rawValue = Snapshot?.CompanySettings?.BackupLastAt;
            if (string.IsNullOrWhiteSpace(rawValue))
            {
                return "Nenhum backup gerado ainda";
            }

            return DashboardFormatting.DateTimeText(rawValue);
        }
    }

    public string BackupStatusText => (Snapshot?.CompanySettings?.BackupLastStatus ?? string.Empty) switch
    {
        "success" => "Último backup concluído",
        "error" => "Último backup falhou",
        _ => "Aguardando primeiro backup",
    };

    public AsyncRelayCommand RefreshCommand { get; }

    public AsyncRelayCommand SaveProfileCommand { get; }

    public AsyncRelayCommand ChangePasswordCommand { get; }

    public AsyncRelayCommand SaveCompanySettingsCommand { get; }

    public AsyncRelayCommand SaveBackupSettingsCommand { get; }

    public AsyncRelayCommand RunManualBackupCommand { get; }

    public AsyncRelayCommand ExportDataCommand { get; }

    public AsyncRelayCommand ImportProductsCommand { get; }

    public AsyncRelayCommand RefreshTeamCommand { get; }

    public AsyncRelayCommand CreateEmployeeCommand { get; }

    public AsyncRelayCommand SaveEmployeeCommand { get; }

    public RelayCommand ClearNewEmployeeCommand { get; }

    public RelayCommand OpenWebSettingsCommand { get; }

    public AsyncRelayCommand ToggleThemeCommand { get; }

    public bool IsDarkMode => _themeService.IsDarkMode;

    public string ThemeToggleText => _themeService.IsDarkMode
        ? "Usar tema claro"
        : "Usar tema escuro";

    public Task InitializeAsync(CancellationToken cancellationToken = default) =>
        LoadAsync(cancellationToken);

    private async Task ToggleThemeAsync(CancellationToken cancellationToken)
    {
        await _themeService.ToggleAsync(cancellationToken);
        OnPropertyChanged(nameof(IsDarkMode));
        OnPropertyChanged(nameof(ThemeToggleText));
    }

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
            var snapshot = await _apiClient.GetSettingsAccountAsync(session.AccessToken, cancellationToken);
            if (!string.Equals(_sessionContext.Current?.AccessToken, session.AccessToken, StringComparison.Ordinal))
            {
                return;
            }

            ApplySnapshot(snapshot);
            if (CanManageTeam)
            {
                await LoadTeamDataAsync(session.AccessToken, cancellationToken);
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
            ErrorMessage = "O servidor demorou para carregar as configurações.";
        }
        catch (HttpRequestException)
        {
            ErrorMessage = "Não foi possível acessar as configurações agora.";
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível carregar as configurações. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task SaveProfileAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            var snapshot = await _apiClient.UpdateSettingsProfileAsync(
                session.AccessToken,
                new UpdateProfileRequest(FirstName.Trim(), LastName.Trim(), Phone.Trim()),
                cancellationToken);
            ApplySnapshot(snapshot);
            _sessionContext.Set(new AuthSession
            {
                AccessToken = session.AccessToken,
                RefreshToken = session.RefreshToken,
                TokenType = session.TokenType,
                ExpiresIn = session.ExpiresIn,
                RefreshExpiresAt = session.RefreshExpiresAt,
                User = snapshot.User,
                Company = snapshot.Company,
            });
            SuccessMessage = "Perfil atualizado com sucesso.";
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível salvar o perfil. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task ChangePasswordAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            var result = await _apiClient.ChangeSettingsPasswordAsync(
                session.AccessToken,
                new ChangePasswordRequest(CurrentPassword, NewPassword, ConfirmPassword),
                cancellationToken);
            CurrentPassword = string.Empty;
            NewPassword = string.Empty;
            ConfirmPassword = string.Empty;
            SuccessMessage = "Senha alterada. Entre novamente para continuar.";
            if (result.RequiresLogin)
            {
                _sessionContext.Clear();
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
        catch (Exception)
        {
            ErrorMessage = "Não foi possível alterar a senha. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task SaveCompanySettingsAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !CanManageTeam)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            var request = new UpdateCompanySettingsRequest(
                AllowNegativeStock,
                PixFeeEnabled,
                ParseRequiredPercent(PixFeePercent, "taxa Pix"),
                DebitFeeEnabled,
                ParseRequiredPercent(DebitFeePercent, "taxa de débito"),
                CreditFeeEnabled,
                ParseRequiredPercent(CreditFeePercent, "taxa de crédito"));
            var snapshot = await _apiClient.UpdateCompanySettingsAsync(
                session.AccessToken,
                request,
                cancellationToken);
            ApplySnapshot(snapshot);
            SuccessMessage = "Regras da adega salvas com sucesso.";
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (FormatException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível salvar as regras da adega. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task SaveBackupSettingsAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !CanManageTeam)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            var snapshot = await _apiClient.UpdateBackupSettingsAsync(
                session.AccessToken,
                new UpdateBackupSettingsRequest(BackupFrequency),
                cancellationToken);
            ApplySnapshot(snapshot);
            SuccessMessage = "Configuração de backup salva com sucesso.";
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível salvar a configuração de backup. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task RunManualBackupAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !CanManageTeam)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            var result = await _apiClient.RunManualBackupAsync(session.AccessToken, cancellationToken);
            ApplySnapshot(result);
            SuccessMessage = string.IsNullOrWhiteSpace(result.Backup.FileName)
                ? "Backup gerado com sucesso."
                : $"Backup gerado com sucesso: {result.Backup.FileName}";
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível gerar o backup agora. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task ExportDataAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !CanExportData)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            var file = await _apiClient.ExportSettingsDataAsync(
                session.AccessToken,
                SelectedExportType,
                cancellationToken);
            var savedPath = await _fileSaveService.SaveFileAsync(
                file.FileName,
                "CSV do Girofy (*.csv)|*.csv|Todos os arquivos (*.*)|*.*",
                file.Content,
                cancellationToken);

            SuccessMessage = string.IsNullOrWhiteSpace(savedPath)
                ? "Exportação cancelada."
                : $"Exportação salva em {savedPath}.";
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível exportar os dados agora. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task ImportProductsAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !CanImportProducts)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            var file = await _filePickerService.PickFileAsync(
                "Planilhas Girofy (*.csv;*.xlsx)|*.csv;*.xlsx|CSV (*.csv)|*.csv|Excel (*.xlsx)|*.xlsx|Todos os arquivos (*.*)|*.*",
                cancellationToken);
            if (file is null)
            {
                SuccessMessage = "Importação cancelada.";
                return;
            }

            var result = await _apiClient.ImportSettingsProductsAsync(
                session.AccessToken,
                file.FileName,
                file.ContentType,
                file.Content,
                cancellationToken);

            SuccessMessage =
                $"Importação concluída: {result.Created} criado(s), {result.Updated} atualizado(s), " +
                $"{result.Skipped} ignorado(s) e {result.Movements} movimentação(ões) de estoque.";
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível importar a planilha agora. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task RefreshTeamAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !CanManageTeam)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            await LoadTeamDataAsync(session.AccessToken, cancellationToken);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível carregar a equipe. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task CreateEmployeeAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        if (session is null || !CanManageTeam)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            await _apiClient.CreateSettingsEmployeeAsync(
                session.AccessToken,
                new CreateEmployeeRequest(
                    NewEmployeeUsername.Trim(),
                    NewEmployeePassword,
                    NewEmployeeFirstName.Trim(),
                    NewEmployeeLastName.Trim(),
                    NewEmployeeCpf.Trim(),
                    NewEmployeeEmail.Trim(),
                    NewEmployeePhone.Trim(),
                    NewEmployeeRole),
                cancellationToken);
            ClearNewEmployeeForm();
            await LoadTeamDataAsync(session.AccessToken, cancellationToken);
            SuccessMessage = "Funcionário cadastrado com sucesso.";
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível cadastrar o funcionário. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task SaveEmployeeAsync(CancellationToken cancellationToken)
    {
        var session = _sessionContext.Current;
        var employee = SelectedEmployee;
        if (session is null || employee is null || !CanManageTeam)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        try
        {
            await _apiClient.UpdateSettingsEmployeeAsync(
                session.AccessToken,
                employee.Id,
                new UpdateEmployeeRequest(
                    EmployeeFirstName.Trim(),
                    EmployeeLastName.Trim(),
                    EmployeeCpf.Trim(),
                    EmployeeEmail.Trim(),
                    EmployeePhone.Trim(),
                    EmployeeRole,
                    EmployeeIsActive),
                cancellationToken);
            await LoadTeamDataAsync(session.AccessToken, cancellationToken, employee.Id);
            SuccessMessage = "Funcionário atualizado com sucesso.";
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            ErrorMessage = exception.Message;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível salvar o funcionário. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LoadTeamDataAsync(
        string accessToken,
        CancellationToken cancellationToken,
        int? preserveEmployeeId = null)
    {
        var team = await _apiClient.GetSettingsTeamAsync(accessToken, TeamSearch, cancellationToken);
        RoleOptions.Clear();
        foreach (var role in team.Roles)
        {
            RoleOptions.Add(role);
        }

        if (RoleOptions.Count > 0)
        {
            if (!RoleOptions.Any(role => string.Equals(role.Value, NewEmployeeRole, StringComparison.Ordinal)))
            {
                NewEmployeeRole = RoleOptions[0].Value;
            }
            if (!RoleOptions.Any(role => string.Equals(role.Value, EmployeeRole, StringComparison.Ordinal)))
            {
                EmployeeRole = RoleOptions[0].Value;
            }
        }

        Employees.Clear();
        foreach (var employee in team.Employees)
        {
            Employees.Add(employee);
        }

        SelectedEmployee = Employees.FirstOrDefault(employee => employee.Id == preserveEmployeeId) ??
            Employees.FirstOrDefault();
    }

    private void ApplySnapshot(SettingsAccountSnapshot snapshot)
    {
        Snapshot = snapshot;
        FirstName = snapshot.Profile.FirstName;
        LastName = snapshot.Profile.LastName;
        Phone = snapshot.Profile.Phone;
        AllowNegativeStock = snapshot.CompanySettings?.AllowNegativeStock ?? false;
        PixFeeEnabled = snapshot.CompanySettings?.PixFeeEnabled ?? false;
        PixFeePercent = FormatPercentInput(snapshot.CompanySettings?.PixFeePercent ?? 0);
        DebitFeeEnabled = snapshot.CompanySettings?.DebitFeeEnabled ?? false;
        DebitFeePercent = FormatPercentInput(snapshot.CompanySettings?.DebitFeePercent ?? 0);
        CreditFeeEnabled = snapshot.CompanySettings?.CreditFeeEnabled ?? false;
        CreditFeePercent = FormatPercentInput(snapshot.CompanySettings?.CreditFeePercent ?? 0);
        BackupFrequency = string.IsNullOrWhiteSpace(snapshot.CompanySettings?.BackupFrequency)
            ? "manual"
            : snapshot.CompanySettings.BackupFrequency;
    }

    private void Reset()
    {
        Snapshot = null;
        FirstName = string.Empty;
        LastName = string.Empty;
        Phone = string.Empty;
        CurrentPassword = string.Empty;
        NewPassword = string.Empty;
        ConfirmPassword = string.Empty;
        AllowNegativeStock = false;
        PixFeeEnabled = false;
        PixFeePercent = "0,00";
        DebitFeeEnabled = false;
        DebitFeePercent = "0,00";
        CreditFeeEnabled = false;
        CreditFeePercent = "0,00";
        BackupFrequency = "manual";
        SelectedExportType = "produtos";
        TeamSearch = string.Empty;
        SelectedEmployee = null;
        Employees.Clear();
        RoleOptions.Clear();
        ClearNewEmployeeForm();
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        IsBusy = false;
    }

    private void ApplySelectedEmployee(SettingsEmployee? employee)
    {
        EmployeeFirstName = employee?.FirstName ?? string.Empty;
        EmployeeLastName = employee?.LastName ?? string.Empty;
        EmployeeCpf = employee?.Cpf ?? string.Empty;
        EmployeeEmail = employee?.Email ?? string.Empty;
        EmployeePhone = employee?.Phone ?? string.Empty;
        EmployeeRole = string.IsNullOrWhiteSpace(employee?.Role) ? "operator" : employee.Role;
        EmployeeIsActive = employee?.IsActive ?? true;
    }

    private void ClearNewEmployeeForm()
    {
        NewEmployeeUsername = string.Empty;
        NewEmployeePassword = string.Empty;
        NewEmployeeFirstName = string.Empty;
        NewEmployeeLastName = string.Empty;
        NewEmployeeCpf = string.Empty;
        NewEmployeeEmail = string.Empty;
        NewEmployeePhone = string.Empty;
        NewEmployeeRole = RoleOptions.FirstOrDefault()?.Value ?? "operator";
    }

    private void NotifyAdministrativeCommands()
    {
        SaveCompanySettingsCommand.NotifyCanExecuteChanged();
        SaveBackupSettingsCommand.NotifyCanExecuteChanged();
        RunManualBackupCommand.NotifyCanExecuteChanged();
        ExportDataCommand.NotifyCanExecuteChanged();
        ImportProductsCommand.NotifyCanExecuteChanged();
        RefreshTeamCommand.NotifyCanExecuteChanged();
        CreateEmployeeCommand.NotifyCanExecuteChanged();
        SaveEmployeeCommand.NotifyCanExecuteChanged();
    }

    private static string FormatFee(bool enabled, decimal percent) =>
        enabled ? $"{percent:0.##}%" : "inativo";

    private static string FormatPercentInput(decimal value) =>
        value.ToString("0.##", CultureInfo.GetCultureInfo("pt-BR"));

    private static decimal ParsePercentOrZero(string value)
    {
        try
        {
            return ParseRequiredPercent(value, "taxa");
        }
        catch (FormatException)
        {
            return 0;
        }
    }

    private static decimal ParseRequiredPercent(string value, string label)
    {
        var text = (value ?? string.Empty).Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            return 0;
        }

        var normalized = text.Replace("%", string.Empty).Trim();
        var firstCulture = normalized.Contains('.') && !normalized.Contains(',')
            ? CultureInfo.InvariantCulture
            : CultureInfo.GetCultureInfo("pt-BR");
        var fallbackCulture = firstCulture.Equals(CultureInfo.InvariantCulture)
            ? CultureInfo.GetCultureInfo("pt-BR")
            : CultureInfo.InvariantCulture;

        if (!decimal.TryParse(normalized, NumberStyles.Number, firstCulture, out var parsed) &&
            !decimal.TryParse(normalized, NumberStyles.Number, fallbackCulture, out parsed))
        {
            throw new FormatException($"Informe uma {label} válida.");
        }

        if (parsed < 0 || parsed > 100)
        {
            throw new FormatException($"A {label} deve ficar entre 0% e 100%.");
        }

        return decimal.Round(parsed, 2);
    }

    public void Dispose() => _sessionContext.Changed -= HandleSessionChanged;

    private sealed class NullThemeService : IThemeService
    {
        public static NullThemeService Instance { get; } = new();

        public bool IsDarkMode => true;

        public Task InitializeAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;

        public Task ToggleAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
    }
}
