"""
JARVIS 2.0 - Asistente de Voz Futurista
Reescritura completa con arquitectura limpia, threading seguro y UI cinematografica.
TODOS los derechos reservados a el pseudonimo JiamiauStudios. no distribuir sin permiso. 
"""

import os, sys, time, json, datetime, threading, traceback
import requests
import xml.etree.ElementTree as ET
import pyautogui
import speech_recognition as sr
import customtkinter as ctk
import tkinter as tk
from groq import Groq
import pygame
import math
import webbrowser
import re
import subprocess
import winreg
import ctypes
import base64
import random
import socket

try:
    import psutil
    PSUTIL_OK = True
except:
    PSUTIL_OK = False

try:
    import cv2
    from PIL import Image, ImageTk
    OPENCV_OK = True
except:
    OPENCV_OK = False

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    TESSERACT_OK = True
except:
    TESSERACT_OK = False

try:
    import numpy as np
    NUMPY_OK = True
except:
    NUMPY_OK = False

# AirDrop modules
try:
    from modules.airdrop_manager import AirDropManager
    from modules.device_registry import DeviceRegistry
    AIRDROP_OK = True
except Exception as e:
    print(f"[AIRDROP] Modulo no disponible: {e}")
    AIRDROP_OK = False

os.chdir(os.path.dirname(os.path.abspath(__file__)))

GROQ_API_KEY = "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"
API_CLIMA = "66e2fc89cd549586ccb87fea887d62b5"
CIUDAD_CLIMA = "Costa Rica"
MODELO_LLM = "llama-3.3-70b-versatile"
MODELO_VISION = "qwen/qwen3.6-27b"

groq_client = Groq(api_key=GROQ_API_KEY)
pygame.mixer.init()

historial_chat = []
historial_cmd = []
VOZ = "em_alex"
KOKORO_OK = False
kokoro = None

try:
    from kokoro_onnx import Kokoro
    import soundfile as sf
    if os.path.exists("kokoro-v1.0.onnx") and os.path.exists("voices-v1.0.bin"):
        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        KOKORO_OK = True
        if hasattr(kokoro, "voices") and isinstance(kokoro.voices, dict):
            voces = list(kokoro.voices.keys())
            if VOZ not in voces:
                compat = [v for v in voces if v.startswith("em") or "alex" in v]
                if compat:
                    VOZ = compat[0]
except Exception as e:
    print(f"[TTS] Kokoro no disponible: {e}")

COMANDOS_DETENER = ["detente", "jarvis detente", "para", "jarvis para", "stop",
                      "silencio", "callate", "calla", "jarvis callate", "ya",
                      "basta", "detener", "interrumpe", "interrumpir"]

class Estado:
    def __init__(self):
        self.lock = threading.Lock()
        self.hablando = False
        self.interrumpir = False
        self.ventana_visible = False
        self.estado = "INICIALIZANDO"
        self.ultima_interaccion = 0
        self.base_x = 800
        self.base_y = 400
        self.conteo_audio = 0
        self.app = None

    def set_estado(self, s):
        with self.lock:
            self.estado = s

    def get_estado(self):
        with self.lock:
            return self.estado

    def set_hablando(self, v):
        with self.lock:
            self.hablando = v

    def get_hablando(self):
        with self.lock:
            return self.hablando

    def set_interrumpir(self, v):
        with self.lock:
            self.interrumpir = v

    def get_interrumpir(self):
        with self.lock:
            return self.interrumpir

    def tocar_interaccion(self):
        self.ultima_interaccion = time.time()

    def debe_escuchar(self):
        return time.time() - self.ultima_interaccion < 45

estado = Estado()


class CommandServer:
    """Servidor TCP para recibir comandos remotos de JarvisEnter"""
    
    def __init__(self, port=7777):
        self.port = port
        self.running = False
        self.server_socket = None
        self.thread = None
    
    def start(self):
        """Inicia el servidor en un hilo daemon"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('127.0.0.1', self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
            self.running = True
            
            self.thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.thread.start()
            
            print(f"[CMDSERVER] Servidor iniciado en puerto {self.port}")
            self.iniciar_analisis_continuo(); return True
        except Exception as e:
            print(f"[CMDSERVER] Error iniciando servidor: {e}")
            return False
    
    def _listen_loop(self):
        """Loop principal del servidor"""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[CMDSERVER] Error aceptando conexion: {e}")
    
    def _handle_client(self, client_socket):
        """Maneja una conexion de cliente"""
        try:
            data = client_socket.recv(1024).decode('utf-8').strip()
            response = self._process_command(data)
            client_socket.send(response.encode('utf-8'))
        except Exception as e:
            try:
                client_socket.send(f'{{"success": false, "error": "{str(e)}"}}'.encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()
    
    def _process_command(self, command):
        """Procesa un comando recibido"""
        cmd = command.upper().strip()
        
        # VISIBLE ON
        if cmd in ['VISIBLE ON', 'VISIBLE /ON', 'SHOW', 'ON']:
            estado.ventana_visible = True
            estado.tocar_interaccion()  # Resetear timeout para que no se oculte
            return json.dumps({
                'success': True,
                'message': 'Orbe de Jarvis visible',
                'action': 'visible_on'
            })
        
        # VISIBLE OFF
        elif cmd in ['VISIBLE OFF', 'VISIBLE /OFF', 'HIDE', 'OFF']:
            estado.ventana_visible = False
            return json.dumps({
                'success': True,
                'message': 'Orbe de Jarvis ocultado',
                'action': 'visible_off'
            })
        
        # STOP
        elif cmd in ['STOP', 'QUIT', 'EXIT', 'KILL']:
            print("[CMDSERVER] Comando STOP recibido, terminando Jarvis...")
            threading.Thread(target=self._shutdown, daemon=True).start()
            return json.dumps({
                'success': True,
                'message': 'Deteniendo Jarvis...',
                'action': 'stop'
            })
        
        # CLOSE CMD
        elif cmd in ['CLOSE CMD', 'CLOSECMD', 'CLOSE']:
            print("[CMDSERVER] Comando CLOSE CMD recibido, cerrando ventana CMD...")
            threading.Thread(target=self._close_cmd, daemon=True).start()
            return json.dumps({
                'success': True,
                'message': 'Cerrando ventana CMD y deteniendo Jarvis...',
                'action': 'close_cmd'
            })
        
        # RELOAD
        elif cmd in ['RELOAD', 'RESTART', 'REINICIAR']:
            print("[CMDSERVER] Comando RELOAD recibido, reiniciando Jarvis...")
            threading.Thread(target=self._reload, daemon=True).start()
            return json.dumps({
                'success': True,
                'message': 'Reiniciando Jarvis...',
                'action': 'reload'
            })
        
        # STATUS
        elif cmd in ['STATUS', 'ESTADO']:
            return json.dumps({
                'success': True,
                'status': estado.get_estado(),
                'hablando': estado.get_hablando(),
                'ventana_visible': estado.ventana_visible,
                'action': 'status'
            })
        
        # HELP
        elif cmd in ['HELP', 'AYUDA', '?']:
            return json.dumps({
                'success': True,
                'commands': [
                    'VISIBLE ON  - Muestra el orbe',
                    'VISIBLE OFF - Oculta el orbe',
                    'STOP        - Detiene Jarvis',
                    'CLOSE CMD   - Cierra CMD (Jarvis sigue corriendo)',
                    'RELOAD      - Reinicia Jarvis',
                    'STATUS      - Muestra estado',
                    'HELP        - Muestra esta ayuda'
                ],
                'action': 'help'
            })
        
        else:
            return json.dumps({
                'success': False,
                'error': f'Comando no reconocido: {command}',
                'hint': 'Usa HELP para ver comandos disponibles'
            })
    
    def _shutdown(self):
        """Apaga Jarvis"""
        time.sleep(0.5)
        self.running = False
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        os._exit(0)
    
    def _reload(self):
        """Reinicia Jarvis"""
        time.sleep(0.5)
        self.running = False
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        # Iniciar nueva instancia
        subprocess.Popen([sys.executable, os.path.abspath(__file__)])
        os._exit(0)
    
    def _close_cmd(self):
        """Cierra la ventana CMD pero deja Jarvis corriendo en background"""
        time.sleep(0.5)
        
        # Primero, iniciar una nueva instancia de Jarvis desacoplada de la CMD
        try:
            # Usar pythonw para ejecutar sin ventana CMD
            pythonw_path = sys.executable.replace('python.exe', 'pythonw.exe')
            if os.path.exists(pythonw_path):
                subprocess.Popen([pythonw_path, os.path.abspath(__file__)], 
                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            else:
                # Fallback: usar start en background
                subprocess.Popen(f'start /b python "{os.path.abspath(__file__)}"', 
                               shell=True)
        except Exception as e:
            print(f"[CMDSERVER] Error iniciando background: {e}")
        
        # Cerrar el servidor y el proceso actual
        self.running = False
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        
        # Cerrar la ventana CMD usando taskkill para el proceso actual
        try:
            current_pid = os.getpid()
            # Usar taskkill /T para cerrar el árbol de procesos de la CMD
            subprocess.run(['taskkill', '/F', '/PID', str(current_pid)], 
                         capture_output=True)
        except:
            pass
        
        os._exit(0)
    
    def stop(self):
        """Detiene el servidor"""
        self.running = False
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass


# Instancia global del servidor de comandos
command_server = CommandServer()

try:
    w, h = pyautogui.size()
    estado.base_x = w - 420
    estado.base_y = h - 540
except:
    pass

def limpiar_tildes(texto):
    return re.sub(r'[¡¿«»"""]', '', texto)

def limpiar_thinking(texto):
    return re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL).strip()

def generar_audio(texto):
    if not KOKORO_OK or not kokoro:
        return None
    try:
        texto_limpio = limpiar_tildes(texto) + "!"
        estado.conteo_audio = (estado.conteo_audio + 1) % 3
        archivo = f"respuesta_{estado.conteo_audio}.wav"
        samples, sr = kokoro.create(texto_limpio, voice=VOZ, speed=1.0, lang='es')
        sf.write(archivo, samples, sr)
        return archivo
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return None

def hablar(texto):
    estado.set_hablando(True)
    estado.set_interrumpir(False)
    estado.set_estado("HABLANDO")
    print(f"\n[JARVIS]: {texto}")
    try:
        pygame.mixer.music.stop()
    except:
        pass
    archivo = generar_audio(texto)
    if archivo and os.path.exists(archivo):
        try:
            pygame.mixer.music.load(archivo)
            pygame.mixer.music.play()
            t0 = time.time()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
                if estado.get_interrumpir():
                    pygame.mixer.music.stop()
                    print("[JARVIS] Audio interrumpido por el usuario.")
                    break
                if time.time() - t0 > 90:
                    break
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"[AUDIO] Error reproduciendo: {e}")
            try:
                pygame.mixer.quit()
                pygame.mixer.init()
            except:
                pass
    estado.set_hablando(False)
    estado.set_estado("ESCUCHANDO")
    estado.tocar_interaccion()

def preguntar(pregunta):
    estado.set_estado("PENSANDO")
    print(f"[PENSANDO]: {pregunta}")
    ahora = datetime.datetime.now().strftime('%I:%M %p')
    if not historial_chat:
        historial_chat.append({"role": "system", "content": (
            f"Eres Jarvis, un asistente IA ultra avanzado, informal, divertido. "
            f"Experto en Python, modelado 3D, sistemas. Hablas como un compa cercano. "
            f"Sin enlaces falsos. Agrega xd. Usa tildes y ene. Hora: {ahora}."
            f"Tu dueño es Jam, se divertido con el, tambien se profesional y no crees una respuesta demasiado larga, porque tus respuestas son pasadas por un modelo de voz"
        )})
    historial_chat.append({"role": "user", "content": pregunta})
    while len(historial_chat) > 11:
        historial_chat.pop(1)
    try:
        estado.set_estado("PROCESANDO")
        r = groq_client.chat.completions.create(
            messages=historial_chat, model=MODELO_LLM, temperature=0.8
        )
        resp = r.choices[0].message.content
        historial_chat.append({"role": "assistant", "content": resp})
        links = re.findall(r'(https?://[^\s]+)', resp)
        if links:
            link = links[0].replace("`","").replace("*","").strip()
            if "example" not in link:
                webbrowser.open(link)
        hablar(resp)
    except Exception as e:
        print(f"[LLM] Error: {e}")
        hablar("Se me fallo la conexion Jam, intenta de nuevo xd")

