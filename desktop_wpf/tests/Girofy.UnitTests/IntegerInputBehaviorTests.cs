using Girofy.Desktop.Behaviors;

namespace Girofy.UnitTests;

public sealed class IntegerInputBehaviorTests
{
    [Theory]
    [InlineData("1")]
    [InlineData("2")]
    [InlineData("8")]
    [InlineData("10")]
    [InlineData("100")]
    public void Integer_text_accepts_only_whole_digit_sequences(string value)
    {
        Assert.True(IntegerInputBehavior.IsValidIntegerText(value));
    }

    [Theory]
    [InlineData("")]
    [InlineData("abc")]
    [InlineData("1,5")]
    [InlineData("1.5")]
    [InlineData("-")]
    [InlineData("---")]
    [InlineData("+")]
    [InlineData("8abc")]
    [InlineData(" ")]
    public void Integer_text_rejects_invalid_typing_or_paste_content(string value)
    {
        Assert.False(IntegerInputBehavior.IsValidIntegerText(value));
    }
}
