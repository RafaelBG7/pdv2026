using Girofy.Application.Models;

namespace Girofy.UnitTests;

public sealed class ReportChartBucketTests
{
    [Theory]
    [InlineData("00", true)]
    [InlineData("02", false)]
    [InlineData("03", true)]
    [InlineData("21", true)]
    [InlineData("2026-08-18", true)]
    public void Axis_labels_follow_web_hour_spacing(string key, bool expected)
    {
        var bucket = new ReportChartBucket { Key = key };

        Assert.Equal(expected, bucket.ShowAxisLabel);
    }

    [Theory]
    [InlineData(0, 4)]
    [InlineData(50, 107.5)]
    [InlineData(100, 215)]
    public void Chart_height_scales_percent_with_visible_baseline(
        double percent,
        double expectedHeight)
    {
        var bucket = new ReportChartBucket { Percent = (decimal)percent };

        Assert.Equal(expectedHeight, bucket.ChartHeight);
    }
}
