using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Media3D;
using System.Windows.Threading;

namespace Girofy.Desktop.Behaviors;

/// <summary>
/// Normalizes mouse-wheel scrolling across the desktop shell. WPF's default
/// behavior advances logical items in several controls, which feels abrupt on
/// large cards and nested lists. This controller keeps a pixel target and eases
/// the visible offset toward it without blocking the UI thread.
/// </summary>
internal sealed class SmoothScrollController : IDisposable
{
    private const double WheelPixelsPerDelta = 0.65;
    private const double Easing = 0.24;
    private const double CompletionThreshold = 0.5;

    private readonly Window _window;
    private readonly DispatcherTimer _timer;
    private readonly Dictionary<ScrollViewer, double> _targets = [];
    private bool _disposed;

    public SmoothScrollController(Window window)
    {
        _window = window;
        _timer = new DispatcherTimer(DispatcherPriority.Render, window.Dispatcher)
        {
            Interval = TimeSpan.FromMilliseconds(16),
        };
        _timer.Tick += HandleAnimationTick;
        _window.AddHandler(UIElement.PreviewMouseWheelEvent, new MouseWheelEventHandler(HandleMouseWheel), true);
    }

    private void HandleMouseWheel(object sender, MouseWheelEventArgs e)
    {
        if (_disposed || e.Handled || Keyboard.Modifiers.HasFlag(ModifierKeys.Control))
        {
            return;
        }

        var viewer = FindScrollableViewer(e.OriginalSource as DependencyObject, e.Delta);
        if (viewer is null || !UsesPixelScrolling(viewer))
        {
            return;
        }

        var currentTarget = _targets.TryGetValue(viewer, out var target)
            ? target
            : viewer.VerticalOffset;
        var nextTarget = Math.Clamp(
            currentTarget - (e.Delta * WheelPixelsPerDelta),
            0,
            viewer.ScrollableHeight);

        if (Math.Abs(nextTarget - viewer.VerticalOffset) < CompletionThreshold)
        {
            return;
        }

        _targets[viewer] = nextTarget;
        if (!_timer.IsEnabled)
        {
            _timer.Start();
        }

        e.Handled = true;
    }

    private void HandleAnimationTick(object? sender, EventArgs e)
    {
        foreach (var (viewer, requestedTarget) in _targets.ToArray())
        {
            if (!viewer.IsLoaded || viewer.ScrollableHeight <= 0)
            {
                _targets.Remove(viewer);
                continue;
            }

            var target = Math.Clamp(requestedTarget, 0, viewer.ScrollableHeight);
            var distance = target - viewer.VerticalOffset;
            if (Math.Abs(distance) <= CompletionThreshold)
            {
                viewer.ScrollToVerticalOffset(target);
                _targets.Remove(viewer);
                continue;
            }

            viewer.ScrollToVerticalOffset(viewer.VerticalOffset + (distance * Easing));
        }

        if (_targets.Count == 0)
        {
            _timer.Stop();
        }
    }

    private static ScrollViewer? FindScrollableViewer(DependencyObject? source, int delta)
    {
        for (var current = source; current is not null; current = GetParent(current))
        {
            if (current is not ScrollViewer viewer || viewer.ScrollableHeight <= 0)
            {
                continue;
            }

            var canMoveUp = delta > 0 && viewer.VerticalOffset > 0;
            var canMoveDown = delta < 0 && viewer.VerticalOffset < viewer.ScrollableHeight;
            if (canMoveUp || canMoveDown)
            {
                return viewer;
            }
        }

        return null;
    }

    private static bool UsesPixelScrolling(ScrollViewer viewer)
    {
        if (!ScrollViewer.GetCanContentScroll(viewer))
        {
            return true;
        }

        for (DependencyObject? current = viewer; current is not null; current = GetParent(current))
        {
            if (current is ItemsControl itemsControl)
            {
                return VirtualizingPanel.GetScrollUnit(itemsControl) == ScrollUnit.Pixel;
            }
        }

        return false;
    }

    private static DependencyObject? GetParent(DependencyObject element)
    {
        if (element is Visual or Visual3D)
        {
            return VisualTreeHelper.GetParent(element);
        }

        return LogicalTreeHelper.GetParent(element);
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _window.RemoveHandler(UIElement.PreviewMouseWheelEvent, new MouseWheelEventHandler(HandleMouseWheel));
        _timer.Stop();
        _timer.Tick -= HandleAnimationTick;
        _targets.Clear();
    }
}
