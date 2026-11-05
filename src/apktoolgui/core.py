"""Logique métier : port des classes Apktool/ApkEditor/Signapk/Zipalign/Adb/Baksmali/Smali/ApkFixer."""
import os
import re
import shlex
import shutil
import subprocess
import zipfile

from . import config as C
from .i18n import tr

SPLIT_EXTS = (".xapk", ".apks", ".apkm", ".zip")
APK_EXTS = (".apk",) + SPLIT_EXTS


class Cancelled(Exception):
    pass


# --------------------------------------------------------------------------- outils
def _which(name):
    return shutil.which(name)


def java_exe(cfg):
    if cfg.get("UseCustomJavaExe") and cfg.get("JavaExe"):
        return cfg["JavaExe"]
    return _which("java")


def jvm_args(cfg):
    if cfg.get("UseCustomJVMArgs") and cfg.get("CustomJVMArgs"):
        return shlex.split(cfg["CustomJVMArgs"])
    return []


def apktool_jar(cfg):
    if cfg.get("UseCustomApktool") and cfg.get("ApktoolPath"):
        return cfg["ApktoolPath"]
    return os.path.join(C.TOOLS_DIR, "apktool.jar")


def tool_jar(name):
    return os.path.join(C.TOOLS_DIR, name)


def _sdk_bin(sub, name):
    p = os.path.join(C.SDK_DIR, sub, name)
    return p if os.path.isfile(p) and os.access(p, os.X_OK) else None


def zipalign_exe(cfg):
    if cfg.get("UseCustomZipalign") and cfg.get("ZipalignPath"):
        return cfg["ZipalignPath"]
    return _sdk_bin("build-tools", "zipalign") or _which("zipalign")


def adb_exe(cfg):
    if cfg.get("UseCustomAdb") and cfg.get("AdbPath"):
        return cfg["AdbPath"]
    return _sdk_bin("platform-tools", "adb") or _which("adb")


def aapt2_exe(cfg=None):
    p = os.path.join(C.TOOLS_DIR, "aapt2")
    if os.path.isfile(p):
        if not os.access(p, os.X_OK):
            try:
                os.chmod(p, 0o755)
            except OSError:
                pass
        return p
    return _sdk_bin("build-tools", "aapt2") or _which("aapt2")


def framework_dir(cfg, use_custom_key="Decode_UseFramework"):
    if cfg.get(use_custom_key) and cfg.get("Framework_FrameDir"):
        return cfg["Framework_FrameDir"]
    os.makedirs(C.FRAMEWORK_DIR, exist_ok=True)
    return C.FRAMEWORK_DIR


def stem_path(path):
    """Équivalent de PathUtils.GetDirectoryNameWithoutExtension : /a/b/x.apk -> /a/b/x"""
    return os.path.splitext(path)[0]


def parse_version(s):
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums[:4]) if nums else (0,)


_version_cache = {}


def simple_output(cmd, timeout=60):
    env = dict(os.environ)
    env.pop("JAVA_TOOL_OPTIONS", None)
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, errors="replace", timeout=timeout, env=env)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def apktool_version(cfg):
    jar = apktool_jar(cfg)
    if jar in _version_cache:
        return _version_cache[jar]
    j = java_exe(cfg)
    v = ""
    if j and os.path.isfile(jar):
        code, out = simple_output([j] + jvm_args(cfg) + ["-jar", jar, "-version"])
        lines = [l for l in out.splitlines() if l.strip() and not l.startswith("Picked up")]
        if code == 0 and lines:
            v = lines[-1].strip()
    _version_cache[jar] = v
    return v


def apkeditor_version(cfg):
    j = java_exe(cfg)
    if not j:
        return ""
    code, out = simple_output([j] + jvm_args(cfg) + ["-jar", tool_jar("APKEditor.jar"), "-version"])
    for l in out.splitlines():
        m = re.search(r"APKEditor\s*-?\s*([\d.]+)", l)
        if m:
            return l.strip()
    return out.strip().splitlines()[0] if out.strip() else ""


def java_version(cfg):
    j = java_exe(cfg)
    if not j:
        return None
    code, out = simple_output([j, "-version"])
    return "\n".join(l for l in out.splitlines() if not l.startswith("Picked up"))


