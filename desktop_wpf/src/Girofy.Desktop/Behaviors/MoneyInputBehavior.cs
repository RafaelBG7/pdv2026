using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Girofy.Application.Formatting;

namespace Girofy.Desktop.Behaviors;

public static class MoneyInputBehavior
{
    public static readonly DependencyProperty IsEnabledProperty = DependencyProperty.RegisterAttached(
        "IsEnabled",
        typeof(bool),
        typeof(MoneyInputBehavior),
        new PropertyMetadata(false, OnIsEnabledChanged));

    public static readonly DependencyProperty IsTouchedProperty = DependencyProperty.RegisterAttached(
        "IsTouched",
        typeof(bool),
        typeof(MoneyInputBehavior),
        new FrameworkPropertyMetadata(false, FrameworkPropertyMetadataOptions.BindsTwoWayByDefault));

    public static void SetIsEnabled(DependencyObject element, bool value) => element.SetValue(IsEnabledProperty, value);
    public static bool GetIsEnabled(DependencyObject element) => (bool)element.GetValue(IsEnabledProperty);
    public static void SetIsTouched(DependencyObject element, bool value) => element.SetValue(IsTouchedProperty, value);
    public static bool GetIsTouched(DependencyObject element) => (bool)element.GetValue(IsTouchedProperty);

    private static void OnIsEnabledChanged(DependencyObject dependencyObject, DependencyPropertyChangedEventArgs args)
    {
        if (dependencyObject is not TextBox textBox)
        {
            return;
        }

        if ((bool)args.NewValue)
        {
            textBox.PreviewTextInput += HandlePreviewTextInput;
            textBox.PreviewKeyDown += HandlePreviewKeyDown;
            textBox.Loaded += HandleLoaded;
            DataObject.AddPastingHandler(textBox, HandlePaste);
            InputMethod.SetIsInputMethodEnabled(textBox, false);
        }
        else
        {
            textBox.PreviewTextInput -= HandlePreviewTextInput;
            textBox.PreviewKeyDown -= HandlePreviewKeyDown;
            textBox.Loaded -= HandleLoaded;
            DataObject.RemovePastingHandler(textBox, HandlePaste);
        }
    }

    private static void HandleLoaded(object sender, RoutedEventArgs args)
    {
        if (sender is TextBox textBox && BrazilianMoneyFormatter.TryNormalize(textBox.Text, out var normalized))
        {
            SetTextAndCaret(textBox, normalized);
        }
    }

    private static void HandlePreviewTextInput(object sender, TextCompositionEventArgs args)
    {
        if (sender is not TextBox textBox)
        {
            return;
        }

        var digits = new string(args.Text.Where(char.IsDigit).ToArray());
        args.Handled = true;
        if (digits.Length == 0)
        {
            return;
        }

        MarkTouched(textBox);
        var currentValue = textBox.SelectionLength > 0 ? string.Empty : textBox.Text;
        SetTextAndCaret(textBox, BrazilianMoneyFormatter.FormatDigits(currentValue + digits));
    }

    private static void HandlePreviewKeyDown(object sender, KeyEventArgs args)
    {
        if (sender is not TextBox textBox || args.Key is not (Key.Back or Key.Delete))
        {
            return;
        }

        args.Handled = true;
        MarkTouched(textBox);
        SetTextAndCaret(
            textBox,
            textBox.SelectionLength > 0
                ? "0,00"
                : BrazilianMoneyFormatter.RemoveLastDigit(textBox.Text));
    }

    private static void HandlePaste(object sender, DataObjectPastingEventArgs args)
    {
        if (sender is not TextBox textBox || !args.SourceDataObject.GetDataPresent(DataFormats.UnicodeText))
        {
            args.CancelCommand();
            return;
        }

        args.CancelCommand();
        var pastedText = args.SourceDataObject.GetData(DataFormats.UnicodeText) as string;
        if (BrazilianMoneyFormatter.TryNormalize(pastedText, out var normalized))
        {
            MarkTouched(textBox);
            SetTextAndCaret(textBox, normalized);
        }
    }

    private static void SetTextAndCaret(TextBox textBox, string value)
    {
        textBox.SetCurrentValue(TextBox.TextProperty, value);
        textBox.GetBindingExpression(TextBox.TextProperty)?.UpdateSource();
        textBox.CaretIndex = value.Length;
    }

    private static void MarkTouched(TextBox textBox)
    {
        textBox.SetCurrentValue(IsTouchedProperty, true);
        textBox.GetBindingExpression(IsTouchedProperty)?.UpdateSource();
    }
}