SKILLS = {
    "conversar": {
        "desc": "Conversa libremente con el usuario sin accion especifica",
        "params": ["texto"],
        "cat": "chat"
    },
    "generar_modelo_blender": {
        "desc": "Genera un modelo 3D en Blender",
        "params": ["descripcion_del_modelo"],
        "cat": "creacion"
    },
    "analizar_pantalla": {
        "desc": "Captura y analiza la pantalla del usuario con IA",
        "params": [],
        "cat": "vision"
    },
    "reproducir_spotify": {
        "desc": "Busca y reproduce musica en Spotify",
        "params": ["busqueda"],
        "cat": "entretenimiento"
    },
    "reanudar_spotify": {
        "desc": "Reanuda la ultima reproduccion en Spotify",
        "params": [],
        "cat": "entretenimiento"
    },
    "abrir_app": {
        "desc": "Abre una aplicacion o carpeta del sistema",
        "params": ["nombre_app"],
        "cat": "sistema"
    },
    "manipular_ventana": {
        "desc": "Maximiza, minimiza o cierra la ventana activa",
        "params": ["accion"],
        "cat": "sistema"
    },
    "mover_ventana": {
        "desc": "Mueve la ventana activa a una posicion (izquierda, derecha, centro)",
        "params": ["instruccion"],
        "cat": "sistema"
    },
    "crear_documento": {
        "desc": "Crea un documento en Google Drive con contenido IA",
        "params": ["tema"],
        "cat": "productividad"
    },
    "generar_imagen": {
        "desc": "Genera una imagen con IA usando Pollinations",
        "params": ["prompt"],
        "cat": "creacion"
    },
    "buscar_video": {
        "desc": "Busca un video en YouTube",
        "params": ["busqueda"],
        "cat": "entretenimiento"
    },
    "mover_monitor": {
        "desc": "Mueve Jarvis a otra pantalla",
        "params": ["numero_pantalla"],
        "cat": "sistema"
    },
    "obtener_clima": {
        "desc": "Obtiene el clima de una ciudad",
        "params": ["ciudad"],
        "cat": "info"
    },
    "obtener_noticias": {
        "desc": "Obtiene las ultimas noticias",
        "params": [],
        "cat": "info"
    },
    "abrir_camara": {
        "desc": "Abre la camara y analiza lo que ve con IA en tiempo real",
        "params": [],
        "cat": "vision"
    },
    "analizar_objetos": {
        "desc": "Activa deteccion de objetos con bounding boxes en la camara",
        "params": [],
        "cat": "camara"
    },
    "que_estas_viendo": {
        "desc": "Responde que esta viendo la camara ahora mismo. Si la camara esta cerrada la abre primero",
        "params": [],
        "cat": "camara"
    },
    "monitorear_sistema": {
        "desc": "Muestra CPU, RAM, disco y procesos del sistema",
        "params": [],
        "cat": "sistema"
    },
    "ver_procesos": {
        "desc": "Lista los procesos que mas consumen",
        "params": [],
        "cat": "sistema"
    },
    "matar_proceso": {
        "desc": "Termina un proceso del sistema",
        "params": ["nombre_proceso"],
        "cat": "sistema"
    },
    "ver_archivos": {
        "desc": "Navega por archivos de una carpeta",
        "params": ["ruta_carpeta"],
        "cat": "sistema"
    },
    "leer_archivo": {
        "desc": "Lee el contenido de un archivo de texto",
        "params": ["ruta_archivo"],
        "cat": "sistema"
    },
    "buscar_archivo": {
        "desc": "Busca un archivo en el sistema por nombre",
        "params": ["nombre_archivo"],
        "cat": "sistema"
    },
    "crear_funcion": {
        "desc": "Crea una funcion nueva en Jarvis segun pida el usuario",
        "params": ["descripcion_funcion"],
        "cat": "sistema"
    },
    "analizar_portapapeles": {
        "desc": "Lee y analiza el portapapeles",
        "params": [],
        "cat": "info"
    },
    "seguir_mouse": {
        "desc": "Mueve Jarvis a la posicion del mouse",
        "params": [],
        "cat": "sistema"
    },
    "ocultar_jarvis": {
        "desc": "Oculta la interfaz de Jarvis",
        "params": [],
        "cat": "sistema"
    },
    ".estado_jarvis": {
        "desc": "Muestra el estado de todos los sistemas de Jarvis",
        "params": [],
        "cat": "info"
    },
    "listar_ventanas": {
        "desc": "Lista todas las ventanas abiertas en el sistema",
        "params": [],
        "cat": "sistema"
    },
    "mover_ventana_a": {
        "desc": "Mueve una ventana especifica a una posicion",
        "params": ["nombre_ventana", "posicion"],
        "cat": "sistema"
    },
    "organizar_ventanas": {
        "desc": "Organiza todas las ventanas en grid, cascada o lado a lado",
        "params": ["modo"],
        "cat": "sistema"
    },
    "cerrar_todas": {
        "desc": "Cierra todas las ventanas excepto las del sistema",
        "params": [],
        "cat": "sistema"
    },
    "siempre_encima": {
        "desc": "Pone la ventana activa siempre encima de las demas",
        "params": [],
        "cat": "sistema"
    },
    "info_pc": {
        "desc": "Muestra informacion completa de la PC: SO, RAM, disco, CPU",
        "params": [],
        "cat": "info"
    },
    "abrir_panel": {
        "desc": "Abre o cierra un panel de Jarvis (camara, sistema, archivos, historial, codigo)",
        "params": ["nombre_panel"],
        "cat": "sistema"
    },
    "cerrar_panel": {
        "desc": "Cierra un panel de Jarvis abierto",
        "params": ["nombre_panel"],
        "cat": "sistema"
    },
    "generar_codigo": {
        "desc": "Genera codigo Python a partir de una descripcion. Ejemplo: 'genera codigo que haga un servidor web'",
        "params": ["descripcion"],
        "cat": "codigo"
    },
    "saltar_anuncios_youtube": {
        "desc": "Activa o desactiva el saltador automatico de anuncios de YouTube. Detecta y omite anuncios cuando ves YouTube.",
        "params": [],
        "cat": "entretenimiento"
    },
    "airdrop": {
        "desc": "Envia archivos o mensajes a dispositivos Apple cercanos via Bluetooth",
        "params": ["mensaje_o_archivo"],
        "cat": "comunicacion"
    },
    "airdrop_discover": {
        "desc": "Escanea y muestra dispositivos Apple cercanos por Bluetooth",
        "params": [],
        "cat": "comunicacion"
    },
}

def skills_json():
    lista = []
    for nombre, info in SKILLS.items():
        entrada = {"nombre": nombre, "descripcion": info["desc"], "categoria": info["cat"]}
        if info["params"]:
            entrada["parametros"] = info["params"]
        lista.append(entrada)
    return json.dumps(lista, ensure_ascii=False, indent=2)

def router_ia(texto):
    prompt = (
        "Eres el router de Jarvis. Analiza el mensaje y devuelve SOLO un JSON valido:\n"
        '{"skill": "nombre_skill", "parametros": {"param": "valor"}}\n\n'
        f"SKILLS:\n{skills_json()}\n\n"
        "REGLAS:\n"
        "- NO incluyas 'respuesta_hablada'. Cada skill habla solo.\n"
        "- Si es conversacion libre o saludo: skill \"conversar\"\n"
        "- Si dice 'genera imagen', 'crea gato', 'dibuja X': skill \"generar_imagen\"\n"
        "- Si dice 'abre camara', 'mira esto': skill \"abrir_camara\"\n"
        "- Si dice 'que estas viendo', 'que ves', 'que hay ahi', 'describe la camara': skill \"que_estas_viendo\"\n"
        "- Si dice 'detecta objetos', 'analiza camara': skill \"analizar_objetos\"\n"
        "- Si dice 'que puedes', 'que tienes': skill \".estado_jarvis\"\n"
        "- Si dice 'genera codigo', 'escribe codigo', 'haz un programa': skill \"generar_codigo\"\n"
        "- Si dice 'saltar anuncios', 'ommitir anuncios', 'skip ads', 'salta anuncios de youtube': skill \"saltar_anuncios_youtube\"\n"
        "- Si dice 'airdrop', 'manda por airdrop', 'envia a apple', 'envia por bluetooth': skill \"airdrop\"\n"
        "- Si dice 'descubre dispositivos', 'que hay cerca', 'busca dispositivos apple': skill \"airdrop_discover\"\n"
        "- Si dice 'enviar archivos', 'file drop', 'quiere enviar archivos': skill \"airdrop\"\n"
        "- Extrae parametros del mensaje"
    )
    try:
        estado.set_estado("PENSANDO")
        r = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": texto}
            ],
            model=MODELO_LLM,
            temperature=0.2,
            max_tokens=400,
        )
        raw = r.choices[0].message.content.strip()
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw).strip()
        resultado = json.loads(raw)
        resultado.pop("respuesta_hablada", None)
        estado.set_estado("PROCESANDO")
        return resultado
    except Exception as e:
        print(f"[ROUTER] Error: {e}")
        return {"skill": "conversar", "parametros": {"texto": texto}}

class CameraManager:
    def __init__(self):
        self.cap = None
        self.lock = threading.Lock()
        self.running = False
        self.objetos = []
        self.detener_analisis_continuo()
        self.ultimo_analisis = ""
    self.analisis_activo = False
    self.analisis_hilo = None

    def abrir(self):
        if not OPENCV_OK:
            hablar("Necesito opencv para la camara. pip install opencv-python")
            return False
        with self.lock:
            try:
                if self.cap and self.cap.isOpened():
                    self.iniciar_analisis_continuo(); return True
                for idx in [0, 1, 2]:
                    try:
                        test = cv2.VideoCapture(idx)
                        if test.isOpened():
                            ok, frame = test.read()
                            if ok and frame is not None:
                                self.cap = test
                                self.running = True
                                print(f"[CAM] Camara abierta en indice {idx}")
                                self.iniciar_analisis_continuo(); return True
                            test.release()
                    except:
                        continue
                hablar("No pude encontrar ninguna camara xd")
                return False
            except Exception as e:
                print(f"[CAM] Error: {e}")
                return False

    def cerrar(self):
        self.running = False
        self.objetos = []
        self.detener_analisis_continuo()
        with self.lock:
            if self.cap:
                try:
                    self.cap.release()
                except:
                    pass
                self.cap = None

    def leer_frame(self):
        with self.lock:
            if self.cap and self.cap.isOpened():
                try:
                    ok, frame = self.cap.read()
                    if ok:
                        return frame

    def iniciar_analisis_continuo(self):
        self.analisis_activo = True
        self.analisis_hilo = threading.Thread(target=self._hilo_analisis, daemon=True)
        self.analisis_hilo.start()
        print('[CAM] Hilo de análisis continuo iniciado')

    def _hilo_analisis(self):
        while getattr(self, 'analisis_activo', False):
            frame = self.leer_frame()
            if frame is not None:
                try:
                    descripcion = self.analizar_ia(frame)
                    self.ultimo_analisis = descripcion
                except Exception as e:
                    print('[CAM] Error en analisis continuo')
            time.sleep(0.5)

    def detener_analisis_continuo(self):
        if hasattr(self, 'analisis_activo'):
            self.analisis_activo = False
        if hasattr(self, 'analisis_hilo') and self.analisis_hilo is not None:
            self.analisis_hilo.join(timeout=1.0)
            print('[CAM] Hilo de análisis continuo detenido')
                except:
                    pass
        return None

    def analizar_ia(self, frame):
        try:
            # Redimensionar a 320x240 para acelerar procesamiento
            frame_resized = cv2.resize(frame, (320, 240))
            _, buf = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 70])
            b64 = base64.b64encode(buf).decode('utf-8')
            r = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": (
                        "Identifica objetos y posiciones (0-1). Responde SOLO JSON: "
                        '{"objetos":[{"nombre":"x","posicion":{"x":0.5,"y":0.5,"ancho":0.2,"alto":0.3}}],'
                        '"descripcion":"breve"}'
                    )},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]}],
                model=MODELO_VISION, temperature=0.2, max_tokens=200
            )
            raw = r.choices[0].message.content.strip()
            raw = limpiar_thinking(raw)
            raw = re.sub(r'```json\s*', '', raw)
            raw = re.sub(r'```\s*', '', raw).strip()
            datos = json.loads(raw)
            self.objetos = datos.get("objetos", [])
            self.ultimo_analisis = datos.get("descripcion", raw)
            return self.ultimo_analisis
        except Exception as e:
            print(f"[CAM] Analisis error: {e}")
            return f"Error: {e}"

    def dibujar_bboxes(self, frame, objetos):
        h, w = frame.shape[:2]
        for obj in objetos:
            p = obj.get("posicion", {})
            cx = int(p.get("x", 0.5) * w)
            cy = int(p.get("y", 0.5) * h)
            aw = int(p.get("ancho", 0.2) * w / 2)
            ah = int(p.get("alto", 0.3) * h / 2)
            x1, y1 = max(0, cx-aw), max(0, cy-ah)
            x2, y2 = min(w-1, cx+aw), min(h-1, cy+ah)
            color = (0, 255, 255)
            cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
            cs = 12
            for (sx,sy,ex,ey) in [(x1,y1,x1+cs,y1),(x1,y1,x1,y1+cs),(x2,y1,x2-cs,y1),(x2,y1,x2,y1+cs),
                                   (x1,y2,x1+cs,y2),(x1,y2,x1,y2-cs),(x2,y2,x2-cs,y2),(x2,y2,x2,y2-cs)]:
                cv2.line(frame,(sx,sy),(ex,ey),color,2)
            nombre = obj.get("nombre","?")
            (tw,th),_ = cv2.getTextSize(nombre, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(frame,(x1,y1-th-8),(x1+tw+8,y1),color,-1)
            cv2.putText(frame,nombre,(x1+4,y1-4),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,0),2)
        return frame

    def iniciar_analisis_continuo(self):
        self.analisis_activo = True
        self.analisis_hilo = threading.Thread(target=self._hilo_analisis, daemon=True)
        self.analisis_hilo.start()
        print('[CAM] Hilo de análisis continuo iniciado')

    def _hilo_analisis(self):
        while getattr(self, 'analisis_activo', False):
            frame = self.leer_frame()
            if frame is not None:
                try:
                    descripcion = self.analizar_ia(frame)
                    self.ultimo_analisis = descripcion
                except Exception as e:
                    print('[CAM] Error en analisis continuo')
            time.sleep(0.5)

    def detener_analisis_continuo(self):
        if hasattr(self, 'analisis_activo'):
            self.analisis_activo = False
        if hasattr(self, 'analisis_hilo') and self.analisis_hilo is not None:
            self.analisis_hilo.join(timeout=1.0)
            print('[CAM] Hilo de análisis continuo detenido')

cam = CameraManager()

