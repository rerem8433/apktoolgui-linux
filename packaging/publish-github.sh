#!/bin/bash
# Crée le dépôt GitHub rerem8433/apktoolgui-linux (si absent), pousse le code et publie la release.
# Prérequis : sudo apt install gh && gh auth login
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="rerem8433/apktoolgui-linux"
VER="$(python3 -c "import sys; sys.path.insert(0,'src'); from apktoolgui import config; print(config.APP_VERSION)")"
DEB="dist/apktoolgui-linux_${VER}_amd64.deb"
[ -f "$DEB" ] || packaging/build-deb.sh dist

if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public \
    --description "APK Tool GUI Linux — fork Linux natif d'APKToolGUI (apktool, APKEditor, apksigner, zipalign, baksmali, adb)" \
    --homepage "https://github.com/$REPO/releases/latest"
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$REPO.git"
git push -u origin main --tags
gh repo edit "$REPO" --add-topic android,apktool,apk,linux-mint,pyqt6,smali,reverse-engineering,apksigner
# La release est aussi créée par GitHub Actions au push du tag : on crée ou on met à jour.
if gh release view "v$VER" --repo "$REPO" >/dev/null 2>&1; then
  gh release upload "v$VER" "$DEB" --repo "$REPO" --clobber
else
  gh release create "v$VER" "$DEB" --repo "$REPO" --title "APK Tool GUI Linux $VER" \
    --notes-file "packaging/RELEASE_NOTES_v$VER.md" --latest
fi
echo "OK : https://github.com/$REPO/releases/tag/v$VER"
