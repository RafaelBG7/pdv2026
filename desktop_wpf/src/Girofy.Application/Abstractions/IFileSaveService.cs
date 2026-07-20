namespace Girofy.Application.Abstractions;

public interface IFileSaveService
{
    Task<string?> SaveFileAsync(
        string suggestedFileName,
        string filter,
        byte[] content,
        CancellationToken cancellationToken);
}
