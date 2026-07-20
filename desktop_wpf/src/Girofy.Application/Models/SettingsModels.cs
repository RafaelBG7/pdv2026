using System.Text.Json.Serialization;

namespace Girofy.Application.Models;

public class SettingsAccountSnapshot
{
    [JsonPropertyName("user")]
    public UserIdentity User { get; init; } = new();

    [JsonPropertyName("company")]
    public CompanyIdentity? Company { get; init; }

    [JsonPropertyName("profile")]
    public SettingsProfile Profile { get; init; } = new();

    [JsonPropertyName("company_settings")]
    public SettingsCompanyOptions? CompanySettings { get; init; }
}

public sealed class SettingsProfile
{
    [JsonPropertyName("username")]
    public string Username { get; init; } = string.Empty;

    [JsonPropertyName("first_name")]
    public string FirstName { get; init; } = string.Empty;

    [JsonPropertyName("last_name")]
    public string LastName { get; init; } = string.Empty;

    [JsonPropertyName("full_name")]
    public string FullName { get; init; } = string.Empty;

    [JsonPropertyName("email")]
    public string Email { get; init; } = string.Empty;

    [JsonPropertyName("phone")]
    public string Phone { get; init; } = string.Empty;

    [JsonPropertyName("role_label")]
    public string RoleLabel { get; init; } = string.Empty;
}

public sealed class SettingsCompanyOptions
{
    [JsonPropertyName("allow_negative_stock")]
    public bool AllowNegativeStock { get; init; }

    [JsonPropertyName("backup_frequency")]
    public string BackupFrequency { get; init; } = string.Empty;

    [JsonPropertyName("backup_last_at")]
    public string? BackupLastAt { get; init; }

    [JsonPropertyName("backup_last_status")]
    public string BackupLastStatus { get; init; } = string.Empty;

    [JsonPropertyName("pix_fee_enabled")]
    public bool PixFeeEnabled { get; init; }

    [JsonPropertyName("debit_fee_enabled")]
    public bool DebitFeeEnabled { get; init; }

    [JsonPropertyName("credit_fee_enabled")]
    public bool CreditFeeEnabled { get; init; }

    [JsonPropertyName("pix_fee_percent")]
    public decimal PixFeePercent { get; init; }

    [JsonPropertyName("debit_fee_percent")]
    public decimal DebitFeePercent { get; init; }

    [JsonPropertyName("credit_fee_percent")]
    public decimal CreditFeePercent { get; init; }
}

public sealed class BackupFrequencyOption
{
    public BackupFrequencyOption(string value, string label)
    {
        Value = value;
        Label = label;
    }

    public string Value { get; }

    public string Label { get; }
}

public sealed class ExportDataTypeOption
{
    public ExportDataTypeOption(string value, string label)
    {
        Value = value;
        Label = label;
    }

    public string Value { get; }

    public string Label { get; }
}

public sealed class ExportFile
{
    public ExportFile(string fileName, string contentType, byte[] content)
    {
        FileName = fileName;
        ContentType = contentType;
        Content = content;
    }

    public string FileName { get; }

    public string ContentType { get; }

    public byte[] Content { get; }
}

public sealed class ProductImportResult
{
    [JsonPropertyName("created")]
    public int Created { get; init; }

    [JsonPropertyName("updated")]
    public int Updated { get; init; }

    [JsonPropertyName("skipped")]
    public int Skipped { get; init; }

    [JsonPropertyName("movements")]
    public int Movements { get; init; }

    [JsonPropertyName("total_rows")]
    public int TotalRows { get; init; }
}

public sealed record UpdateBackupSettingsRequest(
    [property: JsonPropertyName("backup_frequency")] string BackupFrequency);

public sealed record UpdateCompanySettingsRequest(
    [property: JsonPropertyName("allow_negative_stock")] bool AllowNegativeStock,
    [property: JsonPropertyName("pix_fee_enabled")] bool PixFeeEnabled,
    [property: JsonPropertyName("pix_fee_percent")] decimal PixFeePercent,
    [property: JsonPropertyName("debit_fee_enabled")] bool DebitFeeEnabled,
    [property: JsonPropertyName("debit_fee_percent")] decimal DebitFeePercent,
    [property: JsonPropertyName("credit_fee_enabled")] bool CreditFeeEnabled,
    [property: JsonPropertyName("credit_fee_percent")] decimal CreditFeePercent);

public sealed class ManualBackupResult : SettingsAccountSnapshot
{
    [JsonPropertyName("backup")]
    public ManualBackupInfo Backup { get; init; } = new();
}

