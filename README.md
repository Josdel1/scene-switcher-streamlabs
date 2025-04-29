# SLOBS Scene Switcher

Un cambiador automático de escenas para Streamlabs OBS (SLOBS) que monitorea procesos del sistema y cambia entre escenas al detectar el inicio o cierre de aplicaciones específicas.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

## Características

- Cambia automáticamente entre escenas cuando se inicia o cierra un juego específico
- Configuración sencilla mediante un archivo YAML externo
- Sistema de registro (logging) completo para facilitar el diagnóstico
- Monitoreo de recursos del sistema
- Reconexión automática con SLOBS
- Diseñado para ser estable durante streams de larga duración (4-6+ horas)

## Requisitos

- Windows 10/11
- Python 3.7+
- Streamlabs OBS instalado y configurado con tus escenas
- Las siguientes librerías de Python:
  - pywin32
  - psutil
  - pyyaml

## Instalación

1. Clona este repositorio o descarga los archivos
   ```
   git clone https://github.com/TU_USUARIO/slobs-scene-switcher.git
   ```

2. Instala las dependencias requeridas
   ```
   pip install pywin32 psutil pyyaml
   ```

3. Asegúrate de tener las escenas configuradas en Streamlabs OBS

## Configuración

Edita el archivo `scene_switcher_config.yaml` para configurar los procesos que deseas monitorear:

```yaml
# Ruta del pipe para comunicación con SLOBS
pipe_name: \\.\pipe\slobs

# Procesos a monitorear
# Formato: "nombre_ejecutable.exe": ["escena_cuando_activo", "escena_cuando_inactivo"]
processes:
  "League of Legends.exe": ["In game", "Fuera de juego"]
  # Añade más programas según necesites
  # "valorant.exe": ["Jugando Valorant", "Main Scene"]

# Intervalo de verificación en segundos
check_interval: 1

# Configuración de reconexión
reconnect_attempts: 5
reconnect_delay: 2
```

## Uso

1. Primero, asegúrate de iniciar Streamlabs OBS

2. Luego ejecuta el script:
   ```
   python scene_switcher_mejorado.py
   ```

3. El script detectará automáticamente cuando inicies o cierres los programas configurados y cambiará a las escenas correspondientes

4. Para detener el script, presiona `Ctrl+C` en la ventana de la consola

## Solución de problemas

Si experimentas problemas:

1. Verifica los logs en la carpeta `logs/` para información detallada
2. Asegúrate que SLOBS esté abierto antes de iniciar el script
3. Confirma que los nombres de las escenas en tu configuración coincidan exactamente con los nombres en SLOBS
4. Verifica que los nombres de los ejecutables estén correctos, incluyendo la extensión `.exe`

Error común: "Error conectando a SLOBS Pipe"
- Causa usual: SLOBS no está en ejecución o fue iniciado después del script
- Solución: Inicia SLOBS primero, luego ejecuta el script

## Personalización

### Añadir más aplicaciones para monitorear

Simplemente añade nuevas entradas en la sección `processes` del archivo de configuración:

```yaml
processes:
  "League of Legends.exe": ["In game", "Fuera de juego"]
  "discord.exe": ["Discord Scene", "Main Scene"]
  "chrome.exe": ["Browser Scene", "Main Scene"]
```

### Cambiar el intervalo de verificación

Modifica el valor de `check_interval` en el archivo de configuración (en segundos):

```yaml
check_interval: 0.5  # Verificar cada medio segundo
```

## Registro de cambios

- **v1.0.0** - Versión inicial
- **v1.1.0** - Mejoras de estabilidad y configuración externa

## Contribuir

Las contribuciones son bienvenidas! Si tienes ideas para mejorar esta herramienta:

1. Haz un fork del repositorio
2. Crea una rama para tu característica (`git checkout -b feature/nueva-caracteristica`)
3. Haz commit de tus cambios (`git commit -m 'Añade nueva característica'`)
4. Haz push a la rama (`git push origin feature/nueva-caracteristica`)
5. Abre un Pull Request

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## Agradecimientos

- Inspirado en la necesidad de automatizar cambios de escena durante streams de juegos
- Gracias a la comunidad de streamers por sus comentarios y sugerencias