using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Girofy.Application.Models;
using Girofy.Application.ViewModels;

namespace Girofy.Desktop.Views;

public partial class CashRegisterView : UserControl
{
    public CashRegisterView()
    {
        InitializeComponent();
    }

    private void RecentRegistersGrid_PreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        var cell = FindVisualAncestor<DataGridCell>(e.OriginalSource as DependencyObject);
        var row = FindVisualAncestor<DataGridRow>(cell);
        if (cell is null || row is not { IsSelected: true } ||
            DataContext is not CashRegisterViewModel viewModel)
        {
            return;
        }

        e.Handled = true;
        viewModel.CollapseSelectedRegisterDetail();
    }

    private async void RecentRegistersGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (sender is DataGrid { SelectedItem: CashRegisterRecord selectedRegister } &&
            DataContext is CashRegisterViewModel viewModel)
        {
            viewModel.SelectedRegister = selectedRegister;
            await viewModel.LoadSelectedRegisterDetailAsync();
        }
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
