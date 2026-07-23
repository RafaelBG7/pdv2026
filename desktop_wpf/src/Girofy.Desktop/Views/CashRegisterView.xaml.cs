using System.Windows.Controls;
using Girofy.Application.ViewModels;

namespace Girofy.Desktop.Views;

public partial class CashRegisterView : UserControl
{
    public CashRegisterView()
    {
        InitializeComponent();
    }

    private void RecentRegistersGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DataContext is CashRegisterViewModel viewModel &&
            viewModel.SelectedRegister is not null &&
            viewModel.LoadRegisterDetailCommand.CanExecute(null))
        {
            viewModel.LoadRegisterDetailCommand.Execute(null);
        }
    }
}