# --------------------------------------------------------------------------- contexte d'exécution
class Ctx:
    """Contexte passé aux opérations ; l'UI fournit les callbacks (thread-safe via signaux Qt)."""

    def __init__(self, cfg, log_cb, status_cb, ignore_output_dirs=False):
        self.cfg = cfg
        self._log = log_cb
        self._status = status_cb
        self.proc = None
        self.cancelled = False
        self.ignore_output_dirs = ignore_output_dirs
        self.result = {}

    # log kinds : info, success, error, warning, raw, debug, header
    def log(self, text, kind="info"):
        if kind == "debug" and not self.cfg.get("DebugMode"):
            return
        self._log(text, kind)

    def header(self, text):
        self._log("=====[ %s ]=====" % text, "header")

    def status(self, text, icon="waiting"):
        self._status(text, icon)

    def cancel(self):
        self.cancelled = True
        p = self.proc
        if p and p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass

    def check(self):
        if self.cancelled:
            raise Cancelled()

    def run(self, cmd, env_extra=None, log_cmd=True, capture=False):
        self.check()
        if not cmd or not cmd[0]:
            raise RuntimeError(tr("Tool not found: {0}").format(cmd[1] if len(cmd) > 1 else "?"))
        if log_cmd:
            self.log("CMD: " + " ".join(shlex.quote(c) for c in cmd), "debug")
        env = dict(os.environ)
        env.pop("JAVA_TOOL_OPTIONS", None)
        if env_extra:
            env.update(env_extra)
        out_lines = []
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, text=True, errors="replace",
                                     env=env, bufsize=1)
        for line in self.proc.stdout:
            line = line.rstrip("\r\n")
            if not line.strip() or line.startswith("Picked up JAVA_TOOL_OPTIONS"):
                continue
            if capture:
                out_lines.append(line)
            else:
                self.log(line, classify(line))
        code = self.proc.wait()
        self.proc = None
        self.check()
        if capture:
            return code, "\n".join(out_lines)
        return code

    def java(self, jar, args, **kw):
        j = java_exe(self.cfg)
        if not j:
            raise RuntimeError(tr("Java not found. Install it with: sudo apt install default-jre"))
        return self.run([j] + jvm_args(self.cfg) + ["-jar", jar] + args, **kw)


def classify(line):
    s = line.lstrip()
    if s.startswith(("W:", "WARNING", "Warning")):
        return "warning"
    if s.startswith(("E:", "ERROR", "Error", "Exception", "brut.", "Caused by")) or "Exception" in s[:60]:
        return "error"
    return "raw"


# --------------------------------------------------------------------------- Apktool
def apktool_decode(ctx, inp, out):
    cfg = ctx.cfg
    ver = parse_version(apktool_version(cfg))
    v3 = ver >= (3,)
    a = ["d"]
    if cfg["Decode_NoSrc"]:
        a.append("-s")
    if cfg["Decode_NoRes"]:
        a.append("-r")
    if cfg["Decode_Force"]:
        a.append("-f")
    if cfg["Decode_KeepBrokenRes"]:
        a.append("--keep-broken-res")
    if cfg["Decode_MatchOriginal"]:
        a.append("--match-original")
    if cfg["Decode_NoDebugInfo"]:
        a.append("--no-debug-info")
    if v3:
        if cfg["Decode_AllSrc"] and not cfg["Decode_NoSrc"]:
            a.append("-a")
        if cfg["Decode_NoAssets"]:
            a.append("--no-assets")
        if cfg["Decode_OnlyManifest"]:
            a.append("--only-manifest")
    else:
        if not cfg["Decode_AllSrc"] and not cfg["Decode_NoSrc"] and (2, 8) <= ver <= (2, 12, 1):
            a.append("--only-main-classes")
    a += ["-p", framework_dir(cfg)]
    if cfg["Decode_UseFrameTag"] and cfg["Decode_FrameTag"]:
        a += ["-t", cfg["Decode_FrameTag"]]
    if cfg["Decode_SetJobs"]:
        a += ["-j", str(cfg["Decode_Jobs"])]
    a += ["-o", out, inp]
    return ctx.java(apktool_jar(cfg), a)


