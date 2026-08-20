using System.Collections.ObjectModel;
using System.Net.Mail;
using Girofy.Application.Models;
using Girofy.Application.Mvvm;

namespace Girofy.Application.ViewModels;

public sealed class EmailAlertSettingViewModel : ObservableObject
{
    private bool _enabled;
    private string _recipientDraft = string.Empty;
    private string _validationMessage = string.Empty;

    public EmailAlertSettingViewModel(EmailAlertSettingItem item)
    {
        AlertType = item.AlertType;
        Label = item.Label;
        Description = item.Description;
        _enabled = item.Enabled;
        foreach (var recipient in item.Recipients)
        {
            Recipients.Add(recipient);
        }
        AddRecipientCommand = new RelayCommand(AddRecipient);
        RemoveRecipientCommand = new RelayCommand<string>(RemoveRecipient);
    }

    public string AlertType { get; }
    public string Label { get; }
    public string Description { get; }
    public ObservableCollection<string> Recipients { get; } = [];
    public RelayCommand AddRecipientCommand { get; }
    public RelayCommand<string> RemoveRecipientCommand { get; }

    public bool Enabled { get => _enabled; set => SetProperty(ref _enabled, value); }
    public string RecipientDraft { get => _recipientDraft; set => SetProperty(ref _recipientDraft, value); }
    public string ValidationMessage
    {
        get => _validationMessage;
        private set
        {
            if (SetProperty(ref _validationMessage, value))
            {
                OnPropertyChanged(nameof(HasValidationError));
            }
        }
    }
    public bool HasValidationError => !string.IsNullOrWhiteSpace(ValidationMessage);

    public UpdateEmailAlertSettingItem ToRequest() =>
        new(AlertType, Enabled, string.Join(", ", Recipients));

    private void AddRecipient()
    {
        var value = RecipientDraft.Trim();
        if (!MailAddress.TryCreate(value, out var address) || !string.Equals(address.Address, value, StringComparison.OrdinalIgnoreCase))
        {
            ValidationMessage = "Informe um e-mail válido.";
            return;
        }
        if (!Recipients.Any(item => string.Equals(item, value, StringComparison.OrdinalIgnoreCase)))
        {
            Recipients.Add(value);
        }
        RecipientDraft = string.Empty;
        ValidationMessage = string.Empty;
    }

    private void RemoveRecipient(string recipient)
    {
        Recipients.Remove(recipient);
        ValidationMessage = string.Empty;
    }
}
