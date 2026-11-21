"""Interface PyQt6 — clone de MainWindow.xaml (APKToolGUI 3.4.0.0)."""
import html
import os
import shutil
import subprocess
import sys
import time

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QByteArray, QTimer
from PyQt6.QtGui import (QAction, QColor, QDesktopServices, QIcon, QPalette, QPixmap,
                         QTextCursor, QFont, QFontDatabase, QKeySequence)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QSplitter,
                             QPlainTextEdit, QCheckBox, QSpinBox, QComboBox, QGroupBox,
                             QFileDialog, QMessageBox, QListWidget, QScrollArea, QMenu,
                             QStyleFactory, QDialog, QDialogButtonBox, QFrame, QSizePolicy)

from . import config as C
from . import core, apkinfo
from .i18n import tr, set_language

ACCEPT_APK = core.APK_EXTS


def res(name):
    return os.path.join(C.RES_DIR, name)


# =========================================================================== worker
class Worker(QThread):
    sig_log = pyqtSignal(str, str)
    sig_status = pyqtSignal(str, str)
    sig_done = pyqtSignal(int, dict, float)

    def __init__(self, cfg, fn, ignore_output_dirs=False):
        super().__init__()
        self.fn = fn
        self.ctx = core.Ctx(cfg, self.sig_log.emit, self.sig_status.emit, ignore_output_dirs)

    def run(self):
        t0 = time.time()
        code = 1
        try:
            code = self.fn(self.ctx) or 0
        except core.Cancelled:
            self.sig_log.emit(tr("Process cancelled by user"), "warning")
            code = 2
        except Exception as e:  # noqa
            import traceback
            self.sig_log.emit(str(e), "error")
            self.sig_log.emit(traceback.format_exc(), "debug" if not self.ctx.cfg.get("DebugMode") else "error")
            code = 1
        self.sig_done.emit(code, self.ctx.result, time.time() - t0)


class InfoWorker(QThread):
    sig_done = pyqtSignal(object, str)

    def __init__(self, cfg, path):
        super().__init__()
        self.cfg, self.path = cfg, path

    def run(self):
        try:
            self.sig_done.emit(apkinfo.parse(self.cfg, self.path, C.session_temp(self.cfg)), "")
        except Exception as e:  # noqa
            self.sig_done.emit(None, str(e))


# =========================================================================== widgets drag & drop
def _paths_from_event(e):
    if not e.mimeData().hasUrls():
        return []
    return [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]


def _match(paths, kind):
    out = []
    for p in paths:
        if kind == "dir" and os.path.isdir(p):
            out.append(p)
        elif kind == "dex" and os.path.isfile(p) and p.lower().endswith(".dex"):
            out.append(p)
        elif kind == "apk" and os.path.isfile(p) and p.lower().endswith(".apk"):
            out.append(p)
        elif kind == "anyapk" and os.path.isfile(p) and p.lower().endswith(ACCEPT_APK):
            out.append(p)
        elif kind == "split" and os.path.isfile(p) and p.lower().endswith(core.SPLIT_EXTS):
            out.append(p)
        elif kind == "file" and os.path.isfile(p):
            out.append(p)
    return out


class DropMixin:
    drop_kind = None
    on_drop = None

    def setup_drop(self, kind, cb):
        self.drop_kind, self.on_drop = kind, cb
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if self.drop_kind and _match(_paths_from_event(e), self.drop_kind):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dropEvent(self, e):
        m = _match(_paths_from_event(e), self.drop_kind)
        if m and self.on_drop:
            e.acceptProposedAction()
            self.on_drop(m)


class DropLineEdit(DropMixin, QLineEdit):
    pass


class DropButton(DropMixin, QPushButton):
    pass


class ClickLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, e):
        self.clicked.emit()
        super().mousePressEvent(e)


# =========================================================================== thème
def apply_theme(app, dark):
    app.setStyle(QStyleFactory.create("Fusion"))
    p = QPalette()
    if dark:
        bg, base, alt, txt, btn, hl = "#202020", "#2b2b2b", "#323232", "#e6e6e6", "#333333", "#3d6fb6"
        p.setColor(QPalette.ColorRole.Window, QColor(bg))
        p.setColor(QPalette.ColorRole.WindowText, QColor(txt))
        p.setColor(QPalette.ColorRole.Base, QColor(base))
        p.setColor(QPalette.ColorRole.AlternateBase, QColor(alt))
        p.setColor(QPalette.ColorRole.ToolTipBase, QColor(base))
        p.setColor(QPalette.ColorRole.ToolTipText, QColor(txt))
        p.setColor(QPalette.ColorRole.Text, QColor(txt))
        p.setColor(QPalette.ColorRole.Button, QColor(btn))
        p.setColor(QPalette.ColorRole.ButtonText, QColor(txt))
        p.setColor(QPalette.ColorRole.Highlight, QColor(hl))
        p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8a8a8a"))
        p.setColor(QPalette.ColorRole.Link, QColor("#6fa8ff"))
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
            p.setColor(QPalette.ColorGroup.Disabled, role, QColor("#7a7a7a"))
        app.setPalette(p)
        app.setStyleSheet("""
            QPushButton { border: 1px solid #4a4a4a; padding: 4px 10px; background: #333; border-radius: 2px; }
            QPushButton:hover { background: #3e3e3e; border-color: #5a5a5a; }
            QPushButton:pressed { background: #2a2a2a; }
            QPushButton:disabled { color: #6a6a6a; border-color: #3a3a3a; }
            QLineEdit, QComboBox { border: 1px solid #4a4a4a; padding: 2px 4px; background: #2b2b2b; }
            QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #7a7a7a; background: #2b2b2b; border-radius: 2px; }
            QCheckBox::indicator:hover { border-color: #9a9a9a; }
            QCheckBox::indicator:checked { background: #3d6fb6; border-color: #3d6fb6; image: url(CHECK_SVG); }
            QCheckBox::indicator:disabled { border-color: #4a4a4a; }
            QLineEdit:focus { border-color: #3d6fb6; }
            QTabWidget::pane { border: 1px solid #3c3c3c; top: -1px; }
            QTabBar::tab { background: #2a2a2a; border: 1px solid #3c3c3c; padding: 5px 10px; margin-right: 1px; }
            QTabBar::tab:selected { background: #202020; border-bottom-color: #202020; }
            QTabBar::tab:hover { background: #353535; }
            QGroupBox { border: 1px solid #3c3c3c; margin-top: 10px; padding-top: 6px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
            QPlainTextEdit#log { background: #171717; border: 1px solid #3c3c3c; }
            QStatusBar { border-top: 1px solid #3c3c3c; }
            QMenuBar { background: #202020; } QMenuBar::item:selected { background: #3a3a3a; }
            QMenu { background: #2b2b2b; border: 1px solid #444; } QMenu::item:selected { background: #3d6fb6; }
            QListWidget { background: #2b2b2b; border: 1px solid #4a4a4a; }
        """.replace("CHECK_SVG", res("check.svg")))
    else:
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet("QPushButton { padding: 4px 10px; } QPlainTextEdit#log { background: #ffffff; }")


LOG_COLORS_DARK = {"info": "#e6e6e6", "raw": "#d0d0d0", "success": "#5fd068", "error": "#ff6b6b",
                   "warning": "#f0b44c", "debug": "#8a8a8a", "header": "#6fa8ff"}
