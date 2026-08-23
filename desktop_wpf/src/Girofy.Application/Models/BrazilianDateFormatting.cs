using System.Globalization;

namespace Girofy.Application.Models;

/// <summary>Single date boundary for the Windows app: pt-BR in UI and ISO in API contracts.</summary>
public static class BrazilianDateFormatting
{
    public const string DateFormat = "dd/MM/yyyy";
    public const string TimestampFormat = "dd/MM/yyyy HH:mm";
    public const string ApiDateFormat = "yyyy-MM-dd";

    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");
    private static readonly string[] InputFormats = [DateFormat, "d/M/yyyy", ApiDateFormat];
    private static readonly TimeZoneInfo BusinessTimeZone = ResolveBusinessTimeZone();

    public static bool TryParseDate(string? value, out DateOnly date)
    {
        var text = value?.Trim() ?? string.Empty;
        if (text.Length == 8 && text.All(char.IsDigit))
        {
            text = $"{text[..2]}/{text[2..4]}/{text[4..]}";
        }

        return DateOnly.TryParseExact(
            text,
            InputFormats,
            BrazilianCulture,
            DateTimeStyles.None,
            out date);
    }

    public static bool IsValidOptionalDate(string? value) =>
        string.IsNullOrWhiteSpace(value) || TryParseDate(value, out _);

    public static string FormatDate(DateOnly date) => date.ToString(DateFormat, BrazilianCulture);

    public static string? NormalizeDateInput(string? value) =>
        TryParseDate(value, out var date) ? FormatDate(date) : null;

    public static string? ToApiDate(string? value) =>
        TryParseDate(value, out var date)
            ? date.ToString(ApiDateFormat, CultureInfo.InvariantCulture)
            : null;

    public static string FormatPartialDigits(string? value)
    {
        var digits = new string((value ?? string.Empty).Where(char.IsDigit).Take(8).ToArray());
        return digits.Length switch
        {
            <= 2 => digits,
            <= 4 => $"{digits[..2]}/{digits[2..]}",
            _ => $"{digits[..2]}/{digits[2..4]}/{digits[4..]}",
        };
    }

    public static DateTimeOffset? ToBusinessTime(string? value)
    {
        if (!DateTimeOffset.TryParse(
                value,
                CultureInfo.InvariantCulture,
                DateTimeStyles.AllowWhiteSpaces | DateTimeStyles.AssumeUniversal,
                out var instant))
        {
            return null;
        }

        return TimeZoneInfo.ConvertTime(instant, BusinessTimeZone);
    }

    public static string FormatTimestamp(string? value, string fallback = "Data não informada") =>
        ToBusinessTime(value)?.ToString(TimestampFormat, BrazilianCulture) ?? fallback;

    public static DateOnly BusinessToday() =>
        DateOnly.FromDateTime(TimeZoneInfo.ConvertTime(DateTimeOffset.UtcNow, BusinessTimeZone).DateTime);

    private static TimeZoneInfo ResolveBusinessTimeZone()
    {
        foreach (var identifier in new[] { "E. South America Standard Time", "America/Sao_Paulo" })
        {
            try
            {
                return TimeZoneInfo.FindSystemTimeZoneById(identifier);
            }
            catch (TimeZoneNotFoundException)
            {
            }
            catch (InvalidTimeZoneException)
            {
            }
        }

        return TimeZoneInfo.Local;
    }
}
