README.txt
==========
Videos MP3 Downloader - v1.1
Copyright (c) 2025 Bochi

Instrucciones:
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

Código fuente:
Repositorio: https://github.com/adrianllorian/DescargaMusicaYouTube

Para ejecutar desde el código:
1. python -m pip install -r requirements.txt
2. Descarga FFmpeg y coloca el ejecutable en ffmpeg\bin\ffmpeg.exe
3. python gui.py

El repositorio no incluye FFmpeg, build ni dist por su tamaño.

Aviso legal:
- Este software es para uso personal.
- No está afiliado con YouTube.
- Solo usa contenido que tengas derecho a descargar (propio o con licencia).
- Iconos de Flaticon - Diseñados por sonnycandra, Pixel perfect, Freepik y customicondesign_1 (https://www.flaticon.com).
- Licencias en la carpeta 'licenses'.

Compilar el ejecutable:
1. Instala Python 3.10 o superior (marca "Add Python to PATH").
2. Haz doble clic en "compilar.bat".
3. Al terminar, el ejecutable estará en:
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

