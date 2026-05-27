/*
 * ElectroManager – Rack Finder (browser-rendered)
 * Board   : ESP32 (any variant)
 * IDE     : Arduino IDE 2.x
 * Libraries required (install via Library Manager):
 *   - FastLED  by Daniel Garcia  (only when ENABLE_LEDS = 1)
 *   Built-in (ESP32 Arduino core): WiFi, WebServer
 *
 * Architecture
 * ────────────
 * The ESP32 serves a single-page web app stored in Flash (PROGMEM).
 * All ElectroManager API calls are made directly by the browser, so
 * the ESP32 never parses JSON or holds rack-layout data in RAM.
 * Memory stays low no matter how many searches the user runs.
 *
 * Routes
 *   GET /    → serve the HTML/CSS/JS app (~5 KB Flash, 0 heap)
 *   GET /led → light up the target drawer LED (ENABLE_LEDS only)
 *
 * CORS requirement
 * ────────────────
 * Because the browser fetches the EM API directly, the EM server
 * must send CORS headers. These are added automatically to all
 * /api/v1/ responses by the server — no extra setup needed.
 *
 * LED wiring (row-major, left-to-right, top-to-bottom):
 *   Drawer R{r}-C{c}  →  LED index  (r-1)*cols + (c-1)
 *   Change LED_MAP_FN below for serpentine or other layouts.
 *
 * Setup
 * ─────
 *   Admin → System Settings → Server API → Enable "Location, Rack & Drawer"
 *   User  → Settings → User API → Enable API + "Location, Rack & Drawer"
 *   Copy the API key and paste into API_KEY below.
 */

#include <WiFi.h>
#include <WebServer.h>
#include "page_content.h"

// ── Optional WS2812B LED highlight ───────────────────────────────────────
#define ENABLE_LEDS 0   // set to 1 to enable

#if ENABLE_LEDS
#include <FastLED.h>
#define LED_PIN     5
#define NUM_LEDS    25   // must equal rack rows × cols
CRGB leds[NUM_LEDS];
#define LED_MAP_FN(row, col, cols) ((row - 1) * (cols) + (col - 1))
#endif

// ── Configure before uploading ────────────────────────────────────────────
const char* WIFI_SSID = "XXXX";
const char* WIFI_PASS = "XXXX";
const char* EM_SERVER = "http://192.168.0.X:5500";   // no trailing slash
const char* API_KEY   = "XXXX";
// ─────────────────────────────────────────────────────────────────────────

WebServer server(80);

// ═════════════════════════════════════════════════════════════════════════
// Optional LED functions
// ═════════════════════════════════════════════════════════════════════════
#if ENABLE_LEDS
void ledHighlight(int row, int col, int cols) {
    fill_solid(leds, NUM_LEDS, CRGB::Black);
    int idx = LED_MAP_FN(row, col, cols);
    if (idx >= 0 && idx < NUM_LEDS) leds[idx] = CRGB(255, 160, 0);
    FastLED.show();
    Serial.printf("[LED] R%d-C%d → index %d\n", row, col, idx);
}
void ledClear() { fill_solid(leds, NUM_LEDS, CRGB::Black); FastLED.show(); }
#endif

// ═════════════════════════════════════════════════════════════════════════
// Route handlers
// ═════════════════════════════════════════════════════════════════════════

void handleRoot() {
    server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    server.send(200, "text/html", "");
    server.sendContent(PAGE_HEAD, sizeof(PAGE_HEAD) - 1);
    // Inject runtime config as JS variables between CSS and app logic
    String cfg = "const EM='" + String(EM_SERVER) + "',K='" + String(API_KEY) + "';\n";
    server.sendContent(cfg);
    server.sendContent(PAGE_JS,   sizeof(PAGE_JS)   - 1);
    server.sendContent(PAGE_TAIL, sizeof(PAGE_TAIL) - 1);
}

void handleLed() {
#if ENABLE_LEDS
    int row  = server.arg("row").toInt();
    int col  = server.arg("col").toInt();
    int cols = server.arg("cols").toInt();
    if (row > 0 && col > 0 && cols > 0) ledHighlight(row, col, cols);
#endif
    server.send(200, "text/plain", "OK");
}

// ═════════════════════════════════════════════════════════════════════════
// setup / loop
// ═════════════════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\nElectroManager - Rack Finder");
    Serial.println("==============================");

#if ENABLE_LEDS
    FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
    FastLED.setBrightness(80);
    ledClear();
    Serial.printf("LED strip: %d LEDs on pin %d\n", NUM_LEDS, LED_PIN);
#endif

    // WiFi
    Serial.println("\nConnecting to WiFi...");
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    int timeout = 30;
    while (WiFi.status() != WL_CONNECTED && timeout > 0) {
        delay(500);
        Serial.print(".");
        timeout--;
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("Connected! IP: %s\n", WiFi.localIP().toString().c_str());
        Serial.println("Open: http://" + WiFi.localIP().toString() + "/");
    } else {
        Serial.println("WiFi Failed - Starting AP");
        WiFi.softAP("MyESP32", "12345678");
        Serial.printf("AP IP: %s\n", WiFi.softAPIP().toString().c_str());
    }

    server.on("/",    HTTP_GET, handleRoot);
    server.on("/led", HTTP_GET, handleLed);
    server.begin();
    Serial.println("Web server started on port 80.");
}

void loop() {
    server.handleClient();
}