public sealed class ManualBackupInfo
{
    [JsonPropertyName("file_name")]
    public string FileName { get; init; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; init; } = string.Empty;

    [JsonPropertyName("generated_at")]
    public string? GeneratedAt { get; init; }
}

public sealed record UpdateProfileRequest(
    [property: JsonPropertyName("first_name")] string FirstName,
    [property: JsonPropertyName("last_name")] string LastName,
    [property: JsonPropertyName("phone")] string Phone);

public sealed record ChangePasswordRequest(
    [property: JsonPropertyName("current_password")] string CurrentPassword,
    [property: JsonPropertyName("new_password")] string NewPassword,
    [property: JsonPropertyName("confirm_password")] string ConfirmPassword);

public sealed class ChangePasswordResult
{
    [JsonPropertyName("password_changed")]
    public bool PasswordChanged { get; init; }

    [JsonPropertyName("requires_login")]
    public bool RequiresLogin { get; init; }
}

public sealed class SettingsTeamSnapshot
{
    [JsonPropertyName("employees")]
    public IReadOnlyList<SettingsEmployee> Employees { get; init; } = [];

    [JsonPropertyName("roles")]
    public IReadOnlyList<SettingsEmployeeRoleOption> Roles { get; init; } = [];

    [JsonPropertyName("permissions")]
    public IReadOnlyList<SettingsEmployeePermissionOption> Permissions { get; init; } = [];
}

public sealed class SettingsEmployee
{
    [JsonPropertyName("id")]
    public int Id { get; init; }

    [JsonPropertyName("username")]
    public string Username { get; init; } = string.Empty;

    [JsonPropertyName("first_name")]
    public string FirstName { get; init; } = string.Empty;

    [JsonPropertyName("last_name")]
    public string LastName { get; init; } = string.Empty;

    [JsonPropertyName("full_name")]
    public string FullName { get; init; } = string.Empty;

    [JsonPropertyName("cpf")]
    public string Cpf { get; init; } = string.Empty;

    [JsonPropertyName("email")]
    public string Email { get; init; } = string.Empty;

    [JsonPropertyName("phone")]
    public string Phone { get; init; } = string.Empty;

    [JsonPropertyName("role")]
    public string Role { get; init; } = string.Empty;

    [JsonPropertyName("role_label")]
    public string RoleLabel { get; init; } = string.Empty;

    [JsonPropertyName("is_active")]
    public bool IsActive { get; init; }

    [JsonPropertyName("is_current_user")]
    public bool IsCurrentUser { get; init; }

    [JsonPropertyName("created_at")]
    public string? CreatedAt { get; init; }

    [JsonPropertyName("permissions")]
    public IReadOnlyDictionary<string, bool> Permissions { get; init; } =
        new Dictionary<string, bool>();

    public string DisplayName => string.IsNullOrWhiteSpace(FullName) ? Username : FullName;

    public string StatusText => IsActive ? "Ativo" : "Inativo";

    public string CurrentUserText => IsCurrentUser ? "Você" : string.Empty;
}

public sealed class SettingsEmployeeRoleOption
{
    [JsonPropertyName("value")]
    public string Value { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; init; } = string.Empty;

    [JsonPropertyName("default_permissions")]
    public IReadOnlyDictionary<string, bool> DefaultPermissions { get; init; } =
        new Dictionary<string, bool>();
}

public sealed class SettingsEmployeePermissionOption
{
    [JsonPropertyName("value")]
    public string Value { get; init; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; init; } = string.Empty;
}

public sealed record CreateEmployeeRequest(
    [property: JsonPropertyName("username")] string Username,
    [property: JsonPropertyName("password")] string Password,
    [property: JsonPropertyName("first_name")] string FirstName,
    [property: JsonPropertyName("last_name")] string LastName,
    [property: JsonPropertyName("cpf")] string Cpf,
    [property: JsonPropertyName("email")] string Email,
    [property: JsonPropertyName("phone")] string Phone,
    [property: JsonPropertyName("role")] string Role);

public sealed record UpdateEmployeeRequest(
    [property: JsonPropertyName("first_name")] string FirstName,
    [property: JsonPropertyName("last_name")] string LastName,
    [property: JsonPropertyName("cpf")] string Cpf,
    [property: JsonPropertyName("email")] string Email,
    [property: JsonPropertyName("phone")] string Phone,
    [property: JsonPropertyName("role")] string Role,
    [property: JsonPropertyName("is_active")] bool IsActive);
