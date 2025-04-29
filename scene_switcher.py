import win32file
import win32pipe
import json
import time
import os
import psutil
import logging
import sys
from logging.handlers import RotatingFileHandler
import yaml
import traceback
from datetime import datetime

# Configuración del sistema de logging
def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"scene_switcher_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configurar el logger principal
    logger = logging.getLogger("SceneSwitcher")
    logger.setLevel(logging.DEBUG)
    
    # Crear un manejador para archivos con rotación (10 archivos de 5MB cada uno)
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=10)
    file_handler.setLevel(logging.DEBUG)
    
    # Crear un manejador para la consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Formato detallado para el archivo
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Formato simplificado para la consola
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Agregar los manejadores al logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Clase para monitorear los recursos del sistema
class ResourceMonitor:
    def __init__(self, logger, check_interval=60):
        self.logger = logger
        self.check_interval = check_interval
        self.last_check = time.time()
        self.process = psutil.Process(os.getpid())
    
    def check_resources(self):
        if time.time() - self.last_check >= self.check_interval:
            try:
                # Memoria usada por este proceso
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                # CPU usado por este proceso
                cpu_percent = self.process.cpu_percent(interval=0.5)
                
                # Memoria total del sistema
                system_memory = psutil.virtual_memory()
                system_memory_percent = system_memory.percent
                
                self.logger.debug(f"Recursos - Memoria: {memory_mb:.2f} MB ({memory_info.rss} bytes), "
                                 f"CPU: {cpu_percent:.1f}%, "
                                 f"Sistema: {system_memory_percent}% usado")
                
                # Advertencia si el uso es alto
                if memory_mb > 200:  # Más de 200MB
                    self.logger.warning(f"Alto uso de memoria: {memory_mb:.2f} MB")
                if cpu_percent > 10:  # Más del 10% de CPU
                    self.logger.warning(f"Alto uso de CPU: {cpu_percent:.1f}%")
                
                self.last_check = time.time()
            except Exception as e:
                self.logger.error(f"Error monitoreando recursos: {e}")

