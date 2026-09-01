using System;
using System.ComponentModel;
using System.Globalization;
using System.Linq;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using Girofy.Application.Models;
using Girofy.Application.Services;
using Girofy.Application.ViewModels;

namespace Girofy.Desktop.Views;

public partial class SalesView : UserControl
{
    private const double CompactSaleEditorWidth = 1100d;
    private const double CompactPaymentWidth = 640d;
    private static readonly CultureInfo BrazilianCulture = new("pt-BR");
    private static readonly Regex DigitsOnlyRegex = new(@"^\d+$", RegexOptions.Compiled);
    private readonly BarcodeScannerInputService _barcodeScanner = new();

    public SalesView()
    {
        InitializeComponent();
        DataContextChanged += SalesView_DataContextChanged;
        Loaded += SalesView_Loaded;
        Unloaded += SalesView_Unloaded;
    }

    private void SalesView_Loaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        viewModel.PropertyChanged -= ViewModel_PropertyChanged;
        viewModel.PropertyChanged += ViewModel_PropertyChanged;

        if (viewModel.IsProductStepOpen)
        {
            FocusProductSearch();
        }
        else if (viewModel.IsPaymentStepVisible)
        {
            FocusPaymentMethod();
        }
    }

    private void ProductStepRoot_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        var compact = e.NewSize.Width < CompactSaleEditorWidth;

        ProductPrimaryColumn.Width = new GridLength(1.18, GridUnitType.Star);
        ProductContentGapColumn.Width = compact ? new GridLength(0) : new GridLength(16);
        ProductSecondaryColumn.Width = compact
            ? new GridLength(0)
            : new GridLength(0.82, GridUnitType.Star);

        ProductPrimaryRow.Height = compact ? GridLength.Auto : new GridLength(1, GridUnitType.Star);
        ProductContentGapRow.Height = compact ? new GridLength(12) : new GridLength(0);
        ProductSecondaryRow.Height = compact ? GridLength.Auto : new GridLength(0);

        Grid.SetRow(ProductSearchPanel, 0);
        Grid.SetColumn(ProductSearchPanel, 0);
        Grid.SetRow(CartItemsPanel, compact ? 2 : 0);
        Grid.SetColumn(CartItemsPanel, compact ? 0 : 2);
    }

    private void PaymentContentGrid_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        var compact = e.NewSize.Width < CompactPaymentWidth;

        PaymentPrimaryColumn.Width = new GridLength(1.05, GridUnitType.Star);
        PaymentContentGapColumn.Width = compact ? new GridLength(0) : new GridLength(18);
        PaymentSecondaryColumn.Width = compact
            ? new GridLength(0)
            : new GridLength(0.95, GridUnitType.Star);

        PaymentPrimaryRow.Height = GridLength.Auto;
        PaymentContentGapRow.Height = compact ? new GridLength(12) : new GridLength(0);
        PaymentSecondaryRow.Height = compact ? GridLength.Auto : new GridLength(0);

        Grid.SetRow(PaymentMethodsPanel, 0);
        Grid.SetColumn(PaymentMethodsPanel, 0);
        Grid.SetRow(PaymentSummaryPanel, compact ? 2 : 0);
        Grid.SetColumn(PaymentSummaryPanel, compact ? 0 : 2);
    }

    private void SalesView_DataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if (e.OldValue is SalesViewModel oldViewModel)
        {
            oldViewModel.PropertyChanged -= ViewModel_PropertyChanged;
        }

        if (e.NewValue is SalesViewModel newViewModel)
        {
            newViewModel.PropertyChanged += ViewModel_PropertyChanged;
        }
    }

    private void SalesView_Unloaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is SalesViewModel viewModel)
        {
            viewModel.PropertyChanged -= ViewModel_PropertyChanged;
        }
    }

    private void ViewModel_PropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (sender is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.PropertyName == nameof(SalesViewModel.IsOpenCashPromptOpen) && viewModel.IsOpenCashPromptOpen)
        {
            FocusOpeningCashInput();
            return;
        }

        if (e.PropertyName == nameof(SalesViewModel.IsProductStepOpen) && viewModel.IsProductStepOpen)
        {
            FocusProductSearch();
            return;
        }

        if (e.PropertyName == nameof(SalesViewModel.IsPaymentStepVisible) && viewModel.IsPaymentStepVisible)
        {
            FocusPaymentMethod();
            return;
        }

        if (e.PropertyName == nameof(SalesViewModel.IsDiscountPopupVisible) && viewModel.IsDiscountPopupVisible)
        {
            FocusDiscountInput();
            return;
        }

        if (e.PropertyName == nameof(SalesViewModel.IsSaleEditorOpen) && !viewModel.IsSaleEditorOpen)
        {
            _barcodeScanner.Reset();
        }
    }

    private void SalesView_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (viewModel.HasReceipt && (e.Key is Key.Enter or Key.Space) && !IsTextInputFocused())
        {
            ExecuteIfAllowed(viewModel.NewSaleCommand);
            FocusProductSearch();
            e.Handled = true;
            return;
        }

        if (viewModel.IsOpenCashPromptOpen)
        {
            if (e.Key == Key.Enter)
            {
                ExecuteIfAllowed(viewModel.ConfirmOpenCashBeforeSaleCommand);
                e.Handled = true;
                return;
            }

            if (e.Key == Key.Escape)
            {
                ExecuteIfAllowed(viewModel.HandleSaleEscapeCommand);
                e.Handled = true;
                return;
            }
        }

        if (viewModel.IsDiscardConfirmationOpen && e.Key != Key.Escape)
        {
            return;
        }

        if (e.Key == Key.Escape && viewModel.IsSaleEditorOpen)
        {
            ExecuteIfAllowed(viewModel.HandleSaleEscapeCommand);

            e.Handled = true;
            return;
        }

        if (e.Key == Key.Enter && CanCaptureScannerGlobally(viewModel)
            && _barcodeScanner.TryComplete(DateTimeOffset.UtcNow, out var barcode))
        {
            _ = SelectScannedBarcodeAsync(viewModel, barcode);
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

    private void SalesView_PreviewTextInput(object sender, TextCompositionEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel || !CanCaptureScannerGlobally(viewModel))
        {
            _barcodeScanner.Reset();
            return;
        }

        _barcodeScanner.Append(e.Text, DateTimeOffset.UtcNow);
        e.Handled = true;
    }

    private static bool CanCaptureScannerGlobally(SalesViewModel viewModel) =>
        viewModel.IsProductStepOpen
        && !viewModel.IsQuantityPopupOpen
        && !viewModel.IsDiscountPopupVisible
        && !viewModel.IsDiscardConfirmationOpen
        && !IsTextInputFocused();

    private async Task SelectScannedBarcodeAsync(SalesViewModel viewModel, string barcode)
    {
        if (await viewModel.SelectExactBarcodeAsync(barcode, showNotFound: true))
        {
            FocusQuantityInput();
            return;
        }

        FocusProductSearch();
    }

    private async void ProductSearchInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.Key == Key.Down && viewModel.HasSearchResults)
        {
            MoveSearchSuggestion(1, focusList: false);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Up && viewModel.HasSearchResults)
        {
            MoveSearchSuggestion(-1, focusList: false);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Escape)
        {
            viewModel.SearchText = string.Empty;
            FocusProductSearch();
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Enter)
        {
            // When the user navigates the suggestions with the arrow keys, confirm
            // that selection before starting an asynchronous barcode lookup. The
            // lookup can yield long enough for the live search to refresh the list
            // and reset its selection to the first product.
            if (viewModel.HasSearchResults)
            {
                ConfirmSelectedProductAndFocusQuantity(viewModel);
                e.Handled = true;
                return;
            }

            var exactMatch = await viewModel.SelectExactBarcodeAsync(
                viewModel.SearchText,
                showNotFound: false);
            if (exactMatch)
            {
                FocusQuantityInput();
                e.Handled = true;
                return;
            }

            if (!viewModel.HasSearchResults && viewModel.SearchCommand.CanExecute(null))
            {
                await viewModel.SearchCommand.ExecuteAsync();
            }

            if (viewModel.HasSearchResults)
            {
                ConfirmSelectedProductAndFocusQuantity(viewModel);
            }
            else
            {
                FocusProductSearch();
            }

            e.Handled = true;
        }
    }

    private void SearchSuggestionsList_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.Key == Key.Enter)
        {
            ConfirmSelectedProductAndFocusQuantity(viewModel);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Escape)
        {
            viewModel.SearchText = string.Empty;
            FocusProductSearch();
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Down)
        {
            MoveSearchSuggestion(1);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Up)
        {
            MoveSearchSuggestion(-1);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Home)
        {
            SelectSearchSuggestion(0);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.End)
        {
            SelectSearchSuggestion(SearchSuggestionsList.Items.Count - 1);
            e.Handled = true;
        }
    }

    private void SearchSuggestionsList_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel || !viewModel.HasSearchResults)
        {
            return;
        }

        ConfirmSelectedProductAndFocusQuantity(viewModel);
        e.Handled = true;
    }

    private void SearchSuggestionsList_PreviewMouseLeftButtonUp(object sender, MouseButtonEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        var item = FindParent<ListBoxItem>(e.OriginalSource as DependencyObject);
        if (item?.DataContext is not CatalogProduct product)
        {
            return;
        }

        SearchSuggestionsList.SelectedItem = product;
        viewModel.SelectedSearchProduct = product;
        ConfirmSelectedProductAndFocusQuantity(viewModel);
        e.Handled = true;
    }

    private void QuantityInput_LostKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (DataContext is SalesViewModel viewModel)
        {
            NormalizeQuantityText(viewModel);
        }
    }

    private void QuantityInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.Key == Key.Enter)
        {
            NormalizeQuantityText(viewModel);
            AddSelectedProductAndFocusSearch(viewModel);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Escape)
        {
            ExecuteIfAllowed(viewModel.CloseQuantityPopupCommand);
            FocusProductSearch();
            e.Handled = true;
        }
    }

    private void QuantityInput_PreviewTextInput(object sender, TextCompositionEventArgs e)
    {
        if (!DigitsOnlyRegex.IsMatch(e.Text))
        {
            e.Handled = true;
        }
    }

    private void QuantityInput_Pasting(object sender, DataObjectPastingEventArgs e)
    {
        if (sender is not TextBox textBox || !e.DataObject.GetDataPresent(DataFormats.Text))
        {
            e.CancelCommand();
            return;
        }

        var pastedText = e.DataObject.GetData(DataFormats.Text) as string ?? string.Empty;
        var digits = ExtractDigits(pastedText);
        if (digits.Length == 0)
        {
            e.CancelCommand();
            return;
        }

        textBox.Text = digits;
        textBox.CaretIndex = textBox.Text.Length;
        e.CancelCommand();
    }

    private void PaymentTextBox_GotKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (sender is TextBox textBox && textBox.Tag is string method && DataContext is SalesViewModel viewModel)
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

        if (TryGetDigitFromKey(e.Key, out var digit))
        {
            AppendCurrencyDigit(textBox, digit);
            e.Handled = true;
            return;
        }

        if (e.Key is Key.Back or Key.Delete)
        {
            RemoveCurrencyDigit(textBox);
            e.Handled = true;
            return;
        }

        if (e.Key is Key.Space or Key.Decimal or Key.OemComma or Key.OemPeriod)
        {
            e.Handled = true;
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

    private void PaymentTextBox_PreviewTextInput(object sender, TextCompositionEventArgs e)
    {
        if (sender is not TextBox textBox || !DigitsOnlyRegex.IsMatch(e.Text))
        {
            e.Handled = true;
            return;
        }

        AppendCurrencyDigit(textBox, e.Text[^1]);
        e.Handled = true;
    }

    private void PaymentTextBox_Pasting(object sender, DataObjectPastingEventArgs e)
    {
        if (sender is not TextBox textBox || !e.DataObject.GetDataPresent(DataFormats.Text))
        {
            e.CancelCommand();
            return;
        }

        var pastedText = e.DataObject.GetData(DataFormats.Text) as string ?? string.Empty;
        var digits = ExtractDigits(pastedText);
        if (digits.Length == 0)
        {
            e.CancelCommand();
            return;
        }

        SetCurrencyDigits(textBox, digits);
        e.CancelCommand();
    }

    private void PaymentTextBox_LostKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (sender is TextBox textBox)
        {
            EnsureCurrencyText(textBox);
        }
    }

    private void OpeningCashInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        if (e.Key == Key.Enter)
        {
            ExecuteIfAllowed(viewModel.ConfirmOpenCashBeforeSaleCommand);
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Escape)
        {
            ExecuteIfAllowed(viewModel.CancelOpenCashBeforeSaleCommand);
            e.Handled = true;
            return;
        }

        PaymentTextBox_PreviewKeyDown(sender, e);
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

    private void AddProductButton_Click(object sender, RoutedEventArgs e)
    {
        if (DataContext is not SalesViewModel viewModel)
        {
            return;
        }

        NormalizeQuantityText(viewModel);
        AddSelectedProductAndFocusSearch(viewModel);
    }

    private void ConfirmSelectedProductAndFocusQuantity(SalesViewModel viewModel)
    {
        if (SearchSuggestionsList.SelectedItem is CatalogProduct selectedProduct)
        {
            viewModel.SelectedSearchProduct = selectedProduct;
        }
        else if (viewModel.SelectedSearchProduct is null
                 && SearchSuggestionsList.Items.Count > 0
                 && SearchSuggestionsList.Items[0] is CatalogProduct firstProduct)
        {
            viewModel.SelectedSearchProduct = firstProduct;
        }

        if (viewModel.SelectedSearchProduct is null)
        {
            FocusProductSearch();
            return;
        }

        NormalizeQuantityText(viewModel);
        ExecuteIfAllowed(viewModel.OpenQuantityPopupCommand);
        FocusQuantityInput();
    }

    private void CloseQuantityPopupButton_Click(object sender, RoutedEventArgs e)
    {
        if (DataContext is SalesViewModel viewModel)
        {
            ExecuteIfAllowed(viewModel.CloseQuantityPopupCommand);
            FocusProductSearch();
        }
    }

    private static void NormalizeQuantityText(SalesViewModel viewModel)
    {
        if (!int.TryParse(viewModel.QuantityText, out var quantity) || quantity < 1)
        {
            viewModel.QuantityText = "1";
        }
    }

    private void AddSelectedProductAndFocusSearch(SalesViewModel viewModel)
    {
        ExecuteIfAllowed(viewModel.AddProductCommand);
        if (viewModel.HasError)
        {
            FocusQuantityInput();
        }
        else
        {
            FocusProductSearch();
        }
    }

    private void FocusProductSearch() =>
        Dispatcher.BeginInvoke((Action)(() =>
        {
            if (!ProductSearchInput.IsVisible || !ProductSearchInput.IsEnabled)
            {
                return;
            }

            ProductSearchInput.Focus();
            Keyboard.Focus(ProductSearchInput);
            ProductSearchInput.CaretIndex = 0;
            ProductSearchInput.SelectionLength = 0;
        }), DispatcherPriority.Input);

    private void FocusQuantityInput() =>
        Dispatcher.BeginInvoke((Action)(() =>
        {
            QuantityInput.Focus();
            QuantityInput.SelectAll();
        }));

    private void FocusPaymentMethod() =>
        Dispatcher.BeginInvoke((Action)(() =>
        {
            if (!MoneyInput.IsVisible || !MoneyInput.IsEnabled)
            {
                return;
            }

            MoneyInput.Focus();
            Keyboard.Focus(MoneyInput);
            MoneyInput.SelectAll();
        }), DispatcherPriority.Input);

    private void FocusOpeningCashInput() =>
        Dispatcher.BeginInvoke((Action)(() =>
        {
            OpeningCashInput.Focus();
            OpeningCashInput.SelectAll();
        }));

    private void FocusDiscountInput() =>
        Dispatcher.BeginInvoke((Action)(() =>
        {
            DiscountPopupInput.Focus();
            DiscountPopupInput.SelectAll();
        }));

    private void FocusSearchSuggestions(bool selectLast = false, bool focusList = true)
    {
        if (SearchSuggestionsList.Items.Count == 0)
        {
            return;
        }

        if (SearchSuggestionsList.SelectedIndex < 0 || selectLast)
        {
            SearchSuggestionsList.SelectedIndex = selectLast
                ? SearchSuggestionsList.Items.Count - 1
                : 0;
        }

        if (focusList)
        {
            SearchSuggestionsList.Focus();
        }

        SearchSuggestionsList.ScrollIntoView(SearchSuggestionsList.SelectedItem);
    }

    private void MoveSearchSuggestion(int offset, bool focusList = true)
    {
        if (SearchSuggestionsList.Items.Count == 0)
        {
            return;
        }

        var currentIndex = SearchSuggestionsList.SelectedIndex < 0
            ? (offset > 0 ? -1 : SearchSuggestionsList.Items.Count)
            : SearchSuggestionsList.SelectedIndex;
        var nextIndex = Math.Clamp(currentIndex + offset, 0, SearchSuggestionsList.Items.Count - 1);
        SelectSearchSuggestion(nextIndex, focusList);
    }

    private void SelectSearchSuggestion(int index, bool focusList = true)
    {
        if (SearchSuggestionsList.Items.Count == 0)
        {
            return;
        }

        var safeIndex = Math.Clamp(index, 0, SearchSuggestionsList.Items.Count - 1);
        SearchSuggestionsList.SelectedIndex = safeIndex;
        SearchSuggestionsList.ScrollIntoView(SearchSuggestionsList.SelectedItem);
        SearchSuggestionsList.UpdateLayout();

        if (!focusList)
        {
            ProductSearchInput.Focus();
            return;
        }

        if (SearchSuggestionsList.ItemContainerGenerator.ContainerFromIndex(safeIndex) is ListBoxItem item)
        {
            item.Focus();
        }
        else
        {
            SearchSuggestionsList.Focus();
        }
    }

    private static T? FindParent<T>(DependencyObject? current)
        where T : DependencyObject
    {
        while (current is not null)
        {
            if (current is T match)
            {
                return match;
            }

            current = VisualTreeHelper.GetParent(current);
        }

        return null;
    }

    private void FocusNextPaymentField(TextBox current) =>
        FocusPaymentField(current, forward: true);

    private void FocusPreviousPaymentField(TextBox current) =>
        FocusPaymentField(current, forward: false);

    private void FocusPaymentField(TextBox current, bool forward)
    {
        var fields = new[] { MoneyInput, DebitInput, CreditInput, PixInput };
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

    private static bool TryGetDigitFromKey(Key key, out char digit)
    {
        if (key >= Key.D0 && key <= Key.D9)
        {
            digit = (char)('0' + ((int)key - (int)Key.D0));
            return true;
        }

        if (key >= Key.NumPad0 && key <= Key.NumPad9)
        {
            digit = (char)('0' + ((int)key - (int)Key.NumPad0));
            return true;
        }

        digit = '\0';
        return false;
    }

    private static void AppendCurrencyDigit(TextBox textBox, char digit)
    {
        var currentDigits = textBox.SelectionLength == textBox.Text.Length
            ? string.Empty
            : ExtractDigits(textBox.Text);
        SetCurrencyDigits(textBox, currentDigits + digit);
    }

    private static void RemoveCurrencyDigit(TextBox textBox)
    {
        if (textBox.SelectionLength > 0)
        {
            SetCurrencyDigits(textBox, string.Empty);
            return;
        }

        var digits = ExtractDigits(textBox.Text);
        SetCurrencyDigits(textBox, digits.Length > 0 ? digits[..^1] : string.Empty);
    }

    private static void EnsureCurrencyText(TextBox textBox)
    {
        var digits = ExtractDigits(textBox.Text);
        SetCurrencyDigits(textBox, digits);
    }

    private static void SetCurrencyDigits(TextBox textBox, string digits)
    {
        digits = digits.TrimStart('0');
        if (digits.Length == 0)
        {
            digits = "0";
        }

        if (digits.Length > 12)
        {
            digits = digits[^12..];
        }

        var cents = decimal.Parse(digits, CultureInfo.InvariantCulture);
        var value = cents / 100m;
        textBox.Text = value.ToString("N2", BrazilianCulture);
        textBox.CaretIndex = textBox.Text.Length;
        textBox.GetBindingExpression(TextBox.TextProperty)?.UpdateSource();
    }

    private static string ExtractDigits(string text) =>
        new((text ?? string.Empty).Where(char.IsDigit).ToArray());

    private static bool IsTextInputFocused() =>
        Keyboard.FocusedElement is Control { IsVisible: true, IsKeyboardFocusWithin: true } control
        && (control is TextBox or PasswordBox or ComboBox);

    private static void ExecuteIfAllowed(ICommand command)
    {
        if (command.CanExecute(null))
        {
            command.Execute(null);
        }
    }
}
