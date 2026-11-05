"""Extraction d'icône d'APK : raster direct, résolution par ID de ressource, rendu des icônes
adaptatives / VectorDrawable (fond + premier plan + inset + layer-list + dégradés).

Tout passe par aapt2 (dump resources / dump xmltree) et les ID d'attributs Android, donc ça
marche aussi quand les noms de ressources et d'attributs sont obfusqués (R8, AndResGuard...)."""
import re
import zipfile

from . import core

RASTER = (".png", ".webp", ".jpg", ".jpeg")

# ID d'attributs android:*
A_ICON, A_ROUNDICON = 0x01010002, 0x0101052c
A_DRAWABLE, A_SRC = 0x01010199, 0x01010119
A_WIDTH, A_HEIGHT = 0x01010159, 0x01010155
A_VPW, A_VPH = 0x01010402, 0x01010403
A_FILL, A_PATH, A_STROKE, A_STROKEW = 0x01010404, 0x01010405, 0x01010406, 0x01010407
A_FILLALPHA, A_STROKEALPHA, A_FILLTYPE, A_ALPHA = 0x010104cc, 0x010104cb, 0x0101051e, 0x0101031f
A_TX, A_TY, A_SX, A_SY, A_ROT, A_PX, A_PY = 0x0101045a, 0x0101045b, 0x01010324, 0x01010325, 0x01010326, 0x010101b5, 0x010101b6
A_INSET, A_IL, A_IR, A_IT, A_IB = 0x010104b5, 0x010101b7, 0x010101b8, 0x010101b9, 0x010101ba
A_LEFT, A_TOP, A_RIGHT, A_BOTTOM = 0x010101ad, 0x010101ae, 0x010101af, 0x010101b0
A_COLOR = 0x010101a5
A_GSTART, A_GEND, A_GCENTER, A_GTYPE, A_GANGLE = 0x0101019d, 0x0101019e, 0x0101020b, 0x010101a1, 0x010101a0
A_GSX, A_GSY, A_GEX, A_GEY, A_GCX, A_GCY, A_GRAD = 0x01010510, 0x01010511, 0x01010512, 0x01010513, 0x010101a2, 0x010101a3, 0x010101a4
A_OFFSET = 0x01010514
A_TINT = 0x01010121


# --------------------------------------------------------------------------- aapt2
class ResTable:
    def __init__(self, aapt2, apk):
        self.aapt2, self.apk = aapt2, apk
        self.entries = {}   # id -> [(config, value)]
        self.by_file = {}   # path -> id
        code, out = core.simple_output([aapt2, "dump", "resources", apk], timeout=180)
        cur = None
        for line in out.splitlines():
            m = re.match(r"\s*resource (0x[0-9a-f]{8})\s", line)
            if m:
                cur = int(m.group(1), 16)
                self.entries[cur] = []
                continue
            if cur is None:
                continue
            m = re.match(r"\s+\(([^)]*)\)\s+(.*)$", line)
            if m and not line.lstrip().startswith("resource"):
                cfg, val = m.group(1), m.group(2).strip()
                self.entries[cur].append((cfg, val))
                fm = re.match(r"\(file\)\s+(\S+)", val)
                if fm:
                    self.by_file[fm.group(1)] = cur
        self._xml_cache = {}

    def files(self, rid):
        out = []
        for cfg, val in self.entries.get(rid, []):
            fm = re.match(r"\(file\)\s+(\S+)", val)
            if fm:
                out.append((cfg, fm.group(1)))
        return out

    def best_value(self, rid, depth=0):
        """Valeur la plus pertinente : config par défaut, sinon la plus haute densité."""
        vals = self.entries.get(rid, [])
        if not vals or depth > 8:
            return None
        def score(cv):
            c = cv[0]
            s = 0
            if "night" in c:
                s -= 100
            for i, d in enumerate(("ldpi", "mdpi", "tvdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi", "anydpi")):
                if d in c:
                    s += i + 1
            if c == "":
                s += 5
            return s
        cfg, val = max(vals, key=score)
        m = re.match(r"@(0x[0-9a-f]{8})", val)
        if m:
            return self.best_value(int(m.group(1), 16), depth + 1)
        return val

    def xmltree(self, path):
        if path not in self._xml_cache:
            code, out = core.simple_output([self.aapt2, "dump", "xmltree", "--file", path, self.apk], timeout=60)
            self._xml_cache[path] = parse_xmltree(out) if code == 0 else None
        return self._xml_cache[path]


