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

    private void SalesView_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.Key == Key.F3)
        {
            ExecuteIfAllowed(viewModel.OpenSaleEditorCommand);
            FocusProductSearch();
            e.Handled = true;
            return;
        }

        if (e.Key == Key.F2)
        {
            if (viewModel.IsDiscountPopupVisible)
            {
                ExecuteIfAllowed(viewModel.ApplyDiscountCommand);
            }
            else if (viewModel.IsPaymentStepVisible)
            {
                ExecuteIfAllowed(viewModel.FinalizeCommand);
            }
            else if (viewModel.IsProductStepOpen)
            {
                ExecuteIfAllowed(viewModel.OpenPaymentStepCommand);
                FocusPaymentMethod();
            }

            e.Handled = true;
        }
    }

    private void ProductSearchInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.Key == Key.Down && viewModel.HasSearchResults)
        {
            FocusSearchResults();
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Enter)
        {
            if (viewModel.HasSearchResults)
            {
                AddSelectedProductAndFocusSearch(viewModel);
            }
            else
            {
                ExecuteIfAllowed(viewModel.SearchCommand);
            }

            e.Handled = true;
        }
    }

    private void SearchResultsGrid_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.Key == Key.Enter)
        {
            AddSelectedProductAndFocusSearch(viewModel);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Escape)
        {
            FocusProductSearch();
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Up && SearchResultsGrid.SelectedIndex <= 0)
        {
            FocusProductSearch();
            e.Handled = true;
        }
    }

    private void PaymentTextBox_GotKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (sender is TextBox { Tag: string method } && DataContext is SalesViewModel viewModel)
        {
            viewModel.AutoCompletePaymentIfEmpty(method);
        }
    }

    private void PaymentTextBox_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (sender is not TextBox textBox)
        {
            return;
        }

        if (e.Key is Key.Down or Key.Right)
        {
            FocusNextPaymentField(textBox);
            e.Handled = true;
            return;
        }

        if (e.Key is Key.Up or Key.Left)
        {
            FocusPreviousPaymentField(textBox);
            e.Handled = true;
        }
    }

    private void DiscountPopupInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.Key == Key.Enter)
        {
            ExecuteIfAllowed(viewModel.ApplyDiscountCommand);
            if (!viewModel.IsDiscountPopupVisible)
            {
                FocusPaymentMethod();
            }
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Escape)
        {
            ExecuteIfAllowed(viewModel.CloseDiscountPopupCommand);
            FocusPaymentMethod();
            e.Handled = true;
        }
    }

    private void OpenDiscountPopupButton_Click(object sender, System.Windows.RoutedEventArgs e) =>
        FocusDiscountInput();

    private void AddSelectedProductAndFocusSearch(SalesViewModel viewModel)
    {
        ExecuteIfAllowed(viewModel.AddProductCommand);
        FocusProductSearch();
    }

    private void FocusProductSearch() =>
        Dispatcher.BeginInvoke((Action)(() =>
        {
            ProductSearchInput.Focus();
            ProductSearchInput.SelectAll();
        }));

    private void FocusPaymentMethod() =>
        Dispatcher.BeginInvoke((Action)(() =>
        {
            MoneyInput.Focus();
            MoneyInput.SelectAll();
        }));

    private void FocusDiscountInput() =>
        Dispatcher.BeginInvoke((Action)(() =>
        {
            DiscountPopupInput.Focus();
            DiscountPopupInput.SelectAll();
        }));

    private void FocusSearchResults()
    {
        if (SearchResultsGrid.Items.Count == 0)
        {
            return;
        }

        if (SearchResultsGrid.SelectedIndex < 0)
        {
            SearchResultsGrid.SelectedIndex = 0;
        }

        SearchResultsGrid.Focus();
        SearchResultsGrid.ScrollIntoView(SearchResultsGrid.SelectedItem);
    }

    private void FocusNextPaymentField(TextBox current) =>
        FocusPaymentField(current, forward: true);

    private void FocusPreviousPaymentField(TextBox current) =>
        FocusPaymentField(current, forward: false);

    private void FocusPaymentField(TextBox current, bool forward)
    {
        var fields = new[] { MoneyInput, PixInput, DebitInput, CreditInput };
        var currentIndex = Array.IndexOf(fields, current);
        if (currentIndex < 0)
        {
            return;
        }

        var nextIndex = forward
            ? (currentIndex + 1) % fields.Length
            : (currentIndex - 1 + fields.Length) % fields.Length;
        fields[nextIndex].Focus();
        fields[nextIndex].SelectAll();
    }

    private static void ExecuteIfAllowed(ICommand command)
    {
        if (command.CanExecute(null))
        {
            command.Execute(null);
        }
    }
}
