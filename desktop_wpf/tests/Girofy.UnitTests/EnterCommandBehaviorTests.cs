using System.Windows.Controls;
using System.Windows.Input;
using Girofy.Desktop.Behaviors;

namespace Girofy.UnitTests;

public sealed class EnterCommandBehaviorTests
{
    [Fact]
    public void TryExecute_UsesSameCommandAndParameter_WhenEnabled()
    {
        object parameter = new();
        var command = new RecordingCommand(canExecute: true);

        var executed = EnterCommandBehavior.TryExecute(command, parameter);

        Assert.True(executed);
        Assert.Equal(1, command.ExecutionCount);
        Assert.Same(parameter, command.LastParameter);
    }

    [Fact]
    public void TryExecute_DoesNotExecute_WhenCommandIsDisabled()
    {
        var command = new RecordingCommand(canExecute: false);

        var executed = EnterCommandBehavior.TryExecute(command, null);

        Assert.False(executed);
        Assert.Equal(0, command.ExecutionCount);
    }

    [Fact]
    public void ShouldSubmit_PreservesMultilineTextBox()
    {
        Assert.False(EnterCommandBehavior.ShouldSubmit(new TextBox { AcceptsReturn = true }));
    }

    [Fact]
    public void ShouldSubmit_PreservesOpenComboBox_AndSubmitsClosedComboBox()
    {
        var comboBox = new ComboBox();

        Assert.True(EnterCommandBehavior.ShouldSubmit(comboBox));

        comboBox.IsDropDownOpen = true;
        Assert.False(EnterCommandBehavior.ShouldSubmit(comboBox));
    }

    private sealed class RecordingCommand(bool canExecute) : ICommand
    {
        public int ExecutionCount { get; private set; }
        public object? LastParameter { get; private set; }

        public bool CanExecute(object? parameter) => canExecute;

        public void Execute(object? parameter)
        {
            ExecutionCount++;
            LastParameter = parameter;
        }

        public event EventHandler? CanExecuteChanged
        {
            add { }
            remove { }
        }
    }
}
