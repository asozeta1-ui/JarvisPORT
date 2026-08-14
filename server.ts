/**
 * Jarvis TTS Server — Deno + Edge TTS
 * 
 * Ejecutar: deno run --allow-net --allow-env server.ts
 * 
 * Endpoints:
 *   POST /tts  { "text": "hola", "voice": "es-CR-GonzaloNeural" }
 *   GET  /health
 * 
 * edge-tts es gratis, no necesita API key.
 * Voces en español: es-CR-GonzaloNeural, es-CR-MariaNeural, es-MX-DaliaNeural
 */

const PORT = 8080;

const VOICES: Record<string, string> = {
  "es-cr": "es-CR-GonzaloNeural",
  "es-mx": "es-MX-DaliaNeural",
  "es":    "es-CR-GonzaloNeural",
  "en":    "en-US-GuyNeural",
};

async function textToSpeech(text: string, voice?: string): Promise<Uint8Array> {
  const voiceName = voice || VOICES["es-cr"];

  // Edge TTS WebSocket
  const wsUrl = "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4&ConnectionId=" + crypto.randomUUID().replace(/-/g, "");

  const conn = await Deno.connectWebSocket(wsUrl);

  const speechConfig = JSON.stringify({
    context: {
      synthesis: {
        audio: {
          metadataoptions: { sentenceBoundaryEnabled: "false", wordBoundaryEnabled: "false" },
          outputFormat: "riff-24khz-16bit-mono-pcm",
        },
      },
    },
    requestId: crypto.randomUUID(),
    voiceType: "Neural",
    voiceName: voiceName,
  });

  const connectId = crypto.randomUUID();

  // Handshake
  conn.send(`Content-Type:application/json; charset=utf-8\r\nPath:speech.config\r\n\r\n${speechConfig}`);

  // Send SSML
  const requestId = crypto.randomUUID();
  conn.send(`X-RequestId:${requestId}\r\nContent-Type:application/ssml+xml\r\nPath:ssml\r\n\r\n<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='es-CR'><voice name='${voiceName}'>${escapeXml(text)}</voice></speak>`);

  const audioChunks: Uint8Array[] = [];

  // Collect audio data
  const decoder = new TextDecoder();
  let done = false;

  while (!done) {
    try {
      const msg = await conn.receive();
      if (typeof msg === "string") {
        if (msg.includes("Path:turn.end")) {
          done = true;
        }
      } else {
        // Binary message: 2 byte header length + header + audio data
        const headerLen = new DataView(msg.buffer, msg.byteOffset, 2).getUint16(0);
        const audioData = msg.slice(2 + headerLen);
        if (audioData.length > 0) {
          audioChunks.push(audioData);
        }
      }
    } catch {
      done = true;
    }
  }

  conn.close();

  // Concatenate and wrap in WAV
  const mp3Data = concatBytes(audioChunks);
  return mp3Data;
}

function escapeXml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

function concatBytes(chunks: Uint8Array[]): Uint8Array {
  const total = chunks.reduce((sum, c) => sum + c.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

Deno.serve({ port: PORT }, async (req: Request): Promise<Response> => {
  const url = new URL(req.url);

  // CORS
  if (req.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      },
    });
  }

  // Health check
  if (req.method === "GET" && url.pathname === "/health") {
    return new Response(JSON.stringify({ status: "ok", service: "jarvis-tts" }), {
      headers: { "Content-Type": "application/json" },
    });
  }

  // TTS endpoint
  if (req.method === "POST" && url.pathname === "/tts") {
    try {
      const body = await req.json();
      const text = body.text as string;
      const voice = body.voice as string | undefined;

      if (!text || text.trim().length === 0) {
        return new Response(JSON.stringify({ error: "text is required" }), { status: 400 });
      }

      console.log(`[TTS] Generando audio: "${text.substring(0, 60)}..."`);

      const audio = await textToSpeech(text, voice);

      console.log(`[TTS] Audio generado: ${audio.length} bytes`);

      return new Response(audio, {
        headers: {
          "Content-Type": "audio/wav",
          "Access-Control-Allow-Origin": "*",
        },
      });
    } catch (err) {
      console.error("[TTS] Error:", err);
      return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
    }
  }

  return new Response("Jarvis TTS Server\nPOST /tts { text, voice? }", { status: 200 });
});

console.log(`[JARVIS TTS] Servidor escuchando en http://localhost:${PORT}`);
console.log(`[JARVIS TTS] POST /tts { "text": "hola" }`);