class XNode:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag):
        self.tag, self.attrs, self.children = tag, {}, []

    def get(self, aid, default=None):
        return self.attrs.get(aid, default)


def parse_xmltree(out):
    root = XNode("#root")
    stack = [(-1, root)]
    for line in out.splitlines():
        ind = len(line) - len(line.lstrip())
        s = line.strip()
        if s.startswith("E: "):
            tag = s[3:].split(" (line=")[0].split(":")[-1]
            node = XNode(tag)
            while stack and stack[-1][0] >= ind:
                stack.pop()
            stack[-1][1].children.append(node)
            stack.append((ind, node))
        elif s.startswith("A: "):
            m = re.match(r"A: .*?\((0x[0-9a-f]{8})\)=(.*)$", s)
            if not m:
                continue
            val = m.group(2)
            raw = re.match(r'^"(.*)" \(Raw: ".*"\)$', val)
            if raw:
                val = raw.group(1)
            elif val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            while stack and stack[-1][0] >= ind:
                stack.pop()
            if stack:
                stack[-1][1].attrs[int(m.group(1), 16)] = val
    return root.children[0] if root.children else None


# --------------------------------------------------------------------------- valeurs
def num(v, default=0.0):
    if v is None:
        return default
    m = re.match(r"(-?[\d.]+(?:e-?\d+)?)", str(v))
    return float(m.group(1)) if m else default


def parse_color(v):
    """'#aarrggbb' / '#rrggbb' / '#rgb' -> (r, g, b, a) floats 0..1"""
    if not v or not v.startswith("#"):
        return None
    h = v[1:]
    if len(h) == 3:
        h = "ff" + "".join(c * 2 for c in h)
    elif len(h) == 4:
        h = "".join(c * 2 for c in h)
    elif len(h) == 6:
        h = "ff" + h
    try:
        a, r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
    except ValueError:
        return None
    return r, g, b, a / 255.0