class YouTubeAdSkipper:
    def __init__(self):
        self.activo = False
        self.monitorizando = False
        self.lock = threading.Lock()
        self.youtube_detectado = False
        self.ultima_deteccion = 0
        self.ultima_verificacion = 0
        self.ultimo_click = 0  # Cooldown para evitar clics rápidos
        self.saltados = 0
        self.tesseract_ready = False
        self._verificar_tesseract()

    def _verificar_tesseract(self):
        if not TESSERACT_OK:
            print("[YT-SKIP] pytesseract no disponible")
            return
        try:
            pytesseract.get_tesseract_version()
            self.tesseract_ready = True
            print("[YT-SKIP] Tesseract OCR listo")
        except Exception as e:
            print(f"[YT-SKIP] Tesseract no encontrado: {e}")
            print("[YT-SKIP] Instala: https://github.com/UB-Mannheim/tesseract/wiki")
            self.tesseract_ready = False

    def detectar_youtube_ventana(self):
        try:
            EnumWindows = ctypes.windll.user32.EnumWindows
            GetWindowTextW = ctypes.windll.user32.GetWindowTextW
            IsWindowVisible = ctypes.windll.user32.IsWindowVisible
            encontrados = []

            def cb(hwnd, _):
                if IsWindowVisible(hwnd):
                    buf = ctypes.create_unicode_buffer(256)
                    GetWindowTextW(hwnd, buf, 256)
                    titulo = buf.value.lower() if buf.value else ""
                    # Buscar YouTube directamente o en navegadores conocidos
                    if any(k in titulo for k in ["youtube", "yt -", "yt |", "yt—"]):
                        encontrados.append(titulo)
                    # Detectar navegadores comunes (YouTube puede estar en una pestaña)
                    elif any(k in titulo for k in ["chrome", "firefox", "edge", "opera", "brave", "vivaldi"]):
                        # Solo marcar si el navegador está activo
                        if hwnd == ctypes.windll.user32.GetForegroundWindow():
                            encontrados.append(titulo)
                self.iniciar_analisis_continuo(); return True

            EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))(cb), 0)
            if encontrados:
                print(f"[YT-SKIP] Ventana detectada: {encontrados[0][:60]}")
            return len(encontrados) > 0
        except Exception as e:
            print(f"[YT-SKIP] Error detectando YouTube: {e}")
            return False

    def obtener_region_boton_skip(self):
        wp, hp = pyautogui.size()
        x1 = int(wp * 0.72)
        y1 = int(hp * 0.70)
        x2 = int(wp * 0.92)
        y2 = int(hp * 0.82)
        return x1, y1, x2, y2

    def detectar_boton(self, imagen):
        if not self.tesseract_ready:
            return None, None  # Sin Tesseract, no detectar (es mas seguro)
        try:
            img_cv = cv2.cvtColor(np.array(imagen), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Preprocesamiento más estricto para el botón de skip
            # El botón de skip de YouTube tiene texto blanco sobre fondo semi-transparente
            _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            
            # OCR con configuración estricta
            texto_completo = pytesseract.image_to_string(thresh, lang="eng", config="--psm 7 --oem 3")
            texto_lower = texto_completo.lower().strip()
            
            # Solo aceptar texto que sea EXACTAMENTE el botón de skip
            # YouTube usa: "Skip Ad", "Skip Ads", "Saltar anuncio", "Omitir anuncio"
            skip_patterns = [
                "skip ad", "skip ads", "skip now", "skip trial",
                "saltar anuncio", "saltar los anuncios", "omitir anuncio",
                "no thanks", "visit advertiser"
            ]
            
            for pattern in skip_patterns:
                if pattern in texto_lower:
                    # Verificar que el texto es corto y específico (no un párrafo)
                    if len(texto_lower) < 50:
                        datos = pytesseract.image_to_data(thresh, lang="eng", config="--psm 7 --oem 3", output_type=pytesseract.Output.DICT)
                        for i, t in enumerate(datos["text"]):
                            conf = int(datos["conf"][i])
                            # Solo aceptar si la confianza es alta y el texto coincide
                            if conf > 50 and any(p in t.lower() for p in ["skip", "saltar", "omitir", "no thanks"]):
                                bx = datos["left"][i]
                                by = datos["top"][i]
                                bw = datos["width"][i]
                                bh = datos["height"][i]
                                
                                # Verificar que el tamaño del texto es razonable para un botón
                                if 20 < bw < 150 and 10 < bh < 50:
                                    cx = bx + bw // 2
                                    cy = by + bh // 2
                                    print(f"[YT-SKIP] Botón skip detectado: '{t}' (conf: {conf}%)")
                                    return cx, cy
            
            return None, None
        except Exception as e:
            print(f"[YT-SKIP] Error OCR: {e}")
            return None, None

    def saltar_anuncio(self, x, y):
        # Cooldown de 2 segundos para evitar clics rápidos
        ahora = time.time()
        if ahora - self.ultimo_click < 2.0:
            print("[YT-SKIP] Cooldown activo, saltando clic")
            return False
        
        x1, y1, x2, y2 = self.obtener_region_boton_skip()
        click_x = x1 + x
        click_y = y1 + y
        
        # Verificar que las coordenadas están dentro de la región válida
        if click_x < x1 or click_x > x2 or click_y < y1 or click_y > y2:
            print(f"[YT-SKIP] Coordenadas fuera de rango: ({click_x}, {click_y})")
            return False
        
        pyautogui.click(click_x, click_y)
        self.ultimo_click = ahora
        self.saltados += 1
        print(f"[YT-SKIP] Anuncio saltado! (total: {self.saltados}) en ({click_x}, {click_y})")
        self.iniciar_analisis_continuo(); return True

    def monitorizar(self):
        print("[YT-SKIP] Monitor de anuncios YouTube iniciado")
        if not NUMPY_OK:
            print("[YT-SKIP] numpy no disponible, desactivando")
            self.monitorizando = False
            return
        
        if not self.tesseract_ready:
            print("[YT-SKIP] Tesseract no disponible - usando deteccion por posicion")

        intentos = 0
        while self.monitorizando:
            try:
                ahora = time.time()
                if ahora - self.ultima_verificacion < 1.5:
                    time.sleep(0.3)
                    continue
                self.ultima_verificacion = ahora
                intentos += 1

                youtube_abierto = self.detectar_youtube_ventana()

                if youtube_abierto:
                    if not self.youtube_detectado:
                        self.youtube_detectado = True
                        print("[YT-SKIP] YouTube/Navegador detectado, monitoreando anuncios...")

                    try:
                        x1, y1, x2, y2 = self.obtener_region_boton_skip()
                        screenshot = pyautogui.screenshot(region=(x1, y1, x2 - x1, y2 - y1))
                        cx, cy = self.detectar_boton(screenshot)
                        if cx is not None and cy is not None:
                            print(f"[YT-SKIP] Botón encontrado! Clickeando...")
                            time.sleep(0.2)
                            if self.saltar_anuncio(cx, cy):
                                time.sleep(3.0)  # Esperar después de un clic exitoso
                        elif intentos % 15 == 0:
                            print(f"[YT-SKIP] Buscando anuncios... (verificaciones: {intentos})")
                    except Exception as e:
                        print(f"[YT-SKIP] Error en frame: {e}")
                else:
                    if self.youtube_detectado:
                        self.youtube_detectado = False
                        print("[YT-SKIP] YouTube cerrado, pausando monitoreo")

                time.sleep(1.0)

            except Exception as e:
                print(f"[YT-SKIP] Error monitor: {e}")
                time.sleep(2)

        print("[YT-SKIP] Monitor detenido")

    def iniciar(self):
        with self.lock:
            if self.monitorizando:
                print("[YT-SKIP] Ya esta activo")
                return False
            if not NUMPY_OK:
                print("[YT-SKIP] numpy no disponible, no se puede iniciar")
                return False
            self.monitorizando = True
            self.activo = True
            if not self.tesseract_ready:
                print("[YT-SKIP] Tesseract no disponible - usando deteccion por forma/posicion")
            hilo = threading.Thread(target=self.monitorizar, daemon=True)
            hilo.start()
            self.iniciar_analisis_continuo(); return True

    def detener(self):
        with self.lock:
            self.monitorizando = False
            self.activo = False
            print("[YT-SKIP] Monitor detenido por el usuario")

    def toggle(self):
        if self.monitorizando:
            self.detener()
            return False
        else:
            return self.iniciar()

    def estado(self):
        if not self.tesseract_ready:
            return "Tesseract no disponible. Instala pytesseract y tesseract-ocr"
        if self.monitorizando:
            return f"Activo. YouTube detectado: {self.youtube_detectado}. Anuncios saltados: {self.saltados}"
        return f"Inactivo. Anuncios saltados total: {self.saltados}"

def blender_ruta():
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe")
        r,_ = winreg.QueryValueEx(k,"")
        winreg.CloseKey(k)
        if os.path.exists(r): return r
    except: pass
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        sp,_ = winreg.QueryValueEx(k,"SteamPath")
        winreg.CloseKey(k)
        rt = os.path.join(sp.replace("/","\\"),"steamapps","common","Blender","blender.exe")
        if os.path.exists(rt): return rt
    except: pass
    for r in [r"C:\Program Files\Blender Foundation\Blender\blender.exe",
              r"C:\Program Files\Steam\steamapps\common\Blender\blender.exe"]:
        if os.path.exists(r): return r
    return None

def ejecutar_skill(nombre, params):
    global estado
    print(f"[SKILL] {nombre}: {params}")

    if nombre == "conversar":
        t = params.get("texto", params.get("pregunta", ""))
        if t: threading.Thread(target=preguntar, args=(t,), daemon=True).start()
        else: hablar("Que pasa Jam, te escucho xd")

    elif nombre == "generar_modelo_blender":
        d = params.get("descripcion_del_modelo", params.get("descripcion","figura abstracta"))
        def _blender():
            estado.set_estado("PROCESANDO")
            hablar(f"Disenando {d} en Blender xd")
            ruta = blender_ruta()
            if not ruta:
                hablar("No encontre Blender en tu sistema xd")
                return
            carpeta = r"C:\Users\rjams\OneDrive\Escritorio\MODELOS GENERADOS"
            os.makedirs(carpeta, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo = os.path.join(carpeta, f"modelo_{ts}.blend")
            prompt = (
                f"Script bpy para Blender 4.x que borre todo y cree un modelo 3D complejo de: {d}. "
                "Usa multiples objetos, materiales PBR, shade_smooth. "
                f"Al final: bpy.ops.wmsaveasmianfile(filepath='{archivo.replace(chr(92),'/')}')\n"
                "Solo codigo Python en bloque markdown."
            )
            try:
                r = groq_client.chat.completions.create(
                    messages=[{"role":"user","content":prompt}], model=MODELO_LLM, temperature=0.25
                )
                resp = r.choices[0].message.content
                bloques = re.findall(r"```python\s*(.*?)\s*```", resp, re.DOTALL)
                if not bloques: bloques = re.findall(r"```\s*(.*?)\s*```", resp, re.DOTALL)
                codigo = bloques[0].strip() if bloques else resp.strip()
                tmp = "temp_blender.py"
                with open(tmp,"w") as f: f.write(codigo)
                subprocess.run([ruta,"--background","--python",tmp], capture_output=True, timeout=120)
                try: os.remove(tmp)
                except: pass
                if os.path.exists(archivo):
                    hablar("Modelo guardado en tu escritorio. Abriendolo xd")
                    os.startfile(archivo)
                else:
                    hablar("Blender tuvo un problema con el script xd")
            except Exception as e:
                print(f"[BLENDER] Error: {e}")
                hablar("Error comunicandome con Blender xd")
        threading.Thread(target=_blender, daemon=True).start()

    elif nombre == "analizar_pantalla":
        def _pantalla():
            estado.set_estado("PROCESANDO")
            try:
                pyautogui.screenshot("cap_tmp.png")
                with open("cap_tmp.png","rb") as f: b64 = base64.b64encode(f.read()).decode()
                os.remove("cap_tmp.png")
                r = groq_client.chat.completions.create(
                    messages=[{"role":"user","content":[
                        {"type":"text","text":"Analiza la pantalla brevemente y diversion. Usa xd. Tildes y ene."},
                        {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}}
                    ]}], model=MODELO_VISION, temperature=0.7
                )
                hablar(limpiar_thinking(r.choices[0].message.content))
            except Exception as e:
                print(f"[PANTALLA] Error: {e}")
                hablar("No pude analizar la pantalla xd")
        threading.Thread(target=_pantalla, daemon=True).start()

    elif nombre == "reproducir_spotify":
        b = params.get("busqueda","")
        def _spotify():
            estado.set_estado("PROCESANDO")
            if not b:
                hablar("Reanudando Spotify xd")
                try:
                    os.startfile("spotify:")
                    time.sleep(1.5)
                    pyautogui.press("playpause")
                except: pass
            else:
                hablar(f"Buscando {b} en Spotify xd")
                try:
                    os.startfile(f"spotify:search:{b}")
                    time.sleep(3)
                    pyautogui.press("enter")
                    time.sleep(0.4)
                    pyautogui.press("enter")
                except Exception as e: print(f"[SPOTIFY] {e}")
        threading.Thread(target=_spotify, daemon=True).start()

    elif nombre == "reanudar_spotify":
        def _rs():
            estado.set_estado("PROCESANDO")
            hablar("Reanudando musica xd")
            try:
                os.startfile("spotify:")
                time.sleep(1.5)
                pyautogui.press("playpause")
            except: pass
        threading.Thread(target=_rs, daemon=True).start()

    elif nombre == "abrir_app":
        a = params.get("nombre_app","")
        def _abrir():
            estado.set_estado("PROCESANDO")
            rutas = {
                "documentos":"shell:Personal","descargas":"shell:Downloads",
                "imagenes":"shell:My Pictures","escritorio":"shell:Desktop",
                "visual studio":"code","edge":"msedge:","chrome":"chrome.exe",
                "spotify":"spotify:","whatsapp":"whatsapp:","calculadora":"calc.exe"
            }
            for k,v in rutas.items():
                if k in a.lower():
                    hablar(f"Abriendo {k} xd")
                    try: os.startfile(v)
                    except: subprocess.Popen(v, shell=True)
                    return
            hablar(f"Buscando {a} en el sistema xd")
            pyautogui.hotkey("win","s")
            time.sleep(0.8)
            pyautogui.write(a, interval=0.04)
            time.sleep(1.2)
            pyautogui.press("enter")
        threading.Thread(target=_abrir, daemon=True).start()

    elif nombre == "manipular_ventana":
        def _manip():
            estado.set_estado("PROCESANDO")
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd: return
            accion = params.get("accion","")
            if any(p in accion for p in ["maximiza","agranda"]):
                ctypes.windll.user32.ShowWindow(hwnd, 3); hablar("Maximizada xd")
            elif any(p in accion for p in ["minimiza","esconde"]):
                ctypes.windll.user32.ShowWindow(hwnd, 6); hablar("Minimizada xd")
            elif any(p in accion for p in ["cierra","cerrar"]):
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0); hablar("Cerrada xd")
        threading.Thread(target=_manip, daemon=True).start()

    elif nombre == "mover_ventana":
        def _mv():
            estado.set_estado("PROCESANDO")
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd: hablar("No hay ventana activa xd"); return
            wp, hp = pyautogui.size()
            i = params.get("instruccion","")
            if "izquierda" in i:
                ctypes.windll.user32.SetWindowPos(hwnd,0,0,0,wp//2,hp,0x0040); hablar("Izquierda xd")
            elif "derecha" in i:
                ctypes.windll.user32.SetWindowPos(hwnd,0,wp//2,0,wp//2,hp,0x0040); hablar("Derecha xd")
            elif "centro" in i:
                ctypes.windll.user32.SetWindowPos(hwnd,0,(wp-800)//2,(hp-600)//2,800,600,0x0040); hablar("Centro xd")
            elif "arriba" in i:
                ctypes.windll.user32.ShowWindow(hwnd, 3); hablar("Maximizada xd")
            elif "abajo" in i:
                ctypes.windll.user32.ShowWindow(hwnd, 6); hablar("Minimizada xd")
        threading.Thread(target=_mv, daemon=True).start()

    elif nombre == "crear_documento":
        t = params.get("tema","general")
        def _doc():
            estado.set_estado("PROCESANDO")
            hablar(f"Creando documento sobre {t} en Drive xd")
            try:
                r = groq_client.chat.completions.create(
                    messages=[
                        {"role":"system","content":"Genera un reporte extenso. Tildes y ene normalmente."},
                        {"role":"user","content":f"Texto para documento sobre: {t}"}
                    ], model=MODELO_LLM, temperature=0.7
                )
                contenido = r.choices[0].message.content
                try: subprocess.Popen(["msedge.exe","https://docs.new"])
                except: webbrowser.open("https://docs.new")
                time.sleep(6)
                pyautogui.write(f"REPORTE: {t.upper()}", interval=0.02)
                pyautogui.press("enter"); pyautogui.press("enter")
                estado.app.clipboard_clear()
                estado.app.clipboard_append(contenido)
                time.sleep(0.3)
                pyautogui.hotkey("ctrl","v")
                hablar("Documento creado xd")
            except Exception as e:
                print(f"[DOC] Error: {e}")
                hablar("Error creando el documento xd")
        threading.Thread(target=_doc, daemon=True).start()

    elif nombre == "generar_imagen":
        p = params.get("prompt","")
        if p:
            hablar("Generando imagen con IA xd")
            webbrowser.open(f"https://image.pollinations.ai/prompt/{p.replace(' ','%20')}")
        else:
            hablar("Que imagen quieres que genere xd")

    elif nombre == "buscar_video":
        b = params.get("busqueda","")
        if b:
            hablar(f"Buscando {b} en YouTube xd")
            webbrowser.open(f"https://www.youtube.com/results?search_query={b}")
        else:
            hablar("Que video buscas xd")

    elif nombre == "mover_monitor":
        n = params.get("numero_pantalla","1")
        def _mm():
            global estado
            wp, hp = pyautogui.size()
            if "2" in str(n):
                estado.base_x = wp + 100; estado.base_y = 150; hablar("Saltando a pantalla 2 xd")
            else:
                estado.base_x = wp - 420; estado.base_y = hp - 540; hablar("Regresando a pantalla 1 xd")
        threading.Thread(target=_mm, daemon=True).start()

    elif nombre == "obtener_clima":
        c = params.get("ciudad", CIUDAD_CLIMA)
        try:
            clima = requests.get(f"https://wttr.in/{c}?format=%t", timeout=5).text.strip()
            hablar(f"El clima en {c} esta a {clima} xd")
        except:
            hablar("No pude obtener el clima xd")

    elif nombre == "obtener_noticias":
        def _news():
            try:
                url = "https://news.google.com/rss?hl=es-419&gl=CR&ceid=CR:es-419"
                r = requests.get(url, timeout=10)
                root = ET.fromstring(r.content)
                for item in root.findall('./channel/item')[:3]:
                    hablar(item.find('title').text)
            except:
                hablar("No pude obtener noticias xd")
        threading.Thread(target=_news, daemon=True).start()

    elif nombre == "abrir_camara":
        if cam.running:
            hablar("La camara ya esta abierta. Dime que analizar xd")
            if estado.app:
                estado.app.after(0, lambda: estado.app.mostrar_panel("camara"))
        elif cam.abrir():
            hablar("Camara abierta. Analizando en tiempo real xd")
            if estado.app:
                estado.app.after(0, lambda: estado.app.mostrar_panel("camara"))
        else:
            hablar("No pude abrir la camara xd")

    elif nombre == "analizar_objetos":
        if cam.abrir():
            hablar("Camara con deteccion de objetos activa. Vas a ver recuadros xd")
            if estado.app:
                estado.app.after(0, lambda: estado.app.mostrar_panel("camara"))
        else:
            hablar("No pude abrir la camara xd")

    elif nombre == "que_estas_viendo":
        def _que_veo():
            try:
                if not cam.running:
                    hablar("La camara esta cerrada. La abro un momento xd")
                    if not cam.abrir():
                        hablar("No pude abrir la camara xd")
                        return
                time.sleep(0.5)
                frame = cam.leer_frame()
                if frame is None:
                    hablar("No pude capturar imagen de la camara xd")
                    return
                estado.set_estado("PROCESANDO")
                hablar("Dejame ver... xd")
                desc = cam.analizar_ia(frame)
                if desc and not desc.startswith("Error"):
                    hablar(f"Veo lo siguiente: {desc}")
                else:
                    hablar(f"No logre analizar bien. {desc}")
                estado.set_estado("ESCUCHANDO")
            except Exception as e:
                hablar(f"Error viendo: {e}")
                estado.set_estado("ESCUCHANDO")
        threading.Thread(target=_que_veo, daemon=True).start()

    elif nombre == "monitorear_sistema":
        if not PSUTIL_OK:
            hablar("psutil no instalado. pip install psutil"); return
        def _sys():
            estado.set_estado("PROCESANDO")
            try:
                cpu = psutil.cpu_percent(interval=1)
                vm = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                procs = len(psutil.pids())
                msg = (f"CPU {cpu}%, RAM {vm.percent}% ({vm.used/(1024**3):.1f} de {vm.total/(1024**3):.1f} GB), "
                       f"Disco {disk.percent}%, {procs} procesos.")
                hablar(msg)
            except Exception as e:
                hablar(f"Error monitoreando: {e}")
            if estado.app:
                estado.app.after(0, lambda: estado.app.mostrar_panel("sistema"))
        threading.Thread(target=_sys, daemon=True).start()

    elif nombre == "ver_procesos":
        if not PSUTIL_OK: hablar("psutil no disponible"); return
        def _proc():
            try:
                top = sorted(psutil.process_iter(['name','cpu_percent']),
                            key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:5]
                msg = "Procesos top: " + ", ".join([f"{p.info['name'][:15]} ({p.info['cpu_percent']}%)" for p in top])
                hablar(msg)
            except: hablar("Error listando procesos xd")
        threading.Thread(target=_proc, daemon=True).start()

    elif nombre == "matar_proceso":
        n = params.get("nombre_proceso","")
        if n and PSUTIL_OK:
            try:
                c = 0
                for p in psutil.process_iter(['name']):
                    if n.lower() in (p.info['name'] or '').lower():
                        p.kill(); c += 1
                hablar(f"Eliminados {c} procesos con '{n}'" if c else f"No encontre '{n}' xd")
            except: hablar("Error matando proceso xd")
        else: hablar("Que proceso quieres terminar xd")

    elif nombre == "ver_archivos":
        ruta = params.get("ruta_carpeta", os.path.expanduser("~"))
        def _files():
            try:
                items = os.listdir(ruta)
                carpetas = sum(1 for i in items if os.path.isdir(os.path.join(ruta,i)))
                archivos = len(items) - carpetas
                hablar(f"En {ruta}: {carpetas} carpetas y {archivos} archivos")
                if estado.app:
                    info = {"ruta": ruta, "items": []}
                    for item in sorted(items)[:40]:
                        rp = os.path.join(ruta, item)
                        es_dir = os.path.isdir(rp)
                        tam = 0 if es_dir else os.path.getsize(rp)
                        info["items"].append({"nombre": item, "es_carpeta": es_dir, "tamano": tam, "ruta": rp})
                    estado.app.after(0, lambda i=info: estado.app.cargar_archivos(i))
            except Exception as e: hablar(f"Error: {e}")
        threading.Thread(target=_files, daemon=True).start()

    elif nombre == "leer_archivo":
        r = params.get("ruta_archivo","")
        if r:
            try:
                with open(r,'r',encoding='utf-8',errors='replace') as f: c = f.read(2000)
                hablar(f"Archivo: {c[:200]}...")
            except: hablar("No pude leer el archivo xd")
        else: hablar("Que archivo quieres leer xd")

    elif nombre == "buscar_archivo":
        n = params.get("nombre_archivo","")
        if n:
            def _buscar():
                encontrados = []
                for root, dirs, files in os.walk(os.path.expanduser("~")):
                    for f in files:
                        if n.lower() in f.lower():
                            encontrados.append(os.path.join(root,f))
                            if len(encontrados) >= 5: break
                    if len(encontrados) >= 5: break
                if encontrados:
                    hablar(f"Encontre {len(encontrados)}. Primero: {encontrados[0]}")
                else:
                    hablar(f"No encontre nada con '{n}' xd")
            threading.Thread(target=_buscar, daemon=True).start()
        else: hablar("Que archivo buscas xd")

    elif nombre == "crear_funcion":
        d = params.get("descripcion_funcion","")
        if d:
            def _crear():
                hablar("Creando funcion nueva xd")
                try:
                    r = groq_client.chat.completions.create(
                        messages=[
                            {"role":"system","content":"Crea una funcion Python que haga lo que el usuario pide. Solo codigo."},
                            {"role":"user","content":d}
                        ], model=MODELO_LLM, temperature=0.3, max_tokens=1000
                    )
                    resp = r.choices[0].message.content
                    bloques = re.findall(r"```python\s*(.*?)\s*```", resp, re.DOTALL)
                    codigo = bloques[0].strip() if bloques else resp.strip()
                    namespace = {}
                    exec(codigo, {"__builtins__": __builtins__}, namespace)
                    funcs = [k for k,v in namespace.items() if callable(v) and not k.startswith('_')]
                    if funcs:
                        hablar(f"Funcion '{funcs[0]}' creada. Puedes usarla.")
                    else:
                        hablar("Cree el codigo pero no detecte una funcion valida")
                except Exception as e:
                    hablar(f"Error creando funcion: {e}")
            threading.Thread(target=_crear, daemon=True).start()
        else: hablar("Que funcion quieres que cree xd")

    elif nombre == "analizar_portapapeles":
        try:
            c = estado.app.clipboard_get()
            threading.Thread(target=preguntar, args=(f"Analiza esto del portapapeles: {c}",), daemon=True).start()
        except: hablar("Portapapeles vacio xd")

    elif nombre == "seguir_mouse":
        mx, my = pyautogui.position()
        estado.base_x = mx - 130; estado.base_y = my - 130
        hablar("Ahi voy xd")

    elif nombre == "ocultar_jarvis":
        estado.ventana_visible = False
        hablar("Me oculto xd")

    elif nombre == ".estado_jarvis":
        def _estado():
            msg = f"Todo operativo. {len(SKILLS)} skills."
            if PSUTIL_OK:
                cpu = psutil.cpu_percent(interval=0.5)
                vm = psutil.virtual_memory()
                msg += f" CPU {cpu}%, RAM {vm.percent}%. "
            msg += f"Camara {'activa' if cam.running else 'inactiva'}. Listo xd"
            hablar(msg)
        threading.Thread(target=_estado, daemon=True).start()

    elif nombre == "listar_ventanas":
        def _listar_ventanas():
            try:
                EnumWindows = ctypes.windll.user32.EnumWindows
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
                GetWindowTextW = ctypes.windll.user32.GetWindowTextW
                IsWindowVisible = ctypes.windll.user32.IsWindowVisible

                ventanas = []
                def callback(hwnd, lParam):
                    if IsWindowVisible(hwnd):
                        length = GetWindowTextW(hwnd, ctypes.create_unicode_buffer(256), 256)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(256)
                            GetWindowTextW(hwnd, buf, 256)
                            ventanas.append((hwnd, buf.value))
                    self.iniciar_analisis_continuo(); return True

                EnumWindows(EnumWindowsProc(callback), 0)
                if ventanas:
                    msg = f"Encontre {len(ventanas)} ventanas: "
                    for i, (h, titulo) in enumerate(ventanas[:6]):
                        msg += f"{titulo}, "
                    hablar(msg.rstrip(", ") + " xd")
                else:
                    hablar("No encontre ventanas visibles xd")
            except Exception as e:
                hablar(f"Error listando ventanas: {e}")
        threading.Thread(target=_listar_ventanas, daemon=True).start()

    elif nombre == "mover_ventana_a":
        def _mover_a():
            try:
                EnumWindows = ctypes.windll.user32.EnumWindows
                GetWindowTextW = ctypes.windll.user32.GetWindowTextW
                IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                SetWindowPos = ctypes.windll.user32.SetWindowPos
                ShowWindow = ctypes.windll.user32.ShowWindow

                nombre_ventana = params.get("nombre_ventana","").lower()
                posicion = params.get("posicion","centro").lower()
                wp, hp = pyautogui.size()

                ventanas = []
                def cb(hwnd, _):
                    if IsWindowVisible(hwnd):
                        buf = ctypes.create_unicode_buffer(256)
                        GetWindowTextW(hwnd, buf, 256)
                        if buf.value and nombre_ventana in buf.value.lower():
                            ventanas.append((hwnd, buf.value))
                    self.iniciar_analisis_continuo(); return True
                EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))(cb), 0)

                if ventanas:
                    hwnd, titulo = ventanas[0]
                    if posicion in ["izquierda","left"]:
                        SetWindowPos(hwnd, 0, 0, 0, wp//2, hp, 0x0040)
                        hablar(f"Movi {titulo} a la izquierda xd")
                    elif posicion in ["derecha","right"]:
                        SetWindowPos(hwnd, 0, wp//2, 0, wp//2, hp, 0x0040)
                        hablar(f"Movi {titulo} a la derecha xd")
                    elif posicion in ["centro","center"]:
                        SetWindowPos(hwnd, 0, wp//4, hp//6, wp//2, int(hp*0.8), 0x0040)
                        hablar(f"Movi {titulo} al centro xd")
                    elif posicion in ["arriba","maximizar"]:
                        ShowWindow(hwnd, 3)
                        hablar(f"Maximice {titulo} xd")
                    elif posicion in ["abajo","minimizar"]:
                        ShowWindow(hwnd, 6)
                        hablar(f"Minimice {titulo} xd")
                    else:
                        hablar(f"No entendi la posicion '{posicion}'. Puedo: izquierda, derecha, centro, arriba, abajo xd")
                else:
                    hablar(f"No encontre ninguna ventana con '{nombre_ventana}' xd")
            except Exception as e:
                hablar(f"Error moviendo ventana: {e}")
        threading.Thread(target=_mover_a, daemon=True).start()

    elif nombre == "organizar_ventanas":
        def _organizar():
            try:
                EnumWindows = ctypes.windll.user32.EnumWindows
                GetWindowTextW = ctypes.windll.user32.GetWindowTextW
                IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                SetWindowPos = ctypes.windll.user32.SetWindowPos

                modo = params.get("modo","grid").lower()
                ventanas = []
                def cb(hwnd, _):
                    if IsWindowVisible(hwnd):
                        buf = ctypes.create_unicode_buffer(256)
                        GetWindowTextW(hwnd, buf, 256)
                        if buf.value and buf.value not in ["","Program Manager","MSCTFIME UI","Default IME"]:
                            ventanas.append(hwnd)
                    self.iniciar_analisis_continuo(); return True
                EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))(cb), 0)

                wp, hp = pyautogui.size()
                n = len(ventanas[:9])
                if n == 0:
                    hablar("No hay ventanas para organizar xd"); return

                if modo in ["grid","cuadricula"]:
                    cols = math.ceil(math.sqrt(n))
                    rows = math.ceil(n / cols)
                    ww, wh = wp // cols, hp // rows
                    for i, hwnd in enumerate(ventanas[:9]):
                        col, row = i % cols, i // cols
                        SetWindowPos(hwnd, 0, col*ww, row*wh, ww, wh, 0x0040)
                    hablar(f"Organice {n} ventanas en grid de {cols}x{rows} xd")

                elif modo in ["cascada","cascade"]:
                    for i, hwnd in enumerate(ventanas[:8]):
                        SetWindowPos(hwnd, 0, 50+i*40, 50+i*40, wp//2, hp//2, 0x0040)
                    hablar(f"Organice {n} ventanas en cascada xd")

                elif modo in ["lado a lado","lado"]:
                    half = n // 2
                    for i, hwnd in enumerate(ventanas[:8]):
                        if i < half:
                            SetWindowPos(hwnd, 0, 0, int(hp*i/half), wp//2, hp//half, 0x0040)
                        else:
                            SetWindowPos(hwnd, 0, wp//2, int(hp*(i-half)/max(1,n-half)), wp//2, hp//max(1,n-half), 0x0040)
                    hablar(f"Organice {n} ventanas lado a lado xd")
                else:
                    hablar(f"Modo '{modo}' no reconocido. Puedo: grid, cascada, lado a lado xd")
            except Exception as e:
                hablar(f"Error organizando: {e}")
        threading.Thread(target=_organizar, daemon=True).start()

    elif nombre == "cerrar_todas":
        def _cerrar_todas():
            try:
                EnumWindows = ctypes.windll.user32.EnumWindows
                GetWindowTextW = ctypes.windll.user32.GetWindowTextW
                IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                PostMessageW = ctypes.windll.user32.PostMessageW

                cerradas = 0
                protegidas = ["progman","shell_traywnd","workerw","jjjjjjjjjjjjjjjjjj","application frame window"]

                def cb(hwnd, _):
                    nonlocal cerradas
                    if IsWindowVisible(hwnd):
                        buf = ctypes.create_unicode_buffer(256)
                        GetWindowTextW(hwnd, buf, 256)
                        clase = ctypes.create_unicode_buffer(256)
                        ctypes.windll.user32.GetClassNameW(hwnd, clase, 256)
                        if clase.value.lower() not in protegidas and buf.value:
                            PostMessageW(hwnd, 0x0010, 0, 0)
                            cerradas += 1
                    self.iniciar_analisis_continuo(); return True
                EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))(cb), 0)
                hablar(f"Cerre {cerradas} ventanas. Las del sistema las deje xd")
            except Exception as e:
                hablar(f"Error cerrando: {e}")
        threading.Thread(target=_cerrar_todas, daemon=True).start()

    elif nombre == "siempre_encima":
        def _encima():
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd:
                    ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001|0x0002)
                    hablar("Ventana siempre encima activada xd")
                else:
                    hablar("No hay ventana activa xd")
            except: hablar("No pude hacer esto xd")
        threading.Thread(target=_encima, daemon=True).start()

    elif nombre == "info_pc":
        def _info_pc():
            try:
                import platform
                msg = f"Sistema: {platform.system()} {platform.release()}, "
                msg += f"Procesador: {platform.processor()[:40]}, "
                if PSUTIL_OK:
                    vm = psutil.virtual_memory()
                    msg += f"RAM: {vm.total/(1024**3):.1f} GB total, {vm.percent}% usada, "
                    dk = psutil.disk_usage('/')
                    msg += f"Disco: {dk.total/(1024**3):.1f} GB total, {dk.percent}% usado, "
                    msg += f"CPU: {psutil.cpu_count()} nucleos."
                hablar(msg + " xd")
            except Exception as e:
                hablar(f"Error obteniendo info: {e}")
        threading.Thread(target=_info_pc, daemon=True).start()

    elif nombre == "abrir_panel":
        p = params.get("nombre_panel","").lower()
        paneles_map = {"camara":"camara","vision":"camara","sistema":"sistema","monitor":"sistema",
                       "archivos":"archivos","archivos":"archivos","historial":"historial","history":"historial",
                       "codigo":"codigo","code":"codigo","code generator":"codigo"}
        panel = paneles_map.get(p)
        if panel and estado.app:
            estado.app.after(0, lambda pn=panel: estado.app.mostrar_panel(pn))
            threading.Thread(target=lambda: hablar(f"Abriendo panel de {p} xd"), daemon=True).start()
        else:
            threading.Thread(target=lambda: hablar(f"No conozco el panel '{p}'. Puedo: camara, sistema, archivos, historial, codigo xd"), daemon=True).start()

    elif nombre == "cerrar_panel":
        p = params.get("nombre_panel","").lower()
        paneles_map = {"camara":"camara","vision":"camara","sistema":"sistema","monitor":"sistema",
                       "archivos":"archivos","historial":"historial","history":"historial",
                       "codigo":"codigo","code":"codigo","todos":"all","all":"all","todo":"all"}
        panel = paneles_map.get(p)
        if panel and estado.app:
            def _cerrar():
                if panel == "all":
                    for pname, pw in list(estado.app.panels.items()):
                        try: pw.withdraw()
                        except: pass
                    threading.Thread(target=lambda: hablar("Cerre todos los paneles xd"), daemon=True).start()
                elif panel in estado.app.panels:
                    estado.app.panels[panel].withdraw()
                    threading.Thread(target=lambda: hablar(f"Cerre el panel de {p} xd"), daemon=True).start()
                else:
                    threading.Thread(target=lambda: hablar(f"El panel {p} no esta abierto xd"), daemon=True).start()
            estado.app.after(0, _cerrar)
        else:
            threading.Thread(target=lambda: hablar(f"No se que panel cerrar. Puedo: camara, sistema, archivos, historial, codigo, todos xd"), daemon=True).start()

    elif nombre == "generar_codigo":
        desc = params.get("descripcion", params.get("texto", ""))
        if not desc:
            threading.Thread(target=lambda: hablar("Que codigo quieres que genere?"), daemon=True).start()
            return
        def _gen_codigo():
            try:
                estado.set_estado("PROCESANDO")
                hablar(f"Generando codigo para: {desc}")
                r = groq_client.chat.completions.create(
                    model=MODELO_LLM,
                    messages=[
                        {"role":"system","content":"Eres Jarvis. Escribe Python funcional y completo. Solo el codigo en bloque markdown python. Sin explicaciones extras."},
                        {"role":"user","content":desc}
                    ], max_tokens=1500
                )
                txt = r.choices[0].message.content
                import re
                bloques = re.findall(r'```(?:python)?\s*\n(.*?)```', txt, re.DOTALL)
                codigo = bloques[0].strip() if bloques else txt.strip()
                tmp = os.path.join(os.environ.get("TEMP",os.path.expanduser("~")), "jarvis_codigo_gen.py")
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(codigo)
                hablar(f"Listo. Guarde el codigo en {tmp}. Te lo abro?")
                os.startfile(tmp)
                estado.set_estado("ESCUCHANDO")
            except Exception as e:
                hablar(f"Error generando codigo: {e}")
                estado.set_estado("ESCUCHANDO")
        threading.Thread(target=_gen_codigo, daemon=True).start()

    elif nombre == "saltar_anuncios_youtube":
        def _yt_skip():
            toggle = yt_skipper.toggle()
            if toggle:
                hablar("Saltador de anuncios de YouTube activado. Detectare y saltare los anuncios automaticamente xd")
            else:
                hablar("Saltador de anuncios de YouTube desactivado xd")
            estado.set_estado("ESCUCHANDO")
        threading.Thread(target=_yt_skip, daemon=True).start()

    elif nombre == "airdrop":
        def _airdrop():
            if not AIRDROP_OK:
                hablar("Modulo de AirDrop no disponible. Instala las dependencias.")
                return
            
            # Detectar si es mensaje o archivos
            texto_lower = texto.lower() if 'texto' in dir() else ""
            es_mensaje = any(p in texto_lower for p in ["mensaje", "texto", "escribe"])
            
            if es_mensaje:
                # Modo mensaje
                msg = params.get("texto", params.get("mensaje", ""))
                if msg:
                    # Si ya hay mensaje, abrir ventana directamente
                    if estado.app:
                        estado.app.after(0, lambda: airdrop_window.show(mode='message', message=msg))
                else:
                    hablar("Escribe el mensaje que quieres enviar")
                    if estado.app:
                        estado.app.after(0, lambda: airdrop_window.show(mode='message'))
            else:
                # Modo archivos
                if estado.app:
                    estado.app.after(0, lambda: airdrop_window.show(mode='files'))
            
            estado.set_estado("ESCUCHANDO")
        
        threading.Thread(target=_airdrop, daemon=True).start()

    elif nombre == "airdrop_discover":
        def _discover():
            if not AIRDROP_OK:
                hablar("Modulo de AirDrop no disponible")
                return
            
            hablar("Escaneando dispositivos cercanos...")
            
            devices = airdrop_manager.scan_and_remember()
            
            if devices:
                apple_count = sum(1 for d in devices if d.get('type', '').startswith(('iphone', 'ipad', 'mac', 'apple')))
                msg = f"Encontre {len(devices)} dispositivos"
                if apple_count > 0:
                    msg += f", {apple_count} de Apple"
                msg += ". "
                
                # Mostrar algunos dispositivos
                for d in devices[:3]:
                    msg += f"{d['name']}, "
                if len(devices) > 3:
                    msg += f"y {len(devices)-3} mas. "
                
                hablar(msg)
                
                # Abrir ventana para seleccionar
                if estado.app:
                    estado.app.after(0, lambda: airdrop_window.show(mode='files'))
            else:
                hablar("No encontre dispositivos Apple cercanos. Asegurate de que Bluetooth este activado.")
            
            estado.set_estado("ESCUCHANDO")
        
        threading.Thread(target=_discover, daemon=True).start()

    else:
        hablar(f"No se que hacer con {nombre} xd")

