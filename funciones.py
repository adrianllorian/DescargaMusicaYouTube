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
from PIL import Image

import actualizador
from config import CALIDADES, DENO_PATH, FFMPEG_PATH

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

_CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class DescargaCancelada(Exception):
    """El usuario canceló la descarga."""


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
# Motor yt-dlp externo
# ----------------------------------------------------------------------

def _argumentos_js_runtime():
    if os.path.isfile(DENO_PATH):
        return ['--js-runtimes', f'deno:{DENO_PATH}']
    return []


def _comando_ytdlp():
    return [actualizador.asegurar_ytdlp()] + _argumentos_js_runtime()


def _texto_error(salida, codigo):
    lineas = [l.strip() for l in (salida or '').splitlines() if l.strip()]
    detalle = lineas[-1] if lineas else f'yt-dlp terminó con código {codigo}'
    return detalle[:500]


def _titulo_legible(info):
    titulo = (info or {}).get('title') or 'Sin título'
    return re.sub(r'\s+', ' ', str(titulo)).strip()


def obtener_info_video(url):
    """
    Obtiene el título y la URL de la miniatura de un video sin descargarlo.
    Usa el yt-dlp.exe externo actualizable.
    """
    url = limpiar_url(url)
    if not es_url_valida(url):
        raise ValueError('El enlace no es un video válido de YouTube.')

    comando = _comando_ytdlp() + [
        '--dump-single-json',
        '--no-playlist',
        '--no-warnings',
        '--skip-download',
        '--socket-timeout', '30',
        url,
    ]
    try:
        salida = subprocess.run(
            comando, capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace',
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception as e:
        raise RuntimeError(f'No se pudo iniciar yt-dlp: {e}') from e

    if salida.returncode != 0:
        raise RuntimeError(_texto_error(salida.stderr, salida.returncode))

    import json
    try:
        info = json.loads(salida.stdout)
    except Exception as e:
        raise RuntimeError('yt-dlp devolvió una respuesta no válida.') from e

    if not info:
        raise ValueError('YouTube no devolvió información para ese enlace.')

    if info.get('_type') == 'playlist' or 'entries' in info:
        entradas = [e for e in (info.get('entries') or []) if e]
        if len(entradas) != 1:
            raise ValueError(
                'El enlace es una lista de reproducción. '
                'Usa el enlace de un solo video.'
            )
        info = entradas[0]

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
        if not video_id or f'[{video_id}]' not in nombre:
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
    """En Windows el archivo puede seguir abierto un instante tras cancelar."""
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


def _int_o_none(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


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
                creationflags=_CREATE_NO_WINDOW,
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
            creationflags=_CREATE_NO_WINDOW,
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
            creationflags=_CREATE_NO_WINDOW,
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
    Descarga el audio de un video de YouTube como MP3 en la carpeta destino
    usando el yt-dlp.exe externo actualizable.

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
    video_id = parse_qs(urlparse(url).query).get('v', [''])[0]
    plantilla = os.path.join(carpeta_trabajo, '%(title).150B [%(id)s].%(ext)s')

    comando = _comando_ytdlp() + [
        '--newline',
        '--no-playlist',
        '--no-warnings',
        '--socket-timeout', '30',
        '--retries', '3',
        '--fragment-retries', '3',
        '--windows-filenames',
        '--no-mtime',
        '--force-overwrites',
        '-f', 'bestaudio/best',
        '-x',
        '--audio-format', 'mp3',
        '--audio-quality', f'{kbps}K',
        '--ffmpeg-location', ffmpeg_path,
        '-o', plantilla,
        '--progress-template',
        'download:%(progress.status)s|%(progress.downloaded_bytes)s|'
        '%(progress.total_bytes)s|%(progress.total_bytes_estimate)s',
        url,
    ]

    ultimas = []
    try:
        proceso = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception as e:
        raise RuntimeError(f'No se pudo iniciar yt-dlp: {e}') from e

    try:
        for linea in proceso.stdout:
            linea = (linea or '').strip()
            if not linea:
                continue
            ultimas.append(linea)
            if len(ultimas) > 25:
                ultimas.pop(0)

            if cancel_event is not None and cancel_event.is_set():
                proceso.terminate()
                try:
                    proceso.wait(timeout=10)
                except Exception:
                    proceso.kill()
                raise DescargaCancelada('Descarga cancelada por el usuario')

            # El prefijo 'download:' de --progress-template solo selecciona el
            # tipo de progreso, no se imprime. La línea real es, por ejemplo:
            #   downloading|1024|3433755|NA
            partes_progreso = linea.split('|')
            estado_progreso = partes_progreso[0].strip().lower()
            if (progreso_hook and len(partes_progreso) == 4
                    and estado_progreso in ('downloading', 'finished')):
                try:
                    if estado_progreso == 'downloading':
                        descargado = _int_o_none(partes_progreso[1])
                        total = _int_o_none(partes_progreso[2])
                        estimado = _int_o_none(partes_progreso[3])
                        progreso_hook({
                            'status': 'downloading',
                            'downloaded_bytes': descargado or 0,
                            'total_bytes': total,
                            'total_bytes_estimate': estimado,
                        })
                    else:
                        progreso_hook({'status': 'finished'})
                except Exception:
                    pass

        codigo = proceso.wait()
        if cancel_event is not None and cancel_event.is_set():
            raise DescargaCancelada('Descarga cancelada por el usuario')
        if codigo != 0:
            raise RuntimeError(_texto_error('\n'.join(ultimas), codigo))
    except DescargaCancelada:
        _limpiar_con_reintentos(carpeta_trabajo, video_id, incluir_mp3=True)
        raise
    except Exception:
        _limpiar_con_reintentos(carpeta_trabajo, video_id, incluir_mp3=True)
        raise
    finally:
        try:
            if proceso.poll() is None:
                proceso.kill()
        except Exception:
            pass

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
        'titulo': nombre,
        'archivo': destino,
        'id': video_id,
        'aviso': aviso,
    }


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