def apktool_build(ctx, folder, out):
    cfg = ctx.cfg
    ver = parse_version(apktool_version(cfg))
    a = ["b"]
    if cfg["Build_ForceAll"]:
        a.append("-f")
    if cfg["Build_UseAapt"] and cfg["Build_AaptPath"]:
        a += ["--aapt" if ver >= (3,) else "-a", cfg["Build_AaptPath"]]
    if cfg["Build_CopyOriginal"]:
        a.append("--copy-original")
    if cfg["Build_NoCrunch"]:
        a.append("--no-crunch")
    if cfg["Build_NetSecConf"]:
        a.append("--net-sec-conf")
    if cfg["Build_Debuggable"]:
        a.append("--debuggable" if ver >= (3,) else "-d")
    a += ["-p", framework_dir(cfg, "Build_UseFramework")]
    if cfg["Build_SetJobs"]:
        a += ["-j", str(cfg["Build_Jobs"])]
    a += ["-o", out, folder]
    return ctx.java(apktool_jar(cfg), a)


def apktool_install_framework(ctx, path):
    cfg = ctx.cfg
    a = ["if"]
    a += ["-p", cfg["Framework_FrameDir"] if cfg["Framework_UseFrameDir"] and cfg["Framework_FrameDir"]
          else framework_dir(cfg)]
    if cfg["InstallFramework_UseTag"] and cfg["InstallFramework_Tag"]:
        a += ["-t", cfg["InstallFramework_Tag"]]
    a.append(path)
    return ctx.java(apktool_jar(cfg), a)


def apktool_clear_framework(ctx):
    cfg = ctx.cfg
    ver = parse_version(apktool_version(cfg))
    fw = framework_dir(cfg)
    if ver >= (3, 0, 1):
        a = ["clean-frameworks", "-a", "-p", fw]
    else:
        a = ["empty-framework-dir", "-f", "-p", fw]
    return ctx.java(apktool_jar(cfg), a)


# --------------------------------------------------------------------------- APKEditor
def apkeditor(ctx, cmd, inp, out):
    return ctx.java(tool_jar("APKEditor.jar"), [cmd, "-i", inp, "-o", out, "-f"])


def is_apkeditor_project(folder):
    if os.path.isfile(os.path.join(folder, "apktool.yml")):
        return False
    return (os.path.isfile(os.path.join(folder, "path-map.json"))
            or os.path.isdir(os.path.join(folder, "resources"))
            or os.path.isdir(os.path.join(folder, "root")))


# --------------------------------------------------------------------------- ApkFixer
def fix_manifest(folder):
    p = os.path.join(folder, "AndroidManifest.xml")
    if not os.path.isfile(p):
        return False
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        t = f.read()
    t = t.replace("\\ ", "\\u003")
    for s in ('android:isSplitRequired="true"', 'android:extractNativeLibs="false"',
              'android:useEmbeddedDex="true"', 'android:manageSpace="true"',
              'android:localeConfig="@xml/locales_config"'):
        t = t.replace(s, "")
    t = t.replace("STAMP_TYPE_DISTRIBUTION_APK", "STAMP_TYPE_STANDALONE_APK")
    t = re.sub(r'\s*android:requiredSplitTypes="[^"]*"', "", t)
    t = re.sub(r'\s*android:splitTypes="[^"]*"', "", t)
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)
    return True


def fix_apktool_yml(folder):
    p = os.path.join(folder, "apktool.yml")
    if not os.path.isfile(p):
        return False
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        t = f.read()
    t = t.replace("sparseResources: true", "sparseResources: false")
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)
    return True


def remove_apktool_dummies(folder):
    d = os.path.join(folder, "res", "values")
    if not os.path.isdir(d):
        return False
    rx = re.compile(r".*APKTOOL_DUMMY.*\n?")
    for root, _, files in os.walk(d):
        for fn in files:
            if not fn.endswith(".xml"):
                continue
            fp = os.path.join(root, fn)
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                t = f.read()
            if "APKTOOL_DUMMY" in t:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(rx.sub("", t))
    return True


def apply_fixes(ctx, folder):
    if fix_manifest(folder):
        ctx.log(tr("Fixed AndroidManifest.xml"))
    if fix_apktool_yml(folder):
        ctx.log(tr("Fixed apktool.yml (sparseResources: false)"))
    if remove_apktool_dummies(folder):
        ctx.log(tr("Removed APKTOOL_DUMMY entries"))


# --------------------------------------------------------------------------- opérations
def _use_out(ctx, key):
    return ctx.cfg.get(key) and not ctx.ignore_output_dirs


