#!/bin/bash
# Construit apktoolgui-linux_<version>_amd64.deb
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="$(python3 -c "import sys; sys.path.insert(0,'$ROOT/src'); from apktoolgui import config; print(config.APP_VERSION)")"
PKG=apktoolgui-linux
OUT="${1:-$ROOT/dist}"
B="$(mktemp -d)"
trap 'rm -rf "$B"' EXIT

install -d "$B/DEBIAN" "$B/opt/$PKG" "$B/usr/bin" "$B/usr/share/applications" \
           "$B/usr/share/nemo/actions" "$B/usr/share/doc/$PKG"
cp -r "$ROOT/src/apktoolgui" "$B/opt/$PKG/"
find "$B/opt/$PKG" -name "__pycache__" -prune -exec rm -rf {} +
cp -r "$ROOT/tools" "$B/opt/$PKG/tools"
chmod 0755 "$B/opt/$PKG/tools/aapt2"
chmod 0644 "$B/opt/$PKG/tools/"*.jar "$B/opt/$PKG/tools/"testkey.*

cat > "$B/usr/bin/$PKG" <<EOF
#!/bin/sh
export PYTHONPATH="/opt/$PKG\${PYTHONPATH:+:\$PYTHONPATH}"
exec /usr/bin/python3 -m apktoolgui "\$@"
EOF
chmod 0755 "$B/usr/bin/$PKG"

# icônes
for s in 48 64 128 256; do
  install -d "$B/usr/share/icons/hicolor/${s}x${s}/apps"
  python3 - "$ROOT/src/apktoolgui/res/android.png" "$B/usr/share/icons/hicolor/${s}x${s}/apps/$PKG.png" "$s" <<'PY'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGBA")
im.resize((int(sys.argv[3]),) * 2, Image.LANCZOS).save(sys.argv[2])
PY
done

cat > "$B/usr/share/applications/$PKG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=APK Tool GUI Linux
GenericName=APK decompiler / compiler
GenericName[fr]=Décompilateur / compilateur APK
GenericName[es]=Descompilador / compilador APK
GenericName[ru]=Декомпилятор / сборщик APK
Comment=GUI for apktool, APKEditor, apksigner, zipalign, baksmali and adb
Comment[fr]=Interface pour apktool, APKEditor, apksigner, zipalign, baksmali et adb
Comment[es]=Interfaz para apktool, APKEditor, apksigner, zipalign, baksmali y adb
Comment[ru]=Интерфейс для apktool, APKEditor, apksigner, zipalign, baksmali и adb
Exec=$PKG %f
Icon=$PKG
Terminal=false
Categories=Development;Utility;
MimeType=application/vnd.android.package-archive;
Keywords=apk;apktool;android;smali;decompile;sign;zipalign;
StartupWMClass=$PKG
EOF

# actions Nemo (clic droit) pour tout le système
PYTHONPATH="$ROOT/src" python3 - "$B/usr/share/nemo/actions" "/usr/bin/$PKG" <<'PY'
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from apktoolgui import nemo as s, config as C
for key, label, exts, arg in s.NEMO_ACTIONS:
    with open(os.path.join(sys.argv[1], "%s-%s.nemo_action" % (C.APP_ID, key)), "w") as f:
        f.write(s.nemo_action_text(label, exts, arg, sys.argv[2]))
PY

cp "$ROOT/README.md" "$ROOT/LICENSE" "$ROOT/CHANGELOG.md" "$B/usr/share/doc/$PKG/"

SIZE=$(du -sk "$B" | cut -f1)
cat > "$B/DEBIAN/control" <<EOF
Package: $PKG
Version: $VER
Section: devel
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.8), python3-pyqt6, python3-pyqt6.qtsvg, qt6-image-formats-plugins, default-jre-headless | java11-runtime-headless | java17-runtime-headless | java21-runtime-headless, zipalign, adb
Recommends: nemo, qt6-translations-l10n
Installed-Size: $SIZE
Maintainer: ParadoxXx Squad <jaylavet@gmail.com>
Homepage: https://github.com/rerem8433/apktoolgui-linux
Description: APK Tool GUI - Linux fork (apktool, APKEditor, apksigner, zipalign, baksmali, adb)
 Native Linux port (Python/PyQt6) of APKToolGUI 3.4.0.0 by AndnixSH.
 Decompile/compile APK with Apktool 3 or APKEditor, merge XAPK/APKS/APKM,
 sign with apksigner, zipalign, smali/baksmali, install frameworks,
 APK info (aapt2), install over ADB, Nemo right-click actions.
EOF

cat > "$B/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
exit 0
EOF
cp "$B/DEBIAN/postinst" "$B/DEBIAN/postrm"
chmod 0755 "$B/DEBIAN/postinst" "$B/DEBIAN/postrm"

mkdir -p "$OUT"
dpkg-deb --root-owner-group -Zxz --build "$B" "$OUT/${PKG}_${VER}_amd64.deb" >/dev/null
echo "$OUT/${PKG}_${VER}_amd64.deb"
