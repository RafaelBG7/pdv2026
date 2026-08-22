using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Girofy.Application.ViewModels;

namespace Girofy.Desktop.Views;

public partial class StockView : UserControl
{
    public StockView() => InitializeComponent();

    private void MovementsGrid_PreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        var row = FindVisualAncestor<DataGridRow>(e.OriginalSource as DependencyObject);
        if (sender is not DataGrid grid ||
            row is not { IsSelected: true } ||
            DataContext is not StockViewModel viewModel)
        {
            return;
        }

        e.Handled = true;
        grid.SelectedItem = null;
        viewModel.SelectedMovement = null;
    }

    private static T? FindVisualAncestor<T>(DependencyObject? element) where T : DependencyObject
    {
        while (element is not null)
        {
            if (element is T match)
            {
                return match;
            }

            element = element is Visual
                ? VisualTreeHelper.GetParent(element)
                : LogicalTreeHelper.GetParent(element);
        }

        return null;
    }
}
