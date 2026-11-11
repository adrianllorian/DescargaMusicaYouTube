<p align="center">
  <img src="iconos/logo.png" alt="Videos MP3 Downloader" width="120">
</p>

<h1 align="center">Videos MP3 Downloader</h1>

<p align="center">
  Descarga el audio de YouTube en MP3, elige la calidad y conviértelo opcionalmente a 432 Hz.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/versi%C3%B3n-v1.1-blue?style=flat-square" alt="Versión">
  <img src="https://img.shields.io/badge/Windows-10%2F11-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/descarga-101%20MB-2ea44f?style=flat-square" alt="Tamaño">
  <img src="https://img.shields.io/badge/licencia-Apache%202.0-yellow?style=flat-square" alt="Licencia">
</p>

<p align="center">
  <a href="https://github.com/adrianllorian/DescargaMusicaYouTube/releases/latest/download/Videos.MP3.Downloader.exe">
    <img src="https://img.shields.io/badge/Descargar_para_Windows-2ea44f?style=for-the-badge&logo=windows&logoColor=white" alt="Descargar para Windows">
  </a>
</p>

<p align="center">
  <strong>Windows 10/11 · 64 bits · 101 MB · sin instalación</strong>
</p>

---

## Vista previa

<p align="center">
  <img src="docs/screenshot.png" alt="Captura de Videos MP3 Downloader" width="860">
</p>

## Características

- Descarga audio de YouTube en **MP3** con calidad de **64 a 320 kbps**.
- Conversión opcional a **432 Hz** manteniendo la duración.
- Lista de descargas con progreso, estado y cancelación.
- Descargas secuenciales para evitar saturar la conexión.
- Interfaz oscura en español, con miniaturas y detalles de error.
- **FFmpeg integrado** en el ejecutable: no requiere instalación aparte.
- Compatible con enlaces de YouTube, Shorts, `youtu.be` y YouTube Music.

## Descarga

Descarga la última versión desde **Releases**:

**[Videos MP3 Downloader v1.1](https://github.com/adrianllorian/DescargaMusicaYouTube/releases/latest)**

- Archivo: `Videos.MP3.Downloader.exe`
- Tamaño: 101 MB
- Sistema: Windows 10/11 de 64 bits
- No necesita instalador: se ejecuta directamente.

> Windows SmartScreen puede mostrar un aviso porque el ejecutable no está firmado digitalmente. Pulsa **Más información → Ejecutar de todas formas**.

### Verificar la descarga

SHA-256 del ejecutable:

```text
B3251A5BE7D3F35B0FBB8EAE94A5ADADA70C1EBDF59ECEB8D3B2E94DB71D3020
```

## Uso

1. Abre **Videos MP3 Downloader**.
2. Selecciona la carpeta de destino.
3. Escribe o pega un enlace de YouTube y pulsa **Agregar**.
4. Elige la calidad y, si quieres, activa **Convertir a 432 Hz**.
5. Pulsa **Descargar pendientes**.

Las descargas se hacen de una en una. Puedes cancelar una descarga con **Eliminar** y consultar el motivo de un error pulsando sobre el estado en rojo.

## Ejecutar desde el código fuente

Requisitos:

- Python 3.10 o superior.
- FFmpeg (ver la sección siguiente).
- Dependencias de Python:

```powershell
python -m pip install -r requirements.txt
python gui.py
```

## FFmpeg: enlaces y ubicación

El repositorio **no incluye FFmpeg** porque sus binarios superan los 180 MB. Hay que descargarlo antes de ejecutar desde el código o de compilar el `.exe`.

### Descargas

- Página oficial de FFmpeg:  
  https://ffmpeg.org/download.html
- Builds para Windows de Gyan (recomendado):  
  https://www.gyan.dev/ffmpeg/builds/
- Descarga directa, versión essentials (ZIP):  
  https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
- Descarga directa, versión full (7z):  
  https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z
- Alternativa, builds de BtbN en GitHub:  
  https://github.com/BtbN/FFmpeg-Builds/releases

> **Essentials** es la opción más ligera. **Full** incluye más filtros, entre ellos `rubberband`, que mejora la conversión a 432 Hz. Si falta `rubberband`, la aplicación usa un método alternativo y sigue funcionando.

### Dónde colocarlo

1. Descarga y descomprime el ZIP o 7z.
2. Dentro habrá una carpeta similar a `ffmpeg-8.0-essentials_build\bin`.
3. Copia `ffmpeg.exe` dentro de `ffmpeg\bin\` del proyecto.
4. Recomendado: copia también `ffprobe.exe` en la misma carpeta.
5. No necesitas `ffplay.exe`.

La ruta final debe quedar así:

```text
Descarga de youtube\
└── ffmpeg\
    └── bin\
        ├── ffmpeg.exe
        └── ffprobe.exe
```

Ejemplo completo:

```text
C:\Users\bochi\Documents\Mis Creaciones\Descarga de youtube\ffmpeg\bin\ffmpeg.exe
```

Comprueba que funciona:

```powershell
.\ffmpeg\bin\ffmpeg.exe -version
```

Si FFmpeg no está en esa ruta, la aplicación mostrará un aviso y no podrá descargar ni convertir el audio.

## Compilar el ejecutable

1. Instala Python 3.10 o superior y marca **Add Python to PATH**.
2. Coloca FFmpeg en `ffmpeg\bin\ffmpeg.exe`.
3. Ejecuta `compilar.bat` con doble clic.

También puedes compilar manualmente:

```powershell
python -m pip install --upgrade -r requirements.txt
python -m PyInstaller gui.spec --noconfirm
```

El resultado queda en:

```text
dist\Videos MP3 Downloader.exe
```

Notas:

- Cierra el programa antes de volver a compilar.
- La primera compilación tarda varios minutos.
- El `.exe` generado incluye FFmpeg, los iconos y las licencias.
- Para actualizar `yt-dlp` (recomendado si YouTube deja de funcionar):

```powershell
python -m pip install --upgrade yt-dlp
```

## Estructura del proyecto

```text
Descarga de youtube\
├── gui.py
├── funciones.py
├── config.py
├── gui.spec
├── compilar.bat
├── requirements.txt
├── README.md
├── LICENSE
├── iconos\
├── licenses\
├── docs\
│   └── screenshot.png
└── ffmpeg\bin\ffmpeg.exe   (no incluido en el repositorio)
```

## Tecnologías

- Python + Tkinter
- yt-dlp
- FFmpeg
- Pillow

## Aviso legal

Este software es solo para uso personal y educativo. No está afiliado con YouTube ni con sus propietarios. Descarga únicamente contenido que tengas derecho a usar (propio o con licencia). El autor no se hace responsable del uso que se haga del programa.

Iconos de Flaticon: sonnycandra, Pixel perfect, Freepik y customicondesign_1.

## Licencia

Distribuido bajo **Apache License 2.0**. Consulta [LICENSE](LICENSE) y la carpeta [`licenses`](licenses).

---

<p align="center">
  Copyright © 2025 Bochi
</p>
