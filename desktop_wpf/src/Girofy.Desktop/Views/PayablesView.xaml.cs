using System;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;

namespace Girofy.Desktop.Views;

public partial class PayablesView : UserControl
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    public PayablesView()
    {
        InitializeComponent();
    }

    private void CurrencyInput_PreviewTextInput(object sender, TextCompositionEventArgs e)
    {
        if (sender is not TextBox textBox || e.Text.Length != 1 || !char.IsDigit(e.Text[0]))
        {
            e.Handled = true;
            return;
        }

        AppendCurrencyDigit(textBox, e.Text[0]);
        e.Handled = true;
    }

    private void CurrencyInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (sender is not TextBox textBox)
        {
            return;
        }

        if (e.Key is Key.Back or Key.Delete)
        {
            RemoveLastDigit(textBox, SetCurrencyDigits);
            e.Handled = true;
            return;
        }

        if (e.Key is Key.Space or Key.Decimal or Key.OemComma or Key.OemPeriod)
        {
            e.Handled = true;
        }
    }

    private void CurrencyInput_Pasting(object sender, DataObjectPastingEventArgs e)
    {
        if (sender is not TextBox textBox || !e.SourceDataObject.GetDataPresent(DataFormats.Text))
        {
            e.CancelCommand();
            return;
        }

        SetCurrencyDigits(textBox, ExtractDigits(e.SourceDataObject.GetData(DataFormats.Text)?.ToString()));
        e.CancelCommand();
    }

    private void CurrencyInput_LostKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (sender is TextBox textBox)
        {
            SetCurrencyDigits(textBox, ExtractDigits(textBox.Text));
        }
    }

    private void DateInput_PreviewTextInput(object sender, TextCompositionEventArgs e)
    {
        if (sender is not TextBox textBox || e.Text.Length != 1 || !char.IsDigit(e.Text[0]))
        {
            e.Handled = true;
            return;
        }

        var digits = textBox.SelectionLength == textBox.Text.Length
            ? string.Empty
            : ExtractDigits(textBox.Text);
        SetDateDigits(textBox, digits + e.Text[0]);
        e.Handled = true;
    }

    private void DateInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (sender is not TextBox textBox)
        {
            return;
        }

        if (e.Key is Key.Back or Key.Delete)
        {
            RemoveLastDigit(textBox, SetDateDigits);
            e.Handled = true;
            return;
        }

        if (e.Key is Key.Space or Key.Divide or Key.OemQuestion)
        {
            e.Handled = true;
        }
    }

    private void DateInput_Pasting(object sender, DataObjectPastingEventArgs e)
    {
        if (sender is not TextBox textBox || !e.SourceDataObject.GetDataPresent(DataFormats.Text))
        {
            e.CancelCommand();
            return;
        }

        var pastedText = e.SourceDataObject.GetData(DataFormats.Text)?.ToString() ?? string.Empty;
        if (TryFormatBrazilianDate(pastedText, out var formatted))
        {
            SetTextAndUpdateSource(textBox, formatted);
        }
        else
        {
            SetDateDigits(textBox, ExtractDigits(pastedText));
        }

        e.CancelCommand();
    }

    private void DateInput_LostKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (sender is TextBox textBox && TryFormatBrazilianDate(textBox.Text, out var formatted))
        {
            SetTextAndUpdateSource(textBox, formatted);
        }
    }

    private static void AppendCurrencyDigit(TextBox textBox, char digit)
    {
        var digits = textBox.SelectionLength == textBox.Text.Length
            ? string.Empty
            : ExtractDigits(textBox.Text);
        SetCurrencyDigits(textBox, digits + digit);
    }

    private static void RemoveLastDigit(TextBox textBox, Action<TextBox, string> setter)
    {
        var digits = textBox.SelectionLength > 0 ? string.Empty : ExtractDigits(textBox.Text);
        setter(textBox, digits.Length > 0 ? digits[..^1] : string.Empty);
    }

    private static void SetCurrencyDigits(TextBox textBox, string digits)
    {
        digits = digits.TrimStart('0');
        if (string.IsNullOrEmpty(digits))
        {
            digits = "0";
        }

        if (digits.Length > 12)
        {
            digits = digits[^12..];
        }

        var cents = decimal.Parse(digits, CultureInfo.InvariantCulture);
        SetTextAndUpdateSource(textBox, (cents / 100m).ToString("N2", BrazilianCulture));
    }

    private static void SetDateDigits(TextBox textBox, string digits)
    {
        digits = new string(digits.Where(char.IsDigit).Take(8).ToArray());
        var formatted = digits.Length switch
        {
            <= 2 => digits,
            <= 4 => $"{digits[..2]}/{digits[2..]}",
            _ => $"{digits[..2]}/{digits[2..4]}/{digits[4..]}",
        };
        SetTextAndUpdateSource(textBox, formatted);
    }

    private static bool TryFormatBrazilianDate(string text, out string formatted)
    {
        var formats = new[] { "dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd" };
        if (DateOnly.TryParseExact(text.Trim(), formats, BrazilianCulture, DateTimeStyles.None, out var date))
        {
            formatted = date.ToString("dd/MM/yyyy", BrazilianCulture);
            return true;
        }

        formatted = string.Empty;
        return false;
    }

    private static string ExtractDigits(string? value) =>
        new((value ?? string.Empty).Where(char.IsDigit).ToArray());

    private static void SetTextAndUpdateSource(TextBox textBox, string value)
    {
        textBox.Text = value;
        textBox.CaretIndex = value.Length;
        textBox.GetBindingExpression(TextBox.TextProperty)?.UpdateSource();
    }
}
