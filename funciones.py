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
import re
import shutil
import subprocess
import time
from io import BytesIO
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
import yt_dlp
from PIL import Image
from yt_dlp.utils import DownloadCancelled

from config import CALIDADES, FFMPEG_PATH


try:  # Pillow >= 9
    _LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow antiguo
    _LANCZOS = Image.LANCZOS

_EXTENSIONES_TEMPORALES = (
    '.part', '.ytdl', '.tmp', '.temp',
    '.webm', '.m4a', '.opus', '.ogg', '.mp4', '.aac', '.wav',
)

_RE_ID = re.compile(r'[\w-]{11}')
_RE_ESQUEMA = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://')
_RE_HOST_YOUTUBE = re.compile(
    r'^(?:(?:www|m|music)\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)$',
    re.IGNORECASE,
)


# ----------------------------------------------------------------------
# Utilidades de URL
# ----------------------------------------------------------------------

def limpiar_url(url):
    """
    Normaliza un enlace de YouTube para quedarse solo con el identificador
    del video. Si el enlace no es de YouTube, lo devuelve tal cual (con
    esquema https:// si faltaba).
    """
    url = (url or '').strip()
    if not url:
        return ''
    if not _RE_ESQUEMA.match(url):
        url = 'https://' + url.lstrip('/')

    parsed = urlparse(url)
    host = (parsed.netloc or '').split(':')[0].lower()
    if host.startswith('www.'):
        host = host[4:]
    if host.startswith('m.'):
        host = host[2:]

    if host == 'youtu.be':
        video_id = parsed.path.strip('/').split('/')[0]
        if _RE_ID.fullmatch(video_id):
            return f'https://www.youtube.com/watch?v={video_id}'

    if host in ('youtube.com', 'music.youtube.com', 'youtube-nocookie.com'):
        query = parse_qs(parsed.query)
        if 'v' in query and _RE_ID.fullmatch(query['v'][0]):
            return f'https://www.youtube.com/watch?v={query["v"][0]}'
        coincidencia = re.match(r'^/(?:shorts|live|embed)/([\w-]{11})', parsed.path)
        if coincidencia:
            return f'https://www.youtube.com/watch?v={coincidencia.group(1)}'

    # Enlaces que no son de YouTube: se conservan sin parámetros de seguimiento
    query = {
        clave: valores
        for clave, valores in parse_qs(parsed.query).items()
        if not clave.lower().startswith('utm_')
    }
    return urlunparse((
        parsed.scheme, parsed.netloc, parsed.path, '',
        urlencode(query, doseq=True), '',
    ))


def es_url_valida(url):
    """Comprueba que el enlace sea un video individual de YouTube."""
    normalizada = limpiar_url(url)
    parsed = urlparse(normalizada)
    host = (parsed.netloc or '').split(':')[0].lower()
    if not _RE_HOST_YOUTUBE.match(host):
        return False
    if host.endswith('youtu.be'):
        return bool(_RE_ID.fullmatch(parsed.path.strip('/').split('/')[0]))
    return (
        parsed.path == '/watch'
        and bool(_RE_ID.fullmatch(parse_qs(parsed.query).get('v', [''])[0]))
    )


# ----------------------------------------------------------------------
# Opciones comunes de yt-dlp
# ----------------------------------------------------------------------

def _opciones_base(ffmpeg_path=None):
    return {
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'noplaylist': True,
        'nocheckcertificate': False,
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'ffmpeg_location': ffmpeg_path or FFMPEG_PATH,
    }


def _titulo_legible(info):
    titulo = (info or {}).get('title') or 'Sin título'
    return re.sub(r'\s+', ' ', str(titulo)).strip()


def obtener_info_video(url):
    """
    Obtiene el título y la URL de la miniatura de un video sin descargarlo.
    Lanza una excepción con un mensaje claro si el enlace no es válido.
    """
    url = limpiar_url(url)
    if not es_url_valida(url):
        raise ValueError('El enlace no es un video válido de YouTube.')

    with yt_dlp.YoutubeDL(_opciones_base()) as ydl:
        info = ydl.extract_info(url, download=False, process=False)

    if not info:
        raise ValueError('YouTube no devolvió información para ese enlace.')

    if info.get('_type') == 'playlist' or 'entries' in info:
        entradas = [e for e in (info.get('entries') or []) if e]
        if len(entradas) != 1:
            raise ValueError(
                'El enlace es una lista de reproducción. '
                'Usa el enlace de un solo video.'
            )
        with yt_dlp.YoutubeDL(_opciones_base()) as ydl:
            info = ydl.extract_info(entradas[0].get('url') or url, download=False)

    return _titulo_legible(info), info.get('thumbnail')


# ----------------------------------------------------------------------
# Descarga
# ----------------------------------------------------------------------

