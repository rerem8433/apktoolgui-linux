"""Actions de clic droit Nemo (Linux Mint) — équivalent du menu contextuel Explorer."""
import os
import shutil
import sys

from . import config as C


NEMO_DIR = os.path.join(C.XDG_DATA, "nemo", "actions")
NEMO_ACTIONS = [
    ("decompile", "Decompile with APK Tool GUI", "apk;xapk;apks;apkm", "decompile"),
    ("compile", "Compile with APK Tool GUI", None, "compile"),
    ("sign", "Sign with APK Tool GUI", "apk", "sign"),
    ("align", "Zipalign with APK Tool GUI", "apk", "align"),
    ("merge", "Merge split APK with APK Tool GUI", "xapk;apks;apkm", "merge"),
    ("info", "View APK info", "apk;xapk;apks;apkm", "info"),
    ("baksmali", "Baksmali (dex → smali)", "dex", "baksmali"),
    ("install", "Install with ADB (APK Tool GUI)", "apk", "install"),
]


def _launcher():
    exe = shutil.which(C.APP_ID)
    if exe:
        return exe
    return "%s -m apktoolgui" % sys.executable


SYSTEM_NEMO_DIR = "/usr/share/nemo/actions"


def nemo_action_text(label, exts, arg, exe):
    from .i18n import FR
    lines = ["[Nemo Action]", "Name=%s" % label, "Name[fr]=%s" % FR.get(label, label),
             "Comment=%s" % label, "Comment[fr]=%s" % FR.get(label, label),
             "Exec=%s --%s %%F" % (exe, arg), "Icon-Name=%s" % C.APP_ID, "Selection=s",
             "Extensions=dir;" if exts is None else "Extensions=%s;" % exts]
    return "\n".join(lines) + "\n"


def system_actions_installed():
    return os.path.isfile(os.path.join(SYSTEM_NEMO_DIR, C.APP_ID + "-decompile.nemo_action"))


def install_nemo_actions():
    os.makedirs(NEMO_DIR, exist_ok=True)
    exe = _launcher()
    for key, label, exts, arg in NEMO_ACTIONS:
        with open(os.path.join(NEMO_DIR, "%s-%s.nemo_action" % (C.APP_ID, key)), "w") as f:
            f.write(nemo_action_text(label, exts, arg, exe))
    return NEMO_DIR


def uninstall_nemo_actions():
    if not os.path.isdir(NEMO_DIR):
        return
    for fn in os.listdir(NEMO_DIR):
        if fn.startswith(C.APP_ID + "-") and fn.endswith(".nemo_action"):
            os.remove(os.path.join(NEMO_DIR, fn))


