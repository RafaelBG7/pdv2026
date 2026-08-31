using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using Girofy.Application.Models;

namespace Girofy.Desktop.Controls;

internal static class DashboardChartPalette
{
    private static readonly Color[] Colors =
    [
        Color.FromRgb(34, 211, 238),
        Color.FromRgb(139, 92, 246),
        Color.FromRgb(52, 211, 153),
        Color.FromRgb(251, 191, 36),
        Color.FromRgb(251, 113, 133),
        Color.FromRgb(96, 165, 250),
        Color.FromRgb(192, 132, 252),
    ];

    public static Brush BrushAt(int index)
    {
        var brush = new SolidColorBrush(Colors[Math.Abs(index) % Colors.Length]);
        brush.Freeze();
        return brush;
    }
}

public sealed class ChartPaletteBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
        DashboardChartPalette.BrushAt(value is int index ? index : 0);

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        Binding.DoNothing;
}

public sealed class DashboardRankConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
        value is int index ? (index + 1).ToString(CultureInfo.InvariantCulture) : "1";

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        Binding.DoNothing;
}

public sealed class RevenueLineChart : FrameworkElement
{
    public static readonly DependencyProperty PointsProperty = DependencyProperty.Register(
        nameof(Points),
        typeof(IEnumerable<DashboardRevenuePoint>),
        typeof(RevenueLineChart),
        new FrameworkPropertyMetadata(null, FrameworkPropertyMetadataOptions.AffectsRender));

    private readonly ToolTip _toolTip;
    private int _activeIndex = -1;

    public RevenueLineChart()
    {
        SnapsToDevicePixels = true;
        Focusable = true;
        _toolTip = new ToolTip
        {
            Placement = System.Windows.Controls.Primitives.PlacementMode.Mouse,
            PlacementTarget = this,
        };
        ToolTipService.SetInitialShowDelay(this, 0);
        ToolTipService.SetShowDuration(this, 30_000);
    }

    public IEnumerable<DashboardRevenuePoint>? Points
    {
        get => (IEnumerable<DashboardRevenuePoint>?)GetValue(PointsProperty);
        set => SetValue(PointsProperty, value);
    }

    protected override void OnRender(DrawingContext drawingContext)
    {
        base.OnRender(drawingContext);
        var points = Points?.ToArray() ?? [];
        if (points.Length == 0 || ActualWidth < 80 || ActualHeight < 80)
        {
            return;
        }

        var plot = new Rect(14, 16, Math.Max(1, ActualWidth - 28), Math.Max(1, ActualHeight - 52));
        var gridPen = new Pen(new SolidColorBrush(Color.FromArgb(42, 148, 163, 184)), 1);
        gridPen.Freeze();
        for (var index = 0; index < 4; index++)
        {
            var y = plot.Top + (plot.Height * index / 3d);
            drawingContext.DrawLine(gridPen, new Point(plot.Left, y), new Point(plot.Right, y));
        }

        var maximum = Math.Max(points.Max(point => (double)point.Total), 1d);
        var screenPoints = BuildScreenPoints(points, plot, maximum);
        DrawArea(drawingContext, screenPoints, plot.Bottom);
        DrawLine(drawingContext, screenPoints);
        DrawLabels(drawingContext, points, screenPoints);

        if (_activeIndex >= 0 && _activeIndex < screenPoints.Length)
        {
            var markerFill = new SolidColorBrush(Color.FromRgb(11, 23, 41));
            var markerPen = new Pen(new SolidColorBrush(Color.FromRgb(103, 232, 249)), 3);
            drawingContext.DrawEllipse(markerFill, markerPen, screenPoints[_activeIndex], 6, 6);
        }
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        var points = Points?.ToArray() ?? [];
        if (points.Length == 0)
        {
            return;
        }

        var plot = new Rect(14, 16, Math.Max(1, ActualWidth - 28), Math.Max(1, ActualHeight - 52));
        var maximum = Math.Max(points.Max(point => (double)point.Total), 1d);
        var screenPoints = BuildScreenPoints(points, plot, maximum);
        var mouseX = e.GetPosition(this).X;
        var nearest = Enumerable.Range(0, screenPoints.Length)
            .MinBy(index => Math.Abs(screenPoints[index].X - mouseX));
        if (nearest != _activeIndex)
        {
            _activeIndex = nearest;
            InvalidateVisual();
        }

        var activePoint = points[_activeIndex];
        _toolTip.Content = $"{activePoint.Label}\n{DashboardFormatting.Money(activePoint.Total)}";
        _toolTip.IsOpen = true;
    }

    protected override void OnMouseLeave(MouseEventArgs e)
    {
        base.OnMouseLeave(e);
        _activeIndex = -1;
        _toolTip.IsOpen = false;
        InvalidateVisual();
    }