def _kbps(calidad):
    """Acepta 'Alta (256k)', '256' o 256 y devuelve un entero de kbps."""
    if isinstance(calidad, (int, float)):
        return int(calidad)
    texto = str(calidad or '').strip()
    if texto in CALIDADES:
        return CALIDADES[texto]
    coincidencia = re.search(r'(\d{2,3})', texto)
    if coincidencia:
        return int(coincidencia.group(1))
    return 256


def _buscar_mp3(carpeta, video_id):
    """Devuelve la ruta del MP3 descargado (identificado por el id del video)."""
    if not os.path.isdir(carpeta):
        return None
    candidatos = []
    for nombre in os.listdir(carpeta):
        if not nombre.lower().endswith('.mp3'):
            continue
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta):
            continue
        if video_id and f'[{video_id}]' in nombre:
            return ruta
        candidatos.append((os.path.getmtime(ruta), ruta))
    if not candidatos:
        return None
    candidatos.sort(reverse=True)
    return candidatos[0][1]


def _ruta_unica(carpeta, nombre):
    """Evita sobrescribir archivos: agrega ' (1)', ' (2)'... si hace falta."""
    base, extension = os.path.splitext(nombre)
    ruta = os.path.join(carpeta, nombre)
    contador = 1
    while os.path.exists(ruta):
        ruta = os.path.join(carpeta, f'{base} ({contador}){extension}')
        contador += 1
    return ruta


def _limpiar_temporales(carpeta, video_id, incluir_mp3=False):
    """Elimina restos de una descarga fallida o cancelada."""
    if not carpeta or not os.path.isdir(carpeta):
        return
    for nombre in os.listdir(carpeta):
        if video_id and f'[{video_id}]' not in nombre:
            continue
        if not video_id:
            continue
        es_mp3 = nombre.lower().endswith('.mp3')
        if es_mp3 and not incluir_mp3:
            continue
        if not es_mp3 and not nombre.lower().endswith(_EXTENSIONES_TEMPORALES):
            continue
        try:
            os.remove(os.path.join(carpeta, nombre))
        except OSError:
            pass


def _limpiar_con_reintentos(carpeta, video_id, incluir_mp3=False):
    """
    En Windows el archivo puede seguir abierto un instante después de cancelar,
    así que se reintenta la limpieza unas cuantas veces.
    """
    for intento in range(4):
        _limpiar_temporales(carpeta, video_id, incluir_mp3=incluir_mp3)
        pendientes = []
        if os.path.isdir(carpeta):
            for nombre in os.listdir(carpeta):
                if not video_id or f'[{video_id}]' not in nombre:
                    continue
                es_mp3 = nombre.lower().endswith('.mp3')
                if es_mp3 and not incluir_mp3:
                    continue
                if not es_mp3 and not nombre.lower().endswith(_EXTENSIONES_TEMPORALES):
                    continue
                pendientes.append(nombre)
        if not pendientes:
            return
        time.sleep(0.25 * (intento + 1))


# --- Conversión a 432 Hz -------------------------------------------------

_RUBBERBAND_DISPONIBLE = None