def clear_framework(ctx):
    ctx.header(tr("Clearing framework"))
    ctx.status(tr("Clearing framework"))
    code = apktool_clear_framework(ctx)
    ctx.log(tr("Framework cache cleared") if code == 0 else tr("Error clearing framework"),
            "success" if code == 0 else "error")
    return code


def decompile(ctx, inp, use_apkeditor):
    cfg = ctx.cfg
    if inp.lower().endswith(SPLIT_EXTS):
        return merge_and_decompile(ctx, inp, use_apkeditor)
    ctx.header(tr("Decompiling"))
    ctx.status(tr("Decompiling..."))
    ctx.log(tr("Input file: {0}").format(inp))
    out = stem_path(inp)
    if _use_out(ctx, "Decode_UseOutputDir") and cfg["Decode_OutputDir"]:
        out = os.path.join(cfg["Decode_OutputDir"], os.path.basename(stem_path(inp)))
    if not cfg["Decode_Force"] and os.path.exists(out):
        ctx.log(tr("Destination directory ({0}) already exists. Enable \"Force delete destination directory\".").format(out), "error")
        return 1
    if cfg["Framework_ClearBeforeDecode"] and not use_apkeditor:
        ctx.log(tr("Clearing framework"))
        if apktool_clear_framework(ctx) == 0:
            ctx.log(tr("Framework cache cleared"), "success")
    code = apkeditor(ctx, "d", inp, out) if use_apkeditor else apktool_decode(ctx, inp, out)
    if code == 0:
        ctx.result["build_dir"] = out
        ctx.log(tr("Decompiling successfully completed: {0}").format(out), "success")
        if cfg["Decode_FixError"] and not use_apkeditor:
            apply_fixes(ctx, out)
    else:
        ctx.log(tr("Error decompiling"), "error")
    return code


def merge_and_decompile(ctx, inp, use_apkeditor):
    cfg = ctx.cfg
    ctx.header(tr("Merging split APK"))
    ctx.status(tr("Merging split APK..."))
    tmp = C.session_temp(cfg)
    tmp_apk = os.path.join(tmp, "dec.apk")
    out = stem_path(inp)
    if _use_out(ctx, "Decode_UseOutputDir") and cfg["Decode_OutputDir"]:
        out = os.path.join(cfg["Decode_OutputDir"], os.path.basename(stem_path(inp)))
    if cfg["Framework_ClearBeforeDecode"] and not use_apkeditor:
        ctx.log(tr("Clearing framework"))
        if apktool_clear_framework(ctx) == 0:
            ctx.log(tr("Framework cache cleared"), "success")
    ctx.log(tr("Input file: {0}").format(inp))
    ctx.log(tr("Merging with APKEditor..."))
    code = apkeditor(ctx, "m", inp, tmp_apk)
    if code != 0:
        ctx.log(tr("Error merging"), "error")
        return code
    ctx.header(tr("Decompiling"))
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    code = apkeditor(ctx, "d", tmp_apk, out) if use_apkeditor else apktool_decode(ctx, tmp_apk, out)
    if code == 0:
        ctx.result["build_dir"] = out
        ctx.log(tr("Decompiling successfully completed: {0}").format(out), "success")
        if cfg["Decode_FixError"]:
            apply_fixes(ctx, out)
    else:
        ctx.log(tr("Error decompiling"), "error")
    _rm(tmp_apk)
    return code


def merge(ctx, inp):
    ctx.header(tr("Merging split APK"))
    ctx.status(tr("Merging split APK..."))
    ctx.log(tr("Input file: {0}").format(inp))
    out = stem_path(inp) + " merged.apk"
    code = apkeditor(ctx, "m", inp, out)
    if code == 0:
        ctx.result["merged"] = out
        ctx.log(tr("Merged APK saved to: {0}").format(out), "success")
    else:
        ctx.log(tr("Error merging"), "error")
    return code


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass


def build_output_path(cfg, folder, ignore=False):
    folder = folder.rstrip("/")
    out = folder + (" signed.apk" if cfg["Build_SignAfterBuild"] else " compiled.apk")
    if cfg["Build_UseOutputAppPath"] and cfg["Build_OutputAppPath"] and not ignore:
        base = os.path.join(cfg["Build_OutputAppPath"], os.path.basename(folder))
        out = base + (" signed.apk" if cfg["Build_SignAfterBuild"] else ".apk")
    return out


