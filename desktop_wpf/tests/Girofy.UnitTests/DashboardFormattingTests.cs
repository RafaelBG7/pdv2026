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
        var expected = DateTimeOffset.Parse("2026-08-18T15:30:00Z").ToLocalTime();

        Assert.Equal(expected.ToString("dd/MM/yyyy"), record.CreatedDateText);
        Assert.Equal(expected.ToString("HH:mm"), record.CreatedTimeText);
    }
}