    private static Point[] BuildScreenPoints(
        IReadOnlyList<DashboardRevenuePoint> points,
        Rect plot,
        double maximum)
    {
        var lastIndex = Math.Max(points.Count - 1, 1);
        return points.Select((point, index) => new Point(
            plot.Left + (plot.Width * index / lastIndex),
            plot.Bottom - (plot.Height * (double)point.Total / maximum))).ToArray();
    }

    private static void DrawArea(DrawingContext drawingContext, IReadOnlyList<Point> points, double baseline)
    {
        var geometry = new StreamGeometry();
        using (var context = geometry.Open())
        {
            context.BeginFigure(new Point(points[0].X, baseline), true, true);
            foreach (var point in points)
            {
                context.LineTo(point, true, false);
            }
            context.LineTo(new Point(points[^1].X, baseline), true, false);
        }
        geometry.Freeze();
        var fill = new LinearGradientBrush(
            Color.FromArgb(100, 34, 211, 238),
            Color.FromArgb(2, 34, 211, 238),
            new Point(0.5, 0),
            new Point(0.5, 1));
        fill.Freeze();
        drawingContext.DrawGeometry(fill, null, geometry);
    }

    private static void DrawLine(DrawingContext drawingContext, IReadOnlyList<Point> points)
    {
        var geometry = new StreamGeometry();
        using (var context = geometry.Open())
        {
            context.BeginFigure(points[0], false, false);
            foreach (var point in points.Skip(1))
            {
                context.LineTo(point, true, false);
            }
        }
        geometry.Freeze();
        var linePen = new Pen(new SolidColorBrush(Color.FromRgb(34, 211, 238)), 3)
        {
            LineJoin = PenLineJoin.Round,
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round,
        };
        linePen.Freeze();
        drawingContext.DrawGeometry(null, linePen, geometry);
    }

    private void DrawLabels(
        DrawingContext drawingContext,
        IReadOnlyList<DashboardRevenuePoint> points,
        IReadOnlyList<Point> screenPoints)
    {
        var step = Math.Max(1, (int)Math.Ceiling(points.Count / 7d));
        var pixelsPerDip = VisualTreeHelper.GetDpi(this).PixelsPerDip;
        for (var index = 0; index < points.Count; index++)
        {
            if (index % step != 0 && index != points.Count - 1)
            {
                continue;
            }
            var label = new FormattedText(
                points[index].Label,
                CultureInfo.GetCultureInfo("pt-BR"),
                FlowDirection.LeftToRight,
                new Typeface("Segoe UI"),
                11,
                new SolidColorBrush(Color.FromRgb(148, 163, 184)),
                pixelsPerDip);
            drawingContext.DrawText(label, new Point(screenPoints[index].X - (label.Width / 2), ActualHeight - 24));
        }
    }
}

public sealed class CategoryDonutChart : FrameworkElement
{
    public static readonly DependencyProperty ItemsProperty = DependencyProperty.Register(
        nameof(Items),
        typeof(IEnumerable<DashboardCategorySale>),
        typeof(CategoryDonutChart),
        new FrameworkPropertyMetadata(null, FrameworkPropertyMetadataOptions.AffectsRender));

    private readonly ToolTip _toolTip;
    private IReadOnlyList<DonutSegment> _segments = [];
    private int _activeIndex = -1;

    public CategoryDonutChart()
    {
        SnapsToDevicePixels = true;
        Focusable = true;
        _toolTip = new ToolTip
        {
            Placement = System.Windows.Controls.Primitives.PlacementMode.Mouse,
            PlacementTarget = this,
        };
        ToolTipService.SetInitialShowDelay(this, 0);
        ToolTipService.SetShowDuration(this, 30_000);
    }

    public IEnumerable<DashboardCategorySale>? Items
    {
        get => (IEnumerable<DashboardCategorySale>?)GetValue(ItemsProperty);
        set => SetValue(ItemsProperty, value);
    }