def _zip_replace_meta(apk, meta_dir, stamp=None):
    tmp = apk + ".tmp"
    with zipfile.ZipFile(apk) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for it in zin.infolist():
            if it.filename.startswith("META-INF/") or (stamp and it.filename == "stamp-cert-sha256"):
                continue
            zout.writestr(it, zin.read(it.filename), compress_type=it.compress_type)
        for root, _, files in os.walk(meta_dir):
            for fn in files:
                fp = os.path.join(root, fn)
                arc = "META-INF/" + os.path.relpath(fp, meta_dir).replace(os.sep, "/")
                zout.write(fp, arc, compress_type=zipfile.ZIP_DEFLATED)
        if stamp:
            zout.write(stamp, "stamp-cert-sha256", compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, apk)


def build(ctx, folder, device=None):
    cfg = ctx.cfg
    folder = folder.rstrip("/")
    ctx.header(tr("Compiling"))
    ctx.status(tr("Compiling..."))
    ctx.log(tr("Input folder: {0}").format(folder))
    out = build_output_path(cfg, folder, ctx.ignore_output_dirs)
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    use_ed = is_apkeditor_project(folder)
    if use_ed:
        ctx.log(tr("APKEditor project detected"))
    code = apkeditor(ctx, "b", folder, out) if use_ed else apktool_build(ctx, folder, out)
    if code != 0:
        ctx.log(tr("Error compiling"), "error")
        return code
    ctx.log(tr("Compiling successfully completed: {0}").format(out), "success")
    ctx.result["compiled"] = out

    if cfg["Build_CreateUnsignedApk"]:
        ctx.header(tr("Creating unsigned APK with original signature"))
        meta = os.path.join(folder, "original", "META-INF")
        if os.path.isdir(meta):
            stamp = os.path.join(folder, "original", "stamp-cert-sha256")
            _zip_replace_meta(out, meta, stamp if os.path.isfile(stamp) else None)
            unsigned = os.path.join(os.path.dirname(out), os.path.basename(folder) + " unsigned.apk")
            shutil.copyfile(out, unsigned)
            ctx.log(tr("Copied {0} to {1}").format(out, unsigned))
        else:
            ctx.log(tr("original/META-INF does not exist. Decompile with resources (Copy original) first."), "warning")

    if cfg["Build_ZipalignAfterBuild"]:
        ctx.header(tr("Aligning"))
        ctx.status(tr("Aligning..."))
        if zipalign(ctx, out, out) != 0:
            ctx.log(tr("Error zipaligning"), "error")
            return 1
        ctx.log(tr("Done"))

    if cfg["Build_SignAfterBuild"]:
        ctx.header(tr("Signing"))
        ctx.status(tr("Signing..."))
        if apksign(ctx, out, out) == 0:
            ctx.log(tr("Done"))
            if cfg["Sign_InstallApkAfterSign"]:
                _install_after(ctx, device, out)
        else:
            ctx.log(tr("Error signing"), "error")
            return 1
    return 0


def zipalign(ctx, inp, out):
    cfg = ctx.cfg
    exe = zipalign_exe(cfg)
    if not exe:
        raise RuntimeError(tr("zipalign not found. Install it with: sudo apt install zipalign (or download Google build-tools in Settings)"))
    n = str(cfg["Zipalign_AlignmentInBytes"])
    if cfg["Zipalign_CheckOnly"]:
        a = [exe, "-c"]
        if cfg["Zipalign_PageAlign"]:
            a.append("-p")
        if cfg["Zipalign_Verbose"]:
            a.append("-v")
        return ctx.run(a + [n, inp])
    tmp = stem_path(out) + "_align_temp.apk"
    a = [exe, "-f"]
    if cfg["Zipalign_PageAlign"]:
        a.append("-p")
    if cfg["Zipalign_Verbose"]:
        a.append("-v")
    if cfg["Zipalign_Recompress"]:
        a.append("-z")
    code = ctx.run(a + [n, inp, tmp])
    if code == 0 and os.path.isfile(tmp):
        os.replace(tmp, out)
    else:
        _rm(tmp)
    return code


