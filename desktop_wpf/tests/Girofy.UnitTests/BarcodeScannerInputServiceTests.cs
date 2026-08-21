using Girofy.Application.Services;

namespace Girofy.UnitTests;

public sealed class BarcodeScannerInputServiceTests
{
    [Fact]
    public void Fast_keyboard_wedge_sequence_completes_on_enter_boundary()
    {
        var service = new BarcodeScannerInputService();
        var now = DateTimeOffset.UtcNow;
        foreach (var character in "7894900011517")
        {
            service.Append(character.ToString(), now);
            now = now.AddMilliseconds(15);
        }

        Assert.True(service.TryComplete(now, out var barcode));
        Assert.Equal("7894900011517", barcode);
        Assert.False(service.HasPendingInput);
    }

    [Fact]
    public void Slow_human_sequence_is_reset_and_not_misread_as_a_scanner()
    {
        var service = new BarcodeScannerInputService();
        var now = DateTimeOffset.UtcNow;
        service.Append("A", now);
        service.Append("B", now.AddMilliseconds(250));

        Assert.False(service.TryComplete(now.AddMilliseconds(260), out _));
        Assert.False(service.HasPendingInput);
    }
}