def configurar_inicio():
    try:
        ruta = os.path.abspath(__file__)
        vbs = os.path.join(os.path.dirname(ruta), "jarvis_silencioso.vbs")
        if not os.path.exists(vbs):
            with open(vbs,"w") as f:
                f.write(f'Set W = CreateObject("WScript.Shell")\nW.Run "pythonw ""{ruta}""", 0, False\n')
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, "JARVIS_Core", 0, winreg.REG_SZ, f'wscript.exe "{vbs}"')
        winreg.CloseKey(k)
    except Exception as e:
        print(f"[STARTUP] {e}")

def rutina_despertar():
    try:
        estado.set_estado("PROCESANDO")
        meses = ["","enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
        dias = ["lunes","martes","miercoles","jueves","viernes","sabado","domingo"]
        ahora = datetime.datetime.now()
        hablar(f"Que pasa Jam! Hoy es {dias[ahora.weekday()]} {ahora.day} de {meses[ahora.month]} y son las {ahora.strftime('%I:%M %p')} xd")
        try:
            os.startfile("spotify:")
            time.sleep(3)
            pyautogui.press("playpause")
        except: pass
        try:
            clima = requests.get(f"https://wttr.in/{CIUDAD_CLIMA}?format=%t", timeout=5).text.strip()
            hablar(f"Clima: {clima} xd")
        except: pass
        try:
            url = "https://news.google.com/rss?hl=es-419&gl=CR&ceid=CR:es-419"
            r = requests.get(url, timeout=8)
            root = ET.fromstring(r.content)
            for item in root.findall('./channel/item')[:2]:
                hablar(item.find('title').text)
        except: pass
    except Exception as e:
        print(f"[RUTINA] Error: {e}")
    finally:
        estado.set_estado("ESCUCHANDO")

def loop_voz():
    r = sr.Recognizer()
    r.pause_threshold = 1.2
    mic = None
    try:
        mic = sr.Microphone()
        with mic as source:
            r.adjust_for_ambient_noise(source, duration=1)
    except:
        pass

    while True:
        try:
            if not mic:
                time.sleep(1)
                try:
                    mic = sr.Microphone()
                    with mic as source:
                        r.adjust_for_ambient_noise(source, duration=1)
                except:
                    pass
                continue

            if estado.get_hablando():
                try:
                    with mic as source:
                        audio = r.listen(source, timeout=1.5, phrase_time_limit=3)
                    texto_int = r.recognize_google(audio, language="es-ES").lower().strip()
                    print(f"[INTERRUPCION DETECTADA]: {texto_int}")
                    if any(d in texto_int for d in COMANDOS_DETENER):
                        estado.set_interrumpir(True)
                        estado.set_hablando(False)
                        try:
                            pygame.mixer.music.stop()
                        except:
                            pass
                        estado.set_estado("ESCUCHANDO")
                        time.sleep(0.3)
                        continue
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except sr.RequestError:
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[VOZ-INT] Error: {e}")
                continue

            estado.set_estado("ESCUCHANDO")
            with mic as source:
                audio = r.listen(source, timeout=5, phrase_time_limit=8)

            if estado.get_hablando():
                continue

            texto = r.recognize_google(audio, language="es-ES").lower()
            print(f"\n[JAM]: {texto}")

            if any(d in texto for d in COMANDOS_DETENER):
                estado.set_interrumpir(True)
                try:
                    pygame.mixer.music.stop()
                except:
                    pass
                estado.set_estado("ESCUCHANDO")
                continue

            alias = ["despierta jarvis","jarvis despierta","despierta jar","despierta",
                     "despierta harbi","despierta jarbis","despierta yarbis"]
            nombres = ["jarvis","harbi","jarbis","yarbis","yarvis"]

            es_wake = any(a in texto for a in alias)
            menciona = any(n in texto for n in nombres)
            activa = estado.ventana_visible and estado.debe_escuchar()

            if es_wake:
                estado.tocar_interaccion()
                estado.ventana_visible = True
                threading.Thread(target=rutina_despertar, daemon=True).start()
                continue

            if menciona or activa:
                estado.tocar_interaccion()
                if menciona:
                    estado.ventana_visible = True

                cmd = texto
                for n in nombres:
                    if n in texto:
                        partes = texto.split(n)
                        if len(partes) > 1 and partes[1].strip():
                            cmd = partes[1].strip()
                        break

                estado.set_estado("PROCESANDO")
                resultado = router_ia(cmd)
                skill = resultado.get("skill", "conversar")
                params = resultado.get("parametros", {})
                if not params:
                    params = {"texto": cmd}

                historial_cmd.append({
                    "tiempo": datetime.datetime.now().strftime("%H:%M:%S"),
                    "texto": cmd, "skill": skill
                })

                ejecutar_skill(skill, params)

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            time.sleep(1)
        except Exception as e:
            print(f"[VOZ] Error: {e}")
            mic = None
            time.sleep(1)

# ============================================================
#  INTERFAZ FUTURISTA JARVIS
# ============================================================

PARTICULAS = []
for _ in range(15):
    PARTICULAS.append({
        "angulo": math.radians(random.randint(0,360)),
        "dist": 60 + random.randint(0,50),
        "vel": 0.015 + random.randint(0,30)/1000,
        "size": 1 + random.randint(0,25)/10,
        "vida": random.random(),
    })

ang_orbita = 0
ang_pulso = 0
frame_n = 0

class JarvisApp(ctk.CTk):

    NEON = {
        'bg': '#000000',
        'bg_card': '#050510',
        'bg_dark': '#000005',
        'bg_glass': '#080818',
        'border': '#1a1a3e',
        'border_glow': '#2a2a5e',
        'primary': '#06b6d4',
        'primary_dim': '#0891b2',
        'secondary': '#7c3aed',
        'secondary_dim': '#6d28d9',
        'accent': '#f59e0b',
        'success': '#10b981',
        'error': '#ef4444',
        'text': '#e5e7eb',
        'text_dim': '#6b7280',
        'text_bright': '#f0f4ff',
    }

    def __init__(self):
        super().__init__()
        self.title("JARVIS")
        self.geometry("280x280")
        self.overrideredirect(True)
        self.attributes("-alpha", 0.95)
        self.attributes("-transparentcolor", "#050510")
        self.attributes("-topmost", True)
        self.configure(fg_color="#050510")

        self.canvas = tk.Canvas(self, width=270, height=270, bg="#050510", highlightthickness=0)
        self.canvas.pack(expand=True, fill="both")

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<Button-3>", self._menu)

        self.panels = {}
        self.panel_frames = {}

        self.after(100, self._animar)
        self.after(30, self._flotar)
        self.withdraw()

    def _crear_header(self, parent, titulo, color, subtitulo=None, icono="◈"):
        hdr = tk.Frame(parent, bg="#050510", height=52)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        glow = tk.Frame(hdr, bg=color, height=2)
        glow.pack(fill=tk.X, side=tk.BOTTOM)
        left = tk.Frame(hdr, bg="#050510")
        left.pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(left, text=icono, bg="#050510", fg=color,
                font=("Consolas", 14, "bold")).pack(side=tk.LEFT, padx=(0,4))
        tk.Label(left, text=titulo, bg="#050510", fg="#f0f4ff",
                font=("Consolas", 12, "bold")).pack(side=tk.LEFT)
        if subtitulo:
            tk.Label(left, text=subtitulo, bg="#050510", fg="#4b5563",
                    font=("Consolas", 8)).pack(side=tk.LEFT, padx=12)
        return hdr

    def _crear_btn(self, parent, texto, color, comando, icono=None):
        txt = f"{icono} {texto}" if icono else texto
        btn = tk.Button(parent, text=txt, bg=color, fg="#ffffff",
                       font=("Consolas", 9, "bold"), relief="flat",
                       padx=16, pady=5, cursor="hand2",
                       activebackground=color, activeforeground="#ffffff",
                       bd=0, highlightthickness=0,
                       command=comando)
        return btn

    def _crear_card(self, parent, color_borde, title=None):
        card = tk.Frame(parent, bg="#080818", relief="flat", bd=0,
                       highlightbackground=color_borde, highlightthickness=0)
        card.pack(fill=tk.X, pady=3)
        borde = tk.Frame(card, bg=color_borde, height=3)
        borde.pack(fill=tk.X)
        if title:
            row = tk.Frame(card, bg="#080818")
            row.pack(fill=tk.X, padx=14, pady=(10, 2))
            tk.Label(row, text=f"  {title}", bg="#080818", fg=color_borde,
                    font=("Consolas", 10, "bold"), anchor="w").pack(fill=tk.X)
        return card

    def _crear_scroll_area(self, parent, color_borde="#1a1a3e"):
        border = tk.Frame(parent, bg=color_borde, bd=1, relief="flat",
                         highlightbackground="#2a2a5e", highlightthickness=1)
        border.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 4))
        canvas = tk.Canvas(border, bg="#000005", highlightthickness=0,
                          relief="flat", bd=0)
        scroll_frame = tk.Frame(canvas, bg="#000005")
        scroll_frame.bind("<Configure>",
                         lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        scrollbar = tk.Scrollbar(border, orient="vertical", command=canvas.yview,
                                bg="#1a1a3e", troughcolor="#000005",
                                activebackground="#06b6d4",
                                width=10, relief="flat", bd=0)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        return canvas, scroll_frame

    def _drag_start(self, e):
        self._dx = e.x
        self._dy = e.y

    def _drag_move(self, e):
        x = self.winfo_x() + e.x - self._dx
        y = self.winfo_y() + e.y - self._dy
        self.geometry(f"+{x}+{y}")
        estado.base_x = x
        estado.base_y = y

    def _menu(self, e):
        N = self.NEON
        menu = tk.Menu(self, tearoff=0, bg="#050510", fg=N['text'],
                      activebackground=N['secondary'], activeforeground="#ffffff",
                      font=("Consolas", 10),
                      borderwidth=1, relief="solid",
                      selectcolor=N['primary'])
        menu.add_command(label="◆ Vision (Camara)", command=lambda: self.mostrar_panel("camara"))
        menu.add_command(label="■ System Monitor", command=lambda: self.mostrar_panel("sistema"))
        menu.add_command(label="▲ File Explorer", command=lambda: self.mostrar_panel("archivos"))
        menu.add_command(label="● Command History", command=lambda: self.mostrar_panel("historial"))
        menu.add_command(label="✦ Code Generator", command=lambda: self.mostrar_panel("codigo"))
        menu.add_separator()
        menu.add_command(label="◎ Estado de Jarvis", command=lambda: ejecutar_skill(".estado_jarvis",{}))
        menu.add_separator()
        menu.add_command(label="⊙ Ocultar", command=lambda: setattr(estado,"ventana_visible",False))
        menu.tk_popup(e.x_root, e.y_root)

    def _animar(self):
        global ang_orbita, ang_pulso, frame_n
        hablando = estado.get_hablando()
        estado_actual = estado.get_estado()
        paso_pulso = 0.4 if hablando else 0.08
        paso_orbita = 16 if hablando else 3
        frame_n += 1
        ang_pulso += paso_pulso
        ang_orbita += paso_orbita
        t = frame_n * 0.1

        c = self.canvas
        c.delete("all")
        cx, cy = 135, 135

        colores_estado = {
            "ESCUCHANDO": ("#06b6d4", "#0891b2", "#0e7490", "#38bdf8"),
            "PENSANDO": ("#f59e0b", "#d97706", "#b45309", "#fbbf24"),
            "PROCESANDO": ("#8b5cf6", "#7c3aed", "#6d28d9", "#a78bfa"),
            "HABLANDO": ("#a78bfa", "#8b5cf6", "#7c3aed", "#c4b5fd"),
            "INICIALIZANDO": ("#ef4444", "#dc2626", "#b91c1c", "#f87171"),
            "INICIANDO": ("#ef4444", "#dc2626", "#b91c1c", "#f87171"),
        }
        c1, c2, c3, c4 = colores_estado.get(estado_actual, ("#06b6d4", "#0891b2", "#0e7490", "#38bdf8"))

        # Outer glow ring
        for i in range(8):
            r = 130 + i * 4
            alpha = 0.08 - i * 0.008
            if alpha <= 0:
                break
            r_part = int(r)
            col_g = f"#{int(int(c1[1:3],16)*alpha):02x}{int(int(c1[3:5],16)*alpha):02x}{int(int(c1[5:7],16)*alpha):02x}"
            c.create_oval(cx-r_part, cy-r_part, cx+r_part, cy+r_part,
                         outline=col_g, width=1)

        # Hexagonal grid
        for i in range(6):
            ang_hex = math.radians(60 * i) + t * 0.3
            r_ext = 108 + math.sin(t * 0.5 + i) * 5
            r_int = 92 + math.sin(t * 0.5 + i) * 5
            x1 = cx + math.cos(ang_hex) * r_ext
            y1 = cy + math.sin(ang_hex) * r_ext
            x2 = cx + math.cos(ang_hex + math.radians(60)) * r_ext
            y2 = cy + math.sin(ang_hex + math.radians(60)) * r_ext
            x3 = cx + math.cos(ang_hex + math.radians(30)) * r_int
            y3 = cy + math.sin(ang_hex + math.radians(30)) * r_int
            x4 = cx + math.cos(ang_hex + math.radians(90)) * r_int
            y4 = cy + math.sin(ang_hex + math.radians(90)) * r_int
            opacidad = 0.35 + 0.2 * math.sin(t + i)
            col_hex = f"#{int(int(c2[1:3],16)*opacidad):02x}{int(int(c2[3:5],16)*opacidad):02x}{int(int(c2[5:7],16)*opacidad):02x}"
            c.create_line(x1, y1, x2, y2, fill=col_hex, width=1)
            c.create_line(x3, y3, x4, y4, fill=col_hex, width=1)

        # Concentric rings
        for i in range(5):
            r = 112 + i * 4
            alpha = 0.5 - i * 0.08
            col_linea = f"#{int(int(c2[1:3],16)*alpha):02x}{int(int(c2[3:5],16)*alpha):02x}{int(int(c2[5:7],16)*alpha):02x}"
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col_linea, width=1)

        # Rotating arcs
        for i in range(4):
            r = 88 + i * 10
            extent_rot = 45 + 12 * math.sin(t * 0.8 + i)
            offset = ang_orbita + i * 90
            c.create_arc(cx-r, cy-r, cx+r, cy+r, start=offset, extent=extent_rot,
                        outline=c1, width=2, style=tk.ARC)
            c.create_arc(cx-r, cy-r, cx+r, cy+r, start=offset + 180, extent=extent_rot,
                        outline=c1, width=2, style=tk.ARC)

        # Core pulsing orb
        rn_base = 38
        rn_pulso = math.sin(ang_pulso) * (20 if hablando else 6)
        rn = rn_base + rn_pulso

        # Outer glow
        for g in range(3, 0, -1):
            gr = rn + 8 + g * 6
            ga = 0.15 / (g + 1)
            col_g = f"#{int(int(c1[1:3],16)*ga):02x}{int(int(c1[3:5],16)*ga):02x}{int(int(c1[5:7],16)*ga):02x}"
            c.create_oval(cx-gr, cy-gr, cx+gr, cy+gr, fill=col_g, outline="")

        c.create_oval(cx-rn-8, cy-rn-8, cx+rn+8, cy+rn+8, outline=c2, width=1)
        c.create_oval(cx-rn-4, cy-rn-4, cx+rn+4, cy+rn+4, outline=c3, width=1)
        c.create_oval(cx-rn, cy-rn, cx+rn, cy+rn, fill=c1, outline=c2, width=2)

        # Inner iris
        ri = rn * 0.55
        c.create_oval(cx-ri, cy-ri, cx+ri, cy+ri, fill=c2, outline="")

        # Center glow highlight
        br = 14 + math.sin(t * 2.5) * 6
        c.create_oval(cx-br, cy-br-7, cx+br, cy+br-7, fill="#e0e7ff", outline="")

        # Orbiting particle arcs
        for i in range(3):
            r_orbita = 58 + i * 15
            ang = -ang_orbita * (0.8 + i * 0.3) + i * 90
            extent_a = 70 + 22 * math.sin(t + i)
            c.create_arc(cx-r_orbita, cy-r_orbita, cx+r_orbita, cy+r_orbita,
                        start=ang, extent=extent_a, outline=c4, width=2, style=tk.ARC)
            c.create_arc(cx-r_orbita, cy-r_orbita, cx+r_orbita, cy+r_orbita,
                        start=ang + 180, extent=extent_a, outline=c4, width=2, style=tk.ARC)

        # Data dots
        for i in range(2):
            r_dat = 72 + i * 22
            for j in range(4):
                ang_d = math.radians(j * 90 + ang_orbita * (1.5 + i * 0.5))
                dx = cx + math.cos(ang_d) * r_dat
                dy = cy + math.sin(ang_d) * r_dat
                sz = 2 + math.sin(t * 3 + j + i * 2) * 1
                c.create_oval(dx-sz, dy-sz, dx+sz, dy+sz, fill=c4, outline="")

        # Particle system
        for p in PARTICULAS:
            p["angulo"] += p["vel"] * (3.0 if hablando else 1.0)
            p["dist"] += 0.1 if not hablando else 0.3
            p["vida"] -= 0.005 if not hablando else 0.015
            if p["vida"] <= 0:
                p["angulo"] = math.radians(random.randint(0, 360))
                p["dist"] = 55 + random.randint(0, 55)
                p["vida"] = 1.0
            px = cx + math.cos(p["angulo"]) * p["dist"]
            py = cy + math.sin(p["angulo"]) * p["dist"]
            if 5 < px < 265 and 5 < py < 265:
                sz = p["size"] * p["vida"] * (2.0 if hablando else 1.0)
                alpha_p = min(p["vida"] * 0.9, 0.9)
                col_p = f"#{int(int(c1[1:3],16)*alpha_p):02x}{int(int(c1[3:5],16)*alpha_p):02x}{int(int(c1[5:7],16)*alpha_p):02x}"
                c.create_oval(px-sz, py-sz, px+sz, py+sz, fill=col_p, outline="")

        # Sound wave rings when speaking
        if hablando:
            for i in range(4):
                r_ond = rn + 18 + i * 12 + (frame_n % 20)
                if r_ond < 130:
                    alpha_w = 0.5 - i * 0.1
                    col_w = f"#{int(int(c1[1:3],16)*alpha_w):02x}{int(int(c1[3:5],16)*alpha_w):02x}{int(int(c1[5:7],16)*alpha_w):02x}"
                    c.create_oval(cx-r_ond, cy-r_ond, cx+r_ond, cy+r_ond,
                                outline=col_w, width=1)

        # Thinking particles
        if estado_actual == "PENSANDO":
            for i in range(4):
                ang_p = math.radians(i * 90 + ang_orbita * 3)
                r_p = 28 + 8 * math.sin(t * 4 + i)
                px = cx + math.cos(ang_p) * r_p
                py = cy + math.sin(ang_p) * r_p
                sz = 3 + 2 * math.sin(t * 5 + i)
                c.create_oval(px-sz, py-sz, px+sz, py+sz, fill="#fbbf24", outline="")

        # Outer anchor dots
        for i in range(6):
            ang_s = math.radians(60 * i) + t * 0.2
            r_s = 116
            sx = cx + math.cos(ang_s) * r_s
            sy = cy + math.sin(ang_s) * r_s
            sz_s = 1.5 + 0.5 * math.sin(t + i)
            c.create_oval(sx-sz_s, sy-sz_s, sx+sz_s, sy+sz_s, fill="#4b5563", outline="")

        # HUD scan lines
        for i in range(3):
            y_lin = 30 + i * 95 + int(math.sin(t + i) * 5)
            c.create_line(20, y_lin, 250, y_lin, fill="#1e293b", width=1)

        # Labels
        col_label = c1
        c.create_text(cx, cy + rn + 24, text=estado_actual, fill=col_label,
                     font=("Consolas", 8, "bold"))
        c.create_text(cx, cy - rn - 24, text="J A R V I S", fill=c4,
                     font=("Consolas", 10, "bold"))

        self.after(40, self._animar)

    def _flotar(self):
        global estado
        ahora = time.time()
        if estado.ventana_visible and (ahora - estado.ultima_interaccion > 45) and not estado.get_hablando():
            estado.ventana_visible = False
        try:
            if estado.ventana_visible:
                if self.state() == "withdrawn":
                    self.deiconify()
                    self.lift()
                    self.attributes("-topmost", True)
            else:
                if self.state() != "withdrawn":
                    self.withdraw()
        except: pass

        amp = 2.0 if estado.get_hablando() else 0.5
        vel = 0.12 if estado.get_hablando() else 0.04
        try:
            x = self.winfo_x()
            y = self.winfo_y()
            dx = math.sin(time.time()*vel*10) * amp
            dy = math.cos(time.time()*vel*13) * amp
            nx = x + (estado.base_x - x)*0.08 + dx
            ny = y + (estado.base_y - y)*0.08 + dy
            self.geometry(f"+{int(nx)}+{int(ny)}")
        except: pass
        self.after(35, self._flotar)

    def mostrar_panel(self, nombre):
        if nombre == "camara":
            self._panel_camara()
        elif nombre == "sistema":
            self._panel_sistema()
        elif nombre == "archivos":
            self._panel_archivos()
        elif nombre == "historial":
            self._panel_historial()
        elif nombre == "codigo":
            self._panel_codigo()

    def cargar_archivos(self, info):
        if "archivos" in self.panels:
            self.panels["archivos"]._llenar(info)

    def _panel_camara(self):
        if "camara" in self.panels:
            self.panels["camara"].deiconify()
            self.panels["camara"].lift()
            return

        N = self.NEON
        p = tk.Toplevel(self)
        p.title("JARVIS VISION")
        p.geometry("720x600+30+30")
        p.configure(bg=N['bg'])
        p.attributes("-topmost", True)
        p.protocol("WM_DELETE_WINDOW", lambda: (p.withdraw(), cam.cerrar()))

        hdr = self._crear_header(p, "VISION SYSTEM", N['primary'], "Analisis visual en tiempo real", "◈")

        status_row = tk.Frame(hdr, bg="#050510")
        status_row.pack(side=tk.RIGHT, padx=16, pady=8)
        self._cam_status = tk.Label(status_row, text="● ONLINE", bg="#050510", fg=N['success'],
                                   font=("Consolas", 8, "bold"))
        self._cam_status.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(status_row, text=f"{MODELO_VISION.split('/')[1][:12]}", bg="#050510", fg=N['secondary'],
                font=("Consolas", 7)).pack(side=tk.LEFT)

        border = tk.Frame(p, bg=N['border'], bd=1, relief="flat",
                         highlightbackground=N['border_glow'], highlightthickness=1)
        border.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 4))
        self._cam_canvas = tk.Canvas(border, bg=N['bg_dark'], highlightthickness=0)
        self._cam_canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        info_frame = tk.Frame(p, bg="#050510")
        info_frame.pack(fill=tk.X, padx=10, pady=(2, 0))
        inner_info = tk.Frame(info_frame, bg="#080818")
        inner_info.pack(fill=tk.X, padx=0, pady=0)
        tk.Frame(inner_info, bg=N['primary'], height=1).pack(fill=tk.X)
        self._cam_info = tk.Label(inner_info, text="✦ Esperando feed de camara...",
                                 bg="#080818", fg=N['primary'],
                                 font=("Consolas", 9, "bold"), anchor="w")
        self._cam_info.pack(fill=tk.X, padx=10, pady=6)

        bf = tk.Frame(p, bg=N['bg'])
        bf.pack(fill=tk.X, padx=10, pady=(4, 10))

        btn_analizar = self._crear_btn(bf, "ANALIZAR", N['secondary'], self._cam_analizar, "◈")
        btn_analizar.pack(side=tk.LEFT, padx=3)

        btn_auto = self._crear_btn(bf, "AUTO-SCAN", N['primary'], self._cam_auto_toggle, "◎")
        btn_auto.pack(side=tk.LEFT, padx=3)

        btn_close = self._crear_btn(bf, "CERRAR", N['error'], lambda: (p.withdraw(), cam.cerrar()), "✕")
        btn_close.pack(side=tk.RIGHT, padx=3)

        self.panels["camara"] = p
        self._cam_auto = False
        self._cam_scan_y = 0
        self._cam_feed_loop()

    def _cam_feed_loop(self):
        p = self.panels.get("camara")
        if not p or not p.winfo_exists():
            return
        if not cam.running:
            self.after(200, self._cam_feed_loop)
            return

        frame = cam.leer_frame()
        if frame is not None:
            if cam.objetos:
                frame = cam.dibujar_bboxes(frame, cam.objetos)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            sc = min(656/w, 400/h)
            nw, nh = int(w*sc), int(h*sc)
            rsz = cv2.resize(rgb, (nw, nh))

            ov = rsz.copy()
            self._cam_scan_y = (self._cam_scan_y + 2) % nh
            for i in range(3):
                y = (self._cam_scan_y + i*2) % nh
                cv2.line(ov, (0,y), (nw,y), (0,255,255), 1)

            m = 15
            for (x1,y1,x2,y2) in [(m,m,m+18,m),(m,m,m,m+18),(nw-m,m,nw-m-18,m),(nw-m,m,nw-m,m+18),
                                    (m,nh-m,m+18,nh-m),(m,nh-m,m,nh-m-18),(nw-m,nh-m,nw-m-18,nh-m),(nw-m,nh-m,nw-m,nh-m-18)]:
                cv2.line(ov,(x1,y1),(x2,y2),(0,255,255),2)

            chx, chy = nw//2, nh//2
            cs = 25
            cv2.line(ov,(chx-cs,chy),(chx-6,chy),(0,255,255),1)
            cv2.line(ov,(chx+6,chy),(chx+cs,chy),(0,255,255),1)
            cv2.line(ov,(chx,chy-cs),(chx,chy-6),(0,255,255),1)
            cv2.line(ov,(chx,chy+6),(chx,chy+cs),(0,255,255),1)
            cv2.circle(ov,(chx,chy),cs+4,(0,255,255),1)

            ts = datetime.datetime.now().strftime("%H:%M:%S")
            cv2.putText(ov,f"JARVIS VISION | {ts}",(8,nh-8),cv2.FONT_HERSHEY_SIMPLEX,0.35,(0,255,255),1)
            if cam.objetos:
                cv2.putText(ov,f"OBJ: {len(cam.objetos)}",(nw-100,nh-8),cv2.FONT_HERSHEY_SIMPLEX,0.35,(0,255,255),1)

            img = Image.fromarray(ov)
            imgtk = ImageTk.PhotoImage(image=img)
            self._cam_canvas.delete("all")
            self._cam_canvas.create_image(nw//2, nh//2, image=imgtk, anchor=tk.CENTER)
            self._cam_canvas._imgtk = imgtk

            if cam.objetos:
                nombres = [o.get("nombre","?") for o in cam.objetos[:3]]
                self._cam_info.config(text=f"DETECTADO: {', '.join(nombres)} | {cam.ultimo_analisis[:60]}")

        self.after(33, self._cam_feed_loop)

    def _cam_analizar(self):
        frame = cam.leer_frame()
        if frame is not None:
            self._cam_status.config(text="● ANALYZING", fg="#f59e0b")
            def _hacer():
                r = cam.analizar_ia(frame)
                self.after(0, lambda: self._cam_info.config(text=r[:80]))
                self.after(0, lambda: self._cam_status.config(text="● ONLINE", fg="#10b981"))
            threading.Thread(target=_hacer, daemon=True).start()

    def _cam_auto_toggle(self):
        self._cam_auto = not self._cam_auto
        if self._cam_auto:
            self._cam_status.config(text="● AUTO-SCAN", fg="#f59e0b")
            self._cam_auto_analizar()
        else:
            self._cam_status.config(text="● ONLINE", fg="#10b981")

    def _cam_auto_analizar(self):
        if not self._cam_auto:
            return
        frame = cam.leer_frame()
        if frame is not None:
            threading.Thread(target=lambda: cam.analizar_ia(frame), daemon=True).start()
        self.after(3000, self._cam_auto_analizar)

    def _panel_sistema(self):
        if "sistema" in self.panels:
            self.panels["sistema"].deiconify()
            self.panels["sistema"].lift()
            self._sys_refresh()
            return

        N = self.NEON
        p = tk.Toplevel(self)
        p.title("JARVIS SYSTEM")
        p.geometry("480x660+30+30")
        p.configure(bg=N['bg'])
        p.attributes("-topmost", True)
        p.protocol("WM_DELETE_WINDOW", lambda: p.withdraw())

        hdr = self._crear_header(p, "SYSTEM MONITOR", N['primary'], "Rendimiento en tiempo real", "◈")

        main = tk.Frame(p, bg=N['bg'])
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self._sys_cards = {}
        for key, title, color in [("cpu","CPU",N['primary']),("ram","RAM",N['secondary']),("disco","DISCO",N['accent'])]:
            card = tk.Frame(main, bg="#080818", relief="flat", bd=0,
                          highlightbackground=N['border'], highlightthickness=0)
            card.pack(fill=tk.X, pady=4)
            tk.Frame(card, bg=color, height=3).pack(fill=tk.X)
            row = tk.Frame(card, bg="#080818")
            row.pack(fill=tk.X, padx=14, pady=(10, 2))
            tk.Label(row, text=f"  {title}", bg="#080818", fg=color,
                    font=("Consolas", 10, "bold"), anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="0%", bg="#080818", fg=N['text'],
                          font=("Consolas", 14, "bold"))
            val.pack(side=tk.RIGHT)
            bar = tk.Canvas(card, bg=N['bg_dark'], height=16, highlightthickness=0)
            bar.pack(fill=tk.X, padx=14, pady=(4, 2))
            det = tk.Label(card, text="", bg="#080818", fg=N['text_dim'],
                          font=("Consolas", 8), anchor="w")
            det.pack(fill=tk.X, padx=14, pady=(0, 10))
            self._sys_cards[key] = {"val": val, "bar": bar, "det": det}

        # Procesos card
        proc_card = tk.Frame(main, bg="#080818", relief="flat", bd=0,
                           highlightbackground=N['border'], highlightthickness=0)
        proc_card.pack(fill=tk.X, pady=4)
        tk.Frame(proc_card, bg=N['success'], height=3).pack(fill=tk.X)
        tk.Label(proc_card, text="  PROCESOS ACTIVOS", bg="#080818", fg=N['success'],
                font=("Consolas", 10, "bold"), anchor="w").pack(fill=tk.X, padx=14, pady=(10, 4))
        self._sys_proc = tk.Label(proc_card, text="", bg="#080818", fg=N['text_dim'],
                                 font=("Consolas", 8), anchor="w", justify="left")
        self._sys_proc.pack(fill=tk.X, padx=14, pady=(0, 10))

        # Antivirus card
        av_card = tk.Frame(main, bg="#080818", relief="flat", bd=0,
                         highlightbackground=N['border'], highlightthickness=0)
        av_card.pack(fill=tk.X, pady=4)
        tk.Frame(av_card, bg=N['error'], height=3).pack(fill=tk.X)
        tk.Label(av_card, text="  SEGURIDAD", bg="#080818", fg=N['error'],
                font=("Consolas", 10, "bold"), anchor="w").pack(fill=tk.X, padx=14, pady=(10, 4))
        self._sys_av = tk.Label(av_card, text="", bg="#080818", fg=N['text_dim'],
                               font=("Consolas", 8), anchor="w")
        self._sys_av.pack(fill=tk.X, padx=14, pady=(0, 10))

        bf = tk.Frame(p, bg=N['bg'])
        bf.pack(fill=tk.X, padx=10, pady=(4, 10))

        btn_refresh = self._crear_btn(bf, "REFRESH", N['secondary'], self._sys_refresh, "◈")
        btn_refresh.pack(side=tk.LEFT, padx=3)
        btn_close = self._crear_btn(bf, "CERRAR", N['error'], lambda: p.withdraw(), "✕")
        btn_close.pack(side=tk.RIGHT, padx=3)

        self.panels["sistema"] = p
        self._sys_refresh()

    def _sys_refresh(self):
        if not PSUTIL_OK: return
        def _cargar():
            try:
                cpu = psutil.cpu_percent(interval=0.5)
                vm = psutil.virtual_memory()
                dk = psutil.disk_usage('/')
                top = sorted(psutil.process_iter(['name','cpu_percent']),
                            key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:5]

                av_text = "Verificando..."
                try:
                    r = subprocess.run(["powershell","-Command",
                        "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled | ConvertTo-Json"],
                        capture_output=True, text=True, timeout=8)
                    if r.returncode == 0:
                        d = json.loads(r.stdout)
                        av_text = f"Defender: {'ON' if d.get('AntivirusEnabled') else 'OFF'} | RT: {'ON' if d.get('RealTimeProtectionEnabled') else 'OFF'}"
                except: av_text = "No disponible"

                def actualizar():
                    self._sys_cards["cpu"]["val"].config(text=f"{cpu}%")
                    self._dibujar_barra(self._sys_cards["cpu"]["bar"], cpu, "#06b6d4")
                    self._sys_cards["cpu"]["det"].config(text="")

                    self._sys_cards["ram"]["val"].config(text=f"{vm.percent}%")
                    self._dibujar_barra(self._sys_cards["ram"]["bar"], vm.percent, "#7c3aed")
                    self._sys_cards["ram"]["det"].config(text=f"{vm.used/(1024**3):.1f} / {vm.total/(1024**3):.1f} GB")

                    self._sys_cards["disco"]["val"].config(text=f"{dk.percent}%")
                    self._dibujar_barra(self._sys_cards["disco"]["bar"], dk.percent, "#f59e0b")
                    self._sys_cards["disco"]["det"].config(text=f"{dk.used/(1024**3):.1f} / {dk.total/(1024**3):.1f} GB")

                    proc_text = f"{len(psutil.pids())} procesos\n"
                    for p in top:
                        proc_text += f"  {p.info['name'][:20]:<22} {p.info['cpu_percent']:>5.1f}%\n"
                    self._sys_proc.config(text=proc_text.strip())
                    self._sys_av.config(text=av_text)

                self.after(0, actualizar)
            except Exception as e:
                print(f"[SYS] {e}")
        threading.Thread(target=_cargar, daemon=True).start()

    def _dibujar_barra(self, canvas, pct, color):
        canvas.delete("all")
        w = canvas.winfo_width()
        if w <= 1: w = 400
        h = canvas.winfo_height()
        canvas.create_rectangle(0, 0, w, h, fill="#000005", outline=self.NEON['border'], width=1)
        if pct > 0:
            fw = int(w * pct / 100)
            canvas.create_rectangle(0, 0, fw, h, fill=color, outline="")
            if fw > 4:
                canvas.create_rectangle(fw-4, 0, fw, h, fill="#ffffff", outline="",
                                       stipple="gray25")

    def _panel_archivos(self):
        if "archivos" in self.panels:
            self.panels["archivos"].deiconify()
            self.panels["archivos"].lift()
            return

        N = self.NEON
        p = tk.Toplevel(self)
        p.title("JARVIS FILES")
        p.geometry("600x560+30+30")
        p.configure(bg=N['bg'])
        p.attributes("-topmost", True)
        p.protocol("WM_DELETE_WINDOW", lambda: p.withdraw())

        hdr = self._crear_header(p, "FILE EXPLORER", N['primary'], "Navegador de archivos", "◈")

        nav = tk.Frame(p, bg="#080818")
        nav.pack(fill=tk.X, padx=10, pady=(8, 4))
        self._file_ruta = os.path.expanduser("~")
        self._file_lbl_ruta = tk.Label(nav, text=self._file_ruta, bg="#080818", fg=N['primary'],
                                      font=("Consolas", 8, "bold"), anchor="w")
        self._file_lbl_ruta.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        btn_atras = self._crear_btn(nav, "◀", N['primary_dim'], self._file_atras)
        btn_atras.pack(side=tk.RIGHT, padx=2)
        btn_inicio = self._crear_btn(nav, "⌂", N['secondary'], self._file_inicio)
        btn_inicio.pack(side=tk.RIGHT, padx=2)

        self._file_count = tk.Label(nav, text="", bg="#080818", fg=N['text_dim'],
                                   font=("Consolas", 8))
        self._file_count.pack(side=tk.RIGHT, padx=8)

        border = tk.Frame(p, bg=N['border'], bd=1, relief="flat",
                         highlightbackground=N['border_glow'], highlightthickness=1)
        border.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 4))
        self._file_canvas = tk.Canvas(border, bg=N['bg_dark'], highlightthickness=0,
                                     relief="flat", bd=0)
        self._file_list = tk.Frame(self._file_canvas, bg=N['bg_dark'])
        self._file_list.bind("<Configure>", lambda e: self._file_canvas.configure(scrollregion=self._file_canvas.bbox("all")))
        self._file_canvas.create_window((0,0), window=self._file_list, anchor="nw")
        sc = tk.Scrollbar(border, orient="vertical", command=self._file_canvas.yview,
                         bg=N['border'], troughcolor=N['bg_dark'],
                         activebackground=N['primary'], width=10, relief="flat", bd=0)
        self._file_canvas.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        self._file_canvas.pack(side="left", fill="both", expand=True)

        bf = tk.Frame(p, bg=N['bg'])
        bf.pack(fill=tk.X, padx=10, pady=(4, 10))
        btn_close = self._crear_btn(bf, "CERRAR", N['error'], lambda: p.withdraw(), "✕")
        btn_close.pack(side=tk.RIGHT, padx=3)

        self.panels["archivos"] = p
        self._file_listar(self._file_ruta)

    def _file_listar(self, ruta):
        N = self.NEON
        self._file_ruta = ruta
        self._file_lbl_ruta.config(text=ruta)
        for w in self._file_list.winfo_children(): w.destroy()
        try:
            items = sorted(os.listdir(ruta))
            dirs = [i for i in items if os.path.isdir(os.path.join(ruta, i))]
            files = [i for i in items if not os.path.isdir(os.path.join(ruta, i))]
            if hasattr(self, '_file_count'):
                self._file_count.config(text=f"{len(dirs)} carpetas | {len(files)} archivos")

            if dirs:
                sep = tk.Frame(self._file_list, bg="#080818")
                sep.pack(fill=tk.X, padx=8, pady=(6, 2))
                tk.Label(sep, text=" ◆ CARPETAS ", bg="#080818", fg=N['primary'],
                        font=("Consolas", 9, "bold")).pack(side=tk.LEFT)
                tk.Frame(sep, bg=N['border'], height=1).pack(fill=tk.X, expand=True, padx=5)

            for i, item in enumerate(dirs):
                rp = os.path.join(ruta, item)
                bg = "#080818" if i%2==0 else "#060612"
                row = tk.Frame(self._file_list, bg=bg)
                row.pack(fill=tk.X, padx=2)
                lbl = tk.Label(row, text=f"  ▶ {item}", bg=bg, fg=N['primary'],
                              font=("Consolas", 9, "bold"), anchor="w", cursor="hand2")
                lbl.pack(side=tk.LEFT, padx=10, pady=4, fill=tk.X, expand=True)
                lbl.bind("<Button-1>", lambda e, r=rp: self._file_listar(r))

            if files:
                sep = tk.Frame(self._file_list, bg="#080818")
                sep.pack(fill=tk.X, padx=8, pady=(6, 2))
                tk.Label(sep, text=" ◆ ARCHIVOS ", bg="#080818", fg=N['secondary'],
                        font=("Consolas", 9, "bold")).pack(side=tk.LEFT)
                tk.Frame(sep, bg=N['border'], height=1).pack(fill=tk.X, expand=True, padx=5)

            for i, item in enumerate(files):
                rp = os.path.join(ruta, item)
                bg = "#080818" if i%2==0 else "#060612"
                row = tk.Frame(self._file_list, bg=bg)
                row.pack(fill=tk.X, padx=2)
                tam = ""
                try:
                    b = os.path.getsize(rp)
                    tam = f"  {b/(1024*1024):.1f}MB" if b>1024*1024 else f"  {b/1024:.1f}KB" if b>1024 else f"  {b}B"
                except: pass
                ext = os.path.splitext(item)[1].lower()
                ext_colors = {".py":N['accent'],".exe":N['error'],".txt":N['text_dim'],
                             ".md":N['text_dim'],".json":N['success'],".jpg":N['secondary'],
                             ".png":N['secondary'],".mp3":N['secondary'],".mp4":N['primary']}
                color = ext_colors.get(ext, N['text_dim'])
                lbl = tk.Label(row, text=f"  ● {item}{tam}", bg=bg, fg=color,
                              font=("Consolas", 9), anchor="w", cursor="hand2")
                lbl.pack(side=tk.LEFT, padx=10, pady=3, fill=tk.X, expand=True)
                lbl.bind("<Button-1>", lambda e, r=rp: self._abrir_file(r))

            if not items:
                tk.Label(self._file_list, text="  Carpeta vacia", bg=N['bg_dark'], fg=N['text_dim'],
                        font=("Consolas", 10)).pack(pady=40)

        except Exception as e:
            tk.Label(self._file_list, text=f"Error: {e}", bg=N['bg_dark'], fg=N['error'],
                    font=("Consolas", 9)).pack(pady=20)

    def _file_atras(self):
        p = os.path.dirname(self._file_ruta)
        if p != self._file_ruta: self._file_listar(p)

    def _file_inicio(self):
        self._file_listar(os.path.expanduser("~"))

    def _abrir_file(self, r):
        try: os.startfile(r)
        except: pass

    def _panel_historial(self):
        if "historial" in self.panels:
            self.panels["historial"].deiconify()
            self.panels["historial"].lift()
            self._hist_llenar()
            return

        N = self.NEON
        p = tk.Toplevel(self)
        p.title("JARVIS HISTORY")
        p.geometry("520x480+30+30")
        p.configure(bg=N['bg'])
        p.attributes("-topmost", True)
        p.protocol("WM_DELETE_WINDOW", lambda: p.withdraw())

        hdr = self._crear_header(p, "COMMAND HISTORY", N['secondary'], "Ultimos comandos ejecutados", "●")

        count_frame = tk.Frame(p, bg=N['bg'])
        count_frame.pack(fill=tk.X, padx=10, pady=(4, 0))
        self._hist_count = tk.Label(count_frame, text="", bg=N['bg'], fg=N['text_dim'],
                                   font=("Consolas", 8))
        self._hist_count.pack(side=tk.LEFT, padx=4)

        border = tk.Frame(p, bg=N['border'], bd=1, relief="flat",
                         highlightbackground=N['border_glow'], highlightthickness=1)
        border.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 4))
        self._hist_canvas = tk.Canvas(border, bg=N['bg_dark'], highlightthickness=0,
                                     relief="flat", bd=0)
        self._hist_list = tk.Frame(self._hist_canvas, bg=N['bg_dark'])
        self._hist_list.bind("<Configure>", lambda e: self._hist_canvas.configure(scrollregion=self._hist_canvas.bbox("all")))
        self._hist_canvas.create_window((0,0), window=self._hist_list, anchor="nw")
        sc = tk.Scrollbar(border, orient="vertical", command=self._hist_canvas.yview,
                         bg=N['border'], troughcolor=N['bg_dark'],
                         activebackground=N['secondary'], width=10, relief="flat", bd=0)
        self._hist_canvas.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        self._hist_canvas.pack(side="left", fill="both", expand=True)

        bf = tk.Frame(p, bg=N['bg'])
        bf.pack(fill=tk.X, padx=10, pady=(4, 10))
        btn_close = self._crear_btn(bf, "CERRAR", N['error'], lambda: p.withdraw(), "✕")
        btn_close.pack(side=tk.RIGHT, padx=3)

        self.panels["historial"] = p
        self._hist_llenar()

    def _hist_llenar(self):
        N = self.NEON
        for w in self._hist_list.winfo_children(): w.destroy()
        cmds = list(reversed(historial_cmd[-50:]))
        if hasattr(self, '_hist_count'):
            self._hist_count.config(text=f"{len(cmds)} comandos")
        if not cmds:
            tk.Label(self._hist_list, text="  Sin comandos recientes", bg=N['bg_dark'], fg=N['text_dim'],
                    font=("Consolas", 10)).pack(pady=40)
            return
        skill_colors = {
            "conversar":N['text_dim'],"generar_modelo_blender":N['accent'],"analizar_pantalla":N['success'],
            "reproducir_spotify":"#1db954","abrir_app":N['primary'],"generar_imagen":N['secondary'],
            "abrir_camara":N['primary'],"analizar_objetos":N['primary'],"monitorear_sistema":N['secondary'],
            "ver_archivos":N['accent'],"buscar_archivo":N['accent']
        }
        for i, cmd in enumerate(cmds):
            bg = "#080818" if i%2==0 else "#060612"
            row = tk.Frame(self._hist_list, bg=bg)
            row.pack(fill=tk.X, padx=2, pady=1)
            sc = skill_colors.get(cmd['skill'], N['secondary'])
            tk.Label(row, text=f"  {cmd['tiempo']}", bg=bg, fg=N['text_dim'],
                    font=("Consolas", 8, "bold"), width=8, anchor="w").pack(side=tk.LEFT, padx=(8, 0))
            tk.Label(row, text=f"  {cmd['texto'][:45]}", bg=bg, fg=N['text'],
                    font=("Consolas", 9), anchor="w").pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
            tag = tk.Frame(row, bg=sc, relief="flat", bd=0)
            tag.pack(side=tk.RIGHT, padx=(0, 8), pady=2)
            tk.Label(tag, text=f" {cmd['skill'][:18]} ", bg=sc, fg="#ffffff",
                    font=("Consolas", 7, "bold")).pack()

    def _panel_codigo(self):
        if "codigo" in self.panels:
            self.panels["codigo"].deiconify()
            self.panels["codigo"].lift()
            return

        N = self.NEON
        p = tk.Toplevel(self)
        p.title("JARVIS CODE")
        p.geometry("620x540+30+30")
        p.configure(bg=N['bg'])
        p.attributes("-topmost", True)
        p.protocol("WM_DELETE_WINDOW", lambda: p.withdraw())

        hdr = self._crear_header(p, "CODE GENERATOR", N['accent'], "Genera codigo con IA", "✦")

        instr = tk.Frame(p, bg="#080818")
        instr.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(instr, text="  Describe que codigo quieres:", bg="#080818", fg=N['text_dim'],
                font=("Consolas", 9), anchor="w").pack(fill=tk.X, padx=8, pady=(6, 2))

        input_frame = tk.Frame(p, bg="#080818")
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._code_input = tk.Text(input_frame, bg=N['bg_dark'], fg=N['primary'],
                                  font=("Consolas", 10), height=3, wrap="word",
                                  insertbackground=N['primary'], selectbackground=N['border'],
                                  relief="flat", bd=0, padx=6, pady=6)
        self._code_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), pady=6)
        sc_in = tk.Scrollbar(input_frame, orient="vertical", command=self._code_input.yview,
                            bg=N['border'], troughcolor=N['bg_dark'],
                            activebackground=N['accent'], width=10, relief="flat", bd=0)
        self._code_input.configure(yscrollcommand=sc_in.set)
        sc_in.pack(side="right", fill="y", pady=6)

        btn_frame = tk.Frame(p, bg=N['bg'])
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        btn_gen = self._crear_btn(btn_frame, "GENERAR CODIGO", N['accent'], self._code_generar, "◈")
        btn_gen.pack(side=tk.LEFT, padx=3)
        btn_copiar = self._crear_btn(btn_frame, "COPIAR", N['secondary'], self._code_copiar, "◈")
        btn_copiar.pack(side=tk.LEFT, padx=3)
        btn_close = self._crear_btn(btn_frame, "CERRAR", N['error'], lambda: p.withdraw(), "✕")
        btn_close.pack(side=tk.RIGHT, padx=3)

        sep = tk.Frame(p, bg=N['border'], height=1)
        sep.pack(fill=tk.X, padx=10, pady=(0, 4))

        output_frame = tk.Frame(p, bg="#080818")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        tk.Label(output_frame, text="  Salida:", bg="#080818", fg=N['text_dim'],
                font=("Consolas", 8), anchor="w").pack(fill=tk.X, padx=8, pady=(4, 0))
        self._code_output = tk.Text(output_frame, bg=N['bg_dark'], fg=N['success'],
                                   font=("Consolas", 10), wrap="word",
                                   insertbackground=N['success'], selectbackground=N['border'],
                                   relief="flat", bd=0, state="disabled", padx=6, pady=6)
        self._code_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=(0, 6))
        sc_out = tk.Scrollbar(output_frame, orient="vertical", command=self._code_output.yview,
                             bg=N['border'], troughcolor=N['bg_dark'],
                             activebackground=N['success'], width=10, relief="flat", bd=0)
        self._code_output.configure(yscrollcommand=sc_out.set)
        sc_out.pack(side="right", fill="y", pady=(0, 6))

        self.panels["codigo"] = p

    def _code_generar(self):
        desc = self._code_input.get("1.0", "end").strip()
        if not desc:
            return
        self._code_output.config(state="normal")
        self._code_output.delete("1.0", "end")
        self._code_output.insert("1.0", "Generando codigo...")
        self._code_output.config(state="disabled")

        def _gen():
            try:
                resp = groq_client.chat.completions.create(
                    model=MODELO_LLM,
                    messages=[
                        {"role":"system","content":"Eres Jarvis. Escribe Python funcional. Solo el codigo en bloque markdown python. Sin explicaciones."},
                        {"role":"user","content":desc}
                    ], max_tokens=1500
                )
                txt = resp.choices[0].message.content
                import re
                bloques = re.findall(r'```(?:python)?\s*\n(.*?)```', txt, re.DOTALL)
                codigo = bloques[0].strip() if bloques else txt.strip()
                def _update():
                    self._code_output.config(state="normal")
                    self._code_output.delete("1.0", "end")
                    self._code_output.insert("1.0", codigo)
                    self._code_output.config(state="disabled")
                self.after(0, _update)
            except Exception as e:
                def _err():
                    self._code_output.config(state="normal")
                    self._code_output.delete("1.0", "end")
                    self._code_output.insert("1.0", f"Error: {e}")
                    self._code_output.config(state="disabled")
                self.after(0, _err)
        threading.Thread(target=_gen, daemon=True).start()

    def _code_copiar(self):
        try:
            code = self._code_output.get("1.0", "end").strip()
            if code:
                self.clipboard_clear()
                self.clipboard_append(code)
                threading.Thread(target=lambda: hablar("Codigo copiado xd"), daemon=True).start()
        except: pass

