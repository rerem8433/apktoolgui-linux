# APK Tool GUI Linux

[![Release](https://img.shields.io/github/v/release/rerem8433/apktoolgui-linux?style=for-the-badge)](https://github.com/rerem8433/apktoolgui-linux/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/rerem8433/apktoolgui-linux/total?style=for-the-badge)](https://github.com/rerem8433/apktoolgui-linux/releases)
![Platform](https://img.shields.io/badge/Linux%20Mint%20%7C%20Ubuntu-amd64-87CF3E?style=for-the-badge)

Fork Linux natif (Python 3 + PyQt6) d'[APKToolGUI](https://github.com/AndnixSH/APKToolGUI) 3.4.0.0 d'AndnixSH.
Portage Linux : **ParadoxXx Squad**.

![](screenshot.png)

## Fonctions
- Décompiler / compiler avec **Apktool 3.0.2** ou **APKEditor 1.4.7** (projet APKEditor détecté tout seul)
- Fusion XAPK / APKS / APKM / ZIP → APK unique (APKEditor), décompilation directe des split APK
- Signature **apksigner** (clé pem/pk8 ou keystore JKS, schémas v1→v4), **zipalign** (+ `-p`, Zopfli, vérification)
- Chaîne compiler → zipalign → signer → installer ADB
- APK non signé avec la signature d'origine (Core Patch)
- Correctifs Apktool automatiques (manifest, `sparseResources`, `APKTOOL_DUMMY`)
- Smali / Baksmali, installation et nettoyage des frameworks
- Infos APK (aapt2) : icône, versions, SDK, ABI, langues, permissions, dump complet, certificat
- Onglet ADB : appareils, connexion Wi-Fi `IP:port`, installation (`-i com.android.vending`, `--abi`)
- Glisser-déposer partout, journal coloré, thème sombre/clair, FR/EN
- **Clic droit dans Nemo** (Linux Mint) : décompiler, compiler un dossier, signer, aligner, fusionner, infos, baksmali, installer
- Ligne de commande : `apktoolgui-linux --decompile app.apk` (`--compile`, `--sign`, `--align`, `--merge`, `--info`, `--baksmali`, `--install`)

## Installation (Linux Mint 21/22, Ubuntu 22.04+)
Télécharge le `.deb` dans les [Releases](https://github.com/rerem8433/apktoolgui-linux/releases/latest), puis :
```
sudo apt install ./apktoolgui-linux_1.0.1_amd64.deb
```
Dépendances tirées automatiquement : `python3-pyqt6`, Java (`default-jre-headless`), `zipalign`, `adb`.
Optionnel : *Paramètres → Outils* télécharge les derniers platform-tools / build-tools officiels Google dans `~/.local/share/apktoolgui-linux/sdk`.

## Fichiers
- Réglages : `~/.config/apktoolgui-linux/config.json`
- Frameworks : `~/.local/share/apktoolgui-linux/framework`
- Temporaire : `~/.cache/apktoolgui-linux/tmp`

## Lancer depuis les sources
```
sudo apt install python3-pyqt6 default-jre-headless zipalign adb
cd src && python3 -m apktoolgui
```
Construire le .deb : `packaging/build-deb.sh`

## Changelog
Voir [CHANGELOG.md](CHANGELOG.md).

## Problèmes
[Ouvrir une issue](https://github.com/rerem8433/apktoolgui-linux/issues)

## Crédits
APKToolGUI (AndnixSH, domaine public) · Apktool (iBotPeaches) · APKEditor (REAndroid) · smali/baksmali (JesusFreke / Google) · apksigner, zipalign, adb, aapt2 (AOSP).
