using System.Windows.Controls;
using Girofy.Application.Models;
using Girofy.Application.ViewModels;

namespace Girofy.Desktop.Views;

public partial class CashRegisterView : UserControl
{
    public CashRegisterView()
    {
        InitializeComponent();
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
}
