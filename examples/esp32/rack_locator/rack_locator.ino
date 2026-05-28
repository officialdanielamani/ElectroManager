/*
 * ElectroManager – Rack Locator
 * Board   : ESP32 (any variant)
 * IDE     : Arduino IDE 2.x
 * Libraries required (install via Library Manager):
 *   - FastLED  by Daniel Garcia  (only when ENABLE_LEDS = 1)
 *   Built-in (ESP32 Arduino core): WiFi, WebServer
 *
 * Architecture
 * ────────────
 * Unlike the Rack Finder (which searches across all racks), the Rack
 * Locator is pre-configured for one or more specific rack UUIDs.
 *
 * On page load the browser fetches the layout for every configured rack
 * and renders them all below the search bar.  The racks stay visible at
 * all times — no layout fetch happens during a search, so responses are
 * fast even on slow networks.
 *
 * When a search matches a drawer in one of the configured racks:
 *   • That cell is highlighted (pulsing yellow border)
 *   • The LED strip (if enabled) lights the corresponding drawer
 *   • A result card shows the item details
 *
 * When the item is found but not in any configured rack, a result card
 * still appears with the actual location (different rack or general
 * location), but no highlight or LED fires.
 *
 * Clicking any drawer cell shows a popup with the full drawer contents
 * fetched live from the EM server.
 *
 * Multiple racks
 * ──────────────
 * Add extra UUIDs to RACK_UUIDS[] (up to RACK_COUNT).  Each rack gets
 * its own card on the page.  The LED strip maps to RACK_UUIDS[LED_RACK]
 * (default 0 = first rack).
 *
 * Routes
 *   GET /    → serve the single-page app from Flash (PROGMEM)
 *   GET /led → light the target drawer LED (ENABLE_LEDS only)
 *
 * CORS note: all /api/v1/ responses from ElectroManager include
 * Access-Control-Allow-Origin: * so the browser can call the EM server
 * directly from a page hosted on the ESP32's IP.
 *
 * Setup
 * ─────
 *   Admin → System Settings → Server API → Enable "Location, Rack & Drawer"
 *   User  → Settings → User API → Enable API + "Location, Rack & Drawer"
 *   Copy each rack UUID from the rack's settings page in ElectroManager.
 *   Paste the API key and rack UUIDs below, then upload.
 */

#include <WiFi.h>
#include <WebServer.h>
#include "rack_locator_page.h"

// ── Optional WS2812B LED highlight ───────────────────────────────────────
#define ENABLE_LEDS  0   // set to 1 to enable
#define LED_RACK     0   // index into RACK_UUIDS[] whose drawers map to the LED strip

#if ENABLE_LEDS
#include <FastLED.h>
#define LED_PIN      5
#define NUM_LEDS     25   // must equal rows × cols of RACK_UUIDS[LED_RACK]
CRGB leds[NUM_LEDS];
// Row-major, left-to-right, top-to-bottom wiring.
// Change this macro for serpentine or other layouts.
#define LED_MAP_FN(row, col, cols) ((row - 1) * (cols) + (col - 1))
#endif

// ── Configure before uploading ────────────────────────────────────────────
const char* WIFI_SSID = "YourSSID";
const char* WIFI_PASS = "YourPassword";

const char* EM_SERVER = "http://192.168.1.100:5000";   // no trailing slash
const char* API_KEY   = "your_api_key_here";

// Add the UUID of every rack you want displayed.
// Copy UUIDs from the rack settings page in ElectroManager.
// Comment out unused entries — do NOT leave empty strings.
const char* RACK_UUIDS[] = {
    "YOUR-RACK-UUID-HERE",
    // "SECOND-RACK-UUID-HERE",
    // "THIRD-RACK-UUID-HERE",
    // "FOURTH-RACK-UUID-HERE",
};
const int RACK_COUNT = sizeof(RACK_UUIDS) / sizeof(RACK_UUIDS[0]);
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
    Serial.printf("[LED] R%d-C%d -> index %d\n", row, col, idx);
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

    // Inject runtime config: server, key, and rack UUID array
    String cfg = "const EM='" + String(EM_SERVER) + "',K='" + String(API_KEY) + "';\n";
    cfg += "const RACKS=[";
    for (int i = 0; i < RACK_COUNT; i++) {
        cfg += "'";
        cfg += RACK_UUIDS[i];
        cfg += "'";
        if (i < RACK_COUNT - 1) cfg += ",";
    }
    cfg += "];\n";
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
    Serial.println("\nElectroManager - Rack Locator");
    Serial.println("===============================");
    Serial.printf("Configured racks: %d\n", RACK_COUNT);
    for (int i = 0; i < RACK_COUNT; i++) {
        Serial.printf("  [%d] %s\n", i, RACK_UUIDS[i]);
    }

#if ENABLE_LEDS
    FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
    FastLED.setBrightness(80);
    ledClear();
    Serial.printf("LED strip: %d LEDs on pin %d (rack index %d)\n", NUM_LEDS, LED_PIN, LED_RACK);
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
