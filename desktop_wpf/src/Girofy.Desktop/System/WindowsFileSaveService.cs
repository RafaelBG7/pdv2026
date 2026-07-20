using Girofy.Application.Abstractions;
using Microsoft.Win32;

namespace Girofy.Desktop.System;

public sealed class WindowsFileSaveService : IFileSaveService
{
    public async Task<string?> SaveFileAsync(
        string suggestedFileName,
        string filter,
        byte[] content,
        CancellationToken cancellationToken)
    {
        var dialog = new SaveFileDialog
        {
            AddExtension = true,
            DefaultExt = ".csv",
            FileName = suggestedFileName,
            Filter = filter,
            OverwritePrompt = true,
            Title = "Salvar exportação do Girofy",
        };

        if (dialog.ShowDialog() != true)
        {
            return null;
        }

        await File.WriteAllBytesAsync(dialog.FileName, content, cancellationToken);
        return dialog.FileName;
    }
}
