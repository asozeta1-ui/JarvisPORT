# Despliegue del Servidor TTS Kokoro en la Nube

## Arquitectura final

```
┌─────────────┐      BT SPP       ┌──────────────┐      WiFi/HTTPS     ┌─────────────────┐
│  Audifono   │ ◄──────────────► │    ESP32     │ ◄─────────────────► │  Railway.app    │
│  (mic+spk)  │   texto          │  JarvisPORT  │   POST /tts         │  server.py      │
└─────────────┘                  └──────────────┘                      │  Kokoro ONNX    │
                                                                       └─────────────────┘
```

## Opción A: Railway (Recomendado — más fácil)

### 1. Crear cuenta
- Ve a https://railway.app
- Regístrate con GitHub

### 2. Crear repo en GitHub
```bash
cd C:\Users\rjams\OneDrive\Documentos\Arduino\GDkey\JarvisPORT
git init
git add server.py requirements.txt Dockerfile Procfile .dockerignore
git commit -m "Jarvis TTS Kokoro server"
git remote add origin https://github.com/TU_USUARIO/jarvis-tts-kokoro.git
git push -u origin main
```

> **NO subir** los archivos `.onnx` ni `.bin` a Git (pesan ~340MB). Se descargan solos del servidor.

### 3. Desplegar en Railway
1. En Railway, New Project → Deploy from GitHub repo
2. Selecciona tu repo `jarvis-tts-kokoro`
3. Railway detecta el Dockerfile automáticamente
4. En Variables de entorno, agrega:
   - `KOKORO_VOICE` = `em_alex`
   - `KOKORO_LANG` = `es`
5. Railway asigna una URL como: `https://jarvis-tts-kokoro.up.railway.app`

### 4. Configurar el ESP32
En `apikey.h`, cambia:
```cpp
#define TTS_SERVER_URL "https://jarvis-tts-kokoro.up.railway.app"
```

### 5. Verificar
```bash
curl https://jarvis-tts-kokoro.up.railway.app/health
# Debe retornar: {"status":"ok","model_loaded":true}
```

---

## Opción B: Render (Alternativa gratis)

1. Ve a https://render.com
2. New → Web Service → Connect GitHub repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python server.py`
5. Plan Free (512MB RAM, pero Kokoro necesita ~1.5GB) → Plan Starter $7/mes
6. La URL queda: `https://jarvis-tts.onrender.com`

---

## Opción C: Fly.io (Más control)

```bash
# Instalar flyctl
curl -L https://fly.io/install.sh | sh

# Iniciar proyecto
fly launch
# Seleccionar: No, No, y darle nombre "jarvis-tts"

# Subir modelos manualmente (una vez)
fly ssh console
# Dentro del container:
curl -L -o /app/kokoro-v1.0.onnx https://huggingface.co/onnx-community/Kokoro-82M/resolve/main/kokoro-v1.0.onnx
curl -L -o /app/voices-v1.0.bin https://huggingface.co/onnx-community/Kokoro-82M/resolve/main/voices-v1.0.bin

fly deploy
```

---

## Probar localmente antes de desplegar

```bash
cd C:\Users\rjams\OneDrive\Documentos\Arduino\GDkey\JarvisPORT

# Instalar dependencias
pip install -r requirements.txt

# Copiar modelos (si no están en la carpeta actual)
copy "C:\Users\rjams\source\repos\Proyecto_Jarvis\kokoro-v1.0.onnx" .
copy "C:\Users\rjams\source\repos\Proyecto_Jarvis\voices-v1.0.bin" .

# Ejecutar servidor
python server.py
```

Probar:
```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/tts -H "Content-Type: application/json" -d '{"text":"Hola Jam, soy Jarvis"}' --output test.wav
```

---

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PORT` | `8080` | Puerto del servidor (Railway asigna el suyo automáticamente) |
| `KOKORO_VOICE` | `em_alex` | Voz de Kokoro |
| `KOKORO_LANG` | `es` | Idioma |
| `KOKORO_SPEED` | `1.0` | Velocidad de habla |
| `MODEL_DIR` | `.` | Directorio donde están los modelos |
| `KOKORO_MODEL_URL` | HuggingFace | URL para descargar el modelo si no existe |
| `KOKORO_VOICES_URL` | HuggingFace | URL para descargar las voces si no existen |

---

## Archivos del proyecto

```
JarvisPORT/
├── JarvisPORT.ino      # Código ESP32 (Arduino IDE)
├── apikey.h            # Configuración WiFi, API keys, URL del servidor
├── server.py           # Servidor TTS Python + Kokoro
├── requirements.txt    # Dependencias Python
├── Dockerfile          # Para desplegar en la nube
├── Procfile            # Para Railway/Render
├── .dockerignore       # Archivos excluidos del build
├── Librerias.md        # Librerías Arduino
├── Conexiones.md       # Diagrama de conexiones
└── apikey.md           # Referencia de API keys
```