# Cargar configuración desde archivo YAML
def load_config(logger):
    config_file = "scene_switcher_config.yaml"
    default_config = {
        "pipe_name": r"\\.\pipe\slobs",
        "processes": {
            "League of Legends.exe": ["In game", "Fuera de juego"]
        },
        "check_interval": 1,
        "reconnect_attempts": 5,
        "reconnect_delay": 2
    }
    
    # Si no existe el archivo, crear uno con la configuración por defecto
    if not os.path.exists(config_file):
        logger.info(f"Archivo de configuración no encontrado. Creando uno nuevo en {config_file}")
        try:
            with open(config_file, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error creando archivo de configuración: {e}")
            return default_config
    
    # Cargar configuración desde el archivo
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            logger.info("Configuración cargada correctamente")
            return config
    except Exception as e:
        logger.error(f"Error cargando configuración: {e}. Usando configuración por defecto.")
        return default_config

class SceneSwitcher:
    def __init__(self, config, logger):
        self.logger = logger
        self.config = config
        self.pipe_name = config["pipe_name"]
        self.executable_to_scene = {
            exe: (scenes[0], scenes[1]) 
            for exe, scenes in config["processes"].items()
        }
        self.scene_states = {exe: False for exe in self.executable_to_scene}
        self.pipe = None
        self.reconnect_attempts = config.get("reconnect_attempts", 5)
        self.reconnect_delay = config.get("reconnect_delay", 2)
        self.check_interval = config.get("check_interval", 1)
        self.resource_monitor = ResourceMonitor(logger)
        
        # Variables para controlar reconexiones
        self.failed_connections = 0
        self.last_connection_attempt = 0
        self.running = True

    def connect_pipe(self):
        # Limitar reintentos de conexión
        if self.failed_connections >= self.reconnect_attempts:
            self.logger.critical(f"Alcanzado límite de {self.reconnect_attempts} intentos de reconexión. "
                                 f"Esperando 60 segundos antes de reintentar.")
            time.sleep(60)
            self.failed_connections = 0
        
        # Esperar entre reintentos
        if self.failed_connections > 0:
            delay = self.reconnect_delay * self.failed_connections
            self.logger.info(f"Esperando {delay}s antes de reintentar conexión (intento {self.failed_connections+1})")
            time.sleep(delay)
        
        try:
            self.logger.info(f"Intentando conectar a SLOBS Pipe: {self.pipe_name}")
            self.pipe = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            self.logger.info("Conectado exitosamente a SLOBS Pipe")
            self.failed_connections = 0
            return True
        except Exception as e:
            self.failed_connections += 1
            self.logger.error(f"Error conectando a SLOBS Pipe: {e}")
            if self.failed_connections >= self.reconnect_attempts:
                self.logger.warning("¿Está SLOBS en ejecución? Asegúrate que esté abierto.")
            return False

    def send_json(self, data):
        if self.pipe is None:
            if not self.connect_pipe():
                return False
                
        try:
            payload = (json.dumps(data) + "\n").encode('utf-8')
            win32file.WriteFile(self.pipe, payload)
            return True
        except Exception as e:
            self.logger.error(f"Fallo enviando datos: {e}")
            self.pipe = None
            return False

    def read_json(self):
        data = b""
        try:
            while True:
                part = win32file.ReadFile(self.pipe, 4096)[1]
                data += part
                if b"\n" in part:
                    break
            decoded = data.decode('utf-8').strip()
            return json.loads(decoded)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parseando JSON: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Fallo leyendo datos: {e}")
            self.pipe = None
            return None

    def get_scene_id(self, scene_name):
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            if self.send_json({
                "method": "getScenes",
                "params": {
                    "resource": "ScenesService"
                },
                "id": 1
            }):
                response = self.read_json()
                if response and 'result' in response:
                    for scene in response['result']:
                        if scene['name'] == scene_name:
                            return scene['id']
                    self.logger.warning(f"No encontré la escena '{scene_name}'")
                    return None
            
            retry_count += 1
            if retry_count < max_retries:
                self.logger.warning(f"Reintentando obtener ID de escena ({retry_count}/{max_retries})...")
                time.sleep(1)
            
        self.logger.error(f"No se pudo obtener el ID para la escena '{scene_name}' después de {max_retries} intentos")
        return None

    def switch_scene(self, scene_name):
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            # 1. Pedir todas las escenas
            if not self.send_json({
                "method": "getScenes",
                "params": {
                    "resource": "ScenesService",
                    "args": []
                },
                "id": 99
            }):
                retry_count += 1
                continue
                
            scenes_response = self.read_json()

            # 2. Buscar la escena por nombre
            target_scene_id = None
            if scenes_response and "result" in scenes_response:
                for scene in scenes_response["result"]:
                    if scene.get("name") == scene_name:
                        target_scene_id = scene.get("id")
                        break

            if not target_scene_id:
                self.logger.warning(f"No encontré la escena '{scene_name}' en SLOBS.")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1)
                continue

            # 3. Hacer el cambio de escena usando el ID
            if not self.send_json({
                "method": "makeSceneActive",
                "params": {
                    "resource": "ScenesService",
                    "args": [target_scene_id]
                },
                "id": 100
            }):
                retry_count += 1
                continue
                
            ack = self.read_json()
            if ack and ack.get("error") is None:
                self.logger.info(f"Cambié correctamente a la escena: {scene_name}")
                return True
            else:
                self.logger.error(f"No se pudo cambiar a la escena '{scene_name}'. Respuesta: {ack}")
                retry_count += 1
                
            if retry_count < max_retries:
                time.sleep(1)
                
        self.logger.error(f"No se pudo cambiar a la escena '{scene_name}' después de {max_retries} intentos")
        return False

    def is_process_running(self, process_name):
        """Verifica si un proceso específico está en ejecución"""
        try:
            return any(proc.name().lower() == process_name.lower() for proc in psutil.process_iter())
        except Exception as e:
            self.logger.error(f"Error verificando proceso {process_name}: {e}")
            return False

    def monitor(self):
        self.logger.info("Iniciando monitoreo de procesos. Presiona Ctrl-C para salir.")
        last_status_log = time.time()
        
        try:
            while self.running:
                current_time = time.time()
                
                # Verificar recursos del sistema periódicamente
                self.resource_monitor.check_resources()
                
                # Registrar estado cada 5 minutos
                if current_time - last_status_log > 300:  # 5 minutos
                    self.logger.info("Estado: Monitoreo activo, conexión con SLOBS " + 
                                   ("ACTIVA" if self.pipe is not None else "INACTIVA"))
                    states = [f"{exe}:{'ACTIVO' if self.scene_states[exe] else 'INACTIVO'}" 
                             for exe in self.executable_to_scene]
                    self.logger.info(f"Procesos: {', '.join(states)}")
                    last_status_log = current_time
                
                # Verificar cada proceso configurado
                for exe_name, (scene_up, scene_down) in self.executable_to_scene.items():
                    running = self.is_process_running(exe_name)
                    
                    if running and not self.scene_states[exe_name]:
                        self.logger.info(f"{exe_name} detectado. Cambiando a '{scene_up}'...")
                        if self.switch_scene(scene_up):
                            self.scene_states[exe_name] = True
                        
                    elif not running and self.scene_states[exe_name]:
                        self.logger.info(f"{exe_name} cerrado. Cambiando a '{scene_down}'...")
                        if self.switch_scene(scene_down):
                            self.scene_states[exe_name] = False
                            
                # Esperar antes del siguiente ciclo
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Finalización solicitada por el usuario (Ctrl+C)")
        except Exception as e:
            self.logger.critical(f"Error crítico en el monitoreo: {e}")
            self.logger.debug(f"Detalles: {traceback.format_exc()}")
        finally:
            if self.pipe:
                try:
                    win32file.CloseHandle(self.pipe)
                    self.logger.info("Conexión con SLOBS cerrada correctamente")
                except:
                    pass
            self.logger.info("Monitoreo finalizado")