def _tiene_rubberband(ffmpeg_path):
    """Comprueba una sola vez si FFmpeg incluye el filtro rubberband."""
    global _RUBBERBAND_DISPONIBLE
    if _RUBBERBAND_DISPONIBLE is None:
        try:
            resultado = subprocess.run(
                [ffmpeg_path, '-hide_banner', '-filters'],
                capture_output=True, text=True, timeout=20,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            _RUBBERBAND_DISPONIBLE = 'rubberband' in resultado.stdout
        except Exception:
            _RUBBERBAND_DISPONIBLE = False
    return _RUBBERBAND_DISPONIBLE


def _frecuencia_muestreo(ffmpeg_path, ruta):
    """Lee la frecuencia de muestreo del MP3 usando la salida de FFmpeg."""
    try:
        resultado = subprocess.run(
            [ffmpeg_path, '-hide_banner', '-i', ruta],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        coincidencia = re.search(r'(\d+)\s*Hz', resultado.stderr)
        if coincidencia:
            return int(coincidencia.group(1))
    except Exception:
        pass
    return 44100


def _convertir_432(origen, destino, kbps, ffmpeg_path):
    """
    Retunea el audio de 440 Hz a 432 Hz manteniendo la duración.
    Devuelve True si la conversión fue correcta.
    """
    factor = 432.0 / 440.0
    if _tiene_rubberband(ffmpeg_path):
        filtro = f'rubberband=pitch={factor:.8f}'
    else:
        frecuencia = _frecuencia_muestreo(ffmpeg_path, origen)
        nueva = int(round(frecuencia * factor))
        filtro = f'asetrate={nueva},aresample={frecuencia},atempo={1 / factor:.8f}'

    comando = [
        ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
        '-i', origen,
        '-af', filtro,
        '-c:a', 'libmp3lame',
        '-b:a', f'{kbps}k',
        destino,
    ]
    try:
        subprocess.run(
            comando, check=True, capture_output=True, timeout=900,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        return os.path.isfile(destino) and os.path.getsize(destino) > 0
    except Exception:
        try:
            if os.path.exists(destino):
                os.remove(destino)
        except OSError:
            pass
        return False


# --- Descarga principal --------------------------------------------------

def descargar_audio(url, carpeta_destino, calidad, progreso_hook=None,
                    ffmpeg_path=None, temp_dir=None, convertir_432hz=False,
                    cancel_event=None):
    """
    Descarga el audio de un video de YouTube como MP3 en la carpeta destino.

    Parámetros:
      - calidad: etiqueta de CALIDADES ('Alta (256k)') o kbps (256).
      - progreso_hook: función que recibe el diccionario de progreso de yt-dlp.
      - temp_dir: carpeta para archivos intermedios (si se omite, se usa el
        destino).
      - convertir_432hz: retunea el audio a 432 Hz.
      - cancel_event: threading.Event para cancelar la descarga.

    Devuelve: {'titulo', 'archivo', 'id', 'aviso'}.
    """
    ffmpeg_path = ffmpeg_path or FFMPEG_PATH
    if not os.path.isfile(ffmpeg_path):
        raise FileNotFoundError(
            'No se encontró FFmpeg. Revisa la carpeta ffmpeg/bin/.'
        )

    url = limpiar_url(url)
    if not es_url_valida(url):
        raise ValueError('El enlace no es un video válido de YouTube.')

    os.makedirs(carpeta_destino, exist_ok=True)
    carpeta_trabajo = temp_dir or carpeta_destino
    os.makedirs(carpeta_trabajo, exist_ok=True)

    kbps = _kbps(calidad)

    def _hook(d):
        # La cancelación se hace con DownloadCancelled (yt-dlp detiene la descarga)
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled('Descarga cancelada por el usuario')
        if progreso_hook:
            try:
                progreso_hook(d)
            except Exception:
                # Un fallo en la interfaz nunca debe romper la descarga
                pass

    ydl_opts = _opciones_base(ffmpeg_path)
    ydl_opts.update({
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(carpeta_trabajo, '%(title).150B [%(id)s].%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': str(kbps),
        }],
        'progress_hooks': [_hook],
        'windowsfilenames': True,
        'overwrites': True,
    })

    video_id = parse_qs(urlparse(url).query).get('v', [''])[0]
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        if not info:
            raise RuntimeError('YouTube no devolvió información del video.')

        video_id = str(info.get('id') or '')
        titulo = _titulo_legible(info)

        mp3 = _buscar_mp3(carpeta_trabajo, video_id)
        if not mp3:
            raise FileNotFoundError(
                'La descarga terminó, pero no se encontró el archivo MP3.'
            )

        aviso = ''
        convertido_ok = False
        if convertir_432hz:
            convertido = os.path.join(
                carpeta_trabajo,
                f"{os.path.splitext(os.path.basename(mp3))[0]}_432hz.mp3",
            )
            if _convertir_432(mp3, convertido, kbps, ffmpeg_path):
                try:
                    os.remove(mp3)
                except OSError:
                    pass
                mp3 = convertido
                convertido_ok = True
            else:
                aviso = 'No se pudo aplicar la conversión a 432 Hz.'

        nombre = os.path.splitext(os.path.basename(mp3))[0]
        if video_id:
            nombre = nombre.replace(f' [{video_id}]', '')
        if convertido_ok and nombre.lower().endswith('_432hz'):
            nombre = nombre[:-len('_432hz')] + ' (432 Hz)'
        nombre = nombre.strip().rstrip('.') or 'audio'
        if len(nombre) > 120:
            nombre = nombre[:120].rstrip(' .') or 'audio'
        destino = os.path.join(carpeta_destino, nombre + '.mp3')
        if os.path.abspath(destino) != os.path.abspath(mp3):
            destino = _ruta_unica(carpeta_destino, nombre + '.mp3')
            shutil.move(mp3, destino)
        else:
            destino = mp3

        _limpiar_temporales(carpeta_trabajo, video_id)

        return {
            'titulo': titulo,
            'archivo': destino,
            'id': video_id,
            'aviso': aviso,
        }

    except DownloadCancelled:
        _limpiar_con_reintentos(carpeta_trabajo, video_id, incluir_mp3=True)
        raise
    except Exception:
        _limpiar_con_reintentos(carpeta_trabajo, video_id, incluir_mp3=True)
        raise


# ----------------------------------------------------------------------
# Miniaturas
# ----------------------------------------------------------------------

def descargar_miniatura(url, tamaño=(100, 60)):
    """
    Descarga la miniatura de un video y devuelve un objeto PIL.Image.
    Devuelve None si ocurre algún error.
    """
    if not url:
        return None
    try:
        respuesta = requests.get(
            url,
            timeout=15,
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        respuesta.raise_for_status()
        imagen = Image.open(BytesIO(respuesta.content))
        imagen = imagen.convert('RGB')
        imagen.thumbnail(tamaño, _LANCZOS)
        return imagen
    except Exception:
        return None
