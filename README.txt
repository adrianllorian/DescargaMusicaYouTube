README.txt
==========
Videos MP3 Downloader - v1.1
Copyright (c) 2025 Bochi

Repositorio:
https://github.com/adrianllorian/DescargaMusicaYouTube

Descripción:
Programa de escritorio para descargar el audio de videos de YouTube
como MP3, con selección de calidad y conversión opcional a 432 Hz.


USO DEL EJECUTABLE
------------------
1. Ejecuta "Videos MP3 Downloader.exe" (carpeta dist).
2. Selecciona una carpeta de destino.
3. Escribe o pega un enlace de YouTube y pulsa "Agregar"
   (o usa "Desde portapapeles").
4. Ajusta la calidad y, si quieres, activa "Convertir a 432 Hz".
5. Pulsa "Descargar pendientes".

Notas:
- Las descargas se hacen de una en una y pueden cancelarse con "Eliminar".
- Si algo falla, pulsa sobre el estado en rojo del elemento para ver el detalle.
- No cierres el programa durante una descarga.
- El .exe compilado ya incluye FFmpeg; no hace falta descargarlo aparte.


EJECUTAR DESDE EL CÓDIGO FUENTE
-------------------------------
Requisitos:
1. Python 3.10 o superior (marcar "Add Python to PATH").
2. FFmpeg (ver sección FFmpeg).
3. Instalar dependencias:
   python -m pip install -r requirements.txt

Ejecutar:
   python gui.py


FFMPEG: ENLACES Y UBICACIÓN
---------------------------
FFmpeg no se incluye en el repositorio porque sus binarios pesan
más de 180 MB. Hay que descargarlo antes de ejecutar el código
o de compilar el .exe.

Enlaces de descarga:
- Página oficial de FFmpeg (Windows):
  https://ffmpeg.org/download.html

- Builds para Windows de Gyan (recomendado):
  https://www.gyan.dev/ffmpeg/builds/

- Descarga directa, versión essentials (ZIP):
  https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

- Descarga directa, versión full (7z):
  https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z

- Alternativa: builds de BtbN en GitHub:
  https://github.com/BtbN/FFmpeg-Builds/releases

Notas sobre la versión:
- Essentials (ZIP) es la opción más sencilla y ligera.
- Full (7z) incluye más filtros, entre ellos rubberband, que mejora
  la conversión a 432 Hz. Si falta rubberband, la aplicación usa un
  método alternativo y sigue funcionando.

Dónde se deja FFmpeg:
1. Descarga el ZIP o 7z y descomprímelo.
2. Dentro habrá una carpeta parecida a:
   ffmpeg-8.0-essentials_build\bin
3. Copia ffmpeg.exe dentro de la carpeta "ffmpeg\bin" del proyecto.
   La ruta final debe ser exactamente:
   ...\Descarga de youtube\ffmpeg\bin\ffmpeg.exe

   Ejemplo completo:
   C:\Users\bochi\Documents\Mis Creaciones\Descarga de youtube\ffmpeg\bin\ffmpeg.exe

4. Recomendado: copia también ffprobe.exe en esa misma carpeta.
5. No necesitas ffplay.exe.

Estructura esperada:
Descarga de youtube\
  ffmpeg\
    bin\
      ffmpeg.exe
      ffprobe.exe

Comprobar que FFmpeg funciona:
   .\ffmpeg\bin\ffmpeg.exe -version

Si FFmpeg no está en esa ruta, la aplicación mostrará un aviso y no
podrá descargar ni convertir el audio.


COMPILAR EL EJECUTABLE
----------------------
1. Instala Python 3.10 o superior (marcar "Add Python to PATH").
2. Coloca FFmpeg en ffmpeg\bin\ffmpeg.exe (ver sección FFmpeg).
3. Haz doble clic en "compilar.bat".
4. Al terminar, el ejecutable estará en:
   dist\Videos MP3 Downloader.exe

También se puede compilar a mano desde una terminal:
   python -m pip install --upgrade -r requirements.txt
   python -m PyInstaller gui.spec --noconfirm

Notas para compilar:
- Cierra el programa antes de volver a compilar.
- La primera compilación tarda varios minutos.
- El .exe incluye FFmpeg, los iconos y las licencias.
- Para actualizar yt-dlp (recomendado si YouTube deja de funcionar):
   python -m pip install --upgrade yt-dlp
  y vuelve a compilar.


AVISO LEGAL
-----------
- Este software es para uso personal.
- No está afiliado con YouTube.
- Solo usa contenido que tengas derecho a descargar (propio o con licencia).
- Iconos de Flaticon - Diseñados por sonnycandra, Pixel perfect,
  Freepik y customicondesign_1 (https://www.flaticon.com).
- Licencias en la carpeta "licenses" y en el archivo LICENSE.
