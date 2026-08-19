using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using System.Windows.Input;
using Girofy.Application.ViewModels;
using Girofy.Desktop.Behaviors;
using Microsoft.Extensions.Logging;

namespace Girofy.Desktop;

public partial class MainWindow : Window
{
    private readonly ConnectionViewModel _viewModel;
    private readonly ILogger<MainWindow> _logger;
    private bool _initialized;
    private bool _syncingPassword;
    private readonly SmoothScrollController _smoothScrollController;

    public MainWindow(ConnectionViewModel viewModel, ILogger<MainWindow> logger)
    {
        InitializeComponent();
        _viewModel = viewModel;
        _logger = logger;
        DataContext = viewModel;
        _smoothScrollController = new SmoothScrollController(this);
        Loaded += HandleLoaded;
        _viewModel.Login.PropertyChanged += HandleLoginPropertyChanged;
        _viewModel.Login.ForgotPassword.PropertyChanged += HandleForgotPasswordPropertyChanged;
    }

    private void HandleForgotPasswordPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(ForgotPasswordViewModel.IsOpen) &&
            _viewModel.Login.ForgotPassword.IsOpen)
        {
            Dispatcher.InvokeAsync(
                () => ForgotPasswordIdentifierInput.Focus(),
                DispatcherPriority.Background);
        }
    }

    private void HandleForgotPasswordKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape)
        {
            _viewModel.Login.ForgotPassword.Close();
            e.Handled = true;
        }
    }

    private async void HandleLoaded(object sender, RoutedEventArgs e)
    {
        if (_initialized)
        {
            return;
        }

        try
        {
            _initialized = true;
            await _viewModel.InitializeAsync();
            QueueLoginFocus();
        }
        catch (Exception exception)
        {
            _logger.LogError(exception, "Main window initialization failed.");
            _initialized = false;
        }
    }

    private async void HandleNotificationsBellClick(object sender, RoutedEventArgs e)
    {
        NotificationsPopup.IsOpen = !NotificationsPopup.IsOpen;
        if (!NotificationsPopup.IsOpen)
        {
            return;
        }

        try
        {
            await _viewModel.Notifications.InitializeAsync();
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Notification popover initialization failed.");
        }
    }

    private void QueueLoginFocus()
    {
        if (_viewModel.Login.IsAuthenticated)
        {
            return;
        }

        Dispatcher.InvokeAsync(
            () =>
            {
                try
                {
                    if (_viewModel.Login.IsAuthenticated)
                    {
                        return;
                    }

                    if (string.IsNullOrWhiteSpace(_viewModel.Login.Identifier))
                    {
                        TryFocus(IdentifierInput);
                    }
                    else if (_viewModel.Login.ShowPassword)
                    {
                        TryFocus(VisiblePasswordInput);
                    }
                    else
                    {
                        TryFocus(PasswordInput);
                    }
                }
                catch (Exception exception)
                {
                    _logger.LogWarning(exception, "Initial login focus failed.");
                }
            },
            DispatcherPriority.Background);
    }

    private static void TryFocus(Control control)
    {
        if (control.IsVisible && control.IsEnabled)
        {
            control.Focus();
        }
    }

    private void HandlePasswordChanged(object sender, RoutedEventArgs e)
    {
        if (_syncingPassword || sender is not PasswordBox passwordBox)
        {
            return;
        }

        _viewModel.Login.Password = passwordBox.Password;
    }

    private void HandlePasswordVisibilityChanged(object sender, RoutedEventArgs e)
    {
        try
        {
            var showPassword = sender is CheckBox { IsChecked: true };
            _viewModel.Login.ShowPassword = showPassword;

            _syncingPassword = true;
            try
            {
                if (showPassword)
                {
                    VisiblePasswordInput.Text = PasswordInput.Password;
                    VisiblePasswordInput.CaretIndex = VisiblePasswordInput.Text.Length;
                    TryFocus(VisiblePasswordInput);
                }
                else
                {
                    PasswordInput.Password = VisiblePasswordInput.Text;
                    TryFocus(PasswordInput);
                }
            }
            finally
            {
                _syncingPassword = false;
            }
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Password visibility change failed.");
        }
    }

    private void HandleLoginPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(LoginViewModel.IsAuthenticated))
        {
            ApplyAuthenticationWindowMode();
            return;
        }

        if (e.PropertyName != nameof(LoginViewModel.Password) || _syncingPassword)
        {
            return;
        }

        try
        {
            _syncingPassword = true;
            var password = _viewModel.Login.Password;
            if (!string.Equals(PasswordInput.Password, password, StringComparison.Ordinal))
            {
                PasswordInput.Password = password;
            }

            if (!string.Equals(VisiblePasswordInput.Text, password, StringComparison.Ordinal))
            {
                VisiblePasswordInput.Text = password;
            }
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Password field synchronization failed.");
        }
        finally
        {
            _syncingPassword = false;
        }
    }

    private void ApplyAuthenticationWindowMode()
    {
        if (_viewModel.Login.IsAuthenticated)
        {
            MaxWidth = double.PositiveInfinity;
            MaxHeight = double.PositiveInfinity;
            MinWidth = 900;
            MinHeight = 640;
            ResizeMode = ResizeMode.CanResize;
            Width = 1180;
            Height = 780;
            return;
        }

        WindowState = WindowState.Normal;
        ResizeMode = ResizeMode.CanMinimize;
        MinWidth = 470;
        MinHeight = 640;
        MaxWidth = 470;
        MaxHeight = 700;
        Width = 470;
        Height = 700;
        QueueLoginFocus();
    }

    protected override void OnClosed(EventArgs e)
    {
        Loaded -= HandleLoaded;
        _viewModel.Login.PropertyChanged -= HandleLoginPropertyChanged;
        _viewModel.Login.ForgotPassword.PropertyChanged -= HandleForgotPasswordPropertyChanged;
        _smoothScrollController.Dispose();
        base.OnClosed(e);
    }
}