def align(ctx, inp, device=None):
    cfg = ctx.cfg
    ctx.header(tr("Aligning"))
    ctx.status(tr("Aligning..."))
    ctx.log(tr("Input file: {0}").format(inp))
    out = inp
    if _use_out(ctx, "Zipalign_UseOutputDir") and cfg["Zipalign_OutputDir"]:
        out = os.path.join(cfg["Zipalign_OutputDir"], os.path.basename(inp))
    if not cfg["Zipalign_OverwriteOutputFile"]:
        out = stem_path(out) + " aligned.apk"
    code = zipalign(ctx, inp, out)
    if code != 0:
        ctx.log(tr("Error zipaligning"), "error")
        return code
    if cfg["Zipalign_CheckOnly"]:
        ctx.log(tr("Alignment check passed"), "success")
        return 0
    if cfg["Zipalign_SignAfterZipAlign"]:
        ctx.header(tr("Signing"))
        if apksign(ctx, out, out) == 0:
            ctx.log(tr("Done"))
        else:
            ctx.log(tr("Error signing"), "error")
    ctx.result["aligned"] = out
    ctx.log(tr("Zipaligned file saved to: {0}").format(out), "success")
    return 0


def apksign(ctx, inp, out):
    cfg = ctx.cfg
    env = {}
    a = ["sign"]
    if cfg["Sign_UseKeystoreFile"] and cfg["Sign_KeystoreFilePath"]:
        env["ATG_KS_PASS"] = cfg["Sign_KeystorePassword"] or ""
        env["ATG_KEY_PASS"] = cfg["Sign_KeyPassword"] or cfg["Sign_KeystorePassword"] or ""
        a += ["--ks", cfg["Sign_KeystoreFilePath"], "--ks-pass", "env:ATG_KS_PASS",
              "--key-pass", "env:ATG_KEY_PASS"]
        if cfg["Sign_SetAlias"] and cfg["Sign_Alias"]:
            a += ["--ks-key-alias", cfg["Sign_Alias"]]
    else:
        a += ["--key", cfg["Sign_PrivateKey"], "--cert", cfg["Sign_PublicKey"]]
    for i in (1, 2, 3, 4):
        v = cfg["Sign_Schemev%d" % i]
        if v in (1, 2):
            a += ["--v%d-signing-enabled" % i, "true" if v == 1 else "false"]
    if os.path.abspath(out) != os.path.abspath(inp):
        a += ["--out", out]
    a.append(inp)
    code = ctx.java(tool_jar("apksigner.jar"), a, env_extra=env)
    if code == 0 and cfg["AutoDeleteIdsigFile"]:
        if os.path.exists(out + ".idsig"):
            _rm(out + ".idsig")
            ctx.log(tr("Deleted {0}").format(out + ".idsig"), "debug")
    return code


def sign_output_path(cfg, inp, ignore=False):
    out = inp
    if cfg["Sign_UseOutputDir"] and cfg["Sign_OutputDir"] and not ignore:
        out = os.path.join(cfg["Sign_OutputDir"], os.path.basename(inp))
    if not cfg["Sign_OverwriteInputFile"]:
        out = stem_path(out) + "_signed.apk"
    return out


def sign(ctx, inp, device=None):
    cfg = ctx.cfg
    ctx.header(tr("Signing"))
    ctx.status(tr("Signing..."))
    ctx.log(tr("Input file: {0}").format(inp))
    out = sign_output_path(cfg, inp, ctx.ignore_output_dirs)
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    code = apksign(ctx, inp, out)
    if code == 0:
        ctx.result["signed"] = out
        ctx.log(tr("Signing successfully completed: {0}").format(out), "success")
        if cfg["Sign_InstallApkAfterSign"]:
            _install_after(ctx, device, out)
    else:
        ctx.log(tr("Error signing {0}").format(out), "error")
    return code


def _install_after(ctx, device, apk):
    if not device:
        ctx.log(tr("No device selected in ADB tab, {0} was not installed").format(apk), "error")
        return
    ctx.header(tr("Installing APK"))
    if adb_install(ctx, device, apk) == 0:
        ctx.log(tr("APK installed successfully"), "success")
    else:
        ctx.log(tr("APK installation failed"), "error")


