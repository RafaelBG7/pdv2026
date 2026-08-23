using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Threading;
using System.Windows.Input;
using System.Windows.Media;
using Girofy.Application.ViewModels;
using Girofy.Desktop.Behaviors;
using Microsoft.Extensions.Logging;

namespace Girofy.Desktop;

public partial class MainWindow : Window
{
    private const uint MonitorDefaultToNearest = 2;

    private readonly ConnectionViewModel _viewModel;
    private readonly ILogger<MainWindow> _logger;
    private bool _initialized;
    private bool _syncingPassword;
    private readonly SmoothScrollController _smoothScrollController;

    public MainWindow(ConnectionViewModel viewModel, ILogger<MainWindow> logger)
    {
        InitializeComponent();
        _viewModel = viewModel;
        _logger = logger;
        DataContext = viewModel;
        _smoothScrollController = new SmoothScrollController(this);
        Loaded += HandleLoaded;
        Deactivated += HandleWindowDeactivated;
        StateChanged += HandleWindowStateChanged;
        _viewModel.Login.PropertyChanged += HandleLoginPropertyChanged;
        _viewModel.Login.ForgotPassword.PropertyChanged += HandleForgotPasswordPropertyChanged;
    }

    private void HandleForgotPasswordPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(ForgotPasswordViewModel.IsOpen) &&
            _viewModel.Login.ForgotPassword.IsOpen)
        {
            Dispatcher.InvokeAsync(
                () => ForgotPasswordIdentifierInput.Focus(),
                DispatcherPriority.Background);
        }
    }

    private void HandleForgotPasswordKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape)
        {
            _viewModel.Login.ForgotPassword.Close();
            e.Handled = true;
        }
    }

    private async void MainWindow_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape && _viewModel.Catalog.IsDeleteConfirmationOpen)
        {
            if (_viewModel.Catalog.CancelDeleteProductCommand.CanExecute(null))
            {
                _viewModel.Catalog.CancelDeleteProductCommand.Execute(null);
            }
            e.Handled = true;
            return;
        }

        if (e.Key != Key.F3 || !_viewModel.Login.IsAuthenticated)
        {
            return;
        }

        try
        {
            if (_viewModel.IsDashboardView && _viewModel.StartSaleCommand.CanExecute(null))
            {
                e.Handled = true;
                await _viewModel.StartSaleCommand.ExecuteAsync();
            }
            else if (_viewModel.IsSalesView && _viewModel.SalesScreenF3Command.CanExecute(null))
            {
                e.Handled = true;
                await _viewModel.SalesScreenF3Command.ExecuteAsync();
            }
        }
        catch (Exception exception)
        {
            _logger.LogError(exception, "F3 sale shortcut failed.");
        }
    }

    private void ProductBarcodeInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key != Key.Enter || sender is not TextBox textBox)
        {
            return;
        }

        _viewModel.Catalog.CommitEditorBarcodeInput();
        textBox.MoveFocus(new TraversalRequest(FocusNavigationDirection.Next));
        e.Handled = true;
    }

    private async void HandleLoaded(object sender, RoutedEventArgs e)
    {
        if (_initialized)
        {
            return;
        }

        try
        {
            _initialized = true;
            await _viewModel.InitializeAsync();
            QueueLoginFocus();
        }
        catch (Exception exception)
        {
            _logger.LogError(exception, "Main window initialization failed.");
            _initialized = false;
        }
    }

    private async void HandleNotificationsBellClick(object sender, RoutedEventArgs e)
    {
        NotificationsPanel.Visibility = NotificationsPanel.Visibility == Visibility.Visible
            ? Visibility.Collapsed
            : Visibility.Visible;
        if (NotificationsPanel.Visibility != Visibility.Visible)
        {
            return;
        }

        try
        {
            await _viewModel.Notifications.InitializeAsync();
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Notification popover initialization failed.");
        }
    }

    private void HandleAuthenticatedShellPreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (NotificationsPanel.Visibility != Visibility.Visible ||
            e.OriginalSource is not DependencyObject source ||
            IsDescendantOf(source, NotificationsPanel) ||
            IsDescendantOf(source, NotificationsBellButton))
        {
            return;
        }

        CloseNotificationsPanel();
    }

    private void HandleWindowDeactivated(object? sender, EventArgs e) =>
        CloseNotificationsPanel();

    private void HandleWindowStateChanged(object? sender, EventArgs e)
    {
        if (WindowState == WindowState.Minimized)
        {
            CloseNotificationsPanel();
        }
    }

    private void CloseNotificationsPanel()
    {
        if (NotificationsPanel.Visibility == Visibility.Visible)
        {
            NotificationsPanel.Visibility = Visibility.Collapsed;
        }
    }

    private void ProductDeleteConfirmation_IsVisibleChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if (e.NewValue is not true)
        {
            return;
        }

        Dispatcher.InvokeAsync(() => CancelProductDeleteButton.Focus(), DispatcherPriority.Input);
    }

    private void ProductsGrid_PreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        var cell = FindVisualAncestor<DataGridCell>(e.OriginalSource as DependencyObject);
        var row = FindVisualAncestor<DataGridRow>(cell);
        if (sender is not DataGrid productsGrid ||
            cell is null ||
            row is not { IsSelected: true })
        {
            return;
        }

        e.Handled = true;
        productsGrid.SelectedItem = null;
        _viewModel.Catalog.SelectedProduct = null;
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

    private static bool IsDescendantOf(DependencyObject? element, DependencyObject ancestor)
    {
        while (element is not null)
        {
            if (ReferenceEquals(element, ancestor))
            {
                return true;
            }

            element = element is Visual
                ? VisualTreeHelper.GetParent(element)
                : LogicalTreeHelper.GetParent(element);
        }

        return false;
    }

    private void QueueLoginFocus()
    {
        if (_viewModel.Login.IsAuthenticated)
        {
            return;
        }

        Dispatcher.InvokeAsync(
            () =>
            {
                try
                {
                    if (_viewModel.Login.IsAuthenticated)
                    {
                        return;
                    }

                    if (string.IsNullOrWhiteSpace(_viewModel.Login.Identifier))
                    {
                        TryFocus(IdentifierInput);
                    }
                    else if (_viewModel.Login.ShowPassword)
                    {
                        TryFocus(VisiblePasswordInput);
                    }
                    else
                    {
                        TryFocus(PasswordInput);
                    }
                }
                catch (Exception exception)
                {
                    _logger.LogWarning(exception, "Initial login focus failed.");
                }
            },
            DispatcherPriority.Background);
    }

    private static void TryFocus(Control control)
    {
        if (control.IsVisible && control.IsEnabled)
        {
            control.Focus();
        }
    }

    private void HandlePasswordChanged(object sender, RoutedEventArgs e)
    {
        if (_syncingPassword || sender is not PasswordBox passwordBox)
        {
            return;
        }

        _viewModel.Login.Password = passwordBox.Password;
    }

    private void HandlePasswordVisibilityChanged(object sender, RoutedEventArgs e)
    {
        try
        {
            var showPassword = sender is CheckBox { IsChecked: true };
            _viewModel.Login.ShowPassword = showPassword;

            _syncingPassword = true;
            try
            {
                if (showPassword)
                {
                    VisiblePasswordInput.Text = PasswordInput.Password;
                    VisiblePasswordInput.CaretIndex = VisiblePasswordInput.Text.Length;
                    TryFocus(VisiblePasswordInput);
                }
                else
                {
                    PasswordInput.Password = VisiblePasswordInput.Text;
                    TryFocus(PasswordInput);
                }
            }
            finally
            {
                _syncingPassword = false;
            }
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Password visibility change failed.");
        }
    }

    private void HandleLoginPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(LoginViewModel.IsAuthenticated))
        {
            if (!_viewModel.Login.IsAuthenticated)
            {
                CloseNotificationsPanel();
            }

            ApplyAuthenticationWindowMode();
            return;
        }

        if (e.PropertyName != nameof(LoginViewModel.Password) || _syncingPassword)
        {
            return;
        }

        try
        {
            _syncingPassword = true;
            var password = _viewModel.Login.Password;
            if (!string.Equals(PasswordInput.Password, password, StringComparison.Ordinal))
            {
                PasswordInput.Password = password;
            }

            if (!string.Equals(VisiblePasswordInput.Text, password, StringComparison.Ordinal))
            {
                VisiblePasswordInput.Text = password;
            }
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Password field synchronization failed.");
        }
        finally
        {
            _syncingPassword = false;
        }
    }

    private void ApplyAuthenticationWindowMode()
    {
        var workArea = GetCurrentMonitorWorkArea();

        if (_viewModel.Login.IsAuthenticated)
        {
            WindowState = WindowState.Normal;
            MaxWidth = double.PositiveInfinity;
            MaxHeight = double.PositiveInfinity;
            MinWidth = Math.Min(900, workArea.Width);
            MinHeight = Math.Min(640, workArea.Height);
            ResizeMode = ResizeMode.CanResize;
            Width = Math.Min(1180, workArea.Width);
            Height = Math.Min(780, workArea.Height);
            CenterInside(workArea);
            return;
        }

        WindowState = WindowState.Normal;
        ResizeMode = ResizeMode.CanMinimize;
        var loginWidth = Math.Min(470, workArea.Width);
        var loginHeight = Math.Min(700, workArea.Height);
        MinWidth = loginWidth;
        MinHeight = Math.Min(640, workArea.Height);
        MaxWidth = loginWidth;
        MaxHeight = loginHeight;
        Width = loginWidth;
        Height = loginHeight;
        CenterInside(workArea);
        QueueLoginFocus();
    }

    private Rect GetCurrentMonitorWorkArea()
    {
        try
        {
            var handle = new WindowInteropHelper(this).Handle;
            if (handle == IntPtr.Zero)
            {
                return SystemParameters.WorkArea;
            }

            var monitor = MonitorFromWindow(handle, MonitorDefaultToNearest);
            var monitorInfo = new MonitorInfo
            {
                Size = Marshal.SizeOf<MonitorInfo>()
            };

            if (monitor == IntPtr.Zero || !GetMonitorInfo(monitor, ref monitorInfo))
            {
                return SystemParameters.WorkArea;
            }

            var source = PresentationSource.FromVisual(this);
            var fromDevice = source?.CompositionTarget?.TransformFromDevice ?? Matrix.Identity;
            var topLeft = fromDevice.Transform(new Point(monitorInfo.WorkArea.Left, monitorInfo.WorkArea.Top));
            var bottomRight = fromDevice.Transform(new Point(monitorInfo.WorkArea.Right, monitorInfo.WorkArea.Bottom));
            return new Rect(topLeft, bottomRight);
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Current monitor work area could not be resolved; using the primary monitor.");
            return SystemParameters.WorkArea;
        }
    }

    private void CenterInside(Rect workArea)
    {
        Left = workArea.Left + Math.Max(0, (workArea.Width - Width) / 2);
        Top = workArea.Top + Math.Max(0, (workArea.Height - Height) / 2);
    }

    [DllImport("user32.dll")]
    private static extern IntPtr MonitorFromWindow(IntPtr windowHandle, uint flags);

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetMonitorInfo(IntPtr monitorHandle, ref MonitorInfo monitorInfo);

    [StructLayout(LayoutKind.Sequential)]
    private struct MonitorInfo
    {
        public int Size;
        public NativeRect Monitor;
        public NativeRect WorkArea;
        public uint Flags;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeRect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    protected override void OnClosed(EventArgs e)
    {
        Loaded -= HandleLoaded;
        Deactivated -= HandleWindowDeactivated;
        StateChanged -= HandleWindowStateChanged;
        _viewModel.Login.PropertyChanged -= HandleLoginPropertyChanged;
        _viewModel.Login.ForgotPassword.PropertyChanged -= HandleForgotPasswordPropertyChanged;
        _smoothScrollController.Dispose();
        base.OnClosed(e);
    }
}
