"""Fenêtre Paramètres (port de SettingsWindow.xaml) + intégration Nemo + téléchargement des outils Google."""
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QCheckBox,
                             QLineEdit, QPushButton, QComboBox, QLabel, QDialogButtonBox, QFileDialog,
                             QMessageBox, QTabWidget, QWidget, QProgressBar)

from . import config as C
from .i18n import tr, LANGUAGES

REPO = "https://dl.google.com/android/repository/"


# =========================================================================== téléchargement SDK
def _extract_with_perms(zf_path, dest):
    with zipfile.ZipFile(zf_path) as z:
        for info in z.infolist():
            out = os.path.join(dest, info.filename)
            if not os.path.abspath(out).startswith(os.path.abspath(dest) + os.sep):
                continue  # protection zip-slip
            mode = (info.external_attr >> 16) & 0o7777
            if (info.external_attr >> 16) & 0o170000 == 0o120000:  # lien symbolique
                os.makedirs(os.path.dirname(out), exist_ok=True)
                target = z.read(info).decode()
                if os.path.lexists(out):
                    os.remove(out)
                os.symlink(target, out)
                continue
            if info.is_dir():
                os.makedirs(out, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
            if mode:
                os.chmod(out, mode)


class SdkDownloader(QThread):
    sig_msg = pyqtSignal(str)
    sig_prog = pyqtSignal(int)
    sig_done = pyqtSignal(bool, str)

    def _latest_build_tools(self):
        try:
            with urllib.request.urlopen(REPO + "repository2-3.xml", timeout=30) as r:
                root = ET.fromstring(r.read())
            best = None
            for p in root.iter():
                if not p.tag.endswith("remotePackage"):
                    continue
                path = p.get("path", "")
                if not path.startswith("build-tools;") or "-rc" in path:
                    continue
                ver = tuple(int(x) for x in re.findall(r"\d+", path.split(";")[1]))
                url = None
                for a in p.iter():
                    if a.tag.endswith("archive"):
                        hos = [x.text for x in a.iter() if x.tag.endswith("host-os")]
                        if "linux" in hos:
                            for u in a.iter():
                                if u.tag.endswith("url"):
                                    url = u.text
                if url and (best is None or ver > best[0]):
                    best = (ver, url)
            if best:
                return ".".join(map(str, best[0])), best[1]
        except Exception:  # noqa
            pass
        return "35.0.0", "build-tools_r35.0.0_linux.zip"

    def _get(self, url, dst):
        with urllib.request.urlopen(url, timeout=60) as r, open(dst, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                b = r.read(1 << 16)
                if not b:
                    break
                f.write(b)
                done += len(b)
                if total:
                    self.sig_prog.emit(int(done * 100 / total))

    def run(self):
        try:
            os.makedirs(C.SDK_DIR, exist_ok=True)
            tmp = tempfile.mkdtemp(prefix="sdk", dir=C.SDK_DIR)
            self.sig_msg.emit("platform-tools…")
            z1 = os.path.join(tmp, "pt.zip")
            self._get(REPO + "platform-tools-latest-linux.zip", z1)
            ex = os.path.join(tmp, "x1")
            _extract_with_perms(z1, ex)
            dst = os.path.join(C.SDK_DIR, "platform-tools")
            shutil.rmtree(dst, ignore_errors=True)
            shutil.move(os.path.join(ex, "platform-tools"), dst)

            ver, name = self._latest_build_tools()
            self.sig_msg.emit("build-tools %s…" % ver)
            z2 = os.path.join(tmp, "bt.zip")
            self._get(REPO + name, z2)
            ex = os.path.join(tmp, "x2")
            _extract_with_perms(z2, ex)
            sub = [d for d in os.listdir(ex) if os.path.isdir(os.path.join(ex, d))]
            dst = os.path.join(C.SDK_DIR, "build-tools")
            shutil.rmtree(dst, ignore_errors=True)
            shutil.move(os.path.join(ex, sub[0]), dst)
            shutil.rmtree(tmp, ignore_errors=True)
            self.sig_done.emit(True, "platform-tools + build-tools %s → %s" % (ver, C.SDK_DIR))
        except Exception as e:  # noqa
            self.sig_done.emit(False, str(e))


from .nemo import NEMO_ACTIONS, install_nemo_actions, uninstall_nemo_actions, system_actions_installed  # noqa


# =========================================================================== dialogue
class SettingsDialog(QDialog):
    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle(tr("Settings"))
        self.resize(560, 520)
        self.vals = {}
        tabs = QTabWidget()
        tabs.addTab(self._general(), tr("General"))
        tabs.addTab(self._tools(), tr("Tools"))
        tabs.addTab(self._integration(), tr("Context menu"))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("OK"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel"))
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        v = QVBoxLayout(self)
        v.addWidget(tabs)
        v.addWidget(bb)

    # helpers : valeurs appliquées seulement sur OK
    def chk(self, text, key):
        cb = QCheckBox(text)
        cb.setChecked(bool(self.cfg.get(key)))
        self.vals[key] = lambda: cb.isChecked()
        return cb

    def line(self, key):
        le = QLineEdit(str(self.cfg.get(key) or ""))
        self.vals[key] = lambda: le.text()
        return le

    def browse(self, le, mode, filt=""):
        b = QPushButton("...")
        b.setFixedWidth(36)

        def pick():
            if mode == "dir":
                p = QFileDialog.getExistingDirectory(self, tr("Select folder"), le.text() or os.path.expanduser("~"))
            else:
                p, _ = QFileDialog.getOpenFileName(self, tr("Select file"), le.text() or "/usr/bin", filt)
            if p:
                le.setText(p)
        b.clicked.connect(pick)
        return b

    def row(self, g, r, text, chk_key, line_key, mode, filt=""):
        g.addWidget(self.chk(text, chk_key), r, 0)
        le = self.line(line_key)
        g.addWidget(le, r, 1)
        g.addWidget(self.browse(le, mode, filt), r, 2)

    def _general(self):
        w = QWidget()
        v = QVBoxLayout(w)
        gb = QGroupBox(tr("General"))
        g = QGridLayout(gb)
        r = 0
        for text, key in [(tr("Clear log before action"), "ClearLogBeforeAction"),
                          (tr("Play sound when done"), "PlaySoundWhenDone"),
                          (tr("Debug mode (print more logs)"), "DebugMode")]:
            g.addWidget(self.chk(text, key), r, 0, 1, 3)
            r += 1
        self.row(g, r, tr("Custom temp folder:"), "UseCustomTempDir", "TempDir", "dir")
        r += 1
        self.row(g, r, tr("Custom Java executable:"), "UseCustomJavaExe", "JavaExe", "file")
        r += 1
        g.addWidget(self.chk(tr("Custom JVM arguments:"), "UseCustomJVMArgs"), r, 0)
        g.addWidget(self.line("CustomJVMArgs"), r, 1, 1, 2)
        r += 1
        self.row(g, r, tr("Custom apktool.jar:"), "UseCustomApktool", "ApktoolPath", "file", "apktool (*.jar)")
        r += 1
        g.addWidget(QLabel(tr("Theme:")), r, 0)
        th = QComboBox()
        th.addItems([tr("Light"), tr("Dark")])
        th.setCurrentIndex(int(self.cfg.get("Theme", 1)))
        self.vals["Theme"] = lambda: th.currentIndex()
        g.addWidget(th, r, 1, 1, 2)
        r += 1
        g.addWidget(QLabel(tr("Language:")), r, 0)
        lg = QComboBox()
        codes = list(LANGUAGES.keys())
        lg.addItems([LANGUAGES[c] if c != "Auto" else tr("System language") for c in codes])
        cur = self.cfg.get("Culture", "Auto")
        lg.setCurrentIndex(codes.index(cur) if cur in codes else 0)
        self.vals["Culture"] = lambda: codes[lg.currentIndex()]
        g.addWidget(lg, r, 1, 1, 2)
        g.setColumnStretch(1, 1)
        v.addWidget(gb)
        v.addStretch(1)
        return w

    def _tools(self):
        w = QWidget()
        v = QVBoxLayout(w)
        gb = QGroupBox(tr("Native tools"))
        g = QGridLayout(gb)
        self.row(g, 0, tr("Custom zipalign:"), "UseCustomZipalign", "ZipalignPath", "file")
        self.row(g, 1, tr("Custom adb:"), "UseCustomAdb", "AdbPath", "file")
        g.setColumnStretch(1, 1)
        v.addWidget(gb)
        gb2 = QGroupBox(tr("Official Google tools (optional)"))
        g2 = QVBoxLayout(gb2)
        lbl = QLabel(tr("By default the app uses zipalign/adb from your system (sudo apt install zipalign adb). "
                        "You can instead download the latest official platform-tools and build-tools from Google "
                        "into your user folder:") + "\n" + C.SDK_DIR)
        lbl.setWordWrap(True)
        g2.addWidget(lbl)
        h = QHBoxLayout()
        self.dl_btn = QPushButton(tr("Download / update Google tools"))
        self.dl_btn.clicked.connect(self._download)
        h.addWidget(self.dl_btn)
        rm = QPushButton(tr("Remove"))
        rm.clicked.connect(self._remove_sdk)
        h.addWidget(rm)
        h.addStretch(1)
        g2.addLayout(h)
        self.dl_prog = QProgressBar()
        self.dl_prog.hide()
        g2.addWidget(self.dl_prog)
        self.dl_lbl = QLabel(self._sdk_state())
        self.dl_lbl.setWordWrap(True)
        g2.addWidget(self.dl_lbl)
        v.addWidget(gb2)
        v.addStretch(1)
        return w

    def _sdk_state(self):
        bt = os.path.join(C.SDK_DIR, "build-tools", "zipalign")
        pt = os.path.join(C.SDK_DIR, "platform-tools", "adb")
        st = []
        st.append("build-tools: " + (tr("installed") if os.path.isfile(bt) else tr("not installed")))
        st.append("platform-tools: " + (tr("installed") if os.path.isfile(pt) else tr("not installed")))
        return " · ".join(st)

    def _download(self):
        self.dl_btn.setEnabled(False)
        self.dl_prog.show()
        self.dl_prog.setValue(0)
        self.dl = SdkDownloader()
        self.dl.sig_msg.connect(lambda m: self.dl_lbl.setText(tr("Downloading") + " " + m))
        self.dl.sig_prog.connect(self.dl_prog.setValue)

        def done(ok, msg):
            self.dl_btn.setEnabled(True)
            self.dl_prog.hide()
            self.dl_lbl.setText((tr("Done") + " : " if ok else tr("Error") + " : ") + msg + "\n" + self._sdk_state())
        self.dl.sig_done.connect(done)
        self.dl.start()

    def _remove_sdk(self):
        shutil.rmtree(C.SDK_DIR, ignore_errors=True)
        self.dl_lbl.setText(self._sdk_state())

    def _integration(self):
        w = QWidget()
        v = QVBoxLayout(w)
        gb = QGroupBox(tr("Nemo context menu (Linux Mint)"))
        g = QVBoxLayout(gb)
        lbl = QLabel(tr("Adds right-click actions in Nemo: decompile, compile (folder), sign, zipalign, merge, "
                        "APK info, baksmali, ADB install. No root needed."))
        lbl.setWordWrap(True)
        g.addWidget(lbl)
        if system_actions_installed():
            s = QLabel(tr("Already installed system-wide by the .deb package (you can hide actions in Nemo > Edit > Preferences > Plugins)."))
            s.setWordWrap(True)
            s.setStyleSheet("color: #5fd068;")
            g.addWidget(s)
        h = QHBoxLayout()
        bi = QPushButton(tr("Install context menu"))
        bu = QPushButton(tr("Remove context menu"))

        def inst():
            d = install_nemo_actions()
            QMessageBox.information(self, C.APP_NAME, tr("Context menu installed in {0}").format(d))

        def uninst():
            uninstall_nemo_actions()
            QMessageBox.information(self, C.APP_NAME, tr("Context menu removed"))
        bi.clicked.connect(inst)
        bu.clicked.connect(uninst)
        h.addWidget(bi)
        h.addWidget(bu)
        h.addStretch(1)
        g.addLayout(h)
        g.addWidget(self.chk(tr("Ignore output directory options for context menu"), "IgnoreOutputDirContextMenu"))
        v.addWidget(gb)
        v.addStretch(1)
        return w

    def _ok(self):
        old_lang = self.cfg.get("Culture")
        for k, f in self.vals.items():
            self.cfg[k] = f()
        if self.cfg.get("Culture") != old_lang:
            QMessageBox.information(self, C.APP_NAME, tr("Restart the application to apply the language."))
        self.accept()
