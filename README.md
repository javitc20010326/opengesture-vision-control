# OPENGESTURE

Proyecto local para convertir la camara del laptop en un controlador IA por gestos, cara, voz y analisis corporal BODY. Incluye una app web LAN para configurarlo desde el movil.

Detecta:

- Mano cerrada en punio acercandose a camara: zoom in.
- Mano cerrada en punio alejandose de camara: zoom out.
- Mano abierta hacia arriba: scroll hacia arriba.
- Mano abierta hacia abajo: scroll hacia abajo.
- Mano abierta apuntando a la derecha: mueve el cursor a la derecha.
- Mano abierta apuntando a la izquierda: mueve el cursor a la izquierda.

El prototipo usa:

- Python
- OpenCV para la camara
- MediaPipe para detectar la mano
- PyAutoGUI para mandar scroll y atajos de teclado al sistema

Modos:

- `GESTURE`: manos, dos manos, pinza, scroll, cursor, zoom y trayectorias.
- `FACE`: cara, posicion, nariz, sonrisa, ojo izquierdo/derecho abierto o cerrado y mirada aproximada.
- `BODY`: solo analisis corporal, sin controlar pantalla. Dibuja esqueleto, centro de gravedad, trayectorias de manos/pies y un digital twin basico lateral.

## 1. Requisitos

Necesitas Python 3.10, 3.11 o 3.12 instalado en Windows.

Compruebalo en PowerShell:

```powershell
python --version
```

Si no existe, instala Python desde:

https://www.python.org/downloads/windows/

Durante la instalacion marca la opcion `Add python.exe to PATH`.

## 2. Crear entorno e instalar dependencias

Desde esta carpeta:

```powershell
.\setup.ps1
```

O manualmente:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activacion del entorno:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## 3. Probar solo el visualizador

Primero ejecuta sin controlar la pantalla:

```powershell
.\run.ps1
```

Se abrira una ventana de camara. Pulsa `q` para salir.

## 4. Lanzar por atajo E+R

Para poder abrir/cerrar la camara con teclado tiene que quedar activo el lanzador:

```powershell
.\launcher.ps1
```

Con el lanzador abierto:

- `E+R`: abre el visualizador y activa la camara.
- `E+R` otra vez: cierra el visualizador y apaga la camara.

Si quieres que `E+R` funcione despues de reiniciar Windows, crea un acceso directo a `launcher.ps1` en la carpeta de inicio de Windows.

Tambien puedes instalarlo automaticamente en el inicio de Windows:

```powershell
.\install-startup.ps1
```

## 5. Activar control de pantalla

Cuando el visualizador este abierto, el control de pantalla empieza apagado. Activalo con:

```powershell
D+F
```

Controles:

- Mano abierta hacia arriba: scroll arriba.
- Mano abierta hacia abajo: scroll abajo.
- Mano abierta apuntando a la derecha: cursor a la derecha.
- Mano abierta apuntando a la izquierda: cursor a la izquierda.
- Punio acercandose a la camara: zoom in.
- Punio alejandose de la camara: zoom out.
- Tecla `c`: activa/desactiva el control mientras la app esta abierta.
- Teclas `D+F`: activa/desactiva el control aunque la ventana de camara no este enfocada.
- Tecla `q`: salir.

Recomendacion de uso: arranca `.\launcher.ps1`, pulsa `E+R` para abrir camara, deja una pagina o app abierta para probar scroll, pulsa `D+F` para activar control, y vuelve a pulsar `D+F` para apagarlo.

## 6. Web local de configuracion

Arranca la web de configuracion:

```powershell
.\config-server.ps1
```

Abre:

```text
http://127.0.0.1:8765
```

Desde ahi puedes cambiar:

- Atajo de camara, por ejemplo `E+R`.
- Atajo de control, por ejemplo `D+F`.
- Activar/desactivar scroll, zoom o cursor.
- Boton para abrir/cerrar camara.
- Boton para activar/desactivar control.
- Modo de vision: `GESTURE`, `FACE` o `BODY`.
- Pantalla de camara remota para ver el visualizador desde el movil.
- Touchpad remoto para mover el cursor desde el movil, con click y click derecho.
- Acciones por gesto: click, doble click, click derecho, zoom, cerrar ventana, ver escritorio, cambiar ventana, Escape, Enter, cursor y scroll.
- Velocidad y suavidad del scroll.
- Velocidad del cursor.
- Sensibilidad del zoom.
- Camara y modo espejo.

Gestos soportados:

- Una mano abierta arriba, abajo, izquierda, derecha y diagonales.
- Pinza con pulgar e indice.
- Punio acercandose o alejandose.
- Dos manos alejandose o acercandose.
- Ambas manos haciendo pinza.
- Una mano arriba y otra abajo.

Mejoras avanzadas disponibles:

- Mouse aereo 2D: el cursor puede seguir la posicion real de la mano.
- Drag and drop: pinza mantenida puede mantener click pulsado y arrastrar.
- Scroll horizontal para hojas, timelines y editores.
- Perfiles: navegacion, presentacion, multimedia y mouse aereo.
- Modo presentacion: siguiente/anterior slide.
- Modo multimedia: volumen, mute, play/pause y pista siguiente/anterior.
- Dashboard en vivo: gesto, accion, FPS, mano detectada y palma/reverso.
- Calibracion guiada desde la web.
- Voz desde navegador compatible en PC o movil: activar/apagar control, abrir/cerrar camara, cambiar perfil y cambiar modo.
- Trayectoria configurable de mano y dedos durante X segundos.
- Overlay con flechas de direccion de cada dedo.
- Deteccion aproximada de palma frente a reverso de la mano.
- FACE: landmarks de cara, nariz, sonrisa, ojo cerrado y mirada.
- BODY: trayectorias de manos/pies, centro de gravedad y digital twin basico para caminar, correr, bailar o ejercicios con mancuernas.

La web tambien queda expuesta en la red local. Mira `/api/status` o la salida del servidor para ver la URL LAN, por ejemplo:

```text
http://192.168.1.193:8765
```

Si desde el movil no carga, abre PowerShell como administrador y ejecuta:

```powershell
netsh advfirewall firewall add rule name="Gesture Config Web 8765" dir=in action=allow protocol=TCP localport=8765
```

## 7. Consejos de calibracion

- Usa buena luz frontal.
- Manten una sola mano visible.
- Coloca la mano completa dentro de la imagen.
- Si se activa demasiado rapido, sube `--cooldown`.
- Si el scroll va muy lento o muy rapido, ajusta `--scroll-amount`.

Ejemplo:

```powershell
.\run.ps1 -Control -ScrollAmount 2112 -Cooldown 0.35
```

El scroll por defecto ahora es `2112` unidades por segundo, unas 22 veces mas rapido que la version anterior, pero repartido en pasos pequenos para que sea mas suave.

## 8. Limitaciones del prototipo

La camara 2D no entiende perfectamente la profundidad ni la rotacion real de la palma. En este prototipo, "abierta hacia arriba" significa dedos apuntando hacia arriba en la imagen, y "abierta hacia abajo" significa dedos apuntando hacia abajo. Es fiable para empezar y se puede mejorar con calibracion personalizada.

## 9. Publicar en GitHub

Repo sugerido:

```text
opengesture-vision-control
```

Publicacion directa con token local:

```powershell
.\publish-github.ps1
```

El script pide un GitHub Personal Access Token con permiso `repo`, crea el repositorio en tu cuenta y sube los archivos del proyecto. No sube `.venv`, logs, PID, frame de camara ni configuracion runtime personal.
