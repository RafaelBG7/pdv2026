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
}
