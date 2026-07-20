using System.IO;
using Girofy.Application.Abstractions;
using Microsoft.Win32;

namespace Girofy.Desktop.Platform;

public sealed class WindowsFilePickerService : IFilePickerService
{
    public async Task<PickedFile?> PickFileAsync(
        string filter,
        CancellationToken cancellationToken)
    {
        var dialog = new OpenFileDialog
        {
            AddExtension = true,
            CheckFileExists = true,
            Filter = filter,
            Multiselect = false,
            Title = "Importar produtos no Girofy",
        };

        if (dialog.ShowDialog() != true)
        {
            return null;
        }

        var content = await File.ReadAllBytesAsync(dialog.FileName, cancellationToken);
        var contentType = dialog.FileName.EndsWith(".xlsx", StringComparison.OrdinalIgnoreCase)
            ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            : "text/csv";

        return new PickedFile(Path.GetFileName(dialog.FileName), contentType, content);
    }
}
