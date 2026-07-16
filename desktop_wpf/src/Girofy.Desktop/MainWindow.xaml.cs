using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using Girofy.Application.ViewModels;

namespace Girofy.Desktop;

public partial class MainWindow : Window
{
    private readonly ConnectionViewModel _viewModel;
    private bool _initialized;
    private bool _syncingPassword;

    public MainWindow(ConnectionViewModel viewModel)
    {
        InitializeComponent();
        _viewModel = viewModel;
        DataContext = viewModel;
        Loaded += HandleLoaded;
        _viewModel.Login.PropertyChanged += HandleLoginPropertyChanged;
    }

    private async void HandleLoaded(object sender, RoutedEventArgs e)
    {
        if (_initialized)
        {
            return;
        }

        _initialized = true;
        await _viewModel.InitializeAsync();

        if (_viewModel.Login.IsAuthenticated)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(_viewModel.Login.Identifier))
        {
            IdentifierInput.Focus();
        }
        else
        {
            PasswordInput.Focus();
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
        var showPassword = sender is CheckBox { IsChecked: true };
        _viewModel.Login.ShowPassword = showPassword;

        _syncingPassword = true;
        try
        {
            if (showPassword)
            {
                VisiblePasswordInput.Text = PasswordInput.Password;
                VisiblePasswordInput.CaretIndex = VisiblePasswordInput.Text.Length;
                VisiblePasswordInput.Focus();
            }
            else
            {
                PasswordInput.Password = VisiblePasswordInput.Text;
                PasswordInput.Focus();
            }
        }
        finally
        {
            _syncingPassword = false;
        }
    }

    private void HandleLoginPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName != nameof(LoginViewModel.Password) || _syncingPassword)
        {
            return;
        }

        _syncingPassword = true;
        try
        {
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
        finally
        {
            _syncingPassword = false;
        }
    }

    protected override void OnClosed(EventArgs e)
    {
        Loaded -= HandleLoaded;
        _viewModel.Login.PropertyChanged -= HandleLoginPropertyChanged;
        base.OnClosed(e);
    }
}
