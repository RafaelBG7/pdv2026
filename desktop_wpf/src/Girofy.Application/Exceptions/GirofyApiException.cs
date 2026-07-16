namespace Girofy.Application.Exceptions;

public sealed class GirofyApiException(
    string message,
    string code,
    int statusCode) : Exception(message)
{
    public string Code { get; } = code;

    public int StatusCode { get; } = statusCode;
}
