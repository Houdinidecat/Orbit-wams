# Órbita · Registro de misiones

Aplicación académica de exploración espacial con una interfaz en español y una base de datos SQLite para consultar, agregar, editar y eliminar misiones.

- **Curso:** Conceptualización de servicios en la nube
- **Estudiante:** Elena Aurora Islas Martinez
- **Código:** 212487959
- **Contacto:** auroraislasmtz@gmail.com

## Ejecutar en tu computadora

Necesitas Python 3.12 o posterior. Extrae el proyecto completo y abre PowerShell en su carpeta principal. Ejecuta estos comandos, uno por uno:

    py -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe app.py

Abre **http://localhost:8080** y elige **Registro de misiones**, o visita **http://localhost:8080/registro.html**. Mantén PowerShell abierto mientras usas la aplicación; presiona Ctrl+C para detenerla. Los comandos no requieren activar el entorno virtual.

En macOS o Linux, usa "python3 -m venv .venv", ".venv/bin/python -m pip install -r requirements.txt" y ".venv/bin/python app.py".

Esta versión necesita el servidor de Python: abrir el HTML con doble clic no ejecuta las operaciones de la base de datos.

## Las cinco operaciones solicitadas

| Operación | Uso en la interfaz |
| --- | --- |
| Consultar todos los registros | La lista de misiones muestra los registros guardados; se puede actualizar. |
| Consultar un registro individual | La opción **Ver** abre el detalle de una misión. |
| Agregar registros | Completa el formulario de nueva misión y guarda. |
| Editar registros | Elige **Editar**, modifica el formulario y guarda los cambios. |
| Eliminar registros | Elige **Eliminar** y confirma la misión que deseas borrar. |

Los registros son de práctica compartidos y esta versión no incluye cuentas de usuario. Usa información de ejemplo. Los cambios se guardan en SQLite, no en el almacenamiento del navegador.

## Comprobar la aplicación

Después de instalar las dependencias, ejecuta `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` en Windows, o `.venv/bin/python -m unittest discover -s tests -v` en macOS/Linux. Las pruebas usan bases de datos temporales y comprueban las operaciones, la validación y la persistencia.

## Base de datos y archivos

schema.sql define la tabla **misiones**: id, nombre, destino, fecha, estado, notas, creado_en y actualizado_en. La aplicación prepara la base de datos al iniciar. Localmente, el archivo se guarda en **data/orbita.sqlite3**; puedes cambiar su ubicación con la variable DATABASE_PATH. Conserva ese archivo para mantener tus registros entre ejecuciones y no lo subas al repositorio.

| Archivo o carpeta | Función |
| --- | --- |
| app.py | Servidor Flask y API /api/misiones. |
| schema.sql | Estructura de la base de datos SQLite. |
| requirements.txt | Dependencias de Python. |
| dist/index.html | Página principal de Órbita. |
| dist/registro.html | Interfaz de consulta y gestión de registros. |
| dist/crud.js y dist/crud.css | Interacción y diseño del registro. |
| dist/assets/ | Logo e imagen de fondo. |
| dist/procedimiento.html y PROCEDIMIENTO.txt | Documentación de la actividad y fuentes. |
| Dockerfile y railway.toml | Ejecución del servidor en Railway. |

## Publicar en Railway

La estudiante realizará la publicación por separado. Este proyecto incluye configuración, pero esta entrega no ha ejecutado un despliegue.

1. Actualiza **Houdinidecat/Orbit** con el proyecto completo. **Conserva las carpetas dist/ y dist/assets/**; no pongas sus archivos sueltos en la raíz.
2. Si el repositorio aún tiene la versión anterior aplanada, retira sus antiguos index.html, styles.css, procedimiento.html, logo-orbita.svg y universo.jpg de la raíz, además de Staticfile. Sus versiones actuales están dentro de dist/. No subas .venv/ ni archivos de base de datos.
3. En Railway, crea un proyecto desde GitHub y selecciona ese repositorio. Autoriza a Railway a acceder cuando se solicite.
4. Mantén **Root Directory** en la raíz del repositorio. Railway utiliza el **Dockerfile**; no establezcas comandos personalizados de construcción o inicio. Si existía un despliegue estático, elimina sus antiguos ajustes.
5. Añade un **Volume** al servicio y establece su ruta de montaje en **/data**. La imagen configura **DATABASE_PATH=/data/orbita.sqlite3** para guardar allí la base de datos. El volumen es necesario para conservar los registros al volver a desplegar.
6. Mantén **una sola réplica** para esta aplicación SQLite. El endpoint de comprobación de salud es **/healthz**.
7. Despliega, revisa los registros del servicio y genera un dominio desde su configuración de red.
8. Abre la dirección publicada, prueba las cinco operaciones y comprueba que un registro siga disponible después de reiniciar el servicio.

GitHub guarda el código y Railway aloja la aplicación; no necesitas GitHub Pages. La nueva aplicación utiliza Python, Flask, HTML, CSS y JavaScript, en lugar del servidor estático de la primera versión.

## Fuentes y créditos

- [Railway — Quick Start Tutorial](https://docs.railway.com/quick-start), recurso de introducción equivalente a “Getting Started”.
- [Railway — Dockerfiles](https://docs.railway.com/builds/dockerfiles).
- [Railway — Using Volumes](https://docs.railway.com/volumes).
- Imagen de fondo: [NASA, PIA12348 — Great Observatories Unique Views of the Milky Way](https://images.nasa.gov/details/PIA12348).

El logo es una ilustración vectorial original creada para la actividad. Órbita es un proyecto académico y no representa a NASA.
