"""Configuration persistante (JSON) — équivalent de config.xml de la version Windows."""
import json
import os
import shutil
import tempfile

APP_ID = "apktoolgui-linux"
APP_NAME = "APK Tool GUI Linux"
APP_VERSION = "1.0.2"
UPSTREAM_VERSION = "3.4.0.0"

XDG_CONFIG = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
XDG_DATA = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
XDG_CACHE = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))

CONFIG_DIR = os.path.join(XDG_CONFIG, APP_ID)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DATA_DIR = os.path.join(XDG_DATA, APP_ID)
FRAMEWORK_DIR = os.path.join(DATA_DIR, "framework")
SDK_DIR = os.path.join(DATA_DIR, "sdk")  # outils Google téléchargés (optionnel)

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(PKG_DIR, "res")


def _find_tools_dir():
    cands = [
        os.environ.get("APKTOOLGUI_TOOLS", ""),
        os.path.join(os.path.dirname(os.path.dirname(PKG_DIR)), "tools"),  # arbo source
        os.path.join(os.path.dirname(PKG_DIR), "tools"),                   # /opt/apktoolgui-linux/tools
        "/opt/apktoolgui-linux/tools",
    ]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "apktool.jar")):
            return c
    return cands[2]


TOOLS_DIR = _find_tools_dir()

DEFAULTS = {
    # Général
    "Culture": "Auto",
    "Theme": 1,                      # 0 = clair, 1 = sombre
    "CheckForUpdateAtStartup": False,
    "ClearLogBeforeAction": True,
    "PlaySoundWhenDone": False,
    "DebugMode": False,
    "UseCustomTempDir": False,
    "TempDir": "",
    "UseCustomJavaExe": False,
    "JavaExe": "",
    "UseCustomJVMArgs": False,
    "CustomJVMArgs": "-Dfile.encoding=UTF8 -Djdk.util.zip.disableZip64ExtraFieldValidation=true -Djdk.nio.zipfs.allowDotZipEntry=true",
    "UseCustomApktool": False,
    "ApktoolPath": "",
    "UseCustomZipalign": False,
    "ZipalignPath": "",
    "UseCustomAdb": False,
    "AdbPath": "",
    "IgnoreOutputDirContextMenu": False,
    "UseApkeditor": False,
    "WindowGeometry": "",
    "SplitterState": "",
    # Champs de l'onglet Main
    "Decode_InputAppPath": "",
    "BuildProjectDir": "",
    "Zipalign_InputFile": "",
    "Sign_InputFile": "",
    "SplitApk_InputFile": "",
    # Decode
    "Decode_NoSrc": False,
    "Decode_NoRes": False,
    "Decode_Force": True,
    "Decode_KeepBrokenRes": False,
    "Decode_MatchOriginal": False,
    "Decode_UseFramework": False,
    "Framework_FrameDir": "",
    "Decode_UseOutputDir": False,
    "Decode_OutputDir": "",
    "Decode_AllSrc": False,
    "Decode_NoAssets": False,
    "Decode_OnlyManifest": False,
    "Decode_FixError": True,
    "Decode_NoDebugInfo": False,
    "Decode_DontParseApkInfo": False,
    "Decode_SetJobs": False,
    "Decode_Jobs": 4,
    "Decode_UseFrameTag": False,
    "Decode_FrameTag": "",
    # Build
    "Build_ForceAll": True,
    "Build_UseAapt": False,
    "Build_AaptPath": "",
    "Build_UseFramework": False,
    "Build_UseOutputAppPath": False,
    "Build_OutputAppPath": "",
    "Build_NoCrunch": False,
    "Build_NetSecConf": False,
    "Build_Debuggable": False,
    "Build_ZipalignAfterBuild": True,
    "Build_SignAfterBuild": True,
    "Build_CreateUnsignedApk": False,
    "Build_CopyOriginal": False,
    "Build_SetJobs": False,
    "Build_Jobs": 4,
    # Sign
    "Sign_PublicKey": "",
    "Sign_PrivateKey": "",
    "Sign_SetAlias": False,
    "Sign_Alias": "CERT",
    "Sign_UseKeystoreFile": False,
    "Sign_KeystoreFilePath": "",
    "Sign_KeystorePassword": "",
    "Sign_KeyPassword": "",
    "Sign_UseOutputDir": False,
    "Sign_OutputDir": "",
    "Sign_Schemev1": 0,
    "Sign_Schemev2": 0,
    "Sign_Schemev3": 0,
    "Sign_Schemev4": 0,
    "AutoDeleteIdsigFile": True,
    "Sign_OverwriteInputFile": False,
    "Sign_InstallApkAfterSign": False,
    # Zipalign
    "Zipalign_AlignmentInBytes": 4,
    "Zipalign_CheckOnly": False,
    "Zipalign_Verbose": False,
    "Zipalign_Recompress": False,
    "Zipalign_PageAlign": True,
    "Zipalign_OverwriteOutputFile": False,
    "Zipalign_SignAfterZipAlign": True,
    "Zipalign_UseOutputDir": False,
    "Zipalign_OutputDir": "",
    # Framework
    "Framework_UseFrameDir": False,
    "InstallFramework_UseTag": False,
    "InstallFramework_Tag": "",
    "InstallFramework_InputFramePath": "",
    "Framework_ClearBeforeDecode": True,
    # Baksmali / Smali
    "Baksmali_UseOutputDir": False,
    "Baksmali_OutputDir": "",
    "Baksmali_InputDexFile": "",
    "Smali_UseOutputDir": False,
    "Smali_OutputDir": "",
    "Smali_InputDir": "",
    # ADB
    "Adb_SetVendor": False,
    "Adb_SetOverrideAbi": False,
    "Adb_OverrideAbi": 0,
    "Adb_SelectedApkPath": "",
    "Adb_ConnectAddress": "",
}


class Config(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        self.load()
        if not self.get("Sign_PublicKey"):
            self["Sign_PublicKey"] = os.path.join(TOOLS_DIR, "testkey.x509.pem")
        if not self.get("Sign_PrivateKey"):
            self["Sign_PrivateKey"] = os.path.join(TOOLS_DIR, "testkey.pk8")

    def load(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if k in DEFAULTS:
                    self[k] = v
        except (OSError, ValueError):
            pass

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_FILE)


_TEMP = None


def temp_root(cfg):
    if cfg.get("UseCustomTempDir") and cfg.get("TempDir"):
        return os.path.join(cfg["TempDir"], APP_ID)
    return os.path.join(XDG_CACHE, APP_ID, "tmp")


def session_temp(cfg):
    """Dossier temporaire propre à cette instance (comme RandTempDirectory)."""
    global _TEMP
    if _TEMP and os.path.isdir(_TEMP):
        return _TEMP
    root = temp_root(cfg)
    os.makedirs(root, exist_ok=True)
    _TEMP = tempfile.mkdtemp(prefix="s", dir=root)
    return _TEMP


def cleanup_session_temp():
    global _TEMP
    if _TEMP:
        shutil.rmtree(_TEMP, ignore_errors=True)
        _TEMP = None
