using System.Net;
using Girofy.Application.Abstractions;
using Girofy.Application.ViewModels;

namespace Girofy.UnitTests;

public sealed class ForgotPasswordViewModelTests
{
    [Fact]
    public async Task Empty_identifier_does_not_send()
    {
        var service = new StubService();
        var viewModel = new ForgotPasswordViewModel(service);
        viewModel.Identifier = "   ";

        await viewModel.SubmitCommand.ExecuteAsync();

        Assert.Equal(0, service.CallCount);
        Assert.Equal("Informe seu usuário ou e-mail.", viewModel.ErrorMessage);
    }

    [Theory]
    [InlineData("  usuario  ", "usuario")]
    [InlineData("  pessoa@example.com  ", "pessoa@example.com")]
    public async Task Valid_identifier_is_trimmed_and_shows_generic_success(
        string input,
        string expected)
    {
        var service = new StubService();
        var viewModel = new ForgotPasswordViewModel(service) { Identifier = input };

        await viewModel.SubmitCommand.ExecuteAsync();

        Assert.Equal(expected, service.LastIdentifier);
        Assert.Equal(ForgotPasswordViewModel.GenericSuccessMessage, viewModel.SuccessMessage);
        Assert.False(viewModel.IsLoading);
    }

    [Fact]
    public async Task Rate_limit_has_a_friendly_message()
    {
        var service = new StubService
        {
            Exception = new HttpRequestException(
                "limited",
                null,
                HttpStatusCode.TooManyRequests),
        };
        var viewModel = new ForgotPasswordViewModel(service) { Identifier = "usuario" };

        await viewModel.SubmitCommand.ExecuteAsync();

        Assert.Contains("Muitas solicitações", viewModel.ErrorMessage);
        Assert.False(viewModel.IsLoading);
    }

    [Fact]
    public async Task Timeout_has_a_friendly_message()
    {
        var service = new StubService { Exception = new TaskCanceledException() };
        var viewModel = new ForgotPasswordViewModel(service) { Identifier = "usuario" };

        await viewModel.SubmitCommand.ExecuteAsync();

        Assert.Contains("demorou para responder", viewModel.ErrorMessage);
    }

    [Fact]
    public async Task Network_failure_has_a_friendly_message()
    {
        var service = new StubService { Exception = new HttpRequestException("offline") };
        var viewModel = new ForgotPasswordViewModel(service) { Identifier = "usuario" };

        await viewModel.SubmitCommand.ExecuteAsync();

        Assert.Contains("Verifique sua internet", viewModel.ErrorMessage);
    }

    [Fact]
    public async Task Closing_cancels_an_active_request()
    {
        var service = new StubService { WaitForCancellation = true };
        var viewModel = new ForgotPasswordViewModel(service) { Identifier = "usuario" };

        var request = viewModel.SubmitCommand.ExecuteAsync();
        await service.Started.Task;
        viewModel.Close();
        await request;

        Assert.True(service.WasCanceled);
        Assert.False(viewModel.IsLoading);
    }

    private sealed class StubService : IPasswordRecoveryService
    {
        public Exception? Exception { get; init; }
        public bool WaitForCancellation { get; init; }
        public int CallCount { get; private set; }
        public string LastIdentifier { get; private set; } = string.Empty;
        public bool WasCanceled { get; private set; }
        public TaskCompletionSource Started { get; } =
            new(TaskCreationOptions.RunContinuationsAsynchronously);

        public async Task RequestAsync(
            string identifier,
            CancellationToken cancellationToken = default)
        {
            CallCount++;
            LastIdentifier = identifier;
            Started.TrySetResult();
            if (Exception is not null)
                throw Exception;
            if (!WaitForCancellation)
                return;
            try
            {
                await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                WasCanceled = true;
                throw;
            }
        }
    }
}
