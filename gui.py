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
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import actualizador
from config import (
    APP_VERSION,
    CALIDAD_PREDETERMINADA,
    CALIDADES,
    FFMPEG_PATH,
    ICONOS_PATH,
    LICENSES_PATH,
    ffmpeg_disponible,
    mensaje_ffmpeg_faltante,
)
from funciones import (
    DescargaCancelada,
    descargar_audio,
    descargar_miniatura,
    es_url_valida,
    limpiar_url,
    obtener_info_video,
)

try:  # Pillow >= 9
    _LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow antiguo
    _LANCZOS = Image.LANCZOS

FONDO = '#2b2b2b'

# En un .exe de PyInstaller sin consola, sys.stdout/sys.stderr son None.
# Algunas librerías (yt-dlp) escriben en ellos, así que se redirigen.
if getattr(sys, 'frozen', False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')

# ----------------------------------------------------------------------
# Estado global
# ----------------------------------------------------------------------

carpeta_destino = ""
lista_descargas = []
trabajando = False
_cola_ui = queue.Queue()
_estado_timer = None
_actualizacion_app = None
_actualizando_app = False
_ultimo_progreso_update = 0.0

ICONOS = {
    "carpeta": os.path.join(ICONOS_PATH, "folder.png"),
    "agregar": os.path.join(ICONOS_PATH, "add.png"),
    "descargar": os.path.join(ICONOS_PATH, "download.png"),
    "eliminar": os.path.join(ICONOS_PATH, "delete.png"),
    "url": os.path.join(ICONOS_PATH, "url.png"),
    "checkbox_unchecked": os.path.join(ICONOS_PATH, "checkbox_unchecked.png"),
    "checkbox_checked": os.path.join(ICONOS_PATH, "checkbox_checked.png"),
    "logo_ico": os.path.join(ICONOS_PATH, "logo.ico"),  # Para Windows
    "logo_png": os.path.join(ICONOS_PATH, "logo.png"),   # Para macOS y Linux
}

ICONOS_CARGADOS = {}


def cargar_icono(ruta, size=(26, 26)):
    """Carga un PNG como PhotoImage. Devuelve None si no se puede."""
    try:
        if not os.path.isfile(ruta):
            return None
        imagen = Image.open(ruta).convert('RGBA').resize(size, _LANCZOS)
        icono = ImageTk.PhotoImage(imagen)
        ICONOS_CARGADOS[ruta] = icono  # evita que el GC lo elimine
        return icono
    except Exception:
        return None


def ui(funcion, *args):
    """
    Encola una actualización de la interfaz. Es la única forma segura de
    tocar widgets desde un hilo de descarga.
    """
    _cola_ui.put((funcion, args))


def _procesar_cola():
    try:
        while True:
            funcion, args = _cola_ui.get_nowait()
            try:
                funcion(*args)
            except tk.TclError:
                pass
            except Exception:
                traceback.print_exc()
    except queue.Empty:
        pass
    ventana.after(80, _procesar_cola)


def mostrar_estado(texto, error=False):
    """Muestra un mensaje breve en la barra de estado."""
    global _estado_timer
    try:
        label_estado_app.config(
            text=texto,
            foreground='#ff7b72' if error else '#d7d7d7',
        )
        if _estado_timer is not None:
            ventana.after_cancel(_estado_timer)
        _estado_timer = ventana.after(
            9000, lambda: label_estado_app.config(text='')
        )
    except tk.TclError:
        pass


def _recortar(texto, largo=55):
    texto = re.sub(r'\s+', ' ', str(texto or '')).strip()
    return texto if len(texto) <= largo else texto[:largo - 1] + '…'


# ----------------------------------------------------------------------
# Estilos
# ----------------------------------------------------------------------

def configurar_estilo():
    style = ttk.Style()
    style.theme_use('alt')
    style.configure('TFrame', background=FONDO)
    style.configure('TLabel', background=FONDO, foreground='#ffffff',
                    font=('Helvetica', 10))
    style.configure('TButton', background='#4CAF50', foreground='#ffffff',
                    font=('Helvetica', 10, 'bold'), padding=6, borderwidth=0)
    style.map('TButton', background=[('active', '#45a049'),
                                     ('disabled', '#666666')])
    style.configure('Agregar.TButton', background='#2196F3')
    style.map('Agregar.TButton', background=[('active', '#1e88e5'),
                                             ('disabled', '#666666')])
    style.configure('Eliminar.TButton', background='#f44336', padding=6)
    style.map('Eliminar.TButton', background=[('active', '#d32f2f'),
                                              ('disabled', '#666666')])
    style.configure('AbrirCarpeta.TButton', background='#FF9800')
    style.map('AbrirCarpeta.TButton', background=[('active', '#F57C00'),
                                                  ('disabled', '#666666')])
    style.configure('TCombobox', fieldbackground='#3c3c3c',
                    background='#4CAF50', foreground='#ffffff')
    style.map('TCombobox', fieldbackground=[('readonly', '#3c3c3c')])
    style.layout('Custom.TProgressbar', style.layout('Horizontal.TProgressbar'))
    style.configure('Custom.TProgressbar', background='#FFC107',
                    troughcolor='#3c3c3c')
    style.layout('Processing.TProgressbar',
                 style.layout('Horizontal.TProgressbar'))
    style.configure('Processing.TProgressbar', background='#2196F3',
                    troughcolor='#3c3c3c')
    style.layout('Completed.TProgressbar',
                 style.layout('Horizontal.TProgressbar'))
    style.configure('Completed.TProgressbar', background='#4CAF50',
                    troughcolor='#3c3c3c')
    style.configure('Toggle.TButton', background=FONDO, borderwidth=0, padding=0)
    style.configure('Vertical.TScrollbar', background='#4a4a4a',
                    troughcolor=FONDO, arrowcolor='#dddddd', borderwidth=0)


# ----------------------------------------------------------------------
# Acerca de / licencias
# ----------------------------------------------------------------------

def _leer_licencia(nombre):
    ruta = os.path.join(LICENSES_PATH, nombre)
    with open(ruta, 'r', encoding='utf-8') as archivo:
        return archivo.read()


def mostrar_acerca():
    try:
        texto = _leer_licencia('NOTICE.txt') + '\n\n' + _leer_licencia('DISCLAIMER.txt')
        messagebox.showinfo("Acerca de", texto)
    except FileNotFoundError:
        messagebox.showerror(
            "Error",
            f"No se encontraron los archivos de licencia en:\n{LICENSES_PATH}",
        )
    except Exception as e:
        messagebox.showerror("Error", f"Error al leer los archivos: {e}")


def mostrar_descargo_responsabilidad():
    try:
        messagebox.showinfo("Descargo de responsabilidad",
                            _leer_licencia('DISCLAIMER.txt'))
    except FileNotFoundError:
        messagebox.showerror(
            "Error",
            f"No se encontró DISCLAIMER.txt en:\n{LICENSES_PATH}",
        )
    except Exception as e:
        messagebox.showerror("Error", f"Error al leer el archivo: {e}")


# ----------------------------------------------------------------------
# Carpeta de destino
# ----------------------------------------------------------------------

def seleccionar_carpeta():
    global carpeta_destino
    if trabajando:
        mostrar_estado("Espera a que terminen las descargas para cambiar la carpeta.")
        return

    sistema = platform.system()
    musica = os.path.expanduser('~\\Music' if sistema == 'Windows' else '~/Music')
    initial_dir = musica if os.path.isdir(musica) else os.path.expanduser('~')

    carpeta = filedialog.askdirectory(
        initialdir=initial_dir, title="Selecciona una carpeta de destino"
    )
    if not carpeta:
        return

    carpeta_destino = os.path.normpath(carpeta)
    label_ruta.config(text=f"Carpeta: {_recortar(carpeta_destino, 70)}")
    mostrar_estado('')
    actualizar_botones()


def abrir_carpeta_destino():
    if not carpeta_destino or not os.path.isdir(carpeta_destino):
        mostrar_estado("Selecciona primero una carpeta de destino válida.", error=True)
        return
    sistema = platform.system()
    try:
        if sistema == 'Windows':
            os.startfile(carpeta_destino)
        elif sistema == 'Darwin':
            subprocess.Popen(['open', carpeta_destino])
        else:
            subprocess.Popen(['xdg-open', carpeta_destino])
    except Exception as e:
        mostrar_estado(f"No se pudo abrir la carpeta: {e}", error=True)


# ----------------------------------------------------------------------
# Añadir enlaces
# ----------------------------------------------------------------------

def _estado_item(item, texto, color='#ffffff'):
    try:
        item['label_estado'].config(text=texto, foreground=color)
    except tk.TclError:
        pass


def _crear_item(url):
    frame = ttk.Frame(lista_frame, style='TFrame')
    frame.columnconfigure(1, weight=1)

    label_img = tk.Label(frame, background=FONDO)
    label_img.grid(row=0, column=0, padx=(4, 8), pady=4)
    frame.columnconfigure(0, minsize=68)

    label_titulo = ttk.Label(frame, text="Obteniendo información…",
                             style='TLabel', anchor='w')
    label_titulo.grid(row=0, column=1, sticky='ew', pady=4)

    barra = ttk.Progressbar(frame, length=120, style='Custom.TProgressbar')
    barra.grid(row=0, column=2, padx=8, sticky='ew')

    label_estado = ttk.Label(frame, text="Cargando…", style='TLabel',
                             width=20, anchor='w')
    label_estado.grid(row=0, column=3, padx=8, sticky='w')

    item = {
        'url': url,
        'titulo': '',
        'estado': 'cargando',
        'cancel': threading.Event(),
        'eliminar_al_terminar': False,
        'archivo': None,
        'frame': frame,
        'barra': barra,
        'label_titulo': label_titulo,
        'label_estado': label_estado,
        'label_img': label_img,
        'foto': None,
        '_ultimo_ui': 0.0,
    }

    icono_eliminar = ICONOS_CARGADOS.get(ICONOS['eliminar'])
    argumentos = {
        'text': "Eliminar",
        'style': 'Eliminar.TButton',
    }
    if icono_eliminar is not None:
        argumentos.update({'image': icono_eliminar, 'compound': 'left'})
    boton = ttk.Button(frame, **argumentos,
                       command=lambda it=item: eliminar_item(it))
    boton.grid(row=0, column=4, padx=(4, 4), pady=4)
    item['boton'] = boton
    label_estado.bind('<Button-1>', lambda e, it=item: _mostrar_detalle(it))
    label_estado.configure(cursor='hand2')
    return item


def _mostrar_detalle(item):
    """Muestra información ampliada al pulsar el estado del elemento."""
    lineas = [item.get('titulo') or item.get('url') or '', '']
    lineas.append(f"Estado: {item.get('estado', '')}")
    if item.get('error'):
        lineas += ['', f"Error: {item['error']}"]
    if item.get('archivo'):
        lineas += ['', f"Archivo: {item['archivo']}"]
    messagebox.showinfo("Detalle de la descarga", '\n'.join(lineas))


def _cargar_info(item):
    """Se ejecuta en un hilo aparte: título y miniatura del video."""
    try:
        titulo, miniatura = obtener_info_video(item['url'])
    except Exception as e:
        ui(_info_error, item, str(e))
        return
    imagen = descargar_miniatura(miniatura, (64, 48))
    ui(_aplicar_info, item, titulo, imagen)


def _aplicar_info(item, titulo, imagen):
    if item not in lista_descargas:
        return
    item['titulo'] = titulo
    item['label_titulo'].config(text=_recortar(titulo))
    if imagen is not None:
        foto = ImageTk.PhotoImage(imagen)
        item['label_img'].config(image=foto)
        item['foto'] = foto  # mantiene la referencia viva
    if item['estado'] == 'cargando':
        item['estado'] = 'pendiente'
        _estado_item(item, "Pendiente")
    actualizar_botones()


def _info_error(item, mensaje):
    if item not in lista_descargas:
        return
    item['estado'] = 'error'
    item['label_titulo'].config(text=_recortar(item['url']))
    _estado_item(item, "Error", '#ff7b72')
    mostrar_estado(f"No se pudo leer el enlace: {mensaje}", error=True)
    actualizar_botones()


def agregar_desde_portapapeles():
    try:
        texto = ventana.clipboard_get().strip()
    except tk.TclError:
        mostrar_estado("No se pudo leer el portapapeles.", error=True)
        return
    if not texto:
        mostrar_estado("El portapapeles está vacío.", error=True)
        return
    agregar_url(texto)


def agregar_desde_entrada(evento=None):
    texto = entrada_url.get().strip()
    if not texto:
        mostrar_estado("Escribe o pega un enlace de YouTube.", error=True)
        return
    entrada_url.delete(0, tk.END)
    agregar_url(texto)


def agregar_url(texto):
    if not carpeta_destino:
        mostrar_estado("Selecciona una carpeta de destino primero.", error=True)
        return

    url = limpiar_url(texto)
    if not es_url_valida(url):
        mostrar_estado("Enlace no válido. Debe ser un video de YouTube.", error=True)
        return

    for existente in lista_descargas:
        if existente['url'] == url and existente['estado'] in (
                'cargando', 'pendiente', 'descargando'):
            mostrar_estado("Ese enlace ya está en la lista.", error=True)
            return

    item = _crear_item(url)
    lista_descargas.insert(0, item)
    _reordenar()
    actualizar_botones()
    threading.Thread(target=_cargar_info, args=(item,), daemon=True).start()


# ----------------------------------------------------------------------
# Lista de descargas
# ----------------------------------------------------------------------

def _reordenar():
    for indice, item in enumerate(lista_descargas):
        try:
            item['frame'].grid(row=indice, column=0, sticky='ew',
                               padx=2, pady=3)
        except tk.TclError:
            pass
    _actualizar_scrollregion()


def _actualizar_scrollregion():
    try:
        ventana.after_idle(
            lambda: canvas.configure(scrollregion=canvas.bbox('all'))
        )
    except tk.TclError:
        pass


def _quitar_item(item):
    if item in lista_descargas:
        lista_descargas.remove(item)
    item['cancel'].set()
    try:
        item['frame'].destroy()
    except tk.TclError:
        pass
    _reordenar()
    actualizar_botones()


def eliminar_item(item):
    if item.get('estado') == 'descargando':
        # Cancelar y quitar de la lista cuando el hilo de descarga termine
        item['cancel'].set()
        item['eliminar_al_terminar'] = True
        _estado_item(item, "Cancelando…", '#ffc107')
        try:
            item['boton'].config(state='disabled')
        except tk.TclError:
            pass
        return

    if item.get('estado') == 'completado':
        archivo = item.get('archivo')
        if archivo and os.path.isfile(archivo):
            borrar = messagebox.askyesno(
                "Eliminar de la lista",
                "¿Quieres eliminar también el archivo descargado?\n\n"
                f"{os.path.basename(archivo)}",
            )
            if borrar:
                try:
                    os.remove(archivo)
                except OSError as e:
                    messagebox.showerror(
                        "Error", f"No se pudo eliminar el archivo:\n{e}"
                    )
    _quitar_item(item)


def actualizar_botones():
    hay_destino = bool(carpeta_destino) and os.path.isdir(carpeta_destino)
    hay_pendientes = any(i['estado'] == 'pendiente' for i in lista_descargas)
    hay_completados = any(i['estado'] == 'completado' for i in lista_descargas)

    estado_agregar = 'normal' if hay_destino else 'disabled'
    for boton in (boton_agregar, boton_agregar_texto):
        boton.config(state=estado_agregar)
    entrada_url.config(state=estado_agregar)

    boton_descargar.config(
        state='normal' if (hay_destino and hay_pendientes and not trabajando)
        else 'disabled'
    )
    boton_abrir_carpeta.config(
        state='normal' if hay_destino else 'disabled'
    )
    boton_carpeta.config(state='disabled' if trabajando else 'normal')


# ----------------------------------------------------------------------
# Descargas
# ----------------------------------------------------------------------

def _iniciar_descarga_ui(item):
    if item not in lista_descargas:
        return
    item['estado'] = 'descargando'
    item['barra'].configure(value=0, style='Processing.TProgressbar')
    _estado_item(item, "0%")
    actualizar_botones()


def _actualizar_progreso(item, valor, texto):
    if item not in lista_descargas:
        return
    try:
        if valor is not None:
            item['barra'].configure(value=valor)
        _estado_item(item, texto)
    except tk.TclError:
        pass


def _hook_progreso(item, datos):
    """Se ejecuta en el hilo de descarga: solo encola cambios de interfaz."""
    estado = datos.get('status')
    if estado == 'downloading':
        ahora = time.monotonic()
        if ahora - item.get('_ultimo_ui', 0.0) < 0.12:
            return
        item['_ultimo_ui'] = ahora
        total = datos.get('total_bytes') or datos.get('total_bytes_estimate') or 0
        descargado = datos.get('downloaded_bytes') or 0
        if total:
            porcentaje = max(0, min(100, int(descargado * 100 / total)))
            ui(_actualizar_progreso, item, porcentaje, f"{porcentaje}%")
        else:
            ui(_actualizar_progreso, item, None, "Descargando…")
    elif estado == 'finished':
        item['_ultimo_ui'] = 0.0
        ui(_actualizar_progreso, item, 100, "Procesando…")


def _finalizar_ok(item, resultado):
    if item not in lista_descargas:
        return
    if item.get('eliminar_al_terminar'):
        # Se pidió eliminar mientras descargaba, pero terminó antes de cancelar
        _quitar_item(item)
        mostrar_estado(
            "La descarga terminó antes de cancelarse; el archivo se conservó."
        )
        return
    item['estado'] = 'completado'
    item['archivo'] = (resultado or {}).get('archivo')
    item['barra'].configure(value=100, style='Completed.TProgressbar')
    aviso = (resultado or {}).get('aviso')
    if aviso:
        _estado_item(item, "Completado (sin 432)", '#ffc107')
        mostrar_estado(aviso, error=True)
    else:
        _estado_item(item, "Completado", '#7ee787')
    actualizar_botones()


def _finalizar_error(item, mensaje):
    if item not in lista_descargas:
        return
    if item.get('eliminar_al_terminar'):
        _quitar_item(item)
        mostrar_estado(f"Descarga cancelada con error: {mensaje}", error=True)
        return
    item['estado'] = 'error'
    item['error'] = mensaje
    item['barra'].configure(value=0, style='Custom.TProgressbar')
    _estado_item(item, "Error", '#ff7b72')
    mostrar_estado(f"Error al descargar: {mensaje}", error=True)
    actualizar_botones()


def _finalizar_cancelado(item):
    if item not in lista_descargas:
        return
    if item.get('eliminar_al_terminar'):
        _quitar_item(item)
        mostrar_estado("Descarga cancelada.")
        return
    item['estado'] = 'cancelado'
    item['barra'].configure(value=0, style='Custom.TProgressbar')
    _estado_item(item, "Cancelado", '#ffc107')
    try:
        item['boton'].config(state='normal')
    except tk.TclError:
        pass
    actualizar_botones()


def _terminar_trabajador(completados=0, errores=0, cancelados=0):
    global trabajando
    trabajando = False
    actualizar_botones()
    if errores:
        mostrar_estado(
            f"Terminó con {errores} error(es). "
            "Pulsa el estado en rojo para ver el detalle.",
            error=True,
        )
    elif cancelados:
        mostrar_estado("Descarga(s) cancelada(s).")
    elif completados:
        mostrar_estado("Descargas finalizadas.")


def _trabajador(items, destino, calidad, convertir_432hz):
    """Descarga los elementos uno por uno en un solo hilo."""
    global trabajando
    temp_dir = os.path.join(destino, '.temp')
    completados = errores = cancelados = 0
    try:
        try:
            os.makedirs(temp_dir, exist_ok=True)
        except OSError as e:
            for item in items:
                if item in lista_descargas:
                    errores += 1
                    ui(_finalizar_error, item,
                       f"No se pudo crear la carpeta temporal: {e}")
            return

        for item in items:
            if item['cancel'].is_set() or item not in lista_descargas:
                cancelados += 1
                ui(_quitar_item, item)
                continue

            ui(_iniciar_descarga_ui, item)
            try:
                resultado = descargar_audio(
                    item['url'],
                    destino,
                    calidad,
                    progreso_hook=lambda datos, it=item: _hook_progreso(it, datos),
                    ffmpeg_path=FFMPEG_PATH,
                    temp_dir=temp_dir,
                    convertir_432hz=convertir_432hz,
                    cancel_event=item['cancel'],
                )
            except DescargaCancelada:
                cancelados += 1
                ui(_finalizar_cancelado, item)
            except Exception as e:
                errores += 1
                ui(_finalizar_error, item, str(e))
            else:
                completados += 1
                ui(_finalizar_ok, item, resultado)
    finally:
        try:
            if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except OSError:
            pass
        ui(_terminar_trabajador, completados, errores, cancelados)


def descargar_todos():
    global trabajando

    if trabajando:
        mostrar_estado("Ya hay descargas en curso.", error=True)
        return
    if not carpeta_destino or not os.path.isdir(carpeta_destino):
        mostrar_estado("Selecciona una carpeta de destino primero.", error=True)
        return
    if not ffmpeg_disponible():
        messagebox.showerror("FFmpeg no encontrado", mensaje_ffmpeg_faltante())
        return

    pendientes = [i for i in lista_descargas if i['estado'] == 'pendiente']
    if not pendientes:
        mostrar_estado("No hay descargas pendientes.", error=True)
        return

    trabajando = True
    actualizar_botones()
    mostrar_estado(f"Descargando {len(pendientes)} elemento(s)…")

    threading.Thread(
        target=_trabajador,
        args=(
            pendientes,
            carpeta_destino,
            combo_calidad.get(),
            bool(var_432hz.get()),
        ),
        daemon=True,
    ).start()


# ----------------------------------------------------------------------
# Actualizaciones
# ----------------------------------------------------------------------

def _aplicar_resultado_actualizaciones(resultado, forzar=False):
    global _actualizacion_app
    info = resultado.get('app') or {}
    _actualizacion_app = info

    if info.get('disponible'):
        label_actualizacion.config(
            text=f"Hay una versión nueva: {info.get('version')} "
                 f"(tienes {info.get('actual')})."
        )
        frame_actualizacion.grid()
        boton_actualizar.config(state='normal')
        mostrar_estado(f"Actualización disponible: {info.get('version')}")
    else:
        frame_actualizacion.grid_remove()

    if resultado.get('ytdlp_cambio'):
        mostrar_estado(
            f"Motor de descarga actualizado a yt-dlp {resultado.get('ytdlp')}."
        )
    elif resultado.get('ytdlp_error') and not os.path.isfile(
            actualizador.YTDLP_PATH):
        mostrar_estado(
            "No se pudo preparar yt-dlp: " + resultado.get('ytdlp_error'),
            error=True,
        )
    elif forzar:
        if info.get('error'):
            mostrar_estado(f"No se pudo comprobar la app: {info['error']}", error=True)
        elif info.get('disponible'):
            pass
        else:
            mostrar_estado("La aplicación y el motor ya están actualizados.")


def _comprobar_actualizaciones(forzar=False):
    try:
        resultado = actualizador.comprobar_todo(
            progreso=_progreso_update, forzar=forzar
        )
        ui(_aplicar_resultado_actualizaciones, resultado, forzar)
    except Exception as e:
        ui(mostrar_estado, f"Error comprobando actualizaciones: {e}", True)


def _progreso_update(hecho, total, texto):
    global _ultimo_progreso_update
    ahora = time.monotonic()
    if ahora - _ultimo_progreso_update < 0.25 and total and hecho < total:
        return
    _ultimo_progreso_update = ahora
    if total:
        porcentaje = max(0, min(100, int(hecho * 100 / total)))
        ui(mostrar_estado, f"{texto}: {porcentaje}%")
    else:
        ui(mostrar_estado, f"{texto}...")


def _actualizar_app_click():
    global _actualizando_app
    if _actualizando_app:
        return
    if not _actualizacion_app or not _actualizacion_app.get('disponible'):
        threading.Thread(target=_comprobar_actualizaciones, args=(True,),
                         daemon=True).start()
        mostrar_estado("Buscando actualizaciones...")
        return

    info = _actualizacion_app
    if not getattr(sys, 'frozen', False):
        webbrowser.open(info.get('url') or
                        'https://github.com/adrianllorian/DescargaMusicaYouTube/releases')
        return

    if not messagebox.askyesno(
            "Actualizar aplicación",
            f"Se descargará la versión {info.get('version')} y la aplicación "
            "se reiniciará para instalarla.\n\n¿Continuar?"):
        return

    _actualizando_app = True
    boton_actualizar.config(state='disabled')
    mostrar_estado("Descargando actualización...")
    threading.Thread(target=_descargar_actualizacion_app,
                     args=(info,), daemon=True).start()


def _descargar_actualizacion_app(info):
    global _actualizando_app
    try:
        nuevo = actualizador.descargar_actualizacion_app(
            info, _progreso_update
        )
        actualizador.instalar_actualizacion_app(nuevo)
        ui(_cerrar_para_actualizar)
    except Exception as e:
        _actualizando_app = False
        ui(_error_actualizacion, str(e))


def _cerrar_para_actualizar():
    mostrar_estado("Reiniciando para aplicar la actualización...")
    ventana.after(600, ventana.destroy)


def _error_actualizacion(mensaje):
    global _actualizando_app
    _actualizando_app = False
    boton_actualizar.config(state='normal')
    mostrar_estado(f"No se pudo actualizar: {mensaje}", error=True)


# ----------------------------------------------------------------------
# Interfaz
# ----------------------------------------------------------------------

ventana = tk.Tk()
ventana.title("Videos MP3 Downloader")
ventana.geometry("920x660")
ventana.minsize(780, 520)
ventana.configure(bg=FONDO)
ventana.resizable(True, True)

# Menú superior
menubar = tk.Menu(ventana)
ventana.config(menu=menubar)
ayuda_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Ayuda", menu=ayuda_menu)
ayuda_menu.add_command(
    label="Buscar actualizaciones",
    command=lambda: threading.Thread(
        target=_comprobar_actualizaciones, args=(True,), daemon=True
    ).start(),
)
ayuda_menu.add_command(label="Acerca de", command=mostrar_acerca)
ayuda_menu.add_command(label="Descargo de responsabilidad",
                       command=mostrar_descargo_responsabilidad)

# Ícono de la ventana
try:
    if platform.system() == "Windows":
        if os.path.exists(ICONOS["logo_ico"]):
            ventana.iconbitmap(ICONOS["logo_ico"])
    elif os.path.exists(ICONOS["logo_png"]):
        imagen = Image.open(ICONOS["logo_png"]).resize((64, 64), _LANCZOS)
        icono = ImageTk.PhotoImage(imagen)
        ICONOS_CARGADOS['logo'] = icono
        ventana.iconphoto(True, icono)
except (tk.TclError, OSError):
    pass

configurar_estilo()

# Carga de íconos reutilizables (debe hacerse con la ventana ya creada)
for _clave in ("eliminar", "url"):
    cargar_icono(ICONOS[_clave])

ventana.columnconfigure(0, weight=1)
ventana.rowconfigure(1, weight=1)

# --- Controles superiores ---
frame_controles = ttk.Frame(ventana, style='TFrame')
frame_controles.grid(row=0, column=0, pady=(10, 4), padx=12, sticky='ew')
frame_controles.columnconfigure(0, weight=1)

# Carpeta de destino
frame_ruta = ttk.Frame(frame_controles, style='TFrame')
frame_ruta.grid(row=0, column=0, pady=4, sticky='ew')
frame_ruta.columnconfigure(1, weight=1)
icono_carpeta = cargar_icono(ICONOS["carpeta"])
boton_carpeta = ttk.Button(
    frame_ruta, text="Seleccionar carpeta", command=seleccionar_carpeta,
    style='TButton', image=icono_carpeta, compound='left',
)
boton_carpeta.grid(row=0, column=0, padx=(0, 8), sticky='w')
label_ruta = ttk.Label(frame_ruta, text="Carpeta: No seleccionada",
                       style='TLabel', anchor='w')
label_ruta.grid(row=0, column=1, sticky='ew')

# Calidad de audio y opción de 432 Hz
frame_calidad = ttk.Frame(frame_controles, style='TFrame')
frame_calidad.grid(row=1, column=0, pady=4, sticky='ew')
ttk.Label(frame_calidad, text="Calidad de audio:", style='TLabel').grid(
    row=0, column=0, padx=(0, 6), sticky='w'
)
combo_calidad = ttk.Combobox(
    frame_calidad, values=list(CALIDADES.keys()), state='readonly', width=15
)
combo_calidad.set(CALIDAD_PREDETERMINADA)
combo_calidad.grid(row=0, column=1, padx=(0, 12), sticky='w')

var_432hz = tk.BooleanVar(value=False)
icono_unchecked = cargar_icono(ICONOS["checkbox_unchecked"], size=(20, 20))
icono_checked = cargar_icono(ICONOS["checkbox_checked"], size=(20, 20))
if icono_unchecked and icono_checked:
    def alternar_432hz():
        var_432hz.set(not var_432hz.get())
        boton_432hz.config(
            image=icono_checked if var_432hz.get() else icono_unchecked
        )

    boton_432hz = ttk.Button(
        frame_calidad, image=icono_unchecked, command=alternar_432hz,
        style='Toggle.TButton',
    )
    boton_432hz.grid(row=0, column=2, padx=(0, 6), sticky='w')
    ttk.Label(frame_calidad, text="Convertir a 432 Hz",
              style='TLabel').grid(row=0, column=3, sticky='w')
else:
    ttk.Checkbutton(frame_calidad, text="Convertir a 432 Hz",
                    variable=var_432hz).grid(row=0, column=2, sticky='w')

# Añadir enlaces
frame_agregar = ttk.Frame(frame_controles, style='TFrame')
frame_agregar.grid(row=2, column=0, pady=4, sticky='ew')
frame_agregar.columnconfigure(0, weight=1)
entrada_url = ttk.Entry(frame_agregar)
entrada_url.grid(row=0, column=0, sticky='ew', padx=(0, 8), ipady=3)
entrada_url.bind('<Return>', agregar_desde_entrada)
icono_agregar = cargar_icono(ICONOS["agregar"])
boton_agregar_texto = ttk.Button(
    frame_agregar, text="Agregar", command=agregar_desde_entrada,
    style='Agregar.TButton', image=icono_agregar, compound='left',
)
boton_agregar_texto.grid(row=0, column=1, padx=(0, 8))
boton_agregar = ttk.Button(
    frame_agregar, text="Desde portapapeles", command=agregar_desde_portapapeles,
    style='Agregar.TButton',
)
boton_agregar.grid(row=0, column=2)

# Botones principales
frame_botones = ttk.Frame(frame_controles, style='TFrame')
frame_botones.grid(row=3, column=0, pady=4, sticky='ew')
icono_descargar = cargar_icono(ICONOS["descargar"])
boton_descargar = ttk.Button(
    frame_botones, text="Descargar pendientes", command=descargar_todos,
    style='TButton', image=icono_descargar, compound='left',
)
boton_descargar.grid(row=0, column=0, padx=(0, 8), sticky='w')
icono_carpeta2 = cargar_icono(ICONOS["carpeta"])
boton_abrir_carpeta = ttk.Button(
    frame_botones, text="Abrir carpeta", command=abrir_carpeta_destino,
    style='AbrirCarpeta.TButton', image=icono_carpeta2, compound='left',
)
boton_abrir_carpeta.grid(row=0, column=1, sticky='w')
frame_botones.columnconfigure(2, weight=1)

# Barra de estado
frame_estado = ttk.Frame(frame_controles, style='TFrame')
frame_estado.grid(row=4, column=0, pady=(4, 0), sticky='ew')
frame_estado.columnconfigure(0, weight=1)
label_estado_app = ttk.Label(frame_estado, text="", style='TLabel', anchor='w')
label_estado_app.grid(row=0, column=0, sticky='ew')

# Aviso de actualización de la aplicación
frame_actualizacion = ttk.Frame(frame_controles, style='TFrame')
frame_actualizacion.grid(row=5, column=0, pady=(4, 0), sticky='ew')
frame_actualizacion.columnconfigure(0, weight=1)
label_actualizacion = ttk.Label(
    frame_actualizacion, text="", style='TLabel', anchor='w'
)
label_actualizacion.grid(row=0, column=0, sticky='ew')
boton_actualizar = ttk.Button(
    frame_actualizacion, text="Actualizar", command=_actualizar_app_click,
    style='Agregar.TButton',
)
boton_actualizar.grid(row=0, column=1, padx=(8, 0))
frame_actualizacion.grid_remove()

# --- Lista con scroll ---
frame_lista = ttk.Frame(ventana, style='TFrame')
frame_lista.grid(row=1, column=0, sticky='nsew', pady=8, padx=12)
frame_lista.columnconfigure(0, weight=1)
frame_lista.rowconfigure(0, weight=1)

canvas = tk.Canvas(frame_lista, bg=FONDO, highlightthickness=0,
                   yscrollincrement=24)
canvas.grid(row=0, column=0, sticky='nsew')
scrollbar = ttk.Scrollbar(frame_lista, orient='vertical', command=canvas.yview)
scrollbar.grid(row=0, column=1, sticky='ns')
canvas.configure(yscrollcommand=scrollbar.set)

lista_frame = ttk.Frame(canvas, style='TFrame')
lista_frame.columnconfigure(0, weight=1)
_lista_id = canvas.create_window((0, 0), window=lista_frame, anchor='nw')

lista_frame.bind(
    '<Configure>',
    lambda e: canvas.configure(scrollregion=canvas.bbox('all')),
)


def _ajustar_ancho_lista(evento):
    canvas.itemconfigure(_lista_id, width=evento.width)


canvas.bind('<Configure>', _ajustar_ancho_lista)


def _rueda_raton(evento):
    # Solo desplaza si el puntero está sobre la lista
    widget = ventana.winfo_containing(
        ventana.winfo_pointerx(), ventana.winfo_pointery()
    )
    while widget is not None:
        if widget is canvas:
            canvas.yview_scroll(int(-evento.delta / 120), 'units')
            return 'break'
        widget = getattr(widget, 'master', None)


ventana.bind_all('<MouseWheel>', _rueda_raton)
ventana.bind_all('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
ventana.bind_all('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))


def _tecla_flecha(evento):
    widget = evento.widget
    if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox)):
        return
    canvas.yview_scroll(-1 if evento.keysym == 'Up' else 1, 'units')


ventana.bind_all('<Up>', _tecla_flecha)
ventana.bind_all('<Down>', _tecla_flecha)

# --- Pie de página ---
label_copyright = tk.Label(
    ventana,
    text=f"Copyright © 2025 Bochi · v{APP_VERSION}",
    bg=FONDO,
    fg='#aaaaaa',
    font=('Helvetica', 9),
)
label_copyright.grid(row=2, column=0, sticky='e', padx=14, pady=(0, 6))

# --- Estado inicial ---
actualizar_botones()
ventana.after(80, _procesar_cola)


def _al_cerrar():
    for item in lista_descargas:
        item['cancel'].set()
    try:
        ventana.destroy()
    except tk.TclError:
        pass


ventana.protocol('WM_DELETE_WINDOW', _al_cerrar)


def _revisar_ffmpeg():
    if not ffmpeg_disponible():
        messagebox.showwarning(
            "FFmpeg no encontrado",
            mensaje_ffmpeg_faltante() + "\n\nLas descargas no funcionarán.",
        )


ventana.after(300, _revisar_ffmpeg)
ventana.after(1500, lambda: threading.Thread(
    target=_comprobar_actualizaciones, args=(False,), daemon=True
).start())
ventana.mainloop()
