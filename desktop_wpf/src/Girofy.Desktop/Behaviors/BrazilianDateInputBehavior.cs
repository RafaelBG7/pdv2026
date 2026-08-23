using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using Girofy.Application.Models;

namespace Girofy.Desktop.Behaviors;

/// <summary>Reusable DD/MM/YYYY input mask backed by the real .NET calendar parser.</summary>
public static class BrazilianDateInputBehavior
{
    public static readonly DependencyProperty IsEnabledProperty = DependencyProperty.RegisterAttached(
        "IsEnabled",
        typeof(bool),
        typeof(BrazilianDateInputBehavior),
        new PropertyMetadata(false, OnIsEnabledChanged));

    public static void SetIsEnabled(DependencyObject element, bool value) => element.SetValue(IsEnabledProperty, value);

    public static bool GetIsEnabled(DependencyObject element) => (bool)element.GetValue(IsEnabledProperty);

    private static void OnIsEnabledChanged(DependencyObject dependencyObject, DependencyPropertyChangedEventArgs args)
    {
        if (dependencyObject is not TextBox textBox)
        {
            return;
        }

        textBox.PreviewTextInput -= HandlePreviewTextInput;
        textBox.PreviewKeyDown -= HandlePreviewKeyDown;
        textBox.LostKeyboardFocus -= HandleLostKeyboardFocus;
        DataObject.RemovePastingHandler(textBox, HandlePaste);

        if (args.NewValue is true)
        {
            textBox.PreviewTextInput += HandlePreviewTextInput;
            textBox.PreviewKeyDown += HandlePreviewKeyDown;
            textBox.LostKeyboardFocus += HandleLostKeyboardFocus;
            DataObject.AddPastingHandler(textBox, HandlePaste);
            InputMethod.SetIsInputMethodEnabled(textBox, false);
        }
    }

    private static void HandlePreviewTextInput(object sender, TextCompositionEventArgs args)
    {
        if (sender is not TextBox textBox || args.Text.Length != 1 || !char.IsDigit(args.Text[0]))
        {
            args.Handled = true;
            return;
        }

        var digits = textBox.SelectionLength == textBox.Text.Length ? string.Empty : ExtractDigits(textBox.Text);
        SetText(textBox, BrazilianDateFormatting.FormatPartialDigits(digits + args.Text[0]));
        args.Handled = true;
    }

    private static void HandlePreviewKeyDown(object sender, KeyEventArgs args)
    {
        if (sender is not TextBox textBox)
        {
            return;
        }

        if (args.Key is Key.Back or Key.Delete)
        {
            var digits = textBox.SelectionLength > 0 ? string.Empty : ExtractDigits(textBox.Text);
            SetText(textBox, BrazilianDateFormatting.FormatPartialDigits(digits.Length > 0 ? digits[..^1] : string.Empty));
            args.Handled = true;
            return;
        }

        if (args.Key is Key.Space or Key.Divide or Key.OemQuestion)
        {
            args.Handled = true;
        }
    }

    private static void HandlePaste(object sender, DataObjectPastingEventArgs args)
    {
        if (sender is not TextBox textBox || !args.SourceDataObject.GetDataPresent(DataFormats.Text))
        {
            args.CancelCommand();
            return;
        }

        var pasted = args.SourceDataObject.GetData(DataFormats.Text)?.ToString() ?? string.Empty;
        var normalized = BrazilianDateFormatting.NormalizeDateInput(pasted);
        if (normalized is not null)
        {
            SetText(textBox, normalized);
        }
        else if (pasted.All(character => char.IsDigit(character) || character is '/' or '-' || char.IsWhiteSpace(character)))
        {
            SetText(textBox, BrazilianDateFormatting.FormatPartialDigits(ExtractDigits(pasted)));
        }

        args.CancelCommand();
    }

    private static void HandleLostKeyboardFocus(object sender, KeyboardFocusChangedEventArgs args)
    {
        if (sender is TextBox textBox && BrazilianDateFormatting.NormalizeDateInput(textBox.Text) is { } normalized)
        {
            SetText(textBox, normalized);
        }
    }

    private static string ExtractDigits(string? value) => new((value ?? string.Empty).Where(char.IsDigit).ToArray());

    private static void SetText(TextBox textBox, string value)
    {
        textBox.Text = value;
        textBox.CaretIndex = value.Length;
        textBox.GetBindingExpression(TextBox.TextProperty)?.UpdateSource();
    }
}