yt_skipper = YouTubeAdSkipper()

# AirDrop initialization
airdrop_manager = None
airdrop_window = None

if AIRDROP_OK:
    try:
        from modules.airdrop_manager import AirDropManager
        airdrop_manager = AirDropManager()
        print("[AIRDROP] Modulo cargado correctamente")
    except Exception as e:
        print(f"[AIRDROP] Error inicializando: {e}")
        AIRDROP_OK = False

def auto_detectar_youtube():
    print("[YT-SKIP] Auto-deteccion de YouTube iniciada")
    print(f"[YT-SKIP] Tesseract OCR: {'LISTO' if yt_skipper.tesseract_ready else 'NO DISPONIBLE (instala pytesseract + tesseract-ocr)'}")
    while True:
        try:
            if not yt_skipper.monitorizando:
                youtube_abierto = yt_skipper.detectar_youtube_ventana()
                if youtube_abierto:
                    if yt_skipper.tesseract_ready:
                        print("[YT-SKIP] YouTube detectado! Activando saltador de anuncios...")
                        yt_skipper.iniciar()
                        while yt_skipper.monitorizando:
                            time.sleep(5)
                        print("[YT-SKIP] Saltador desactivado, volviendo a monitorear...")
                    else:
                        print("[YT-SKIP] YouTube abierto pero tesseract no disponible. No puedo saltar anuncios.")
                        print("[YT-SKIP] Instala: pip install pytesseract + https://github.com/UB-Mannheim/tesseract/wiki")
                        time.sleep(15)
                else:
                    print("[YT-SKIP] YouTube no detectado, buscando...")
        except Exception as e:
            print(f"[YT-SKIP] Error auto-detect: {e}")
        time.sleep(3)

def check_inicio():
    errores = []
    if not KOKORO_OK: errores.append("Kokoro TTS")
    if not OPENCV_OK: errores.append("OpenCV")
    if not PSUTIL_OK: errores.append("psutil")
    if errores:
        print(f"[SISTEMA] Check Complete Not Error -0995 (error al iniciar): {', '.join(errores)}")
    else:
        print("[SISTEMA] Check Complete Not Error -0995")
        print(f"[SISTEMA] Skills: {len(SKILLS)} | Modelos: {MODELO_LLM}")
        print("[SISTEMA] Todos los sistemas operativos. Jarvis listo.")

configurar_inicio()
app = JarvisApp()
estado.app = app

# Initialize AirDrop window after app is created
if AIRDROP_OK and airdrop_manager:
    try:
        from ui.airdrop_window import AirDropWindow
        airdrop_window = AirDropWindow(app, airdrop_manager)
        print("[AIRDROP] Ventana inicializada")
    except Exception as e:
        print(f"[AIRDROP] Error creando ventana: {e}")

# Initialize Command Server for JarvisEnter
command_server.start()

threading.Thread(target=loop_voz, daemon=True).start()
threading.Thread(target=auto_detectar_youtube, daemon=True).start()
check_inicio()
app.mainloop()
