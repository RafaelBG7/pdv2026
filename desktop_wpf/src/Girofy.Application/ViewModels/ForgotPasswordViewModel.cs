using System.Net;
using Girofy.Application.Abstractions;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class ForgotPasswordViewModel : ObservableObject
{
    public const string GenericSuccessMessage =
        "Se existir uma conta associada aos dados informados, enviaremos um link de recuperação. " +
        "Abra seu e-mail e siga as instruções no navegador.";

    private readonly IPasswordRecoveryService _service;
    private string _identifier = string.Empty;
    private string _errorMessage = string.Empty;
    private string _successMessage = string.Empty;
    private bool _isOpen;
    private bool _isLoading;

    public ForgotPasswordViewModel(IPasswordRecoveryService service)
    {
        _service = service;
        SubmitCommand = new AsyncRelayCommand(SubmitAsync, () => !IsLoading);
        CancelCommand = new RelayCommand(Close);
    }

    public string Identifier
    {
        get => _identifier;
        set => SetProperty(ref _identifier, value);
    }

    public string ErrorMessage
    {
        get => _errorMessage;
        private set
        {
            if (SetProperty(ref _errorMessage, value))
                OnPropertyChanged(nameof(HasError));
        }
    }

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    public string SuccessMessage
    {
        get => _successMessage;
        private set
        {
            if (SetProperty(ref _successMessage, value))
                OnPropertyChanged(nameof(IsSuccess));
        }
    }

    public bool IsSuccess => !string.IsNullOrWhiteSpace(SuccessMessage);

    public bool IsOpen
    {
        get => _isOpen;
        private set => SetProperty(ref _isOpen, value);
    }

    public bool IsLoading
    {
        get => _isLoading;
        private set
        {
            if (SetProperty(ref _isLoading, value))
            {
                OnPropertyChanged(nameof(SubmitButtonText));
                SubmitCommand.NotifyCanExecuteChanged();
            }
        }
    }

    public string SubmitButtonText => IsLoading ? "Enviando..." : "Enviar link";
    public AsyncRelayCommand SubmitCommand { get; }
    public RelayCommand CancelCommand { get; }

    public void Open()
    {
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        IsOpen = true;
    }

    public void Close()
    {
        SubmitCommand.Cancel();
        IsOpen = false;
    }

    private async Task SubmitAsync(CancellationToken cancellationToken)
    {
        ErrorMessage = string.Empty;
        SuccessMessage = string.Empty;
        var identifier = Identifier.Trim();
        if (string.IsNullOrWhiteSpace(identifier))
        {
            ErrorMessage = "Informe seu usuário ou e-mail.";
            return;
        }

        IsLoading = true;
        try
        {
            await _service.RequestAsync(identifier, cancellationToken);
            Identifier = identifier;
            SuccessMessage = GenericSuccessMessage;
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
        catch (TaskCanceledException)
        {
            ErrorMessage = "O servidor demorou para responder. Tente novamente.";
        }
        catch (HttpRequestException exception) when (exception.StatusCode == HttpStatusCode.TooManyRequests)
        {
            ErrorMessage = "Muitas solicitações foram realizadas. Aguarde alguns minutos e tente novamente.";
        }
        catch (HttpRequestException exception) when (exception.StatusCode is null)
        {
            ErrorMessage = "Não foi possível conectar ao servidor. Verifique sua internet e tente novamente.";
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível enviar a solicitação agora. Tente novamente mais tarde.";
        }
        finally
        {
            IsLoading = false;
        }
    }
}
