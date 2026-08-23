using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Media3D;

namespace Girofy.Desktop.Behaviors;

/// <summary>
/// Executes an explicitly assigned command when Enter is pressed inside a filter area.
/// The behavior deliberately preserves native Enter handling for multiline inputs,
/// buttons and open combo boxes.
/// </summary>
public static class EnterCommandBehavior
{
    public static readonly DependencyProperty CommandProperty = DependencyProperty.RegisterAttached(
        "Command",
        typeof(ICommand),
        typeof(EnterCommandBehavior),
        new PropertyMetadata(null, OnCommandChanged));

    public static readonly DependencyProperty CommandParameterProperty = DependencyProperty.RegisterAttached(
        "CommandParameter",
        typeof(object),
        typeof(EnterCommandBehavior),
        new PropertyMetadata(null));

    public static void SetCommand(DependencyObject element, ICommand? value) => element.SetValue(CommandProperty, value);

    public static ICommand? GetCommand(DependencyObject element) => (ICommand?)element.GetValue(CommandProperty);

    public static void SetCommandParameter(DependencyObject element, object? value) =>
        element.SetValue(CommandParameterProperty, value);

    public static object? GetCommandParameter(DependencyObject element) => element.GetValue(CommandParameterProperty);

    private static void OnCommandChanged(DependencyObject dependencyObject, DependencyPropertyChangedEventArgs args)
    {
        if (dependencyObject is not UIElement element)
        {
            return;
        }

        element.PreviewKeyDown -= HandlePreviewKeyDown;
        if (args.NewValue is ICommand)
        {
            element.PreviewKeyDown += HandlePreviewKeyDown;
        }
    }

    private static void HandlePreviewKeyDown(object sender, KeyEventArgs args)
    {
        if (args.Handled || args.Key != Key.Enter || Keyboard.Modifiers != ModifierKeys.None ||
            sender is not DependencyObject commandOwner || !ShouldSubmit(args.OriginalSource as DependencyObject))
        {
            return;
        }

        var command = GetCommand(commandOwner);
        var parameter = GetCommandParameter(commandOwner);
        args.Handled = TryExecute(command, parameter);
    }

    internal static bool ShouldSubmit(DependencyObject? source)
    {
        for (var current = source; current is not null; current = GetParent(current))
        {
            if (current is TextBoxBase { AcceptsReturn: true } || current is ButtonBase)
            {
                return false;
            }

            if (current is ComboBox comboBox)
            {
                return !comboBox.IsDropDownOpen;
            }
        }

        return true;
    }

    internal static bool TryExecute(ICommand? command, object? parameter)
    {
        if (command?.CanExecute(parameter) != true)
        {
            return false;
        }

        command.Execute(parameter);
        return true;
    }

    private static DependencyObject? GetParent(DependencyObject current)
    {
        if (current is Visual or Visual3D)
        {
            return VisualTreeHelper.GetParent(current);
        }

        return LogicalTreeHelper.GetParent(current);
    }
}
