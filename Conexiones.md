# Conexiones

## Arquitectura general

```
┌─────────────┐      Bluetooth SPP       ┌──────────────────┐
│  Audífono   │ ◄──────────────────────► │     ESP32        │
│  BT con mic │   texto STT / respuesta  │  JarvisPORT.ino  │
└─────────────┘                          └────────┬─────────┘
                                                  │ WiFi
                                                  ▼
                                         ┌─────────────────┐
                                         │  Router / Groq  │
                                         │    API Cloud    │
                                         └─────────────────┘
```

El micrófono y los parlantes están DENTRO del audífono Bluetooth. El ESP32 no necesita hardware de audio externo — solo envía/recibe texto por Bluetooth Serial (SPP).

## Flujo de audio

1. El celular/audífono captura voz → convierte a texto (STT en el celular)
2. Envía texto al ESP32 vía Bluetooth Serial
3. ESP32 procesa (Groq API, skills locales) y responde
4. ESP32 envía respuesta de texto de vuelta por BT
5. El celular/audífono convierte texto a voz (TTS en el celular)

## Alimentación

### Opción A: LiPo directo (sin regulador)

```
LiPo 3.7V ──┬── TP4056 (carga por USB-C/Micro-USB) ──┬── ESP32 VIN (pin 2)
             │                                         │
             └── GND ──────────────────────────────────┘ GND
```

- La LiPo nominal es 3.7V (4.2V cargada, 3.0V descargada)
- La mayoría de boards ESP32 aceptan 3.7-4.2V en VIN sin problemas
- Cuando la batería baje de ~3.4V, el ESP32 se reiniciará o se apagará
- **Para прототipo funciona bien**

### Opción B: Con boost 5V (recomendado para uso continuo)

```
LiPo 3.7V ──┬── TP4056 ──┬── Boost MT3608 (3.7V→5V) ── ESP32 VIN
             │            │
             └── GND ─────┴─────────────────────────── GND
```

- Módulo MT3608 (~$0.50 en AliExpress) convierte 3.7V a 5V estable
- ESP32 recibe 5V por VIN → regulador interno AMS1117 → 3.3V
- Funciona hasta que la LiPo esté casi descargada

### Carga

- El TP4056 permite cargar la LiPo vía USB mientras el ESP32 sigue encendido
- Corriente de carga: 1A (configurable con resistor en pin PROG)
- Alimentación USB del TP4056: 5V desde cualquier cargador de celular

## Bluetooth

- El ESP32 se empareja con el audífono/celular como dispositivo BT clásico
- Nombre del dispositivo BT: `JARVIS-ESP32` (configurable en `apikey.h`)
- Protocolo: Bluetooth Serial (SPP) — solo texto, sin streaming de audio
- No se requieren pines externos, es módulo interno del ESP32

## LED de estado (opcional)

- LED → GPIO `2` → resistencia 220 Ω → GND
- Indica estado de Jarvis (parpadea pensando, encendido hablando)

## Puerto serie (depuración)

- TX0 (`1`) y RX0 (`3`) para monitor serial a 115200 baud
- Útil para ver logs en Arduino IDE mientras se desarrolla