# --------------------------------------------------------------------------- rendu
class Renderer:
    def __init__(self, rt, zf):
        self.rt, self.zf = rt, zf
        from PyQt6.QtGui import QImage, QPainter, QColor  # noqa
        self.depth = 0

    # résout une valeur d'attribut (@ref, #couleur) -> ('color', rgba) | ('file', path) | None
    def resolve(self, v):
        if v is None:
            return None
        if v.startswith("#"):
            c = parse_color(v)
            return ("color", c) if c else None
        m = re.match(r"@(0x[0-9a-f]{8})", v)
        if m:
            rid = int(m.group(1), 16)
            files = self.rt.files(rid)
            if files:
                return ("file", pick_file(files))
            bv = self.rt.best_value(rid)
            if bv:
                return self.resolve(bv)
        return None

    def color_of(self, v):
        """Couleur simple (gère aussi les selector/color-state-list : 1er item)."""
        r = self.resolve(v)
        if not r:
            return None
        if r[0] == "color":
            return r[1]
        if r[1].endswith(".xml"):
            node = self.rt.xmltree(r[1])
            if node is not None and node.tag == "selector":
                for it in node.children:
                    c = self.color_of(it.get(A_COLOR))
                    if c:
                        return c
        return None

    def draw(self, painter, value_or_node, rect):
        """Dessine un drawable (ref/couleur/fichier ou noeud XML) dans rect (QRectF)."""
        from PyQt6.QtGui import QColor, QImage
        self.depth += 1
        try:
            if self.depth > 12:
                return
            node = None
            if isinstance(value_or_node, XNode):
                node = value_or_node
            else:
                r = self.resolve(value_or_node)
                if not r:
                    return
                if r[0] == "color":
                    rr, g, b, a = r[1]
                    painter.fillRect(rect, QColor(rr, g, b, int(a * 255)))
                    return
                path = r[1]
                if path.lower().endswith(RASTER):
                    img = QImage()
                    if img.loadFromData(self.zf.read(path)):
                        painter.drawImage(rect, img)
                    return
                node = self.rt.xmltree(path)
            if node is None:
                return
            t = node.tag
            if t == "vector":
                self.draw_vector(painter, node, rect)
            elif t == "inset":
                from PyQt6.QtCore import QRectF

                def frac(v):
                    if not v:
                        return 0.0
                    return num(v) if "%" in v else num(v) / 108.0  # aapt2 affiche les fractions brutes (20% -> 0.2%)
                il = it = ir = ib = frac(node.get(A_INSET))
                il = frac(node.get(A_IL)) if node.get(A_IL) else il
                it = frac(node.get(A_IT)) if node.get(A_IT) else it
                ir = frac(node.get(A_IR)) if node.get(A_IR) else ir
                ib = frac(node.get(A_IB)) if node.get(A_IB) else ib
                r2 = QRectF(rect.x() + rect.width() * il, rect.y() + rect.height() * it,
                            rect.width() * (1 - il - ir), rect.height() * (1 - it - ib))
                child = node.get(A_DRAWABLE)
                if child:
                    self.draw(painter, child, r2)
                elif node.children:
                    self.draw(painter, node.children[0], r2)
            elif t == "layer-list":
                from PyQt6.QtCore import QRectF
                for it in node.children:
                    if it.tag != "item":
                        continue
                    k = rect.width() / 108.0
                    l, tp, rg, bt = (num(it.get(a)) * k for a in (A_LEFT, A_TOP, A_RIGHT, A_BOTTOM))
                    r2 = QRectF(rect.x() + l, rect.y() + tp, rect.width() - l - rg, rect.height() - tp - bt)
                    if it.get(A_DRAWABLE):
                        self.draw(painter, it.get(A_DRAWABLE), r2)
                    elif it.children:
                        self.draw(painter, it.children[0], r2)
            elif t in ("bitmap", "nine-patch"):
                self.draw(painter, node.get(A_SRC), rect)
            elif t == "shape":
                for ch in node.children:
                    if ch.tag == "solid":
                        c = self.color_of(ch.get(A_COLOR))
                        if c:
                            painter.fillRect(rect, QColor(c[0], c[1], c[2], int(c[3] * 255)))
            elif t == "color":
                c = self.color_of(node.get(A_COLOR))
                if c:
                    painter.fillRect(rect, QColor(c[0], c[1], c[2], int(c[3] * 255)))
            elif t == "adaptive-icon":
                for ch in node.children:
                    if ch.tag in ("background", "foreground"):
                        if ch.get(A_DRAWABLE):
                            self.draw(painter, ch.get(A_DRAWABLE), rect)
                        elif ch.children:
                            self.draw(painter, ch.children[0], rect)
            elif t == "selector" or t == "level-list" or t == "state-list":
                for it in node.children:
                    if it.get(A_DRAWABLE):
                        self.draw(painter, it.get(A_DRAWABLE), rect)
                        break
        finally:
            self.depth -= 1

    # ------------------------------------------------------------------ VectorDrawable -> SVG
    def draw_vector(self, painter, node, rect):
        from PyQt6.QtCore import QByteArray
        try:
            from PyQt6.QtSvg import QSvgRenderer
        except ImportError:
            return
        vw = num(node.get(A_VPW), 24) or 24
        vh = num(node.get(A_VPH), 24) or 24
        self._defs, self._gid = [], 0
        tint = self.color_of(node.get(A_TINT)) if node.get(A_TINT) else None
        body = "".join(self._svg_children(node, tint))
        alpha = num(node.get(A_ALPHA), 1.0)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g" width="%g" height="%g">'
               '<defs>%s</defs><g opacity="%g">%s</g></svg>') % (vw, vh, vw, vh, "".join(self._defs), alpha, body)
        r = QSvgRenderer(QByteArray(svg.encode()))
        if r.isValid():
            r.render(painter, rect)

    def _paint(self, v, alpha, tint):
        """Retourne (svg_paint, opacity)."""
        if v is None:
            return "none", 1
        if tint:
            return "rgb(%d,%d,%d)" % tint[:3], tint[3] * alpha
        res = self.resolve(v)
        if not res:
            return "none", 1
        if res[0] == "color":
            r, g, b, a = res[1]
            return "rgb(%d,%d,%d)" % (r, g, b), a * alpha
        node = self.rt.xmltree(res[1]) if res[1].endswith(".xml") else None
        if node is not None and node.tag == "gradient":
            return self._gradient(node), alpha
        if node is not None and node.tag == "selector":
            c = self.color_of(v)
            if c:
                return "rgb(%d,%d,%d)" % c[:3], c[3] * alpha
        return "none", 1

    def _gradient(self, g):
        self._gid += 1
        gid = "g%d" % self._gid
        stops = []
        items = [it for it in g.children if it.tag == "item"]
        if items:
            for it in items:
                c = self.color_of(it.get(A_COLOR)) or (0, 0, 0, 1)
                stops.append((num(it.get(A_OFFSET)), c))
        else:
            for off, aid in ((0, A_GSTART), (0.5, A_GCENTER), (1, A_GEND)):
                c = self.color_of(g.get(aid)) if g.get(aid) else None
                if c:
                    stops.append((off, c))
        st = "".join('<stop offset="%g" stop-color="rgb(%d,%d,%d)" stop-opacity="%g"/>' % (o, c[0], c[1], c[2], c[3])
                     for o, c in stops)
        gtype = g.get(A_GTYPE, "0")
        if gtype in ("1", "radial"):
            self._defs.append('<radialGradient id="%s" gradientUnits="userSpaceOnUse" cx="%g" cy="%g" r="%g">%s</radialGradient>'
                              % (gid, num(g.get(A_GCX)), num(g.get(A_GCY)), num(g.get(A_GRAD), 1), st))
        else:
            self._defs.append('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%g" y1="%g" x2="%g" y2="%g">%s</linearGradient>'
                              % (gid, num(g.get(A_GSX)), num(g.get(A_GSY)), num(g.get(A_GEX)), num(g.get(A_GEY)), st))
        return "url(#%s)" % gid

    def _svg_children(self, node, tint):
        out = []
        clip = None
        for ch in node.children:
            if ch.tag == "clip-path" and ch.get(A_PATH):
                self._gid += 1
                clip = "c%d" % self._gid
                self._defs.append('<clipPath id="%s"><path d="%s"/></clipPath>' % (clip, _esc(ch.get(A_PATH))))
            elif ch.tag == "group":
                tx, ty = num(ch.get(A_TX)), num(ch.get(A_TY))
                sx, sy = num(ch.get(A_SX), 1), num(ch.get(A_SY), 1)
                rot, px, py = num(ch.get(A_ROT)), num(ch.get(A_PX)), num(ch.get(A_PY))
                tr = "translate(%g %g) translate(%g %g) rotate(%g) scale(%g %g) translate(%g %g)" % (
                    tx, ty, px, py, rot, sx, sy, -px, -py)
                inner = "".join(self._svg_children(ch, tint))
                out.append('<g transform="%s"%s>%s</g>' % (tr, ' clip-path="url(#%s)"' % clip if clip else "", inner))
            elif ch.tag == "path" and ch.get(A_PATH):
                fill, fo = self._paint(ch.get(A_FILL), num(ch.get(A_FILLALPHA), 1), tint)
                stroke, so = self._paint(ch.get(A_STROKE), num(ch.get(A_STROKEALPHA), 1), tint)
                rule = "evenodd" if ch.get(A_FILLTYPE) in ("1", "evenOdd") else "nonzero"
                out.append('<path d="%s" fill="%s" fill-opacity="%g" fill-rule="%s" stroke="%s" stroke-opacity="%g" stroke-width="%g"%s/>'
                           % (_esc(ch.get(A_PATH)), fill, fo, rule, stroke, so, num(ch.get(A_STROKEW)),
                              ' clip-path="url(#%s)"' % clip if clip else ""))
        return out