LOG_COLORS_LIGHT = {"info": "#1e1e1e", "raw": "#333333", "success": "#1a8a2a", "error": "#c62828",
                    "warning": "#b26a00", "debug": "#777777", "header": "#1f5fbf"}


# =========================================================================== fenêtre principale
class MainWindow(QMainWindow):
    def __init__(self, cfg, cli_action=None):
        super().__init__()
        self.cfg = cfg
        self.worker = None
        self.info_worker = None
        self.action_widgets = []
        self.cli_action = cli_action
        self.setWindowTitle("%s - v%s" % (C.APP_NAME, C.APP_VERSION))
        self.setWindowIcon(QIcon(res("android.png")))
        self.resize(660, 720)
        self.setMinimumSize(560, 560)
        self.setAcceptDrops(True)
        self._build_menu()
        self._build_ui()
        self._build_status()
        geo = cfg.get("WindowGeometry")
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))
        st = cfg.get("SplitterState")
        if st:
            self.splitter.restoreState(QByteArray.fromBase64(st.encode()))
        QTimer.singleShot(50, self._startup)

    # ------------------------------------------------------------------ helpers de binding
    def bind_check(self, cb, key, on_change=None):
        cb.setChecked(bool(self.cfg.get(key)))

        def f(v):
            self.cfg[key] = bool(v)
            if on_change:
                on_change()
        cb.toggled.connect(f)
        return cb

    def bind_line(self, le, key):
        le.setText(str(self.cfg.get(key) or ""))
        le.textChanged.connect(lambda t: self.cfg.__setitem__(key, t))
        return le

    def bind_spin(self, sp, key, lo, hi):
        sp.setRange(lo, hi)
        sp.setValue(int(self.cfg.get(key) or lo))
        sp.valueChanged.connect(lambda v: self.cfg.__setitem__(key, v))
        sp.setFixedWidth(80)
        return sp

    def bind_combo(self, cbx, key, items):
        cbx.addItems(items)
        cbx.setCurrentIndex(int(self.cfg.get(key) or 0))
        cbx.currentIndexChanged.connect(lambda i: self.cfg.__setitem__(key, i))
        return cbx

    def act(self, w):
        self.action_widgets.append(w)
        return w

    def browse_btn(self, line, mode, filt="", title=""):
        b = QPushButton("...")
        b.setFixedWidth(36)

        def pick():
            start = line.text() or os.path.expanduser("~")
            if mode == "dir":
                p = QFileDialog.getExistingDirectory(self, title or tr("Select folder"), start)
            elif mode == "save":
                p, _ = QFileDialog.getSaveFileName(self, title or tr("Save as"), start, filt)
            else:
                p, _ = QFileDialog.getOpenFileName(self, title or tr("Select file"),
                                                   os.path.dirname(start) if os.path.isfile(start) else start, filt)
            if p:
                line.setText(p)
        b.clicked.connect(pick)
        return b

    def option_path_row(self, grid, row, check_text, check_key, line_key, mode, filt=""):
        cb = self.bind_check(QCheckBox(check_text), check_key)
        le = self.bind_line(QLineEdit(), line_key)
        grid.addWidget(cb, row, 0)
        grid.addWidget(le, row, 1)
        grid.addWidget(self.browse_btn(le, mode, filt), row, 2)
        return cb, le

    # ------------------------------------------------------------------ menu
    def _build_menu(self):
        mb = self.menuBar()
        m = mb.addMenu(tr("File"))
        m.addAction(tr("New instance"), self.new_instance)
        m.addAction(tr("Save log to file"), self.save_log)
        m.addSeparator()
        m.addAction(tr("Open temp folder"), lambda: self.open_path(C.session_temp(self.cfg)))
        m.addAction(tr("Clear temp folder"), self.clear_temp)
        m.addSeparator()
        a = m.addAction(tr("Exit"), self.close)
        a.setShortcut(QKeySequence("Ctrl+Q"))
        m = mb.addMenu(tr("Settings"))
        self.menu_use_apkeditor = QAction(tr("Use APKEditor for decompiling"), self, checkable=True)
        self.menu_use_apkeditor.setChecked(bool(self.cfg["UseApkeditor"]))
        self.menu_use_apkeditor.toggled.connect(lambda v: self.cfg.__setitem__("UseApkeditor", v))
        m.addAction(self.menu_use_apkeditor)
        m.addAction(tr("Open settings..."), self.open_settings)
        m = mb.addMenu(tr("Help"))
        m.addAction(tr("Report an issue"), lambda: self.url("https://github.com/rerem8433/apktoolgui-linux/issues"))
        m.addAction(tr("Apktool issue tracker"), lambda: self.url("https://github.com/iBotPeaches/Apktool/issues?q=is%3Aissue"))
        m.addAction(tr("Baksmali issue tracker"), lambda: self.url("https://github.com/JesusFreke/smali/issues?q=is%3Aissue"))
        m.addSeparator()
        m.addAction(tr("About"), self.about)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_main(), tr("Main"))
        self.tabs.addTab(self._tab_info(), tr("APK Info"))
        self.tabs.addTab(self._scroll(self._tab_decode()), tr("Decode"))
        self.tabs.addTab(self._scroll(self._tab_build()), tr("Build"))
        self.tabs.addTab(self._scroll(self._tab_sign()), tr("Sign"))
        self.tabs.addTab(self._scroll(self._tab_zipalign()), tr("Zip align"))
        self.tabs.addTab(self._scroll(self._tab_framework()), tr("Framework"))
        self.tabs.addTab(self._scroll(self._tab_baksmali()), "Baksmali")
        self.tabs.addTab(self._tab_adb(), "ADB")
        self.tabs.tabBar().setUsesScrollButtons(True)
        QTimer.singleShot(0, self._fit_tabs)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(20000)
        f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        f.setPointSize(max(9, f.pointSize()))
        self.log_view.setFont(f)
        self.log_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._log_menu)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.tabs)
        self.splitter.addWidget(self.log_view)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setChildrenCollapsible(False)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 0)
        lay.addWidget(self.splitter)
        self.setCentralWidget(w)

    def ask(self, text):
        """Question Oui/Non avec boutons traduits."""
        box = QMessageBox(QMessageBox.Icon.Question, C.APP_NAME, text, parent=self)
        yes = box.addButton(tr("Yes"), QMessageBox.ButtonRole.YesRole)
        box.addButton(tr("No"), QMessageBox.ButtonRole.NoRole)
        box.exec()
        return box.clickedButton() is yes

    def _fit_tabs(self):
        """Largeur mini pour que les 9 onglets restent visibles (langues longues comme le russe)."""
        need = self.tabs.tabBar().sizeHint().width() + 24
        self.setMinimumWidth(max(560, need))
        if self.width() < need:
            self.resize(need, self.height())

    def _scroll(self, w):
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setWidget(w)
        return sa

    def _build_status(self):
        sb = self.statusBar()
        self.status_icon = QLabel()
        self.status_text = ClickLabel(tr("Ready"))
        self.status_text.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_text.clicked.connect(self.prompt_cancel)
        self.status_icon.setPixmap(QPixmap(res("Done.png")).scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio,
                                                                   Qt.TransformationMode.SmoothTransformation))
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(4, 0, 0, 0)
        h.addWidget(self.status_icon)
        h.addWidget(self.status_text)
        h.addStretch(1)
        sb.addWidget(box, 1)
        from PyQt6.QtWidgets import QProgressBar
        self.progress = QProgressBar()
        self.progress.setFixedWidth(170)
        self.progress.setFixedHeight(14)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        sb.addPermanentWidget(self.progress)

    # ------------------------------------------------------------------ onglet Main
    def _main_row(self, lay, label, key, kind, mode, filt, btn_text, action):
        lay.addWidget(QLabel(label))
        h = QHBoxLayout()
        le = DropLineEdit()
        self.bind_line(le, key)
        le.setup_drop(kind, lambda ps: le.setText(ps[0]))
        b = DropButton(btn_text)
        b.setMinimumWidth(130)
        b.setup_drop(kind, lambda ps: (le.setText(ps[0]), action()))
        b.clicked.connect(action)
        self.act(b)
        h.addWidget(le)
        h.addWidget(self.browse_btn(le, mode, filt))
        h.addWidget(b)
        lay.addLayout(h)
        return le, b

    def _tab_main(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(3)
        f_any = tr("APK files") + " (*.apk *.xapk *.apks *.apkm *.zip);;" + tr("All files") + " (*)"
        f_apk = tr("APK files") + " (*.apk);;" + tr("All files") + " (*)"
        f_split = tr("Split APK") + " (*.xapk *.apks *.apkm *.zip);;" + tr("All files") + " (*)"
        self.le_decode, _ = self._main_row(lay, tr("APK/XAPK/APKS/ZIP/APKM File:"), "Decode_InputAppPath", "anyapk",
                                           "file", f_any, tr("Decompile"), self.do_decompile)
        self.le_decode.textChanged.connect(self._decode_input_changed)
        self.le_build, _ = self._main_row(lay, tr("Decompiled APK folder:"), "BuildProjectDir", "dir",
                                          "dir", "", tr("Compile"), self.do_build)
        self.le_align, _ = self._main_row(lay, tr("APK file to align:"), "Zipalign_InputFile", "apk",
                                          "file", f_apk, tr("Align"), self.do_align)
        self.le_sign, _ = self._main_row(lay, tr("APK File to sign:"), "Sign_InputFile", "apk",
                                         "file", f_apk, tr("Sign"), self.do_sign)
        self.le_split, _ = self._main_row(lay, tr("Merge split APK into single APK:"), "SplitApk_InputFile", "split",
                                          "file", f_split, tr("Merge"), self.do_merge)
        g = QGridLayout()
        g.setSpacing(6)
        btns = [
            (tr("Decompile output location"), self.open_decompile_output),
            (tr("Decompiled APK location"), lambda: self.open_parent(self.le_decode.text())),
            (tr("Zipalign APK location"), self.open_align_output),
            (tr("Compile output location"), lambda: self.open_path(self.le_build.text())),
            (tr("Compiled APK location"), self.open_compiled_output),
            (tr("Sign APK location"), self.open_sign_output),
            ("AndroidManifest.xml", lambda: self.open_in_build("AndroidManifest.xml")),
            ("Apktool.yml", lambda: self.open_in_build("apktool.yml")),
            (tr("Main activity smali"), self.open_main_activity),
        ]
        for i, (t, f) in enumerate(btns):
            b = QPushButton(t)
            b.setMinimumHeight(30)
            b.clicked.connect(f)
            g.addWidget(b, i // 3, i % 3)
        lay.addSpacing(6)
        lay.addLayout(g)
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ onglet APK Info
    def _ro(self):
        le = QLineEdit()
        le.setReadOnly(True)
        return le

    def _tab_info(self):
        sub = QTabWidget()
        basic = QWidget()
        v = QVBoxLayout(basic)
        top = QHBoxLayout()
        left = QGridLayout()
        self.i_file = DropLineEdit()
        self.i_file.setReadOnly(True)
        self.i_file.setup_drop("anyapk", lambda ps: self.load_apk_info(ps[0]))
        bsel = QPushButton("...")
        bsel.setFixedWidth(36)
        bsel.clicked.connect(self.pick_info_file)
        left.addWidget(QLabel(tr("File:")), 0, 0)
        hl = QHBoxLayout()
        hl.addWidget(self.i_file)
        hl.addWidget(bsel)
        left.addLayout(hl, 0, 1)
        self.i_app, self.i_pkg = self._ro(), self._ro()
        left.addWidget(QLabel(tr("App name:")), 1, 0)
        left.addWidget(self.i_app, 1, 1)
        left.addWidget(QLabel(tr("Package name:")), 2, 0)
        left.addWidget(self.i_pkg, 2, 1)
        top.addLayout(left, 1)
        self.i_icon = ClickLabel()
        self.i_icon.setFixedSize(92, 92)
        self.i_icon.setFrameShape(QFrame.Shape.Box)
        self.i_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.i_icon.setToolTip(tr("Click to export the icon"))
        self.i_icon.clicked.connect(self.export_icon)
        top.addWidget(self.i_icon)
        v.addLayout(top)
        v.addWidget(QLabel(tr("Links:")))
        lg = QGridLayout()
        self.link_btns = []
        links = [("Play Store", "https://play.google.com/store/apps/details?id={}"),
                 ("ApkCombo", "https://apkcombo.com/a/{}"), ("ApkPure", "https://apkpure.com/a/{}"),
                 ("ApkGk", "https://apkgk.com/{}/download"), ("Apk.support", "https://apk.support/app/{}"),
                 ("Apk Mirror", "https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s={}")]
        for i, (t, u) in enumerate(links):
            b = QPushButton(t)
            b.setEnabled(False)
            b.clicked.connect(lambda _=False, u=u: self.url(u.format(self.i_pkg.text())))
            self.link_btns.append(b)
            lg.addWidget(b, i // 3, i % 3)
        v.addLayout(lg)
        fg = QGridLayout()
        self.i_launch, self.i_ver, self.i_build = self._ro(), self._ro(), self._ro()
        self.i_min, self.i_target, self.i_screen, self.i_arch, self.i_dens = (self._ro() for _ in range(5))
        fg.addWidget(QLabel(tr("Launch activity:")), 0, 0)
        fg.addWidget(self.i_launch, 0, 1, 1, 3)
        fg.addWidget(QLabel(tr("Version:")), 1, 0)
        fg.addWidget(self.i_ver, 1, 1)
        fg.addWidget(QLabel(tr("Build:")), 1, 2)
        fg.addWidget(self.i_build, 1, 3)
        fg.addWidget(QLabel(tr("Min. SDK:")), 2, 0)
        fg.addWidget(self.i_min, 2, 1)
        fg.addWidget(QLabel(tr("Target SDK:")), 2, 2)
        fg.addWidget(self.i_target, 2, 3)
        fg.addWidget(QLabel(tr("Screen sizes:")), 3, 0)
        fg.addWidget(self.i_screen, 3, 1)
        fg.addWidget(QLabel(tr("Architectures:")), 3, 2)
        fg.addWidget(self.i_arch, 3, 3)
        fg.addWidget(QLabel(tr("Densities:")), 4, 0)
        fg.addWidget(self.i_dens, 4, 1, 1, 3)
        v.addLayout(fg)
        v.addWidget(QLabel(tr("Locales:")))
        self.i_locales = QPlainTextEdit()
        self.i_locales.setReadOnly(True)
        self.i_locales.setMaximumHeight(64)
        v.addWidget(self.i_locales)
        v.addWidget(QLabel(tr("Permissions:")))
        self.i_perms = QPlainTextEdit()
        self.i_perms.setReadOnly(True)
        self.i_perms.setMinimumHeight(90)
        v.addWidget(self.i_perms, 1)
        sub.addTab(self._scroll(basic), tr("Basic info"))
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.i_full = QPlainTextEdit()
        self.i_full.setReadOnly(True)
        self.i_full.setFont(mono)
        self.i_full.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        sub.addTab(self.i_full, tr("AAPT dump"))
        self.i_sig = QPlainTextEdit()
        self.i_sig.setReadOnly(True)
        self.i_sig.setFont(mono)
        self.i_sig.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        sub.addTab(self.i_sig, tr("Signature"))
        self._icon_bytes = None
        return sub

    # ------------------------------------------------------------------ onglet Decode
    def _tab_decode(self):
        w = QWidget()
        v = QVBoxLayout(w)
        gb = QGroupBox(tr("Options"))
        g = QGridLayout(gb)
        r = 0
        for text, key in [
            (tr("Do not decode sources. (-s)"), "Decode_NoSrc"),
            (tr("Do not decode resources. (-r)"), "Decode_NoRes"),
            (tr("Force delete destination directory. (-f)"), "Decode_Force"),
            (tr("Keep broken resource. (--keep-broken-res)"), "Decode_KeepBrokenRes"),
            (tr("Keeps files to closest to original as possible. Prevents rebuild. (--match-original)"), "Decode_MatchOriginal"),
            (tr("Decode all sources, including unknown dex files. (-a)"), "Decode_AllSrc"),
            (tr("Do not decode assets. (--no-assets)"), "Decode_NoAssets"),
            (tr("Only decode AndroidManifest.xml. (--only-manifest)"), "Decode_OnlyManifest"),
        ]:
            g.addWidget(self.bind_check(QCheckBox(text), key), r, 0, 1, 3)
            r += 1
        self.option_path_row(g, r, tr("Uses framework files located in:"), "Decode_UseFramework", "Framework_FrameDir", "dir")
        r += 1
        cb = self.bind_check(QCheckBox(tr("Use framework files tagged with:")), "Decode_UseFrameTag")
        g.addWidget(cb, r, 0)
        g.addWidget(self.bind_line(QLineEdit(), "Decode_FrameTag"), r, 1)
        r += 1
        self.option_path_row(g, r, tr("Output directory:"), "Decode_UseOutputDir", "Decode_OutputDir", "dir")
        r += 1
        for text, key in [
            (tr("Fix ApkTool errors after decompile"), "Decode_FixError"),
            (tr("Don't write out debug info (.local, .param, .line, etc.)"), "Decode_NoDebugInfo"),
            (tr("Don't parse APK info when selecting APK for decompiling"), "Decode_DontParseApkInfo"),
        ]:
            g.addWidget(self.bind_check(QCheckBox(text), key), r, 0, 1, 3)
            r += 1
        g.addWidget(self.bind_check(QCheckBox(tr("Set the number of threads to use.")), "Decode_SetJobs"), r, 0)
        g.addWidget(self.bind_spin(QSpinBox(), "Decode_Jobs", 1, 64), r, 1, 1, 2, Qt.AlignmentFlag.AlignRight)
        g.setColumnStretch(1, 1)
        v.addWidget(gb)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ onglet Build
    def _tab_build(self):
        w = QWidget()
        v = QVBoxLayout(w)
        gb = QGroupBox(tr("Options"))
        g = QGridLayout(gb)
        r = 0
        g.addWidget(self.bind_check(QCheckBox(tr("Skip changes detection and build all files. (-f)")), "Build_ForceAll"), r, 0, 1, 3)
        r += 1
        self.option_path_row(g, r, tr("Uses aapt2 located in:"), "Build_UseAapt", "Build_AaptPath", "file")
        r += 1
        self.option_path_row(g, r, tr("Uses framework files located in:"), "Build_UseFramework", "Framework_FrameDir", "dir")
        r += 1
        self.option_path_row(g, r, tr("APK output directory:"), "Build_UseOutputAppPath", "Build_OutputAppPath", "dir")
        r += 1
        for text, key in [
            (tr("Disable crunching of resource files during the build step."), "Build_NoCrunch"),
            (tr("Add a generic Network Security Configuration file in the output APK"), "Build_NetSecConf"),
            (tr("Set android:debuggable to \"true\" in the built APK (--debuggable)"), "Build_Debuggable"),
            (tr("Zipalign after build"), "Build_ZipalignAfterBuild"),
            (tr("Sign after build / zipalign"), "Build_SignAfterBuild"),
            (tr("Create unsigned APK with original signature after build"), "Build_CreateUnsignedApk"),
            (tr("Copy original AndroidManifest.xml and META-INF folder"), "Build_CopyOriginal"),
        ]:
            g.addWidget(self.bind_check(QCheckBox(text), key), r, 0, 1, 3)
            r += 1
        g.addWidget(self.bind_check(QCheckBox(tr("Set the number of threads to use.")), "Build_SetJobs"), r, 0)
        g.addWidget(self.bind_spin(QSpinBox(), "Build_Jobs", 1, 64), r, 1, 1, 2, Qt.AlignmentFlag.AlignRight)
        g.setColumnStretch(1, 1)
        v.addWidget(gb)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ onglet Sign
    def _tab_sign(self):
        w = QWidget()
        v = QVBoxLayout(w)
        gb = QGroupBox(tr("Options"))
        g = QGridLayout(gb)
        note = QLabel(tr("It is strongly recommended that you use your own key, created via Android Studio or other tools"))
        note.setWordWrap(True)
        note.setStyleSheet("color: #9a9a9a;")
        g.addWidget(note, 0, 0, 1, 3)
        pem = self.bind_line(QLineEdit(), "Sign_PublicKey")
        pk8 = self.bind_line(QLineEdit(), "Sign_PrivateKey")
        g.addWidget(QLabel(tr("Public key:")), 1, 0)
        g.addWidget(pem, 1, 1)
        g.addWidget(self.browse_btn(pem, "file", tr("Public key") + " (*.pem *.x509.pem);;" + tr("All files") + " (*)"), 1, 2)
        g.addWidget(QLabel(tr("Private key:")), 2, 0)
        g.addWidget(pk8, 2, 1)
        g.addWidget(self.browse_btn(pk8, "file", tr("Private key") + " (*.pk8);;" + tr("All files") + " (*)"), 2, 2)
        g.addWidget(self.bind_check(QCheckBox(tr("Alias:")), "Sign_SetAlias"), 3, 0)
        g.addWidget(self.bind_line(QLineEdit(), "Sign_Alias"), 3, 1, 1, 2)
        g.addWidget(self.bind_check(QCheckBox(tr("Use keystore")), "Sign_UseKeystoreFile"), 4, 0, 1, 3)
        ks = self.bind_line(QLineEdit(), "Sign_KeystoreFilePath")
        g.addWidget(QLabel(tr("keystore/jks file:")), 5, 0)
        g.addWidget(ks, 5, 1)
        g.addWidget(self.browse_btn(ks, "file", "Keystore (*.jks *.keystore *.bks *.p12);;" + tr("All files") + " (*)"), 5, 2)
        for row, (lbl, key) in enumerate([(tr("Password:"), "Sign_KeystorePassword"),
                                          (tr("Private key password:"), "Sign_KeyPassword")], start=6):
            le = self.bind_line(QLineEdit(), key)
            le.setEchoMode(QLineEdit.EchoMode.Password)
            g.addWidget(QLabel(lbl), row, 0)
            g.addWidget(le, row, 1, 1, 2)
        self.option_path_row(g, 8, tr("APK output directory:"), "Sign_UseOutputDir", "Sign_OutputDir", "dir")
        sg = QGridLayout()
        opts = [tr("Default"), "True", "False"]
        for i in range(4):
            sg.addWidget(QLabel(tr("Scheme v%d:") % (i + 1)), i // 2, (i % 2) * 2)
            sg.addWidget(self.bind_combo(QComboBox(), "Sign_Schemev%d" % (i + 1), opts), i // 2, (i % 2) * 2 + 1)
        g.addLayout(sg, 9, 0, 1, 3)
        r = 10
        for text, key in [(tr("Auto delete idsig file"), "AutoDeleteIdsigFile"),
                          (tr("Overwrite input file"), "Sign_OverwriteInputFile"),
                          (tr("Install APK after signing (Make sure the device is selected in ADB tab first)"), "Sign_InstallApkAfterSign")]:
            g.addWidget(self.bind_check(QCheckBox(text), key), r, 0, 1, 3)
            r += 1
        g.setColumnStretch(1, 1)
        v.addWidget(gb)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ onglet Zipalign
    def _tab_zipalign(self):
        w = QWidget()
        v = QVBoxLayout(w)
        gb = QGroupBox(tr("Options"))
        g = QGridLayout(gb)
        g.addWidget(QLabel(tr("Alignment in bytes, e.g. '4' provides 32-bit alignment")), 0, 0)
        g.addWidget(self.bind_spin(QSpinBox(), "Zipalign_AlignmentInBytes", 1, 65536), 0, 1, 1, 2, Qt.AlignmentFlag.AlignRight)
        r = 1
        for text, key in [(tr("Check alignment only (does not modify file)"), "Zipalign_CheckOnly"),
                          (tr("Verbose output"), "Zipalign_Verbose"),
                          (tr("Recompress using Zopfli"), "Zipalign_Recompress"),
                          (tr("Page-align uncompressed .so files (-p)"), "Zipalign_PageAlign"),
                          (tr("Overwrite existing output file"), "Zipalign_OverwriteOutputFile"),
                          (tr("Sign after zipalign"), "Zipalign_SignAfterZipAlign")]:
            g.addWidget(self.bind_check(QCheckBox(text), key), r, 0, 1, 3)
            r += 1
        self.option_path_row(g, r, tr("APK output directory:"), "Zipalign_UseOutputDir", "Zipalign_OutputDir", "dir")
        g.setColumnStretch(1, 1)
        v.addWidget(gb)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ onglet Framework
    def _tab_framework(self):
        w = QWidget()
        v = QVBoxLayout(w)
        gb = QGroupBox(tr("Install Framework"))
        g = QGridLayout(gb)
        self.option_path_row(g, 0, tr("Stores framework files into:"), "Framework_UseFrameDir", "Framework_FrameDir", "dir")
        g.addWidget(self.bind_check(QCheckBox(tr("Tag frameworks using:")), "InstallFramework_UseTag"), 1, 0)
        g.addWidget(self.bind_line(QLineEdit(), "InstallFramework_Tag"), 1, 1, 1, 2)
        h = QHBoxLayout()
        fw = DropLineEdit()
        self.bind_line(fw, "InstallFramework_InputFramePath")
        fw.setup_drop("file", lambda ps: fw.setText(ps[0]))
        fw.setPlaceholderText("framework-res.apk")
        h.addWidget(fw)
        h.addWidget(self.browse_btn(fw, "file", tr("APK files") + " (*.apk *.jar);;" + tr("All files") + " (*)"))
        b = self.act(QPushButton(tr("Install")))
        b.clicked.connect(lambda: self.run_op(lambda c: core.install_framework(c, fw.text()), need=fw.text(), kind="file"))
        h.addWidget(b)
        g.addLayout(h, 2, 0, 1, 3)
        g.setColumnStretch(1, 1)
        v.addWidget(gb)
        gb2 = QGroupBox(tr("Options"))
        g2 = QGridLayout(gb2)
        g2.addWidget(self.bind_check(QCheckBox(tr("Clear framework before decompiling")), "Framework_ClearBeforeDecode"), 0, 0)
        b = self.act(QPushButton(tr("Clear framework")))
        b.clicked.connect(lambda: self.run_op(core.clear_framework))
        g2.addWidget(b, 0, 1)
        b2 = QPushButton(tr("Open framework folder"))
        b2.clicked.connect(lambda: self.open_path(core.framework_dir(self.cfg)))
        g2.addWidget(b2, 1, 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(gb2)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ onglet Baksmali
    def _tab_baksmali(self):
        w = QWidget()
        v = QVBoxLayout(w)
        for title, use_key, out_key, in_key, label, kind, mode, filt, btn, fn in [
            ("Baksmali", "Baksmali_UseOutputDir", "Baksmali_OutputDir", "Baksmali_InputDexFile",
             tr("Dex to decompile:"), "dex", "file", "DEX (*.dex);;" + tr("All files") + " (*)", tr("Decompile"), core.baksmali),
            ("Smali", "Smali_UseOutputDir", "Smali_OutputDir", "Smali_InputDir",
             tr("Smali folder to compile:"), "dir", "dir", "", tr("Compile"), core.smali),
        ]:
            gb = QGroupBox(title)
            g = QGridLayout(gb)
            self.option_path_row(g, 0, tr("Folder output directory:") if title == "Baksmali" else tr("Dex output directory:"),
                                 use_key, out_key, "dir")
            g.addWidget(QLabel(label), 1, 0, 1, 3)
            le = DropLineEdit()
            self.bind_line(le, in_key)
            le.setup_drop(kind, lambda ps, le=le: le.setText(ps[0]))
            h = QHBoxLayout()
            h.addWidget(le)
            h.addWidget(self.browse_btn(le, mode, filt))
            b = self.act(QPushButton(btn))
            b.setMinimumWidth(110)
            b.clicked.connect(lambda _=False, le=le, fn=fn, kind=kind:
                              self.run_op(lambda c: fn(c, le.text()), need=le.text(), kind="dir" if kind == "dir" else "file"))
            h.addWidget(b)
            g.addLayout(h, 2, 0, 1, 3)
            g.setColumnStretch(1, 1)
            v.addWidget(gb)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ onglet ADB
    def _tab_adb(self):
        w = QWidget()
        v = QVBoxLayout(w)
        h = QHBoxLayout()
        h.addWidget(QLabel(tr("Selected device: ")))
        self.sel_device = QLabel("")
        self.sel_device.setStyleSheet("font-weight: bold;")
        h.addWidget(self.sel_device, 1)
        v.addLayout(h)
        v.addWidget(self.bind_check(QCheckBox(tr("Set vendor to Play Store (com.android.vending)")), "Adb_SetVendor"))
        h = QHBoxLayout()
        h.addWidget(self.bind_check(QCheckBox(tr("Override platform's default ABI: ")), "Adb_SetOverrideAbi"))
        cb = self.bind_combo(QComboBox(), "Adb_OverrideAbi", core.ABIS)
        cb.setFixedWidth(150)
        h.addWidget(cb)
        h.addStretch(1)
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel(tr("Selected APK: ")))
        self.adb_apk = DropLineEdit()
        self.bind_line(self.adb_apk, "Adb_SelectedApkPath")
        self.adb_apk.setup_drop("apk", lambda ps: self.adb_apk.setText(ps[0]))
        h.addWidget(self.adb_apk)
        h.addWidget(self.browse_btn(self.adb_apk, "file", tr("APK files") + " (*.apk);;" + tr("All files") + " (*)"))
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel(tr("Connect (IP:port):")))
        self.adb_addr = self.bind_line(QLineEdit(), "Adb_ConnectAddress")
        self.adb_addr.setPlaceholderText("192.168.1.50:5555")
        h.addWidget(self.adb_addr)
        b = self.act(QPushButton(tr("Connect")))
        b.clicked.connect(self.adb_connect)
        h.addWidget(b)
        v.addLayout(h)
        h = QHBoxLayout()
        b = self.act(QPushButton(tr("Kill adb process")))
        b.clicked.connect(lambda: self.run_op(core.adb_kill, status_title=tr("Killing adb")))
        h.addWidget(b)
        b = self.act(QPushButton(tr("Refresh")))
        b.clicked.connect(self.refresh_devices)
        h.addWidget(b)
        h.addStretch(1)
        b = self.act(DropButton(tr("Install APK")))
        b.setup_drop("apk", lambda ps: (self.adb_apk.setText(ps[0]), self.adb_install()))
        b.clicked.connect(self.adb_install)
        h.addWidget(b)
        v.addLayout(h)
        self.devices = QListWidget()
        self.devices.currentTextChanged.connect(self.sel_device.setText)
        v.addWidget(self.devices, 1)
        return w

    # ================================================================== log
    def log(self, text, kind="info"):
        if kind == "debug" and not self.cfg.get("DebugMode"):
            return
        colors = LOG_COLORS_DARK if self.cfg.get("Theme", 1) == 1 else LOG_COLORS_LIGHT
        col = colors.get(kind, colors["info"])
        esc = html.escape(text).replace("\n", "<br>")
        if kind in ("info", "success", "error", "warning", "header"):
            esc = "[%s] %s" % (time.strftime("%H:%M:%S"), esc)
        self.log_view.appendHtml('<span style="color:%s; white-space:pre-wrap;">%s</span>' % (col, esc))
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _log_menu(self, pos):
        m = QMenu(self)
        m.addAction(tr("Copy"), self.log_view.copy)
        m.addAction(tr("Copy all"), lambda: QApplication.clipboard().setText(self.log_view.toPlainText()))
        m.addSeparator()
        m.addAction(tr("Clear log"), self.log_view.clear)
        m.exec(self.log_view.mapToGlobal(pos))

    def save_log(self):
        p, _ = QFileDialog.getSaveFileName(self, tr("Save log to file"),
                                           os.path.expanduser("~/apktoolgui-log-%s.txt" % time.strftime("%Y%m%d-%H%M%S")),
                                           "Text (*.txt)")
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.log_view.toPlainText())

    def set_status(self, text, icon="waiting"):
        self.status_text.setText(text)
        ic = {"waiting": "waiting.png", "done": "Done.png", "error": "Error.png", "warning": "warning.png"}.get(icon, "info.png")
        self.status_icon.setPixmap(QPixmap(res(ic)).scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio,
                                                           Qt.TransformationMode.SmoothTransformation))

    # ================================================================== démarrage
    def _startup(self):
        cfg = self.cfg
        jv = core.java_version(cfg)
        if jv:
            self.log(jv.splitlines()[0])
            for l in jv.splitlines()[1:]:
                self.log(l, "raw")
        else:
            self.log(tr("Java not found. Install it with: sudo apt install default-jre"), "error")
        if jv:
            v = core.apktool_version(cfg)
            self.log(tr("Apktool version {0}").format(v) if v else tr("Apktool not found or not working"),
                     "info" if v else "error")
            ev = core.apkeditor_version(cfg)
            if ev:
                self.log(ev)
        for name, fn, pkg in (("zipalign", core.zipalign_exe, "zipalign"), ("adb", core.adb_exe, "adb")):
            p = fn(cfg)
            if p:
                self.log("%s: %s" % (name, p), "debug")
            else:
                self.log(tr("{0} not found: sudo apt install {1}").format(name, pkg), "warning")
        self.log(tr("Drag & drop is supported"))
        self.log(tr("Temp directory: \"{0}\"").format(C.session_temp(cfg)))
        self.set_status(tr("Ready"), "done")
        if core.adb_exe(cfg):
            self.refresh_devices(quiet=True)
        if self.cli_action:
            QTimer.singleShot(300, self._run_cli)

    def _run_cli(self):
        act, path = self.cli_action
        path = os.path.abspath(path)
        ign = bool(self.cfg.get("IgnoreOutputDirContextMenu"))
        if act == "decompile":
            self.le_decode.setText(path)
            self.do_decompile(ignore=ign)
        elif act == "compile":
            self.le_build.setText(path)
            self.do_build(ignore=ign)
        elif act == "sign":
            self.le_sign.setText(path)
            self.do_sign(ignore=ign)
        elif act == "align":
            self.le_align.setText(path)
            self.do_align(ignore=ign)
        elif act == "merge":
            self.le_split.setText(path)
            self.do_merge()
        elif act == "info":
            self.load_apk_info(path)
        elif act == "baksmali":
            self.run_op(lambda c: core.baksmali(c, path), ignore=ign)
        elif act == "install":
            self.tabs.setCurrentIndex(8)
            self.adb_apk.setText(path)

    # ================================================================== exécution
    def busy(self):
        return self.worker is not None and self.worker.isRunning()

    def run_op(self, fn, need=None, kind=None, ignore=False, status_title=None, on_result=None, quiet=False):
        if self.busy():
            self.log(tr("A process is already running"), "warning")
            return
        if need is not None:
            if not need or (kind == "file" and not os.path.isfile(need)) or (kind == "dir" and not os.path.isdir(need)):
                self.log(tr("File or folder not found: {0}").format(need or "-"), "error")
                self.set_status(tr("Error"), "error")
                return
        if self.cfg.get("ClearLogBeforeAction"):
            self.log_view.clear()
        self.cfg.save()
        self.worker = Worker(self.cfg, fn, ignore)
        self.worker.sig_log.connect(self.log)
        self.worker.sig_status.connect(self.set_status)
        self.worker.sig_done.connect(lambda code, r, dt: self._done(code, r, dt, on_result, quiet))
        for w in self.action_widgets:
            w.setEnabled(False)
        self.progress.show()
        self.set_status(status_title or tr("Running... (click here to cancel)"))
        self.worker.start()

    def _done(self, code, result, dt, on_result, quiet=False):
        for w in self.action_widgets:
            w.setEnabled(True)
        self.progress.hide()
        if result.get("build_dir"):
            self.le_build.setText(result["build_dir"])
        if result.get("signed") and result["signed"].endswith(".apk"):
            self.adb_apk.setText(result["signed"])
        if code == 0:
            self.set_status(tr("Done") + ("" if quiet else "  (%.1fs)" % dt), "done")
            if not quiet:
                self.log(tr("Done in {0:.1f} s").format(dt), "success")
        elif code == 2:
            self.set_status(tr("Cancelled"), "warning")
        else:
            self.set_status(tr("Error"), "error")
        if self.cfg.get("PlaySoundWhenDone") and not quiet:
            self._beep()
        if on_result:
            on_result(code, result)

    def _beep(self):
        for snd in ("/usr/share/sounds/freedesktop/stereo/complete.oga",
                    "/usr/share/sounds/LinuxMint/stereo/dialog-information.ogg"):
            if os.path.isfile(snd) and shutil.which("paplay"):
                subprocess.Popen(["paplay", snd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
        QApplication.beep()

    def prompt_cancel(self):
        if not self.busy():
            return
        if self.ask(tr("Do you want to cancel the current process?")):
            self.worker.ctx.cancel()

    # ================================================================== actions principales
    def do_decompile(self, ignore=False):
        p = self.le_decode.text().strip()
        use_ed = self.menu_use_apkeditor.isChecked()
        self.run_op(lambda c: core.decompile(c, p, use_ed), need=p, kind="file", ignore=ignore)

    def do_build(self, ignore=False):
        p = self.le_build.text().strip()
        dev = self.selected_device()
        self.run_op(lambda c: core.build(c, p, dev), need=p, kind="dir", ignore=ignore)

    def do_align(self, ignore=False):
        p = self.le_align.text().strip()
        self.run_op(lambda c: core.align(c, p), need=p, kind="file", ignore=ignore)

    def do_sign(self, ignore=False):
        p = self.le_sign.text().strip()
        dev = self.selected_device()
        self.run_op(lambda c: core.sign(c, p, dev), need=p, kind="file", ignore=ignore)

    def do_merge(self):
        p = self.le_split.text().strip()
        self.run_op(lambda c: core.merge(c, p), need=p, kind="file")

    def _decode_input_changed(self, t):
        if t and os.path.isfile(t) and t.lower().endswith(ACCEPT_APK) and not self.cfg.get("Decode_DontParseApkInfo"):
            self.load_apk_info(t, switch=False)

    # ================================================================== APK info
    def pick_info_file(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("Select file"), os.path.expanduser("~"),
                                           tr("APK files") + " (*.apk *.xapk *.apks *.apkm *.zip)")
        if p:
            self.load_apk_info(p)

    def load_apk_info(self, path, switch=True):
        if self.info_worker and self.info_worker.isRunning():
            return
        self.i_file.setText(path)
        if switch:
            self.tabs.setCurrentIndex(1)
        self.log(tr("Parsing APK info: {0}").format(path), "debug")
        self.info_worker = InfoWorker(self.cfg, path)
        self.info_worker.sig_done.connect(self._info_done)
        self.info_worker.start()

    def _info_done(self, info, err):
        if err or not info:
            self.log(tr("Cannot read APK info: {0}").format(err), "error")
            return
        self.i_app.setText(info.get("label", ""))
        self.i_pkg.setText(info.get("package", ""))
        self.i_launch.setText(info.get("launch", ""))
        self.i_ver.setText(info.get("versionName", ""))
        self.i_build.setText(info.get("versionCode", ""))
        self.i_min.setText(info.get("minSdkText", ""))
        self.i_target.setText(info.get("targetSdkText", ""))
        self.i_screen.setText(", ".join(info.get("screens", [])))
        self.i_arch.setText(", ".join(info.get("native", [])))
        self.i_dens.setText(", ".join(info.get("densities", [])))
        self.i_locales.setPlainText(", ".join(info.get("locales", [])))
        self.i_perms.setPlainText("\n".join(info.get("perms", [])))
        self.i_full.setPlainText(info.get("full", ""))
        self.i_sig.setPlainText(info.get("signature", ""))
        for b in self.link_btns:
            b.setEnabled(bool(info.get("package")))
        self._icon_bytes = info.get("icon")
        pm = QPixmap()
        if self._icon_bytes and pm.loadFromData(self._icon_bytes):
            self.i_icon.setPixmap(pm.scaled(88, 88, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        else:
            self.i_icon.setPixmap(QPixmap(res("android.png")).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                                                     Qt.TransformationMode.SmoothTransformation))

    def export_icon(self):
        if not self._icon_bytes:
            return
        ext = ".webp" if self._icon_bytes[:4] == b"RIFF" else ".png"
        name = (self.i_pkg.text() or "icon") + ext
        p, _ = QFileDialog.getSaveFileName(self, tr("Save icon"), os.path.join(os.path.expanduser("~"), name))
        if p:
            with open(p, "wb") as f:
                f.write(self._icon_bytes)
            self.log(tr("Icon saved to: {0}").format(p), "success")

    # ================================================================== ADB
    def selected_device(self):
        return self.sel_device.text().strip()

    def refresh_devices(self, quiet=False):
        def fn(c):
            c.log(tr("Getting devices..."))
            c.result["devices"] = core.adb_devices(c)
            n = len(c.result["devices"])
            c.log(tr("{0} devices found").format(n) if n else tr("No devices found"))
            return 0

        def res_cb(code, r):
            cur = self.selected_device()
            self.devices.clear()
            for d in r.get("devices", []):
                self.devices.addItem(d)
            items = [self.devices.item(i).text() for i in range(self.devices.count())]
            for i, t in enumerate(items):
                if cur and t.split()[0] == cur.split()[0]:
                    self.devices.setCurrentRow(i)
                    break
            else:
                if len(items) == 1:
                    self.devices.setCurrentRow(0)
                elif not items:
                    self.sel_device.setText("")
        if quiet:
            clear = self.cfg.get("ClearLogBeforeAction")
            self.cfg["ClearLogBeforeAction"] = False
            self.run_op(fn, on_result=res_cb, status_title=tr("Getting devices..."), quiet=True)
            self.cfg["ClearLogBeforeAction"] = clear
        else:
            self.run_op(fn, on_result=res_cb, status_title=tr("Getting devices..."))

    def adb_install(self):
        apk = self.adb_apk.text().strip()
        dev = self.selected_device()
        if not dev:
            self.log(tr("No device selected in ADB tab, {0} was not installed").format(apk), "error")
            return

        def fn(c):
            c.header(tr("Installing APK"))
            c.log(tr("Installing {0}").format(apk))
            code = core.adb_install(c, dev, apk)
            c.log(tr("APK installed successfully") if code == 0 else tr("APK installation failed"),
                  "success" if code == 0 else "error")
            return code
        self.run_op(fn, need=apk, kind="file", status_title=tr("Installing APK"))

    def adb_connect(self):
        addr = self.adb_addr.text().strip()
        if not addr:
            return
        if ":" not in addr:
            addr += ":5555"
        self.run_op(lambda c: core.adb_connect(c, addr), on_result=lambda *_: QTimer.singleShot(200, self.refresh_devices))

    # ================================================================== ouverture dossiers/fichiers
    def url(self, u):
        QDesktopServices.openUrl(QUrl(u))

    def open_path(self, p):
        if p and os.path.exists(p):
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        else:
            self.log(tr("File or folder not found: {0}").format(p or "-"), "error")

    def open_parent(self, p):
        """Ouvre le dossier et sélectionne le fichier si nemo/nautilus est dispo."""
        if p and os.path.exists(p):
            for fm in ("nemo", "nautilus", "caja", "dolphin"):
                if shutil.which(fm):
                    arg = ["--select", p] if fm in ("nautilus", "dolphin") else [p]
                    if fm == "nemo":
                        arg = [p]
                    subprocess.Popen([fm] + arg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
            self.open_path(os.path.dirname(p))
        else:
            self.log(tr("File or folder not found: {0}").format(p or "-"), "error")

    def open_decompile_output(self):
        p = self.le_decode.text()
        out = core.stem_path(p) if p else ""
        if self.cfg["Decode_UseOutputDir"] and self.cfg["Decode_OutputDir"]:
            out = os.path.join(self.cfg["Decode_OutputDir"], os.path.basename(out))
        self.open_path(out)

    def open_compiled_output(self):
        b = self.le_build.text().strip()
        if not b:
            return self.log(tr("File or folder not found: {0}").format("-"), "error")
        self.open_parent(core.build_output_path(self.cfg, b))

    def open_sign_output(self):
        p = self.le_sign.text().strip()
        if p:
            self.open_parent(core.sign_output_path(self.cfg, p))

    def open_align_output(self):
        p = self.le_align.text().strip()
        if not p:
            return
        out = p
        if self.cfg["Zipalign_UseOutputDir"] and self.cfg["Zipalign_OutputDir"]:
            out = os.path.join(self.cfg["Zipalign_OutputDir"], os.path.basename(p))
        if not self.cfg["Zipalign_OverwriteOutputFile"]:
            out = core.stem_path(out) + " aligned.apk"
        self.open_parent(out)

    def open_in_build(self, name):
        self.open_path(os.path.join(self.le_build.text().strip(), name))

    def open_main_activity(self):
        d = self.le_build.text().strip()
        p = core.find_main_activity_smali(d) if d else None
        if p:
            self.open_path(p)
        else:
            self.log(tr("Main activity smali not found"), "error")

    # ================================================================== menu fichier
    def new_instance(self):
        exe = shutil.which(C.APP_ID)
        cmd = [exe] if exe else [sys.executable, "-m", "apktoolgui"]
        subprocess.Popen(cmd, start_new_session=True)

    def clear_temp(self):
        root = C.temp_root(self.cfg)
        cur = C.session_temp(self.cfg)
        n = 0
        for d in os.listdir(root):
            p = os.path.join(root, d)
            if p == cur:
                for x in os.listdir(cur):
                    xp = os.path.join(cur, x)
                    shutil.rmtree(xp, ignore_errors=True) if os.path.isdir(xp) else os.remove(xp)
                continue
            shutil.rmtree(p, ignore_errors=True)
            n += 1
        self.log(tr("Temp folder cleared"), "success")

    def open_settings(self):
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, self.cfg)
        if dlg.exec():
            self.cfg.save()
            core._version_cache.clear()
            apply_theme(QApplication.instance(), self.cfg.get("Theme", 1) == 1)

    def about(self):
        link = "<a href='https://github.com/AndnixSH/APKToolGUI'>APKToolGUI</a>"
        tools = "Apktool %s (iBotPeaches), APKEditor (REAndroid), smali/baksmali, apksigner, zipalign, adb (AOSP)" % (
            core.apktool_version(self.cfg) or "?")
        QMessageBox.about(self, tr("About"), (
            "<h3>%s v%s</h3><p>%s</p><p>%s</p><p>%s</p><p>%s</p>"
        ) % (C.APP_NAME, C.APP_VERSION,
             tr("GUI for apktool, APKEditor, apksigner, zipalign, baksmali and adb."),
             tr("Linux fork (Python/PyQt6) of {0} {1} by AndnixSH (public domain / Unlicense).").format(link, C.UPSTREAM_VERSION),
             tr("Linux port: {0}").format("<b>ParadoxXx Squad</b>"),
             tr("Tools: {0}").format(tools)))

    # ================================================================== DnD fenêtre
    def dragEnterEvent(self, e):
        if _paths_from_event(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        ps = _paths_from_event(e)
        if not ps:
            return
        p = ps[0]
        idx = self.tabs.currentIndex()
        if os.path.isdir(p):
            self.le_build.setText(p)
        elif p.lower().endswith(".dex"):
            self.tabs.setCurrentIndex(7)
        elif p.lower().endswith(ACCEPT_APK):
            if idx == 1:
                self.load_apk_info(p)
            elif idx == 8 and p.lower().endswith(".apk"):
                self.adb_apk.setText(p)
            else:
                self.le_decode.setText(p)
        e.acceptProposedAction()

    def closeEvent(self, e):
        if self.busy():
            if not self.ask(tr("A process is running. Quit anyway?")):
                e.ignore()
                return
            self.worker.ctx.cancel()
            self.worker.wait(3000)
        self.cfg["WindowGeometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.cfg["SplitterState"] = bytes(self.splitter.saveState().toBase64()).decode()
        self.cfg.save()
        C.cleanup_session_temp()
        e.accept()


def _install_qt_translator(app):
    """Boutons/dialogues standard de Qt dans la langue choisie (paquet qt6-translations-l10n)."""
    from PyQt6.QtCore import QTranslator, QLibraryInfo
    from .i18n import current
    lang = current()
    if lang == "en":
        return
    paths = [QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath), "/usr/share/qt6/translations"]
    tr_ = QTranslator(app)
    for p in paths:
        if tr_.load("qtbase_" + lang, p):
            app.installTranslator(tr_)
            app._qt_translator = tr_
            return


def main(argv=None):
    import argparse
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog=C.APP_ID, description=C.APP_NAME)
    g = ap.add_mutually_exclusive_group()
    for a in ("decompile", "compile", "sign", "align", "merge", "info", "baksmali", "install"):
        g.add_argument("--" + a, metavar="PATH")
    ap.add_argument("path", nargs="?", help="APK/dossier à ouvrir")
    ns = ap.parse_args(argv)
    cli = None
    for a in ("decompile", "compile", "sign", "align", "merge", "info", "baksmali", "install"):
        if getattr(ns, a):
            cli = (a, getattr(ns, a))
    if not cli and ns.path:
        p = ns.path
        cli = ("compile", p) if os.path.isdir(p) else ("info", p)

    cfg = C.Config()
    set_language(cfg.get("Culture", "Auto"))
    QApplication.setApplicationName(C.APP_NAME)
    QApplication.setDesktopFileName(C.APP_ID)
    app = QApplication(sys.argv[:1])
    _install_qt_translator(app)
    apply_theme(app, cfg.get("Theme", 1) == 1)
    w = MainWindow(cfg, cli)
    w.show()
    return app.exec()
