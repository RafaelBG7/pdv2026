using System.Windows.Controls;
using System.Windows.Input;
using Girofy.Application.ViewModels;

namespace Girofy.Desktop.Views;

public partial class SalesView : UserControl
{
    public SalesView()
    {
        InitializeComponent();
    }

    private void PaymentTextBox_GotKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (sender is TextBox { Tag: string method } && DataContext is SalesViewModel viewModel)
        {
            viewModel.AutoCompletePaymentIfEmpty(method);
        }
    }
}
