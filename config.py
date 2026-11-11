# Videos MP3 Downloader
# Copyright (c) 2025 Bochi
# Licencia: Apache License 2.0 (ver LICENSE en la raíz del proyecto)

# ---------------------------------------------------------------------
# Descargo de responsabilidad:
# Este software es solo para uso personal y educativo.
# No promueve la violación de derechos de autor ni los Términos de Servicio
# de ningún sitio web, incluyendo YouTube.
# El autor no se hace responsable del uso que los usuarios hagan de este programa.
# ---------------------------------------------------------------------


import os
import platform
import sys

from version import APP_VERSION


def _carpeta_recursos():
    """
    Devuelve la carpeta donde viven ffmpeg/, iconos/ y licenses/.

    - Ejecutando desde el código fuente: la carpeta del proyecto.
    - Ejecutable de PyInstaller (--onefile): la carpeta temporal _MEIPASS.
    - Ejecutable de PyInstaller (--onedir): la carpeta junto al .exe.
    """
    if getattr(sys, 'frozen', False):
        candidatos = []
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidatos.append(meipass)
        candidatos.append(os.path.dirname(os.path.abspath(sys.executable)))
        for candidato in candidatos:
            if (os.path.isdir(os.path.join(candidato, 'iconos'))
                    or os.path.isdir(os.path.join(candidato, 'ffmpeg'))):
                return candidato
        return candidatos[0]
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _carpeta_recursos()

# Carpeta real del programa. En un .exe de PyInstaller, _MEIPASS es una
# carpeta temporal; los ejecutables auxiliares (yt-dlp/Deno) deben vivir
# junto al .exe para sobrevivir a las actualizaciones.
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

TOOLS_DIR = os.path.join(APP_DIR, 'tools')

_EXT = '.exe' if platform.system() == 'Windows' else ''

YTDLP_PATH = os.path.join(TOOLS_DIR, 'yt-dlp' + _EXT)
DENO_PATH = os.path.join(TOOLS_DIR, 'deno' + _EXT)
UPDATE_STATE_PATH = os.path.join(TOOLS_DIR, 'update_state.json')

APP_REPO = 'adrianllorian/DescargaMusicaYouTube'
YTDLP_REPO = 'yt-dlp/yt-dlp'
DENO_REPO = 'denoland/deno'


# Ruta al ejecutable de FFmpeg portable (se puede sobrescribir con la variable
# de entorno FFMPEG_PATH).
FFMPEG_PATH = os.environ.get('FFMPEG_PATH') or os.path.join(
    BASE_DIR, 'ffmpeg', 'bin', 'ffmpeg' + _EXT
)

# Ruta a FFprobe (opcional, se usa solo si está disponible)
FFPROBE_PATH = os.path.join(BASE_DIR, 'ffmpeg', 'bin', 'ffprobe' + _EXT)

# Ruta de la carpeta donde se guardan los íconos
ICONOS_PATH = os.path.join(BASE_DIR, 'iconos')

# Ruta de la carpeta con las licencias y avisos legales
LICENSES_PATH = os.path.join(BASE_DIR, 'licenses')

# Calidades disponibles: etiqueta -> kbps
CALIDADES = {
    "Máxima (320k)": 320,
    "Alta (256k)": 256,
    "Media (128k)": 128,
    "Baja (64k)": 64,
}

# Calidad de audio por defecto
CALIDAD_PREDETERMINADA = "Máxima (320k)"


def ffmpeg_disponible():
    """Indica si el ejecutable de FFmpeg existe en la ruta configurada."""
    return os.path.isfile(FFMPEG_PATH)


def mensaje_ffmpeg_faltante():
    """Mensaje de ayuda cuando no se encuentra FFmpeg."""
    return (
        "No se encontró FFmpeg.\n\n"
        f"Ruta esperada:\n{FFMPEG_PATH}\n\n"
        "Asegúrate de que ffmpeg.exe esté en la carpeta 'ffmpeg/bin/' "
        "junto al programa."
    )
