using Girofy.Application.Abstractions;
using Girofy.Application.Exceptions;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class LoginViewModel : ObservableObject
{
    private readonly IGirofyApiClient _apiClient;
    private readonly ISecureSessionStore _sessionStore;
    private readonly IUserPreferencesStore _preferencesStore;
    private readonly IExternalBrowserService _browserService;
    private readonly IAppSessionContext _sessionContext;
    private readonly Uri _forgotPasswordUri;
    private AuthSession? _session;
    private string _identifier = string.Empty;
    private string _password = string.Empty;
    private string _errorMessage = string.Empty;
    private string _activationKey = string.Empty;
    private bool _rememberUsername;
    private bool _showPassword;
    private bool _isBusy;
    private bool _isAuthenticated;
    private bool _requiresSubscriptionActivation;
    private string _authenticatedUserName = string.Empty;
    private string _authenticatedCompanyName = string.Empty;
    private string _authenticatedRoleLabel = string.Empty;

    public LoginViewModel(
        IGirofyApiClient apiClient,
        ISecureSessionStore sessionStore,
        IUserPreferencesStore preferencesStore,
        IExternalBrowserService browserService,
        IAppSessionContext sessionContext,
        Uri forgotPasswordUri)
    {
        _apiClient = apiClient;
        _sessionStore = sessionStore;
        _preferencesStore = preferencesStore;
        _browserService = browserService;
        _sessionContext = sessionContext;
        _forgotPasswordUri = forgotPasswordUri;
        LoginCommand = new AsyncRelayCommand(LoginAsync);
        ActivateSubscriptionCommand = new AsyncRelayCommand(ActivateSubscriptionAsync);
        LogoutCommand = new AsyncRelayCommand(LogoutAsync);
        ForgotPasswordCommand = new RelayCommand(() => _browserService.Open(_forgotPasswordUri));
    }

    public string Identifier
    {
        get => _identifier;
        set => SetProperty(ref _identifier, value);
    }

    public string Password
    {
        get => _password;
        set => SetProperty(ref _password, value);
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

    public string ActivationKey
    {
        get => _activationKey;
        set => SetProperty(ref _activationKey, value);
    }

    public bool RequiresSubscriptionActivation
    {
        get => _requiresSubscriptionActivation;
        private set
        {
            if (SetProperty(ref _requiresSubscriptionActivation, value))
            {
                OnPropertyChanged(nameof(ShowLoginButton));
            }
        }
    }

    public bool ShowLoginButton => !RequiresSubscriptionActivation;

    public bool RememberUsername
    {
        get => _rememberUsername;
        set => SetProperty(ref _rememberUsername, value);
    }

    public bool ShowPassword
    {
        get => _showPassword;
        set => SetProperty(ref _showPassword, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetProperty(ref _isBusy, value))
            {
                OnPropertyChanged(nameof(LoginButtonText));
                OnPropertyChanged(nameof(ActivationButtonText));
            }
        }
    }

    public string LoginButtonText => IsBusy ? "Entrando..." : "Entrar";

    public string ActivationButtonText => IsBusy ? "Ativando..." : "Ativar assinatura";

    public bool IsAuthenticated
    {
        get => _isAuthenticated;
        private set => SetProperty(ref _isAuthenticated, value);
    }

    public string AuthenticatedUserName
    {
        get => _authenticatedUserName;
        private set => SetProperty(ref _authenticatedUserName, value);
    }

    public string AuthenticatedCompanyName
    {
        get => _authenticatedCompanyName;
        private set => SetProperty(ref _authenticatedCompanyName, value);
    }

    public string AuthenticatedRoleLabel
    {
        get => _authenticatedRoleLabel;
        private set => SetProperty(ref _authenticatedRoleLabel, value);
    }

    public AsyncRelayCommand LoginCommand { get; }

    public AsyncRelayCommand ActivateSubscriptionCommand { get; }

    public AsyncRelayCommand LogoutCommand { get; }

    public RelayCommand ForgotPasswordCommand { get; }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        var preferences = await _preferencesStore.LoadAsync(cancellationToken);
        RememberUsername = preferences.RememberUsername;
        Identifier = preferences.RememberedIdentifier;

        var storedSession = await _sessionStore.LoadAsync(cancellationToken);
        if (storedSession is null || string.IsNullOrWhiteSpace(storedSession.RefreshToken))
        {
            return;
        }

        IsBusy = true;
        try
        {
            var refreshedSession = await _apiClient.RefreshSessionAsync(
                storedSession.RefreshToken,
                cancellationToken);
            await _sessionStore.SaveAsync(refreshedSession, cancellationToken);
            ApplySession(refreshedSession);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            await _sessionStore.ClearAsync(cancellationToken);
            if (string.Equals(exception.Code, "https_required", StringComparison.Ordinal))
            {
                ErrorMessage = exception.Message;
            }
        }
        catch (Exception)
        {
            // A transient startup failure must not prevent a manual login attempt.
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LoginAsync(CancellationToken cancellationToken)
    {
        ErrorMessage = string.Empty;
        RequiresSubscriptionActivation = false;
        ActivationKey = string.Empty;
        var normalizedIdentifier = Identifier.Trim();
        if (string.IsNullOrWhiteSpace(normalizedIdentifier))
        {
            ErrorMessage = "Informe seu usuário ou e-mail.";
            return;
        }

        if (string.IsNullOrEmpty(Password))
        {
            ErrorMessage = "Informe sua senha.";
            return;
        }

        IsBusy = true;
        var keepPasswordForActivation = false;
        try
        {
            var session = await _apiClient.LoginAsync(
                normalizedIdentifier,
                Password,
                cancellationToken);
            await _sessionStore.SaveAsync(session, cancellationToken);
            await _preferencesStore.SaveAsync(
                new UserPreferences
                {
                    RememberUsername = RememberUsername,
                    RememberedIdentifier = RememberUsername ? normalizedIdentifier : string.Empty,
                },
                cancellationToken);
            ApplySession(session);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (GirofyApiException exception)
        {
            if (string.Equals(exception.Code, "subscription_required", StringComparison.Ordinal))
            {
                RequiresSubscriptionActivation = true;
                keepPasswordForActivation = true;
                ErrorMessage = "Sua assinatura precisa de ativação. Informe a key para continuar.";
                return;
            }

            ErrorMessage = exception.Message;
        }
        catch (TaskCanceledException)
        {
            ErrorMessage = "O servidor demorou para responder. Tente novamente.";
        }
        catch (HttpRequestException)
        {
            ErrorMessage = "Não foi possível acessar o servidor Girofy.";
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível entrar agora. Tente novamente.";
        }
        finally
        {
            if (!keepPasswordForActivation)
            {
                Password = string.Empty;
            }
            IsBusy = false;
        }
    }

    private async Task ActivateSubscriptionAsync(CancellationToken cancellationToken)
    {
        ErrorMessage = string.Empty;
        var normalizedIdentifier = Identifier.Trim();
        var normalizedActivationKey = ActivationKey.Trim();

        if (string.IsNullOrWhiteSpace(normalizedIdentifier))
        {
            ErrorMessage = "Informe seu usuário ou e-mail.";
            RequiresSubscriptionActivation = false;
            return;
        }

        if (string.IsNullOrEmpty(Password))
        {
            ErrorMessage = "Informe sua senha novamente para ativar a assinatura.";
            RequiresSubscriptionActivation = false;
            return;
        }

        if (string.IsNullOrWhiteSpace(normalizedActivationKey))
        {
            ErrorMessage = "Informe a key de ativação.";
            return;
        }

        IsBusy = true;
        try
        {
            var session = await _apiClient.ActivateSubscriptionAsync(
                normalizedIdentifier,
                Password,
                normalizedActivationKey,
                cancellationToken);
            await _sessionStore.SaveAsync(session, cancellationToken);
            await _preferencesStore.SaveAsync(
                new UserPreferences
                {
                    RememberUsername = RememberUsername,
                    RememberedIdentifier = RememberUsername ? normalizedIdentifier : string.Empty,
                },
                cancellationToken);
            RequiresSubscriptionActivation = false;
            ActivationKey = string.Empty;
            Password = string.Empty;
            ApplySession(session);
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
            ErrorMessage = "O servidor demorou para responder. Tente novamente.";
        }
        catch (HttpRequestException)
        {
            ErrorMessage = "Não foi possível acessar o servidor Girofy.";
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível ativar a assinatura agora. Tente novamente.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LogoutAsync(CancellationToken cancellationToken)
    {
        var accessToken = _session?.AccessToken;
        try
        {
            if (!string.IsNullOrWhiteSpace(accessToken))
            {
                await _apiClient.LogoutAsync(accessToken, cancellationToken);
            }
        }
        catch (Exception)
        {
            // Local logout always wins, even when the server is unavailable.
        }
        finally
        {
            // O logout local precisa vencer mesmo se a chamada ao servidor for cancelada.
            await _sessionStore.ClearAsync(CancellationToken.None);
            ClearAuthentication();
        }
    }

    private void ApplySession(AuthSession session)
    {
        _session = session;
        _sessionContext.Set(session);
        AuthenticatedUserName = string.IsNullOrWhiteSpace(session.User.FullName)
            ? session.User.Username
            : session.User.FullName;
        AuthenticatedCompanyName = session.Company?.Name ?? "Painel master";
        AuthenticatedRoleLabel = session.User.RoleLabel;
        RequiresSubscriptionActivation = false;
        ActivationKey = string.Empty;
        ErrorMessage = string.Empty;
        IsAuthenticated = true;
    }

    private void ClearAuthentication()
    {
        _session = null;
        _sessionContext.Clear();
        AuthenticatedUserName = string.Empty;
        AuthenticatedCompanyName = string.Empty;
        AuthenticatedRoleLabel = string.Empty;
        RequiresSubscriptionActivation = false;
        ActivationKey = string.Empty;
        IsAuthenticated = false;
    }
}
