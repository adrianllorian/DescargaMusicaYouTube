"""Actualizaciones de yt-dlp, Deno y de la propia aplicación.

- yt-dlp y Deno viven en la carpeta ``tools`` junto al .exe.
- Se descargan de sus Releases oficiales y se verifica su SHA-256.
- La aplicación comprueba su propia Release y ofrece actualizarse.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from typing import Callable, Optional

import requests

from config import (
    APP_DIR,
    APP_REPO,
    APP_VERSION,
    DENO_PATH,
    DENO_REPO,
    TOOLS_DIR,
    UPDATE_STATE_PATH,
    YTDLP_PATH,
    YTDLP_REPO,
)

try:
    _FROZEN = bool(getattr(sys, 'frozen', False))
except Exception:
    _FROZEN = False

_CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
_CABECERAS = {
    'User-Agent': f'VideosMP3Downloader/{APP_VERSION}',
    'Accept': 'application/vnd.github+json',
}
_TIMEOUT = 30
_CACHE_SEGUNDOS = 12 * 60 * 60

_engine_lock = threading.Lock()
_deno_lock = threading.Lock()
_estado_lock = threading.Lock()

Progreso = Optional[Callable[[int, int, str], None]]


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------

def _crear_tools() -> None:
    os.makedirs(TOOLS_DIR, exist_ok=True)


def _leer_estado() -> dict:
    try:
        with open(UPDATE_STATE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_estado(datos: dict) -> None:
    with _estado_lock:
        try:
            _crear_tools()
            with open(UPDATE_STATE_PATH, 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def _version_key(texto: str) -> tuple:
    """Convierte 'v2026.10.26' o '2.0.0' en una tupla comparable."""
    numeros = re.findall(r'\d+', str(texto or ''))
    return tuple(int(n) for n in numeros) if numeros else (0,)


def _sha256(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b''):
            h.update(bloque)
    return h.hexdigest()


def _api(url: str) -> dict:
    resp = requests.get(url, headers=_CABECERAS, timeout=_TIMEOUT)
    if resp.status_code == 404:
        raise RuntimeError('No se pudo acceder al repositorio de actualizaciones.')
    resp.raise_for_status()
    return resp.json()


def _descargar(url: str, destino: str, progreso: Progreso = None,
               descripcion: str = '') -> None:
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    parcial = destino + '.part'
    with requests.get(url, headers=_CABECERAS, timeout=_TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get('Content-Length') or 0)
        hecho = 0
        with open(parcial, 'wb') as f:
            for bloque in resp.iter_content(chunk_size=1024 * 256):
                if not bloque:
                    continue
                f.write(bloque)
                hecho += len(bloque)
                if progreso:
                    try:
                        progreso(hecho, total, descripcion)
                    except Exception:
                        pass
    os.replace(parcial, destino)


def _hash_de_sums(texto: str, nombre: str) -> Optional[str]:
    for linea in texto.splitlines():
        partes = linea.strip().split()
        if len(partes) >= 2 and partes[-1].lstrip('*') == nombre:
            return partes[0].lower()
    return None


def _reemplazar(origen: str, destino: str, intentos: int = 8) -> None:
    for i in range(intentos):
        try:
            os.replace(origen, destino)
            return
        except PermissionError:
            if i == intentos - 1:
                raise
            time.sleep(0.5)


# ----------------------------------------------------------------------
# yt-dlp
# ----------------------------------------------------------------------

def version_ytdlp() -> str:
    if not os.path.isfile(YTDLP_PATH):
        return ''
    try:
        salida = subprocess.run(
            [YTDLP_PATH, '--version'],
            capture_output=True, text=True, timeout=20,
            encoding='utf-8', errors='replace',
            creationflags=_CREATE_NO_WINDOW,
        )
        return (salida.stdout or '').strip().splitlines()[0].strip()
    except Exception:
        return ''


def _release_ytdlp() -> dict:
    return _api(f'https://api.github.com/repos/{YTDLP_REPO}/releases/latest')


def actualizar_ytdlp(progreso: Progreso = None) -> dict:
    """
    Descarga la última versión de yt-dlp.exe si es más nueva.
    Devuelve {'cambio', 'version', 'error'}.
    """
    with _engine_lock:
        _crear_tools()
        local = version_ytdlp()
        try:
            release = _release_ytdlp()
            remota = str(release.get('tag_name') or '')
            if not remota:
                return {'cambio': False, 'version': local, 'error': 'Versión remota desconocida'}

            if os.path.isfile(YTDLP_PATH) and _version_key(remota) <= _version_key(local):
                return {'cambio': False, 'version': local, 'error': ''}

            nombre_exe = 'yt-dlp.exe' if os.name == 'nt' else 'yt-dlp'
            assets = {a.get('name'): a for a in release.get('assets', [])}
            if nombre_exe not in assets:
                return {'cambio': False, 'version': local,
                        'error': 'La Release de yt-dlp no tiene el ejecutable esperado'}

            esperado = None
            sums = assets.get('SHA2-256SUMS')
            if sums:
                try:
                    texto = requests.get(sums['browser_download_url'],
                                         headers=_CABECERAS, timeout=_TIMEOUT).text
                    esperado = _hash_de_sums(texto, nombre_exe)
                except Exception:
                    esperado = None

            _crear_tools()
            temporal = os.path.join(TOOLS_DIR, nombre_exe + '.new')
            _descargar(assets[nombre_exe]['browser_download_url'], temporal,
                       progreso, 'Actualizando yt-dlp')
            if esperado:
                obtenido = _sha256(temporal)
                if obtenido.lower() != esperado.lower():
                    os.remove(temporal)
                    return {'cambio': False, 'version': local,
                            'error': 'El SHA-256 de yt-dlp no coincide'}

            _reemplazar(temporal, YTDLP_PATH)
            return {'cambio': True, 'version': version_ytdlp() or remota, 'error': ''}
        except Exception as e:
            return {'cambio': False, 'version': local, 'error': str(e)}


def asegurar_ytdlp(progreso: Progreso = None) -> str:
    """Devuelve la ruta de yt-dlp, descargándolo si aún no existe."""
    if os.path.isfile(YTDLP_PATH):
        return YTDLP_PATH
    resultado = actualizar_ytdlp(progreso)
    if not os.path.isfile(YTDLP_PATH):
        raise RuntimeError(resultado.get('error') or
                           'No se pudo descargar yt-dlp. Revisa tu conexión.')
    return YTDLP_PATH


# ----------------------------------------------------------------------
# Deno
# ----------------------------------------------------------------------

def version_deno() -> str:
    if not os.path.isfile(DENO_PATH):
        return ''
    try:
        salida = subprocess.run(
            [DENO_PATH, '--version'],
            capture_output=True, text=True, timeout=15,
            encoding='utf-8', errors='replace',
            creationflags=_CREATE_NO_WINDOW,
        )
        return (salida.stdout or '').strip().splitlines()[0].strip()
    except Exception:
        return ''


def asegurar_deno(progreso: Progreso = None) -> str:
    """Descarga Deno junto al programa si aún no está instalado."""
    with _deno_lock:
        if os.path.isfile(DENO_PATH):
            return DENO_PATH
        if os.name != 'nt':
            return ''
        _crear_tools()
        try:
            release = _api(f'https://api.github.com/repos/{DENO_REPO}/releases/latest')
            assets = {a.get('name'): a for a in release.get('assets', [])}
            nombre_zip = 'deno-x86_64-pc-windows-msvc.zip'
            if nombre_zip not in assets:
                return ''
            zip_tmp = os.path.join(TOOLS_DIR, 'deno.zip')
            _descargar(assets[nombre_zip]['browser_download_url'], zip_tmp,
                       progreso, 'Preparando Deno')

            esperado = None
            sums = assets.get(nombre_zip + '.sha256sum')
            if sums:
                try:
                    texto = requests.get(sums['browser_download_url'],
                                         headers=_CABECERAS, timeout=_TIMEOUT).text
                    coincidencia = re.search(r'(?i)hash\s*:\s*([0-9a-f]{64})', texto)
                    if coincidencia:
                        esperado = coincidencia.group(1).lower()
                    else:
                        coincidencia = re.search(r'[0-9a-f]{64}', texto, re.I)
                        esperado = coincidencia.group(0).lower() if coincidencia else None
                except Exception:
                    esperado = None
            if esperado and _sha256(zip_tmp).lower() != esperado:
                os.remove(zip_tmp)
                return ''

            with zipfile.ZipFile(zip_tmp) as z:
                with z.open('deno.exe') as origen, open(DENO_PATH, 'wb') as destino:
                    shutil.copyfileobj(origen, destino)
            os.remove(zip_tmp)
            return DENO_PATH
        except Exception:
            return ''


# ----------------------------------------------------------------------
# Aplicación
# ----------------------------------------------------------------------

def _release_app() -> dict:
    return _api(f'https://api.github.com/repos/{APP_REPO}/releases/latest')


def _hash_asset_app(release: dict, asset: dict) -> Optional[str]:
    digest = asset.get('digest')
    if digest and digest.lower().startswith('sha256:'):
        return digest.split(':', 1)[1]

    for a in release.get('assets', []):
        if a.get('name') == 'SHA256SUMS.txt':
            try:
                texto = requests.get(a['browser_download_url'],
                                     headers=_CABECERAS, timeout=_TIMEOUT).text
                return _hash_de_sums(texto, asset.get('name') or '')
            except Exception:
                return None
    return None


def comprobar_actualizacion_app() -> dict:
    """
    Devuelve información de la última Release.
    {'disponible', 'version', 'actual', 'url', 'asset_url', 'asset_name',
     'sha256', 'error'}
    """
    try:
        release = _release_app()
        remota = str(release.get('tag_name') or '')
        disponible = _version_key(remota) > _version_key(APP_VERSION)
        exe = next((a for a in release.get('assets', [])
                    if (a.get('name') or '').lower().endswith('.exe')), None)
        info = {
            'disponible': disponible,
            'version': remota,
            'actual': APP_VERSION,
            'url': release.get('html_url'),
            'asset_url': exe.get('browser_download_url') if exe else None,
            'asset_name': exe.get('name') if exe else None,
            'sha256': _hash_asset_app(release, exe) if exe else None,
            'error': '',
        }
        return info
    except Exception as e:
        return {'disponible': False, 'version': '', 'actual': APP_VERSION,
                'url': '', 'asset_url': None, 'asset_name': None,
                'sha256': None, 'error': str(e)}


def descargar_actualizacion_app(info: dict, progreso: Progreso = None) -> str:
    """Descarga el .exe de la nueva Release y verifica su SHA-256."""
    if not info.get('asset_url'):
        raise RuntimeError('La Release no tiene un ejecutable descargable.')
    carpeta = os.path.join(tempfile.gettempdir(), 'VideosMP3Downloader_update')
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, 'Videos MP3 Downloader.new.exe')
    if os.path.exists(destino):
        os.remove(destino)
    _descargar(info['asset_url'], destino, progreso, 'Descargando actualización')
    esperado = info.get('sha256')
    if esperado and _sha256(destino).lower() != esperado.lower():
        os.remove(destino)
        raise RuntimeError('El SHA-256 de la actualización no coincide.')
    return destino


def instalar_actualizacion_app(nuevo: str) -> None:
    """Crea un .bat que sustituye el exe al cerrarse la app y la reinicia."""
    if not _FROZEN:
        raise RuntimeError('La actualización automática solo está disponible en el .exe.')
    actual = os.path.abspath(sys.executable)
    if not os.path.isfile(actual):
        actual = os.path.abspath(os.path.join(APP_DIR, 'Videos MP3 Downloader.exe'))

    carpeta = os.path.dirname(nuevo)
    bat = os.path.join(carpeta, 'actualizar_app.bat')
    contenido = f'''@echo off
setlocal
set "NUEVO={nuevo}"
set "ACTUAL={actual}"
set /a INTENTOS=0
timeout /t 2 /nobreak >nul
:reintentar
move /y "%NUEVO%" "%ACTUAL%" >nul 2>&1
if errorlevel 1 (
  set /a INTENTOS+=1
  if %INTENTOS% GEQ 60 goto fallo
  timeout /t 1 /nobreak >nul
  goto reintentar
)
start "" "%ACTUAL%"
del "%~f0"
exit /b 0
:fallo
echo No se pudo sustituir el ejecutable. > "%~dp0error_actualizacion.txt"
exit /b 1
'''
    with open(bat, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(contenido)
    subprocess.Popen(
        ['cmd.exe', '/c', bat],
        cwd=carpeta,
        creationflags=_CREATE_NO_WINDOW,
        close_fds=True,
    )


# ----------------------------------------------------------------------
# Comprobación conjunta
# ----------------------------------------------------------------------

def comprobar_todo(progreso: Progreso = None, forzar: bool = False) -> dict:
    """
    Actualiza yt-dlp/Deno y comprueba la app.
    Usa una caché de 12 h salvo que forzar=True.
    """
    estado = _leer_estado()
    ahora = time.time()
    reciente = (not forzar and estado.get('ultima_comprobacion')
                and ahora - float(estado.get('ultima_comprobacion', 0)) < _CACHE_SEGUNDOS)

    resultado = {'ytdlp': '', 'ytdlp_cambio': False, 'ytdlp_error': '',
                 'deno': '', 'app': None}
    if not os.path.isfile(YTDLP_PATH):
        r = actualizar_ytdlp(progreso)
        resultado['ytdlp'] = r['version']
        resultado['ytdlp_cambio'] = r['cambio']
        resultado['ytdlp_error'] = r['error']
    elif not reciente:
        r = actualizar_ytdlp(progreso)
        resultado['ytdlp'] = r['version']
        resultado['ytdlp_cambio'] = r['cambio']
        resultado['ytdlp_error'] = r['error']
    else:
        resultado['ytdlp'] = version_ytdlp()

    if not os.path.isfile(DENO_PATH):
        resultado['deno'] = asegurar_deno(progreso)
    else:
        resultado['deno'] = DENO_PATH

    if not reciente:
        resultado['app'] = comprobar_actualizacion_app()
        _guardar_estado({
            'ultima_comprobacion': ahora,
            'ytdlp': resultado['ytdlp'],
            'app': (resultado['app'] or {}).get('version', ''),
        })
    else:
        resultado['app'] = comprobar_actualizacion_app()

    return resultado
