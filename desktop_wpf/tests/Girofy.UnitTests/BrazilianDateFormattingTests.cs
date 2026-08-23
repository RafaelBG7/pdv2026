using System.Globalization;
using Girofy.Application.Models;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class BrazilianDateFormattingTests
{
    [Theory]
    [InlineData("23/08/2026", 2026, 8, 23)]
    [InlineData("23082026", 2026, 8, 23)]
    [InlineData("2026-08-23", 2026, 8, 23)]
    [InlineData("01/01/2026", 2026, 1, 1)]
    [InlineData("28/02/2026", 2026, 2, 28)]
    [InlineData("29/02/2024", 2024, 2, 29)]
    [InlineData("29/02/2028", 2028, 2, 29)]
    [InlineData("30/04/2026", 2026, 4, 30)]
    [InlineData("31/12/2026", 2026, 12, 31)]
    public void TryParseDate_accepts_supported_valid_dates(string input, int year, int month, int day)
    {
        Assert.True(BrazilianDateFormatting.TryParseDate(input, out var parsed));
        Assert.Equal(new DateOnly(year, month, day), parsed);
    }

    [Theory]
    [InlineData("31/02/2026")]
    [InlineData("29/02/2025")]
    [InlineData("00/00/0000")]
    [InlineData("00/08/2026")]
    [InlineData("32/01/2026")]
    [InlineData("23/13/2026")]
    [InlineData("01/14/2026")]
    [InlineData("texto")]
    [InlineData("2308202")]
    public void TryParseDate_rejects_invalid_dates(string input) =>
        Assert.False(BrazilianDateFormatting.TryParseDate(input, out _));

    [Theory]
    [InlineData("2", "2")]
    [InlineData("23", "23")]
    [InlineData("230", "23/0")]
    [InlineData("2308", "23/08")]
    [InlineData("23082026", "23/08/2026")]
    [InlineData("23a08-2026", "23/08/2026")]
    public void FormatPartialDigits_applies_brazilian_mask(string input, string expected) =>
        Assert.Equal(expected, BrazilianDateFormatting.FormatPartialDigits(input));

    [Fact]
    public void Formatting_is_independent_from_operating_system_culture()
    {
        var originalCulture = CultureInfo.CurrentCulture;
        var originalUiCulture = CultureInfo.CurrentUICulture;
        try
        {
            CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo("en-US");
            CultureInfo.CurrentUICulture = CultureInfo.GetCultureInfo("en-US");

            Assert.Equal("23/08/2026", BrazilianDateFormatting.FormatDate(new DateOnly(2026, 8, 23)));
            Assert.Equal("2026-08-23", BrazilianDateFormatting.ToApiDate("23/08/2026"));
        }
        finally
        {
            CultureInfo.CurrentCulture = originalCulture;
            CultureInfo.CurrentUICulture = originalUiCulture;
        }
    }

    [Theory]
    [InlineData("2026-08-24T02:30:00Z", "23/08/2026 23:30")]
    [InlineData("2027-01-01T02:30:00Z", "31/12/2026 23:30")]
    [InlineData("2024-03-01T02:30:00Z", "29/02/2024 23:30")]
    public void FormatTimestamp_converts_once_to_sao_paulo_and_handles_rollovers(
        string timestamp,
        string expected) =>
        Assert.Equal(expected, BrazilianDateFormatting.FormatTimestamp(timestamp));

    [Fact]
    public void Reports_period_description_never_exposes_iso_dates()
    {
        var snapshot = new ReportsSnapshot
        {
            StartDate = "2026-08-23",
            EndDate = "2026-08-30",
            PeriodLabel = "2026-08-23 - 2026-08-30",
        };

        Assert.Equal("23/08/2026 a 30/08/2026", snapshot.PeriodDescription);
    }

    [Fact]
    public void Cash_timeline_prefers_created_at_and_formats_timestamp()
    {
        var item = new CashRegisterTimelineSaleViewModel(
            new CashRegisterTimelineSale
            {
                Id = 1,
                CreatedAt = "2026-08-24T02:30:00Z",
                Date = "2026-08-24",
                Time = "02:30:00",
            },
            canViewFinancials: true,
            (_, _) => Task.CompletedTask);

        Assert.Equal("23/08/2026 23:30", item.DateTimeText);
    }
}
