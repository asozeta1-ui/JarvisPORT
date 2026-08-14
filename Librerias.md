# Librerías requeridas

## 1. Instalar placa ESP32 en Arduino IDE

1. Abrir Arduino IDE → **Archivo → Preferencias**
2. En **URLs adicionales de gestor de tarjetas** agregar:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Ir a **Herramientas → Placa → Gestor de tarjetas**
4. Buscar **esp32** y instalar **"esp32 by Espressif Systems"** (última versión)
5. Seleccionar placa: **Herramientas → Placa → ESP32 Arduino → ESP32 Dev Module**

## 2. Librerías de Arduino

- **ArduinoJson** (>= 6.19.0)
  - Administrar bibliotecas → buscar "ArduinoJson" → instalar la última versión estable (p.ej. 6.21.2).

## 3. Librerías incluidas en el núcleo ESP32 (no requieren instalación)

- **WiFi** — conexión a redes
- **HTTPClient** — peticiones HTTP/HTTPS
- **BluetoothSerial** — comunicación Bluetooth clásica
- **driver/i2s** — audio digital I2S