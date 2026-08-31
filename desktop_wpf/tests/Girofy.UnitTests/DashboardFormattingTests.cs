using Girofy.Application.Models;

namespace Girofy.UnitTests;

public sealed class DashboardFormattingTests
{
    [Fact]
    public void DateTimeText_treats_legacy_timestamp_without_offset_as_utc()
    {
        var legacyValue = DashboardFormatting.DateTimeText("2026-08-18T15:30:00");
        var explicitUtcValue = DashboardFormatting.DateTimeText("2026-08-18T15:30:00Z");

        Assert.Equal(explicitUtcValue, legacyValue);
    }

    [Fact]
    public void DateTimeText_returns_safe_message_for_missing_value()
    {
        Assert.Equal("Data não informada", DashboardFormatting.DateTimeText(null));
    }

    [Fact]
    public void Audit_record_exposes_date_and_time_for_the_new_table_layout()
    {
        var record = new AuditLogRecord { CreatedAt = "2026-08-18T15:30:00Z" };

        Assert.Equal("18/08/2026", record.CreatedDateText);
        Assert.Equal("12:30", record.CreatedTimeText);
    }

    [Fact]
    public void Dashboard_snapshot_only_exposes_charts_when_the_period_has_values()
    {
        var emptySnapshot = new DashboardSnapshot();
        var populatedSnapshot = new DashboardSnapshot
        {
            Summary = new DashboardSummary { SalesCount = 1 },
            RevenueSeries = new DashboardRevenueSeries
            {
                Points = [new DashboardRevenuePoint { Label = "18h", Total = 24 }],
            },
            CategorySales =
            [
                new DashboardCategorySale
                {
                    Category = "Refrigerante",
                    Total = 24,
                    Percent = 100,
                },
            ],
        };

        Assert.False(emptySnapshot.HasRevenueData);
        Assert.False(emptySnapshot.HasCategorySales);
        Assert.True(populatedSnapshot.HasRevenueData);
        Assert.True(populatedSnapshot.HasCategorySales);
    }

    [Fact]
    public void Dashboard_snapshot_formats_the_web_period_caption()
    {
        var snapshot = new DashboardSnapshot
        {
            Period = new DashboardPeriod
            {
                Label = "Este mês",
                StartDate = "2026-08-01",
                EndDate = "2026-08-31",
            },
        };

        Assert.Equal("Este mês · 01/08/2026 a 31/08/2026", snapshot.PeriodRangeText);
    }
}
