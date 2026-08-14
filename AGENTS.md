# Development workflow

- Primary sketch: `JarvisPort.ino` in Arduino IDE; open, compile (Verify), and upload to ESP32.
- Use Arduino CLI for scripted builds: `arduino-cli compile -b esp32:esp32:esp32 .` then `arduino-cli upload -p <PORT> -b esp32:esp32:esp32`.
- API key location: `apikey.md`; load it as an environment variable or include it via `#include "apikey.h"`.
- Reference Python implementation: `jarvis.py`; keep for spec but final code must be C++.
- Create `Librerias.md` as instructed: list required Arduino libraries, installation method, and version constraints for ESP32.
- Create `Conexiones.md`: wiring diagram for LiPo battery and Bluetooth headset, power requirements, and pin connections.
- Code must be memory‑constrained for ESP32; avoid heap fragmentation, use static buffers where possible.
- Follow the exact steps in `instrucciones.md`; no additional libraries or hardware assumptions.