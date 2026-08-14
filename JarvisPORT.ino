/*
 * JARVIS ESP32 - Asistente Virtual
 * Reescritura completa en C++ para ESP32
 * Basado en el original jarvis.py
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <BluetoothSerial.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>

#include "apikey.h"

// ==================== CONFIGURACION ====================

#define LED_PIN 2

#define I2S_PORT I2S_NUM_0
#define I2S_BCK_PIN 26
#define I2S_WS_PIN 25
#define I2S_DATA_PIN 22

// ==================== ESTADO ====================

enum JarvisState {
  STATE_INIT,
  STATE_CONNECTING,
  STATE_IDLE,
  STATE_LISTENING,
  STATE_THINKING,
  STATE_SPEAKING,
  STATE_ERROR
};

volatile JarvisState currentState = STATE_INIT;
volatile bool interruptionRequested = false;

// ==================== GLOBALES ====================

BluetoothSerial SerialBT;
String btBuffer = "";
bool btConnected = false;

unsigned long lastInteraction = 0;
const unsigned long IDLE_TIMEOUT = 45000;

// ==================== HISTORIAL ====================

struct ChatMessage {
  String role;
  String content;
};

ChatMessage chatHistory[12];
int historyCount = 0;
const int MAX_HISTORY = 11;

// ==================== WAKE WORD ====================

const char* wakeWords[] = {
  "jarvis", "harbi", "jarbis", "yarbis", "yarvis",
  "despierta jarvis", "jarvis despierta", "despierta"
};
const int wakeWordCount = 8;

const char* stopCommands[] = {
  "detente", "jarvis detente", "para", "jarvis para", "stop",
  "silencio", "callate", "ya", "basta", "detener"
};
const int stopCommandCount = 10;

// ==================== FUNCIONES DE ESTADO ====================

void setState(JarvisState newState) {
  currentState = newState;
  digitalWrite(LED_PIN, newState == STATE_SPEAKING ? HIGH : LOW);
}

const char* getStateName() {
  switch (currentState) {
    case STATE_INIT: return "INICIALIZANDO";
    case STATE_CONNECTING: return "CONECTANDO";
    case STATE_IDLE: return "INACTIVO";
    case STATE_LISTENING: return "ESCUCHANDO";
    case STATE_THINKING: return "PENSANDO";
    case STATE_SPEAKING: return "HABLANDO";
    case STATE_ERROR: return "ERROR";
    default: return "DESCONOCIDO";
  }
}

// ==================== WIFI ====================

bool connectWiFi() {
  if (strlen(WIFI_SSID) == 0) {
    Serial.println("[WIFI] No configurado, saltando...");
    return false;
  }

  setState(STATE_CONNECTING);
  Serial.printf("[WIFI] Conectando a %s...\n", WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] Conectado! IP: %s\n", WiFi.localIP().toString().c_str());
    setState(STATE_IDLE);
    return true;
  }

  Serial.println("\n[WIFI] Error de conexion");
  setState(STATE_ERROR);
  return false;
}

// ==================== BLUETOOTH ====================

void bluetoothCallback(esp_spp_cb_event_t event, esp_spp_cb_param_t* param) {
  if (event == ESP_SPP_SRV_OPEN_EVT) {
    btConnected = true;
    Serial.println("[BT] Cliente conectado");
  } else if (event == ESP_SPP_CLOSE_EVT) {
    btConnected = false;
    Serial.println("[BT] Cliente desconectado");
  }
}

bool initBluetooth() {
  Serial.printf("[BT] Iniciando como %s...\n", BT_DEVICE_NAME);

  SerialBT.begin(BT_DEVICE_NAME);
  SerialBT.register_callback(bluetoothCallback);

  Serial.println("[BT] Bluetooth listo");
  return true;
}

// ==================== AUDIO I2S (DAC) ====================

bool initI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 24000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = true
  };

  esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("[I2S] Error instalando driver: %d\n", err);
    return false;
  }

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_BCK_PIN,
    .ws_io_num = I2S_WS_PIN,
    .data_out_num = I2S_DATA_PIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  err = i2s_set_pin(I2S_PORT, &pin_config);
  if (err != ESP_OK) {
    Serial.printf("[I2S] Error configurando pins: %d\n", err);
    return false;
  }

  i2s_zero_dma_buffer(I2S_PORT);
  Serial.println("[I2S] DAC listo (MAX98357A)");
  return true;
}

// ==================== TTS SERVER ====================

String fetchTTS(const String& text) {
  if (WiFi.status() != WL_CONNECTED) {
    return "";
  }

  Serial.printf("[TTS] Solicitando a %s\n", TTS_SERVER_URL);

  HTTPClient http;
  http.begin(String(TTS_SERVER_URL) + "/tts");
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(15000);

  StaticJsonDocument<512> doc;
  doc["text"] = text;
  String body;
  serializeJson(doc, body);

  int httpCode = http.POST(body);

  if (httpCode != 200) {
    Serial.printf("[TTS] Error HTTP: %d\n", httpCode);
    http.end();
    return "";
  }

  int len = http.getSize();
  Serial.printf("[TTS] Recibiendo audio... (%d bytes)\n", len);

  setState(STATE_SPEAKING);

  WiFiClient* stream = http.getStreamPtr();
  uint8_t buf[1024];
  int skipBytes = 44;
  bool headerParsed = false;

  while (http.connected() && (len > 0 || len == -1)) {
    size_t size = stream->available();
    if (size) {
      int bytesRead = stream->readBytes(buf, min(size, sizeof(buf)));

      if (!headerParsed) {
        if (skipBytes > 0) {
          int toSkip = min(bytesRead, skipBytes);
          memmove(buf, buf + toSkip, bytesRead - toSkip);
          bytesRead -= toSkip;
          skipBytes -= toSkip;
        }
        headerParsed = true;
      }

      if (bytesRead > 0) {
        size_t written = 0;
        while (written < (size_t)bytesRead) {
          size_t w = i2s_write(I2S_PORT, buf + written, bytesRead - written, pdMS_TO_TICKS(500));
          if (w == 0) break;
          written += w;
        }
      }

      if (len > 0) len -= bytesRead;
    }
    delay(1);
  }

  http.end();
  i2s_zero_dma_buffer(I2S_PORT);
  Serial.println("[TTS] Audio reproducido");
  return "ok";
}

// ==================== GROQ API ====================

void addToHistory(const String& role, const String& content) {
  if (historyCount >= MAX_HISTORY) {
    for (int i = 0; i < historyCount - 1; i++) {
      chatHistory[i] = chatHistory[i + 1];
    }
    historyCount--;
  }
  chatHistory[historyCount].role = role;
  chatHistory[historyCount].content = content;
  historyCount++;
}

String buildSystemPrompt() {
  unsigned long now = millis();
  int hours = (now / 3600000) % 24;
  int minutes = (now / 60000) % 60;

  String prompt = "Eres Jarvis, un asistente IA avanzado, informal y divertido. ";
  prompt += "Hablas como un compa cercano. Sin enlaces falsos. ";
  prompt += "Eres amigable con tu dueno Jam. ";
  prompt += "No crees respuestas demasiado largas porque tus respuestas son pasadas por un modelo de voz. ";

  return prompt;
}

String queryGroq(const String& userMessage) {
  if (WiFi.status() != WL_CONNECTED) {
    return "No tengo conexion a internet, no puedo procesar tu pregunta.";
  }

  setState(STATE_THINKING);

  HTTPClient http;
  http.begin("https://api.groq.com/openai/v1/chat/completions");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + GROQ_API_KEY);

  StaticJsonDocument<4096> doc;
  doc["model"] = GROQ_MODEL;
  doc["temperature"] = 0.8;
  doc["max_tokens"] = 300;

  JsonArray messages = doc.createNestedArray("messages");

  JsonObject sysMsg = messages.createNestedObject();
  sysMsg["role"] = "system";
  sysMsg["content"] = buildSystemPrompt();

  for (int i = 0; i < historyCount; i++) {
    JsonObject msg = messages.createNestedObject();
    msg["role"] = chatHistory[i].role;
    msg["content"] = chatHistory[i].content;
  }

  JsonObject userMsg = messages.createNestedObject();
  userMsg["role"] = "user";
  userMsg["content"] = userMessage;

  String requestBody;
  serializeJson(doc, requestBody);

  int httpCode = http.POST(requestBody);

  if (httpCode != 200) {
    Serial.printf("[GROQ] Error HTTP: %d\n", httpCode);
    http.end();
    return "Tuve un error de conexion. Intenta de nuevo.";
  }

  String response = http.getString();
  http.end();

  StaticJsonDocument<2048> respDoc;
  DeserializationError error = deserializeJson(respDoc, response);

  if (error) {
    Serial.printf("[GROQ] Error JSON: %s\n", error.c_str());
    return "No pude procesar la respuesta.";
  }

  const char* content = respDoc["choices"][0]["message"]["content"];
  if (!content) {
    return "No obtuve respuesta del modelo.";
  }

  addToHistory("user", userMessage);
  addToHistory("assistant", String(content));

  return String(content);
}

// ==================== SKILLS ====================

String getWeather() {
  if (WiFi.status() != WL_CONNECTED) {
    return "No tengo conexion para obtener el clima.";
  }

  HTTPClient http;
  String url = "https://wttr.in/" + String(WEATHER_CITY) + "?format=%t";
  http.begin(url);

  int httpCode = http.GET();
  if (httpCode != 200) {
    http.end();
    return "No pude obtener el clima.";
  }

  String weather = http.getString();
  http.end();
  weather.trim();

  return "El clima en " + String(WEATHER_CITY) + " esta a " + weather;
}

String getDateTime() {
  unsigned long now = millis() / 1000;
  int hours = (now / 3600) % 24;
  int minutes = (now / 60) % 60;

  char timeStr[20];
  sprintf(timeStr, "%02d:%02d", hours, minutes);

  return String("Son las ") + timeStr;
}

String getESP32Info() {
  String info = "Sistema: ESP32. ";
  info += "RAM libre: " + String(ESP.getFreeHeap()) + " bytes. ";
  info += "CPU: " + String(ESP.getCpuFreqMHz()) + " MHz. ";
  info += "Temperatura: " + String(temperatureRead()) + " grados.";
  return info;
}

String processSkill(const String& text) {
  String lower = text;
  lower.toLowerCase();

  if (lower.indexOf("clima") >= 0 || lower.indexOf("weather") >= 0) {
    return getWeather();
  }

  if (lower.indexOf("hora") >= 0 || lower.indexOf("time") >= 0) {
    return getDateTime();
  }

  if (lower.indexOf("info") >= 0 || lower.indexOf("estado") >= 0) {
    return getESP32Info();
  }

  if (lower.indexOf("ayuda") >= 0 || lower.indexOf("help") >= 0) {
    return "Puedo ayudarte con: clima, hora, estado del sistema, o conversar libremente. Solo dime 'Jarvis' y preguntame.";
  }

  return queryGroq(text);
}

// ==================== DETECCION WAKE WORD ====================

bool detectWakeWord(const String& text) {
  String lower = text;
  lower.toLowerCase();

  for (int i = 0; i < wakeWordCount; i++) {
    if (lower.indexOf(wakeWords[i]) >= 0) {
      return true;
    }
  }
  return false;
}

bool isStopCommand(const String& text) {
  String lower = text;
  lower.toLowerCase();

  for (int i = 0; i < stopCommandCount; i++) {
    if (lower.indexOf(stopCommands[i]) >= 0) {
      return true;
    }
  }
  return false;
}

String extractCommand(const String& text, const String& wakeWord) {
  String lower = text;
  lower.toLowerCase();

  int pos = lower.indexOf(wakeWord);
  if (pos >= 0) {
    String cmd = text.substring(pos + wakeWord.length());
    cmd.trim();
    if (cmd.length() > 0) {
      return cmd;
    }
  }
  return text;
}

// ==================== ENTRADA DE VOZ (BLUETOOTH) ====================

String readVoiceInput() {
  btBuffer = "";

  unsigned long startTime = millis();
  unsigned long timeout = 10000;

  while (millis() - startTime < timeout) {
    if (SerialBT.available()) {
      char c = SerialBT.read();
      if (c == '\n' || c == '\r') {
        if (btBuffer.length() > 0) {
          break;
        }
      } else {
        btBuffer += c;
      }
    }
    delay(10);
  }

  btBuffer.trim();
  return btBuffer;
}

// ==================== SALIDA DE VOZ ====================

void speak(const String& text) {
  setState(STATE_SPEAKING);
  Serial.printf("[JARVIS]: %s\n", text.c_str());

  String result = fetchTTS(text);

  if (result.length() == 0 && btConnected) {
    Serial.println("[TTS] Servidor no disponible, enviando por BT");
    SerialBT.println(text);
    delay(100);
  }

  setState(STATE_IDLE);
}

// ==================== PROCESAMIENTO PRINCIPAL ====================

void processCommand(const String& command) {
  Serial.printf("[CMD]: %s\n", command.c_str());

  lastInteraction = millis();

  String response = processSkill(command);
  speak(response);
}

// ==================== RUTINA DE DESPERTAR ====================

void wakeUpRoutine() {
  String greeting = "Que pasa Jam! ";
  greeting += getDateTime() + ". ";
  greeting += "Tu Jarvis esta listo. En que te puedo ayudar?";

  speak(greeting);
}

// ==================== SETUP ====================

void setup() {
  Serial.begin(115200);
  Serial.println("\n=============================");
  Serial.println("  JARVIS ESP32 v1.0");
  Serial.println("  Asistente Virtual");
  Serial.println("=============================\n");

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  setState(STATE_INIT);

  initI2S();
  initBluetooth();

  if (connectWiFi()) {
    Serial.println("[INIT] WiFi conectado");
  } else {
    Serial.println("[INIT] WiFi no disponible, funcionando offline");
  }

  digitalWrite(LED_PIN, LOW);
  setState(STATE_IDLE);

  Serial.println("\n[INIT] Jarvis listo!");
  Serial.println("[INIT] Di 'Jarvis' para activarme\n");
}

// ==================== LOOP ====================

void loop() {
  if (SerialBT.available()) {
    String input = readVoiceInput();

    if (input.length() > 0) {
      Serial.printf("[RECV]: %s\n", input.c_str());

      if (isStopCommand(input)) {
        interruptionRequested = true;
        speak("Entendido, me detengo.");
        interruptionRequested = false;
        return;
      }

      if (detectWakeWord(input)) {
        lastInteraction = millis();

        String cmd = extractCommand(input, "jarvis");
        if (cmd.length() > 0 && cmd != input) {
          processCommand(cmd);
        } else {
          wakeUpRoutine();
        }
      }
    }
  }

  if (currentState == STATE_IDLE && 
      (millis() - lastInteraction > IDLE_TIMEOUT) && 
      lastInteraction > 0) {
    Serial.println("[IDLE] Timeout de inactividad");
  }

  delay(10);
}