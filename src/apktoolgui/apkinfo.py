"""Port d'AaptParser / ApkIconExtractor : infos APK via aapt2 dump badging + apksigner."""
import os
import re
import zipfile

from . import core

SDK_NAMES = {
    1: "1.0", 2: "1.1", 3: "1.5", 4: "1.6", 5: "2.0", 6: "2.0.1", 7: "2.1", 8: "2.2", 9: "2.3",
    10: "2.3.3", 11: "3.0", 12: "3.1", 13: "3.2", 14: "4.0", 15: "4.0.3", 16: "4.1", 17: "4.2",
    18: "4.3", 19: "4.4", 20: "4.4W", 21: "5.0", 22: "5.1", 23: "6.0", 24: "7.0", 25: "7.1",
    26: "8.0", 27: "8.1", 28: "9", 29: "10", 30: "11", 31: "12", 32: "12L", 33: "13", 34: "14",
    35: "15", 36: "16", 37: "17",
}


def sdk_to_android(v):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return v or ""
    name = SDK_NAMES.get(n)
    return "%s (Android %s)" % (n, name) if name else str(n)


def _q(line, key):
    m = re.search(r"%s='([^']*)'" % re.escape(key), line)
    return m.group(1) if m else ""


def _list(line):
    return re.findall(r"'([^']*)'", line.split(":", 1)[1] if ":" in line else "")


def extract_base_apk(path, dest_dir):
    """Pour XAPK/APKS/APKM/ZIP : extrait l'APK de base (sans « config. »)."""
    with zipfile.ZipFile(path) as z:
        apks = [n for n in z.namelist() if n.lower().endswith(".apk")]
        base = None
        for n in apks:
            b = os.path.basename(n)
            if b == "base.apk":
                base = n
                break
        if not base:
            for n in apks:
                if "config." not in os.path.basename(n) and "split_" not in os.path.basename(n):
                    base = n
                    break
        if not base and apks:
            base = max(apks, key=lambda n: z.getinfo(n).file_size)
        if not base:
            return None
        os.makedirs(dest_dir, exist_ok=True)
        out = os.path.join(dest_dir, "base.apk")
        with z.open(base) as src, open(out, "wb") as dst:
            while True:
                b = src.read(1 << 20)
                if not b:
                    break
                dst.write(b)
        return out


def parse(cfg, path, temp_dir):
    info = {"file": path}
    apk = path
    if path.lower().endswith(core.SPLIT_EXTS):
        apk = extract_base_apk(path, os.path.join(temp_dir, "SplitInfo"))
        if not apk:
            raise RuntimeError("Aucun APK trouvé dans " + path)
    aapt2 = core.aapt2_exe(cfg)
    code, out = core.simple_output([aapt2, "dump", "badging", apk], timeout=120)
    info["full"] = out
    perms, locales, screens, dens, native = [], [], [], [], []
    icons = {}
    for line in out.splitlines():
        if line.startswith("package:"):
            info["package"] = _q(line, "name")
            info["versionName"] = _q(line, "versionName")
            info["versionCode"] = _q(line, "versionCode")
        elif line.startswith("uses-permission:") or line.startswith("uses-permission-sdk-23:"):
            p = _q(line, "name")
            if p and p not in perms:
                perms.append(p)
        elif line.startswith("minSdkVersion:") or line.startswith("sdkVersion:"):
            info["minSdk"] = _list(line)[0] if _list(line) else ""
        elif line.startswith("targetSdkVersion:"):
            info["targetSdk"] = _list(line)[0] if _list(line) else ""
        elif line.startswith("application-label:"):
            info["label"] = _list(line)[0] if _list(line) else ""
        elif line.startswith("application:") and not info.get("label"):
            info["label"] = _q(line, "label")
            ic = _q(line, "icon")
            if ic:
                icons.setdefault(0, ic)
        elif line.startswith("application-icon-"):
            m = re.match(r"application-icon-(\d+):'([^']*)'", line)
            if m:
                icons[int(m.group(1))] = m.group(2)
        elif line.startswith("launchable-activity:") or line.startswith("leanback-launchable-activity:"):
            info.setdefault("launch", _q(line, "name"))
        elif line.startswith("supports-screens:"):
            screens = _list(line)
        elif line.startswith("locales:"):
            locales = [l for l in _list(line) if l]
        elif line.startswith("densities:"):
            dens = _list(line)
        elif line.startswith("native-code:") or line.startswith("alt-native-code:"):
            native += [x for x in _list(line) if x not in native]
    if not native:
        try:
            with zipfile.ZipFile(apk) as z:
                for n in z.namelist():
                    m = re.match(r"lib/([^/]+)/", n)
                    if m and m.group(1) not in native:
                        native.append(m.group(1))
        except zipfile.BadZipFile:
            pass
    info.update(perms=perms, locales=locales, screens=screens, densities=dens, native=native)
    info["minSdkText"] = sdk_to_android(info.get("minSdk"))
    info["targetSdkText"] = sdk_to_android(info.get("targetSdk"))
    try:
        from . import icon as _icon
        info["icon"] = _icon.extract_icon(aapt2, apk, icons) or _extract_icon(apk, icons)
    except Exception:  # noqa
        info["icon"] = _extract_icon(apk, icons)
    info["icon"] = _webp_to_png(info["icon"])
    # signature
    j = core.java_exe(cfg)
    if j:
        c2, sig = core.simple_output([j] + core.jvm_args(cfg) + ["-jar", core.tool_jar("apksigner.jar"),
                                      "verify", "--print-certs", "-v", apk], timeout=120)
        info["signature"] = "\n".join(l for l in sig.splitlines() if not l.startswith("Picked up"))
    else:
        info["signature"] = "Java introuvable"
    return info


def _extract_icon(apk, icons):
    """Retourne les octets PNG/WEBP de l'icône la plus grande possible, ou None."""
    try:
        z = zipfile.ZipFile(apk)
    except (zipfile.BadZipFile, OSError):
        return None
    with z:
        names = set(z.namelist())
        order = sorted(icons.items(), key=lambda kv: -(kv[0] if kv[0] not in (0, 65534, 65535) else -1))
        for _, p in order:
            if p in names and p.lower().endswith((".png", ".webp", ".jpg")):
                return z.read(p)
        # icône adaptative (.xml) : chercher un bitmap du même nom
        bases = []
        for _, p in order:
            b = os.path.splitext(os.path.basename(p))[0]
            for cand in (b, b + "_foreground", b.replace("_round", ""), "ic_launcher", "ic_launcher_round"):
                if cand not in bases:
                    bases.append(cand)
        best = None
        for b in bases:
            for n in names:
                if not n.startswith("res/"):
                    continue
                fn = os.path.basename(n)
                if os.path.splitext(fn)[0] == b and fn.lower().endswith((".png", ".webp")):
                    sz = z.getinfo(n).file_size
                    if best is None or sz > best[1]:
                        best = (n, sz)
            if best:
                return z.read(best[0])
    return None


def _webp_to_png(data):
    """Convertit une icône WebP en PNG (au cas où le plugin WebP de Qt est absent)."""
    if not data or data[:4] != b"RIFF":
        return data
    try:
        import io
        from PIL import Image
        out = io.BytesIO()
        Image.open(io.BytesIO(data)).save(out, "PNG")
        return out.getvalue()
    except Exception:  # noqa
        return data