    protected override void OnRender(DrawingContext drawingContext)
    {
        base.OnRender(drawingContext);
        var items = Items?.Where(item => item.Total > 0).ToArray() ?? [];
        var total = items.Sum(item => item.Total);
        if (items.Length == 0 || total <= 0 || ActualWidth < 80 || ActualHeight < 80)
        {
            _segments = [];
            return;
        }

        var center = new Point(ActualWidth / 2, ActualHeight / 2);
        var outerRadius = Math.Max(10, Math.Min(ActualWidth, ActualHeight) / 2 - 10);
        var innerRadius = outerRadius * 0.62;
        var start = -Math.PI / 2;
        var segments = new List<DonutSegment>(items.Length);
        for (var index = 0; index < items.Length; index++)
        {
            var sweep = Math.PI * 2 * (double)(items[index].Total / total);
            var end = start + sweep;
            var activeOffset = index == _activeIndex ? 4 : 0;
            var geometry = CreateRingSegment(center, innerRadius, outerRadius + activeOffset, start, end);
            drawingContext.DrawGeometry(DashboardChartPalette.BrushAt(index), null, geometry);
            segments.Add(new DonutSegment(start, end, innerRadius, outerRadius + activeOffset, items[index]));
            start = end;
        }
        _segments = segments;
        DrawCenterLabel(drawingContext, center, total);
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        var position = e.GetPosition(this);
        var center = new Point(ActualWidth / 2, ActualHeight / 2);
        var distance = Math.Sqrt(Math.Pow(position.X - center.X, 2) + Math.Pow(position.Y - center.Y, 2));
        var angle = Math.Atan2(position.Y - center.Y, position.X - center.X);
        if (angle < -Math.PI / 2)
        {
            angle += Math.PI * 2;
        }
        var index = _segments
            .Select((segment, segmentIndex) => (segment, segmentIndex))
            .Where(value => distance >= value.segment.InnerRadius && distance <= value.segment.OuterRadius)
            .Where(value => angle >= value.segment.StartAngle && angle <= value.segment.EndAngle)
            .Select(value => value.segmentIndex)
            .DefaultIfEmpty(-1)
            .First();
        if (index < 0)
        {
            CloseTooltip();
            return;
        }
        if (_activeIndex != index)
        {
            _activeIndex = index;
            InvalidateVisual();
        }
        var item = _segments[index].Item;
        _toolTip.Content = $"{item.Category}\n{DashboardFormatting.Money(item.Total)} · {item.Percent:N1}%";
        _toolTip.IsOpen = true;
    }

    protected override void OnMouseLeave(MouseEventArgs e)
    {
        base.OnMouseLeave(e);
        CloseTooltip();
    }

    private void CloseTooltip()
    {
        if (_activeIndex != -1)
        {
            _activeIndex = -1;
            InvalidateVisual();
        }
        _toolTip.IsOpen = false;
    }

    private static Geometry CreateRingSegment(
        Point center,
        double innerRadius,
        double outerRadius,
        double startAngle,
        double endAngle)
    {
        var sweep = Math.Min(endAngle - startAngle, (Math.PI * 2) - 0.0001);
        endAngle = startAngle + sweep;
        var outerStart = PolarPoint(center, outerRadius, startAngle);
        var outerEnd = PolarPoint(center, outerRadius, endAngle);
        var innerEnd = PolarPoint(center, innerRadius, endAngle);
        var innerStart = PolarPoint(center, innerRadius, startAngle);
        var largeArc = sweep > Math.PI;
        var figure = new PathFigure { StartPoint = outerStart, IsClosed = true, IsFilled = true };
        figure.Segments.Add(new ArcSegment(outerEnd, new Size(outerRadius, outerRadius), 0, largeArc, SweepDirection.Clockwise, true));
        figure.Segments.Add(new LineSegment(innerEnd, true));
        figure.Segments.Add(new ArcSegment(innerStart, new Size(innerRadius, innerRadius), 0, largeArc, SweepDirection.Counterclockwise, true));
        var geometry = new PathGeometry([figure]);
        geometry.Freeze();
        return geometry;
    }

    private static Point PolarPoint(Point center, double radius, double angle) =>
        new(center.X + (Math.Cos(angle) * radius), center.Y + (Math.Sin(angle) * radius));

    private void DrawCenterLabel(DrawingContext drawingContext, Point center, decimal total)
    {
        var pixelsPerDip = VisualTreeHelper.GetDpi(this).PixelsPerDip;
        var value = new FormattedText(
            DashboardFormatting.Money(total),
            CultureInfo.GetCultureInfo("pt-BR"),
            FlowDirection.LeftToRight,
            new Typeface(new FontFamily("Segoe UI"), FontStyles.Normal, FontWeights.Bold, FontStretches.Normal),
            17,
            new SolidColorBrush(Color.FromRgb(232, 238, 248)),
            pixelsPerDip);
        var caption = new FormattedText(
            "faturamento",
            CultureInfo.GetCultureInfo("pt-BR"),
            FlowDirection.LeftToRight,
            new Typeface("Segoe UI"),
            10,
            new SolidColorBrush(Color.FromRgb(148, 163, 184)),
            pixelsPerDip);
        drawingContext.DrawText(value, new Point(center.X - (value.Width / 2), center.Y - 18));
        drawingContext.DrawText(caption, new Point(center.X - (caption.Width / 2), center.Y + 7));
    }

    private sealed record DonutSegment(
        double StartAngle,
        double EndAngle,
        double InnerRadius,
        double OuterRadius,
        DashboardCategorySale Item);
}
