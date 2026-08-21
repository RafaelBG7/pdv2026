using System.Text;

namespace Girofy.Application.Services;

public sealed class BarcodeScannerInputService
{
    private static readonly TimeSpan DefaultInterCharacterTimeout = TimeSpan.FromMilliseconds(150);
    private readonly TimeSpan _interCharacterTimeout;
    private readonly StringBuilder _buffer = new();
    private DateTimeOffset? _lastInputAt;

    public BarcodeScannerInputService(TimeSpan? interCharacterTimeout = null)
    {
        _interCharacterTimeout = interCharacterTimeout ?? DefaultInterCharacterTimeout;
    }

    public bool HasPendingInput => _buffer.Length > 0;

    public void Append(string text, DateTimeOffset timestamp)
    {
        if (string.IsNullOrEmpty(text) || text.Any(char.IsControl))
        {
            return;
        }

        if (_lastInputAt is not null && timestamp - _lastInputAt > _interCharacterTimeout)
        {
            Reset();
        }

        _buffer.Append(text);
        _lastInputAt = timestamp;
        if (_buffer.Length > 100)
        {
            Reset();
        }
    }

    public bool TryComplete(DateTimeOffset timestamp, out string barcode)
    {
        barcode = string.Empty;
        if (_lastInputAt is null || timestamp - _lastInputAt > _interCharacterTimeout)
        {
            Reset();
            return false;
        }

        var candidate = _buffer.ToString().Trim();
        Reset();
        if (candidate.Length < 3)
        {
            return false;
        }

        barcode = candidate;
        return true;
    }

    public void Reset()
    {
        _buffer.Clear();
        _lastInputAt = null;
    }
}
