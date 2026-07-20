namespace Girofy.Application.Abstractions;

public sealed class PickedFile
{
    public PickedFile(string fileName, string contentType, byte[] content)
    {
        FileName = fileName;
        ContentType = contentType;
        Content = content;
    }

    public string FileName { get; }

    public string ContentType { get; }

    public byte[] Content { get; }
}

public interface IFilePickerService
{
    Task<PickedFile?> PickFileAsync(
        string filter,
        CancellationToken cancellationToken);
}
