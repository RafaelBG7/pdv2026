#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/Girofy.app}"
CERT_BASE64="${APPLE_DEVELOPER_ID_CERTIFICATE_BASE64:-}"
CERT_PASSWORD="${APPLE_DEVELOPER_ID_CERTIFICATE_PASSWORD:-}"
SIGNING_IDENTITY="${APPLE_DEVELOPER_IDENTITY:-}"
APPLE_ID_VALUE="${APPLE_ID:-}"
APPLE_TEAM_ID_VALUE="${APPLE_TEAM_ID:-}"
APPLE_PASSWORD_VALUE="${APPLE_APP_SPECIFIC_PASSWORD:-}"
KEYCHAIN_PASSWORD_VALUE="${APPLE_BUILD_KEYCHAIN_PASSWORD:-$(uuidgen)}"

if [[ -z "$CERT_BASE64" || -z "$CERT_PASSWORD" || -z "$SIGNING_IDENTITY" ]]; then
  echo "Certificado Apple Developer ID não configurado. Pulando assinatura/notarização."
  exit 0
fi

if [[ ! -d "$APP_PATH" ]]; then
  echo "App não encontrado em $APP_PATH"
  exit 1
fi

KEYCHAIN_PATH="$RUNNER_TEMP/girofy-signing.keychain-db"
CERT_PATH="$RUNNER_TEMP/girofy-developer-id.p12"

echo "$CERT_BASE64" | base64 --decode > "$CERT_PATH"

security create-keychain -p "$KEYCHAIN_PASSWORD_VALUE" "$KEYCHAIN_PATH"
security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASSWORD_VALUE" "$KEYCHAIN_PATH"
security import "$CERT_PATH" -P "$CERT_PASSWORD" -A -t cert -f pkcs12 -k "$KEYCHAIN_PATH"
security list-keychains -d user -s "$KEYCHAIN_PATH" login.keychain-db
security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PASSWORD_VALUE" "$KEYCHAIN_PATH"

codesign --force --deep --options runtime --timestamp --sign "$SIGNING_IDENTITY" "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

if [[ -z "$APPLE_ID_VALUE" || -z "$APPLE_TEAM_ID_VALUE" || -z "$APPLE_PASSWORD_VALUE" ]]; then
  echo "Credenciais de notarização Apple não configuradas. App foi assinado, mas não notarizado."
  exit 0
fi

NOTARY_ZIP="$RUNNER_TEMP/Girofy-notary.zip"
ditto -c -k --keepParent "$APP_PATH" "$NOTARY_ZIP"

xcrun notarytool submit "$NOTARY_ZIP" \
  --apple-id "$APPLE_ID_VALUE" \
  --team-id "$APPLE_TEAM_ID_VALUE" \
  --password "$APPLE_PASSWORD_VALUE" \
  --wait

xcrun stapler staple "$APP_PATH"
xcrun stapler validate "$APP_PATH"
