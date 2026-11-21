# Changelog

**English** | [Français](CHANGELOG.fr.md) | [Español](CHANGELOG.es.md) | [Русский](CHANGELOG.ru.md)

All notable changes to **APK Tool GUI Linux** are listed here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [SemVer](https://semver.org/).

## [1.0.2] - 2026-11-21

### Added
- **Spanish** and **Russian** interface, in addition to English and French (choose in *Settings → Language*, system language by default).
- Nemo right-click actions and the menu shortcut translated into all 4 languages.
- Standard buttons (OK/Cancel, Yes/No) translated; standard Qt dialogs translated when the `qt6-translations-l10n` package is installed (recommended by the .deb).
- The About box is translated and shows the bundled Apktool version.
- README and CHANGELOG available in English, French, Spanish and Russian.

### Changed
- **Apktool 3.0.2 → 3.0.3**: fixes "android:* not found" errors, accepts empty flag values, optimized string pool. Command-line options unchanged.
- **APKEditor 1.4.7 → 1.4.9**: fixes a split APK merging bug, smali wide register handling, better performance.
- The window widens when needed so all 9 tabs stay visible (Russian).
- GitHub Actions build: `actions/checkout` and `actions/upload-artifact` moved to v7 (Node.js 24), removing the Node.js 20 deprecation warning.

### Fixed
- The "Picked up _JAVA_OPTIONS…" line was shown instead of the APKEditor version when the `_JAVA_OPTIONS` variable is set (common on Linux for Java font antialiasing). These lines are now filtered everywhere.
- Action buttons cut off when the text is long (Baksmali tab in Russian).

## [1.0.1] - 2026-10-28

### Fixed
- **Missing icon in the APK Info tab** for recent apps (e.g. AnyDesk) that declare an XML adaptive icon (`mipmap-anydpi-v26`) with shortened or obfuscated resource names.

### Added
- New icon extraction engine (`icon.py`) based on resource IDs (`aapt2 dump resources` / `dump xmltree`):
  - picks the original highest-density PNG/WebP hidden behind the adaptive icon;
  - otherwise renders the adaptive icon: background, foreground, VectorDrawable (groups, transforms, clip-path), `inset`, `layer-list`, `bitmap`, `shape`, linear/radial gradients, rounded mask;
  - falls back to the icon declared in the AndroidManifest;
  - also works when attribute and resource names are obfuscated (R8, AndResGuard, `--shorten-resource-paths`).
- WebP → PNG fallback conversion via Pillow when Qt's WebP plugin is missing.

### Changed
- New package dependencies: `python3-pyqt6.qtsvg`, `qt6-image-formats-plugins`.

## 1.0.0 - 2026-10-19

*Not published on GitHub (the repository was created with 1.0.1).*

First release: native Linux port (Python 3 + PyQt6) of [APKToolGUI](https://github.com/AndnixSH/APKToolGUI) 3.4.0.0 by AndnixSH.

### Added
- The 9 tabs of the original: Main, APK Info, Decode, Build, Sign, Zip align, Framework, Baksmali, ADB.
- Bundled tools: Apktool 3.0.2, APKEditor 1.4.7, apksigner, smali/baksmali, Linux aapt2.
- Decompile/compile with Apktool or APKEditor (APKEditor projects detected automatically).
- Merge XAPK/APKS/APKM/ZIP and decompile split APKs directly.
- Compile → zipalign → sign → install over ADB chain; unsigned APK with the original signature.
- Automatic Apktool fixes (manifest, `sparseResources`, `APKTOOL_DUMMY`).
- Signing with pem/pk8 key or JKS keystore, schemes v1 to v4; passwords passed through environment variables.
- Options adapted to Apktool 3 (`-a`, `--no-assets`, `--only-manifest`, `--debuggable`, framework tag).
- ADB tab: device list, Wi-Fi connection `IP:port`, install (`-i com.android.vending`, `--abi`).
- Nemo right-click actions (Linux Mint) installed system-wide.
- Command line: `--decompile`, `--compile`, `--sign`, `--align`, `--merge`, `--info`, `--baksmali`, `--install`.
- Optional download of the official Google platform-tools / build-tools from Settings.
- English and French interface, dark/light theme, drag & drop everywhere, colored log.

[1.0.2]: https://github.com/rerem8433/apktoolgui-linux/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/rerem8433/apktoolgui-linux/releases/tag/v1.0.1
