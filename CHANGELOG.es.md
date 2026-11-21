# Changelog

[English](CHANGELOG.md) | [Français](CHANGELOG.fr.md) | **Español** | [Русский](CHANGELOG.ru.md)

Aquí se recogen todos los cambios importantes de **APK Tool GUI Linux**.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/), versiones según [SemVer](https://semver.org/lang/es/).

## [1.0.2] - 2026-11-21

### Añadido
- Interfaz en **español** y **ruso**, además de inglés y francés (se elige en *Ajustes → Idioma*; por defecto, el idioma del sistema).
- Acciones del menú contextual de Nemo y acceso directo del menú traducidos a los 4 idiomas.
- Botones estándar (Aceptar/Cancelar, Sí/No) traducidos; diálogos estándar de Qt traducidos si está instalado el paquete `qt6-translations-l10n` (recomendado por el .deb).
- El cuadro «Acerca de» está traducido y muestra la versión de Apktool incluida.
- README y CHANGELOG disponibles en inglés, francés, español y ruso.

### Cambiado
- **Apktool 3.0.2 → 3.0.3**: corrige los errores «android:* not found», acepta valores de flags vacíos, pool de cadenas optimizado. Opciones de línea de comandos sin cambios.
- **APKEditor 1.4.7 → 1.4.9**: corrige un error al fusionar split APK, gestión de registros «wide» en smali, mejor rendimiento.
- La ventana se ensancha si es necesario para que las 9 pestañas sigan visibles (ruso).
- Build de GitHub Actions: `actions/checkout` y `actions/upload-artifact` pasan a v7 (Node.js 24), lo que elimina el aviso de obsolescencia de Node.js 20.

### Corregido
- La línea «Picked up _JAVA_OPTIONS…» aparecía en lugar de la versión de APKEditor cuando la variable `_JAVA_OPTIONS` está definida (habitual en Linux para el suavizado de fuentes de Java). Ahora estas líneas se filtran en todas partes.
- Botones de acción cortados cuando el texto es largo (pestaña Baksmali en ruso).

## [1.0.1] - 2026-10-28

### Corregido
- **Icono ausente en la pestaña Info APK** en apps recientes (p. ej. AnyDesk) que declaran un icono adaptativo XML (`mipmap-anydpi-v26`) con nombres de recursos acortados u ofuscados.

### Añadido
- Nuevo motor de extracción de iconos (`icon.py`) basado en los ID de recursos (`aapt2 dump resources` / `dump xmltree`):
  - recupera el PNG/WebP original de mayor densidad oculto tras el icono adaptativo;
  - si no, renderiza el icono adaptativo: fondo, primer plano, VectorDrawable (grupos, transformaciones, clip-path), `inset`, `layer-list`, `bitmap`, `shape`, degradados lineales/radiales, máscara con esquinas redondeadas;
  - como último recurso, lee el icono declarado en el AndroidManifest;
  - funciona también cuando los nombres de atributos y recursos están ofuscados (R8, AndResGuard, `--shorten-resource-paths`).
- Conversión WebP → PNG de respaldo con Pillow si falta el plugin WebP de Qt.

### Cambiado
- Nuevas dependencias del paquete: `python3-pyqt6.qtsvg`, `qt6-image-formats-plugins`.

## 1.0.0 - 2026-10-19

*Versión no publicada en GitHub (el repositorio se creó con la 1.0.1).*

Primera versión: port nativo para Linux (Python 3 + PyQt6) de [APKToolGUI](https://github.com/AndnixSH/APKToolGUI) 3.4.0.0 de AndnixSH.

### Añadido
- Las 9 pestañas del original: Principal, Info APK, Decodificación, Build, Firmar, Zipalign, Framework, Baksmali, ADB.
- Herramientas incluidas: Apktool 3.0.2, APKEditor 1.4.7, apksigner, smali/baksmali, aapt2 para Linux.
- Descompilación/compilación con Apktool o APKEditor (proyectos APKEditor detectados automáticamente).
- Fusión de XAPK/APKS/APKM/ZIP y descompilación directa de split APK.
- Cadena compilar → zipalign → firmar → instalar por ADB; APK sin firmar con la firma original.
- Correcciones automáticas de Apktool (manifest, `sparseResources`, `APKTOOL_DUMMY`).
- Firma con clave pem/pk8 o keystore JKS, esquemas v1 a v4; contraseñas transmitidas por variables de entorno.
- Opciones adaptadas a Apktool 3 (`-a`, `--no-assets`, `--only-manifest`, `--debuggable`, etiqueta de framework).
- Pestaña ADB: lista de dispositivos, conexión Wi-Fi `IP:puerto`, instalación (`-i com.android.vending`, `--abi`).
- Acciones del menú contextual de Nemo (Linux Mint) instaladas para todo el sistema.
- Línea de comandos: `--decompile`, `--compile`, `--sign`, `--align`, `--merge`, `--info`, `--baksmali`, `--install`.
- Descarga opcional de los platform-tools / build-tools oficiales de Google desde Ajustes.
- Interfaz en inglés y francés, tema oscuro/claro, arrastrar y soltar en todas partes, registro en colores.

[1.0.2]: https://github.com/rerem8433/apktoolgui-linux/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/rerem8433/apktoolgui-linux/releases/tag/v1.0.1
