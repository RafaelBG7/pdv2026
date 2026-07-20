using System.Windows;
using System.Windows.Controls;
using Girofy.Application.ViewModels;

namespace Girofy.Desktop.Views;

public partial class SettingsView : UserControl
{
    public SettingsView()
    {
        InitializeComponent();
    }

    private SettingsViewModel? ViewModel => DataContext as SettingsViewModel;

    private void HandleCurrentPasswordChanged(object sender, RoutedEventArgs e)
    {
        if (ViewModel is not null && sender is PasswordBox passwordBox)
        {
            ViewModel.CurrentPassword = passwordBox.Password;
        }
    }

    private void HandleNewPasswordChanged(object sender, RoutedEventArgs e)
    {
        if (ViewModel is not null && sender is PasswordBox passwordBox)
        {
            ViewModel.NewPassword = passwordBox.Password;
        }
    }

    private void HandleConfirmPasswordChanged(object sender, RoutedEventArgs e)
    {
        if (ViewModel is not null && sender is PasswordBox passwordBox)
        {
            ViewModel.ConfirmPassword = passwordBox.Password;
        }
    }

    private void HandleNewEmployeePasswordChanged(object sender, RoutedEventArgs e)
    {
        if (ViewModel is not null && sender is PasswordBox passwordBox)
        {
            ViewModel.NewEmployeePassword = passwordBox.Password;
        }
    }
}
