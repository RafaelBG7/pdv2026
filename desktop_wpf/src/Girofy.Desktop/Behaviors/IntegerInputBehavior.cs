using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace Girofy.Desktop.Behaviors;

public static class IntegerInputBehavior
{
    public static readonly DependencyProperty IsEnabledProperty = DependencyProperty.RegisterAttached(
        "IsEnabled",
        typeof(bool),
        typeof(IntegerInputBehavior),
        new PropertyMetadata(false, OnIsEnabledChanged));

    public static void SetIsEnabled(DependencyObject element, bool value) => element.SetValue(IsEnabledProperty, value);
    public static bool GetIsEnabled(DependencyObject element) => (bool)element.GetValue(IsEnabledProperty);

    private static void OnIsEnabledChanged(DependencyObject dependencyObject, DependencyPropertyChangedEventArgs args)
    {
        if (dependencyObject is not TextBox textBox)
        {
            return;
        }

        if ((bool)args.NewValue)
        {
            textBox.PreviewTextInput += HandlePreviewTextInput;
            DataObject.AddPastingHandler(textBox, HandlePaste);
            InputMethod.SetIsInputMethodEnabled(textBox, false);
        }
        else
        {
            textBox.PreviewTextInput -= HandlePreviewTextInput;
            DataObject.RemovePastingHandler(textBox, HandlePaste);
        }
    }

    private static void HandlePreviewTextInput(object sender, TextCompositionEventArgs args) =>
        args.Handled = args.Text.Any(character => !char.IsDigit(character));

    private static void HandlePaste(object sender, DataObjectPastingEventArgs args)
    {
        if (!args.SourceDataObject.GetDataPresent(DataFormats.UnicodeText)
            || args.SourceDataObject.GetData(DataFormats.UnicodeText) is not string text
            || string.IsNullOrEmpty(text)
            || text.Any(character => !char.IsDigit(character)))
        {
            args.CancelCommand();
        }
    }
}