def _esc(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


DENS = ["ldpi", "mdpi", "tvdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"]


def _dens_rank(cfg):
    for i in range(len(DENS) - 1, -1, -1):
        if re.search(r"(^|-)%s(-|$)" % DENS[i], cfg):
            return i + 1
    return 0


def pick_file(files):
    """Parmi [(config, path)] : raster haute densité d'abord, sinon xml (anydpi / défaut)."""
    files = [f for f in files if "night" not in f[0]] or files
    rasters = [f for f in files if f[1].lower().endswith(RASTER)]
    if rasters:
        return max(rasters, key=lambda f: _dens_rank(f[0]))[1]
    xmls = sorted(files, key=lambda f: ("anydpi" not in f[0], -_dens_rank(f[0])))
    return xmls[0][1]


def _to_png(img):
    from PyQt6.QtCore import QBuffer, QIODevice
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def render_xml_icon(rt, zf, path, size=192):
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QImage, QPainter, QPainterPath
    node = rt.xmltree(path)
    if node is None:
        return None
    adaptive = node.tag == "adaptive-icon"
    full = int(size * 108 / 72) if adaptive else size
    img = QImage(full, full, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    Renderer(rt, zf).draw(p, node, QRectF(0, 0, full, full))
    p.end()
    if adaptive:
        off = (full - size) / 2
        out = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(Qt.GlobalColor.transparent)
        q = QPainter(out)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
        q.setClipPath(clip)
        q.drawImage(QRectF(-off, -off, full, full), img)
        q.end()
        img = out
    # image vide ? (rien de dessiné)
    if all(img.pixelColor(x, y).alpha() == 0 for x in range(0, img.width(), 8) for y in range(0, img.height(), 8)):
        return None
    return _to_png(img)


def _manifest_icon_ids(rt):
    node = rt.xmltree("AndroidManifest.xml")
    ids = []
    if node is None:
        return ids
    for ch in node.children:
        if ch.tag == "application":
            for aid in (A_ICON, A_ROUNDICON):
                v = ch.get(aid, "")
                m = re.match(r"@(0x[0-9a-f]{8})", v)
                if m:
                    ids.append(int(m.group(1), 16))
    return ids


def extract_icon(aapt2, apk, badging_icons):
    """badging_icons : {densité: chemin} issus de « aapt2 dump badging »."""
    try:
        zf = zipfile.ZipFile(apk)
    except (zipfile.BadZipFile, OSError):
        return None
    with zf:
        names = set(zf.namelist())
        order = [p for _, p in sorted(badging_icons.items(),
                                      key=lambda kv: -(kv[0] if kv[0] not in (0, 65534, 65535) else -1))]
        # 1) raster direct
        for p in order:
            if p in names and p.lower().endswith(RASTER):
                return zf.read(p)
        rt = ResTable(aapt2, apk)
        # 2) même ressource, autre config (ex. PNG xxxhdpi derrière un mipmap-anydpi-v26 adaptatif)
        rids = []
        for p in order:
            rid = rt.by_file.get(p)
            if rid is not None and rid not in rids:
                rids.append(rid)
        for rid in _manifest_icon_ids(rt):
            if rid not in rids:
                rids.append(rid)
        for rid in rids:
            files = [f for f in rt.files(rid) if f[1] in names]
            rasters = [f for f in files if f[1].lower().endswith(RASTER)]
            if rasters:
                return zf.read(max(rasters, key=lambda f: _dens_rank(f[0]))[1])
        # 3) rendu de l'XML (adaptive-icon / vector / layer-list...)
        xml_paths = [p for p in order if p.endswith(".xml")]
        for rid in rids:
            for cfg, p in sorted(rt.files(rid), key=lambda f: ("anydpi" not in f[0], -_dens_rank(f[0]))):
                if p.endswith(".xml") and p not in xml_paths:
                    xml_paths.append(p)
        for p in xml_paths:
            try:
                png = render_xml_icon(rt, zf, p)
            except Exception:  # noqa
                png = None
            if png:
                return png
    return None