def main():
    # Inicializar el logger
    logger = setup_logging()
    logger.info("=== Scene Switcher para SLOBS iniciado ===")
    
    try:
        # Intentar importar las librerías requeridas
        required_libs = ['win32file', 'win32pipe', 'psutil', 'yaml']
        missing_libs = []
        
        for lib in required_libs:
            try:
                __import__(lib)
            except ImportError:
                missing_libs.append(lib)
        
        if missing_libs:
            logger.critical(f"Librerías requeridas no encontradas: {', '.join(missing_libs)}")
            logger.info("Instala las librerías usando: pip install " + " ".join(missing_libs))
            return
            
        # Cargar configuración
        config = load_config(logger)
        
        # Verificar configuración
        if not config["processes"]:
            logger.warning("No hay procesos configurados para monitorear. "
                          "Edita el archivo scene_switcher_config.yaml")
            return
            
        # Iniciar el monitor
        switcher = SceneSwitcher(config, logger)
        
        # Intentar la conexión inicial
        if not switcher.connect_pipe():
            logger.warning("No se pudo conectar inicialmente a SLOBS. "
                          "Asegúrate que Streamlabs OBS esté en ejecución.")
        
        # Iniciar monitoreo
        switcher.monitor()
    
    except Exception as e:
        logger.critical(f"Error al iniciar Scene Switcher: {e}")
        logger.debug(f"Detalles del error: {traceback.format_exc()}")
    
    logger.info("=== Scene Switcher para SLOBS finalizado ===")

if __name__ == "__main__":
    main()