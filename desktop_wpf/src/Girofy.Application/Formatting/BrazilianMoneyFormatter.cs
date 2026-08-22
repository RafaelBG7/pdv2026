using System.Globalization;
using System.Text.RegularExpressions;

namespace Girofy.Application.Formatting;

public static partial class BrazilianMoneyFormatter
{
    private static readonly CultureInfo BrazilianCulture = CultureInfo.GetCultureInfo("pt-BR");

    public static string Format(decimal value) => value.ToString("N2", BrazilianCulture);

    public static string FormatDigits(string? value)
    {
        var digits = DigitsOnly().Replace(value ?? string.Empty, string.Empty);
        if (string.IsNullOrEmpty(digits))
        {
            return "0,00";
        }

        if (!decimal.TryParse(digits, NumberStyles.None, CultureInfo.InvariantCulture, out var cents))
        {
            return "0,00";
        }

        return (cents / 100m).ToString("N2", BrazilianCulture);
    }

    public static string RemoveLastDigit(string? formattedValue)
    {
        var digits = DigitsOnly().Replace(formattedValue ?? string.Empty, string.Empty);
        return FormatDigits(digits.Length > 0 ? digits[..^1] : string.Empty);
    }

    public static bool TryNormalize(string? value, out string formattedValue)
    {
        formattedValue = "0,00";
        var text = (value ?? string.Empty).Trim();
        if (string.IsNullOrEmpty(text))
        {
            return true;
        }

        text = text.Replace("R$", string.Empty, StringComparison.OrdinalIgnoreCase)
            .Replace(" ", string.Empty, StringComparison.Ordinal);
        var lastComma = text.LastIndexOf(',');
        var lastDot = text.LastIndexOf('.');
        var decimalSeparator = Math.Max(lastComma, lastDot);
        var decimalDigits = decimalSeparator >= 0 ? text.Length - decimalSeparator - 1 : 0;

        string normalized;
        if (decimalSeparator >= 0 && decimalDigits is 1 or 2)
        {
            var integerPart = DigitsOnly().Replace(text[..decimalSeparator], string.Empty);
            var fractionPart = DigitsOnly().Replace(text[(decimalSeparator + 1)..], string.Empty);
            normalized = $"{(string.IsNullOrEmpty(integerPart) ? "0" : integerPart)}.{fractionPart.PadRight(2, '0')}";
        }
        else
        {
            normalized = DigitsOnly().Replace(text, string.Empty);
        }

        if (!decimal.TryParse(normalized, NumberStyles.Number, CultureInfo.InvariantCulture, out var amount) || amount < 0)
        {
            return false;
        }

        formattedValue = Format(amount);
        return true;
    }

    public static bool TryParse(string? value, out decimal amount)
    {
        amount = 0;
        return TryNormalize(value, out var normalized)
            && decimal.TryParse(normalized, NumberStyles.Number, BrazilianCulture, out amount);
    }

    [GeneratedRegex("[^0-9]")]
    private static partial Regex DigitsOnly();
}