# --------------------------------------------------------------------------- Baksmali / Smali
def baksmali(ctx, dex):
    cfg = ctx.cfg
    ctx.header("Baksmali")
    ctx.status(tr("Decompiling..."))
    out = os.path.join(os.path.dirname(dex), "dexout", os.path.basename(stem_path(dex)))
    if _use_out(ctx, "Baksmali_UseOutputDir") and cfg["Baksmali_OutputDir"]:
        out = os.path.join(cfg["Baksmali_OutputDir"], os.path.basename(stem_path(dex)))
    code = ctx.java(tool_jar("baksmali.jar"), ["d", dex, "-o", out])
    ctx.log(tr("Decompiled to: {0}").format(out) if code == 0 else tr("Error decompiling"),
            "success" if code == 0 else "error")
    return code


def smali(ctx, folder):
    cfg = ctx.cfg
    folder = folder.rstrip("/")
    ctx.header("Smali")
    ctx.status(tr("Compiling..."))
    out = folder + ".dex"
    if _use_out(ctx, "Smali_UseOutputDir") and cfg["Smali_OutputDir"]:
        out = os.path.join(cfg["Smali_OutputDir"], os.path.basename(folder) + ".dex")
    code = ctx.java(tool_jar("smali.jar"), ["a", folder, "-o", out])
    ctx.log(tr("Compiled to: {0}").format(out) if code == 0 else tr("Error compiling"),
            "success" if code == 0 else "error")
    return code


def install_framework(ctx, path):
    ctx.header(tr("Installing framework"))
    ctx.status(tr("Installing framework"))
    code = apktool_install_framework(ctx, path)
    ctx.log(tr("Done") if code == 0 else tr("Error installing framework"),
            "success" if code == 0 else "error")
    return code


# --------------------------------------------------------------------------- ADB
ABIS = ["arm64-v8a", "armeabi-v7a", "x86", "x86_64"]


def _adb(cfg):
    exe = adb_exe(cfg)
    if not exe:
        raise RuntimeError(tr("adb not found. Install it with: sudo apt install adb (or download Google platform-tools in Settings)"))
    return exe


def adb_devices(ctx):
    code, out = ctx.run([_adb(ctx.cfg), "devices", "-l"], capture=True)
    devs = []
    for l in out.splitlines():
        l = l.strip()
        if not l or l.startswith("List of devices") or l.startswith("*"):
            continue
        devs.append(l)
    return devs


def adb_install(ctx, device, apk):
    cfg = ctx.cfg
    serial = device.split()[0]
    a = [_adb(cfg), "-s", serial, "install", "-r"]
    if cfg["Adb_SetVendor"]:
        a += ["-i", "com.android.vending"]
    if cfg["Adb_SetOverrideAbi"]:
        a += ["--abi", ABIS[int(cfg["Adb_OverrideAbi"]) % 4]]
    a.append(apk)
    return ctx.run(a)


def adb_connect(ctx, addr):
    return ctx.run([_adb(ctx.cfg), "connect", addr])


def adb_kill(ctx):
    return ctx.run([_adb(ctx.cfg), "kill-server"])


# --------------------------------------------------------------------------- divers
def find_main_activity_smali(folder):
    man = os.path.join(folder, "AndroidManifest.xml")
    if not os.path.isfile(man):
        return None
    import xml.etree.ElementTree as ET
    A = "{http://schemas.android.com/apk/res/android}"
    try:
        root = ET.parse(man).getroot()
    except ET.ParseError:
        return None
    pkg = root.get("package", "")
    app = root.find("application")
    if app is None:
        return None
    target = None
    for el in list(app):
        if el.tag not in ("activity", "activity-alias"):
            continue
        for f in el.findall("intent-filter"):
            acts = [a.get(A + "name") for a in f.findall("action")]
            cats = [c.get(A + "name") for c in f.findall("category")]
            if "android.intent.action.MAIN" in acts and (
                    "android.intent.category.LAUNCHER" in cats or "android.intent.category.LEANBACK_LAUNCHER" in cats):
                target = el.get(A + "targetActivity") if el.tag == "activity-alias" else el.get(A + "name")
                break
        if target:
            break
    if not target:
        return None
    if target.startswith("."):
        target = pkg + target
    elif "." not in target:
        target = pkg + "." + target
    rel = target.replace(".", "/") + ".smali"
    for d in sorted(os.listdir(folder)):
        if d.startswith("smali"):
            p = os.path.join(folder, d, rel)
            if os.path.isfile(p):
                return p
    return None
