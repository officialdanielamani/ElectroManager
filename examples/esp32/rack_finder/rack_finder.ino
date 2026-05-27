/*
 * ElectroManager – Rack Finder Web UI  (+ optional WS2812B LED highlight)
 * Board   : ESP32 (any variant)
 * IDE     : Arduino IDE 2.x
 * Libraries required (install via Library Manager):
 *   - ArduinoJson  by Benoit Blanchon  (v6 or v7)
 *   - FastLED      by Daniel Garcia     (only when ENABLE_LEDS = 1)
 *   Built-in (ESP32 Arduino core): WiFi, WebServer, HTTPClient
 *
 * How it works
 * ────────────
 * 1. ESP32 connects to WiFi and starts a tiny HTTP server on port 80.
 * 2. Open  http://<esp32-ip>/  in any browser on the same network.
 * 3. Type an item name, UUID, batch UID (e.g. ABC-B01), or ISN and hit Find.
 * 4. The ESP32 calls the ElectroManager location search API to find the
 *    item's rack + drawer, then fetches the full rack layout and returns a
 *    rendered HTML page showing the grid with the target drawer highlighted
 *    in amber — mirroring the Visual Storage view in the web UI.
 * 5. (Optional) If ENABLE_LEDS = 1, the LED at the target drawer position
 *    lights up in amber so you can find it without looking at a screen.
 *
 * LED wiring assumption
 * ─────────────────────
 * LEDs are wired row-major, left-to-right, top-to-bottom:
 *   Drawer R{r}-C{c}  →  LED index  (r-1)*cols + (c-1)
 * Adjust LED_MAP_FN below if your physical strip is wired differently
 * (e.g. serpentine, column-major).
 *
 * Setup (in ElectroManager web UI)
 * ──────────────────────────────────
 *   Admin → System Settings → Server API → Enable "Location, Rack & Drawer"
 *   User  → Settings → User API → Enable API + "Location, Rack & Drawer" scope
 *   Copy the API key and paste it into API_KEY below.
 */

#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── Optional WS2812B LED highlight ───────────────────────────────────────
#define ENABLE_LEDS 0   // change to 1 to enable the LED strip

#if ENABLE_LEDS
#include <FastLED.h>
#define LED_PIN     5
#define NUM_LEDS    25   // must equal rack_rows * rack_cols
CRGB leds[NUM_LEDS];
// Row-major wiring: row r, col c → index (r-1)*cols + (c-1)
// Change this macro if your strip is wired differently.
#define LED_MAP_FN(row, col, cols) ((row - 1) * (cols) + (col - 1))
#endif

// ── Configure these before uploading ─────────────────────────────────────
const char* WIFI_SSID = "YourSSID";
const char* WIFI_PASS = "YourPassword";

const char* EM_SERVER = "http://192.168.1.100:5000";  // no trailing slash
const char* API_KEY   = "your_api_key_here";
// ─────────────────────────────────────────────────────────────────────────

WebServer server(80);

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────

// Percent-encode a string for use in a URL query parameter
static String urlEncode(const String& s) {
    String out;
    out.reserve(s.length() * 2);
    for (size_t i = 0; i < s.length(); i++) {
        char c = s[i];
        if (isAlphaNumeric(c) || c == '-' || c == '_' || c == '.' || c == '~') {
            out += c;
        } else {
            char buf[4];
            snprintf(buf, sizeof(buf), "%%%02X", (uint8_t)c);
            out += buf;
        }
    }
    return out;
}

// Minimal HTML escaping so item names can't inject tags
static String htmlEsc(const String& s) {
    String out;
    out.reserve(s.length() + 8);
    for (size_t i = 0; i < s.length(); i++) {
        char c = s[i];
        if      (c == '<')  out += "&lt;";
        else if (c == '>')  out += "&gt;";
        else if (c == '"')  out += "&quot;";
        else if (c == '&')  out += "&amp;";
        else                out += c;
    }
    return out;
}

// Authenticated GET request; returns HTTP status code, body via reference
static int apiGet(const String& url, String& body) {
    if (WiFi.status() != WL_CONNECTED) return -1;
    HTTPClient http;
    http.begin(url);
    http.addHeader("Authorization", String("Bearer ") + API_KEY);
    http.setTimeout(10000);
    int code = http.GET();
    if (code > 0) body = http.getString();
    http.end();
    return code;
}

// ─────────────────────────────────────────────────────────────────────────
// HTML page scaffolding — uses sendContent() to stream without buffering
// the full page in RAM.
// ─────────────────────────────────────────────────────────────────────────

static const char PAGE_CSS[] PROGMEM = R"CSS(
body{font-family:system-ui,sans-serif;margin:0;padding:14px;background:#f8f9fa;}
h2{margin:0 0 4px;font-size:1.2rem;}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.1);
      padding:14px;margin-bottom:14px;}
.card-header{border-radius:6px 6px 0 0;padding:10px 14px;margin:-14px -14px 12px;
             color:#fff;font-weight:600;}
.search-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;}
input[type=text]{flex:1;min-width:180px;padding:7px 11px;
    border:1px solid #ced4da;border-radius:6px;font-size:.95rem;}
button{padding:7px 18px;background:#0d6efd;color:#fff;border:none;
       border-radius:6px;cursor:pointer;font-size:.95rem;}
button:hover{background:#0b5ed7;}
.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));
           gap:8px;margin-top:10px;}
.info-item{background:#f1f3f5;border-radius:6px;padding:7px 10px;}
.info-item .lbl{font-size:.68rem;color:#6c757d;text-transform:uppercase;letter-spacing:.04em;}
.info-item .val{font-size:.92rem;font-weight:600;margin-top:2px;word-break:break-all;}
.rack-scroll{overflow-x:auto;padding-bottom:4px;}
.rack-grid{display:grid;gap:4px;width:max-content;}
.cell{border:2px solid #dee2e6;border-radius:6px;padding:4px 3px;
      min-width:68px;min-height:62px;text-align:center;
      display:flex;flex-direction:column;align-items:center;
      justify-content:center;font-size:11px;}
.cell .cid{font-weight:700;font-size:10px;color:#495057;}
.cell .si {font-size:9px;color:#6c757d;margin-top:1px;max-width:64px;
           white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cell .cnt{margin-top:3px;}
.empty     {background:#f8f9fa;}
.has-items {background:#cfe2ff;border-color:#9ec5fe;}
.merged    {background:#cfe2ff;border-style:dashed;border-color:#0d6efd;}
.grouped   {background:#d1e7dd;border-color:#a3cfbb;}
.unavail   {background:#6c757d;border-color:#495057;color:#fff;}
.unavail .cid,.unavail .si{color:#ddd;}
.highlight {background:#ffc107!important;border:3px solid #fd7e14!important;
            animation:pulse 1.1s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.6;}}
.badge{display:inline-block;padding:1px 6px;border-radius:10px;
       font-size:10px;font-weight:700;}
.bg-pri{background:#0d6efd;color:#fff;}
.bg-suc{background:#198754;color:#fff;}
.bg-sec{background:#6c757d;color:#fff;}
.legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px;}
.leg{display:flex;align-items:center;gap:5px;font-size:11px;}
.leg-box{width:14px;height:14px;border-radius:3px;border:1px solid rgba(0,0,0,.2);}
.alert{padding:11px 14px;border-radius:6px;margin-top:8px;font-size:.88rem;}
.alert-w{background:#fff3cd;border:1px solid #ffc107;color:#664d03;}
.alert-e{background:#f8d7da;border:1px solid #f5c2c7;color:#842029;}
.muted{color:#6c757d;}
)CSS";

static void sendHead(const String& title) {
    server.sendContent(F("<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>"));
    server.sendContent(title);
    server.sendContent(F("</title><style>"));
    server.sendContent(PAGE_CSS);
    server.sendContent(F("</style></head><body>"));
}

static void sendSearchBar(const String& q) {
    server.sendContent(F("<div class='card'>"
        "<h2>&#128269; Rack Finder</h2>"
        "<p class='muted' style='font-size:.82rem;margin:3px 0 10px;'>"
        "Enter item name, UUID, batch UID (e.g. ABC-B01), or ISN</p>"
        "<form method='GET' action='/find'>"
        "<div class='search-row'>"
        "<input type='text' name='q' placeholder='Arduino, ABC-B01, ISN-0042 …'"
        " value='"));
    String safe = htmlEsc(q);
    if (safe.length()) server.sendContent(safe);  // skip empty: zero-length chunk ends chunked transfer
    server.sendContent(F("' autocomplete='off' autofocus>"
        "<button type='submit'>Find</button>"
        "</div></form></div>"));
}

// Map API cell state to CSS class
static const char* cellCss(const char* state, bool highlight) {
    if (highlight)                          return "cell highlight";
    if (strcmp(state, "empty") == 0)        return "cell empty";
    if (strcmp(state, "has_items") == 0)    return "cell has-items";
    if (strcmp(state, "merged_master") == 0)return "cell merged has-items";
    if (strcmp(state, "group_master") == 0) return "cell grouped";
    if (strcmp(state, "group_slave") == 0)  return "cell grouped";
    if (strcmp(state, "unavailable") == 0)  return "cell unavail";
    return "cell empty";
}

// ─────────────────────────────────────────────────────────────────────────
// Route: GET /
// ─────────────────────────────────────────────────────────────────────────
void handleRoot() {
    server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    server.send(200, "text/html", "");
    sendHead("Rack Finder");
    sendSearchBar("");
    server.sendContent(F("<div class='card' style='text-align:center;padding:32px;'>"
        "<span style='font-size:3rem;'>&#128230;</span>"
        "<p class='muted'>Search for an item to highlight its drawer.</p>"
        "</div></body></html>"));
}

// ─────────────────────────────────────────────────────────────────────────
// Route: GET /find?q=<query>
// ─────────────────────────────────────────────────────────────────────────
void handleFind() {
    String q = server.arg("q");
    q.trim();

    server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    server.send(200, "text/html", "");
    sendHead("Rack Finder – " + htmlEsc(q));
    sendSearchBar(q);

    if (q.isEmpty()) {
        server.sendContent(F("<div class='alert alert-w'>Please enter a search query.</div>"
            "</body></html>"));
        return;
    }

    // ── Step 1: location search ───────────────────────────────────────────
    String searchBody;
    int code = apiGet(String(EM_SERVER) + "/api/v1/location/search?q=" + urlEncode(q),
                      searchBody);
    if (code != 200) {
        server.sendContent("<div class='alert alert-e'>Location search failed (HTTP " +
            String(code) + "). Check EM_SERVER and API_KEY.</div></body></html>");
        return;
    }

    // Parse search response — keep it small: 4 KB is enough for the first result
    JsonDocument searchDoc;
    DeserializationError perr = deserializeJson(searchDoc, searchBody);
    if (perr || !searchDoc["success"].as<bool>()) {
        const char* msg = searchDoc["message"] | perr.c_str();
        server.sendContent("<div class='alert alert-e'>API error: " +
            htmlEsc(msg) + "</div></body></html>");
        return;
    }

    JsonArray results = searchDoc["results"].as<JsonArray>();
    if (results.size() == 0) {
        server.sendContent(F("<div class='alert alert-w'>"
            "No items found for that query.</div></body></html>"));
        return;
    }

    // Use the first result and its first rack location
    JsonObject first   = results[0];
    String itemName    = first["name"]       | "Unknown";
    String itemUuid    = first["item_uuid"]  | "";
    String sku         = first["sku"]        | "";
    String shortInfo   = first["short_info"] | "";
    const char* isn    = first["isn"];            // only present for ISN queries
    bool   lentOut     = first["lent_out"]   | false;

    String rackUuid, rackName, rackColor = "#3a86ff", drawerCell, batchLabel, drawerSI;
    int drawerRow = 0, drawerCol = 0, qty = 0, avail = 0;
    bool foundRack = false;

    for (JsonObject loc : first["locations"].as<JsonArray>()) {
        if (String(loc["location_type"] | "") == "rack") {
            rackUuid   = loc["rack_uuid"]         | "";
            rackName   = loc["rack_name"]         | "";
            rackColor  = loc["rack_color"]        | "#3a86ff";
            drawerCell = loc["drawer_cell"]       | "";
            drawerRow  = loc["drawer_row"]        | 0;
            drawerCol  = loc["drawer_col"]        | 0;
            drawerSI   = loc["drawer_short_info"] | "";
            batchLabel = loc["batch_label"]       | "";
            qty        = loc["quantity"]          | 0;
            avail      = loc["available"]         | 0;
            foundRack  = true;
            break;
        }
    }

    // ── Info panel ────────────────────────────────────────────────────────
    server.sendContent("<div class='card'><div class='card-header' style='background:" +
        rackColor + ";'>&#128230; " + htmlEsc(itemName) + "</div>");
    server.sendContent("<div class='info-grid'>");

    if (sku.length())
        server.sendContent("<div class='info-item'><div class='lbl'>SKU</div>"
            "<div class='val'>" + htmlEsc(sku) + "</div></div>");
    if (shortInfo.length())
        server.sendContent("<div class='info-item'><div class='lbl'>Info</div>"
            "<div class='val'>" + htmlEsc(shortInfo) + "</div></div>");
    if (isn)
        server.sendContent("<div class='info-item'><div class='lbl'>ISN</div>"
            "<div class='val'>" + htmlEsc(isn) + "</div></div>");
    if (batchLabel.length())
        server.sendContent("<div class='info-item'><div class='lbl'>Batch</div>"
            "<div class='val'>" + htmlEsc(batchLabel) + "</div></div>");
    if (qty > 0) {
        server.sendContent("<div class='info-item'><div class='lbl'>Total Qty</div>"
            "<div class='val'>" + String(qty) + "</div></div>");
        server.sendContent("<div class='info-item'><div class='lbl'>Available</div>"
            "<div class='val'>" + String(avail) + "</div></div>");
    }
    if (isn && lentOut)
        server.sendContent(F("<div class='info-item'><div class='lbl'>Status</div>"
            "<div class='val' style='color:#dc3545;'>Lent out</div></div>"));

    server.sendContent("</div>");  // info-grid

    if (!foundRack) {
        server.sendContent(F("<div class='alert alert-w' style='margin-top:10px;'>"
            "Item found but has no rack location set.</div></div></body></html>"));
        return;
    }

    server.sendContent("<p style='margin:10px 0 0;'>Rack: <strong>" +
        htmlEsc(rackName) + "</strong> &nbsp; Drawer: <strong style='color:#fd7e14;'>" +
        htmlEsc(drawerCell) + "</strong>" +
        (drawerSI.length() ? " &mdash; " + htmlEsc(drawerSI) : "") +
        "</p></div>");  // card

    // ── Step 2: rack layout ───────────────────────────────────────────────
    String layoutBody;
    code = apiGet(String(EM_SERVER) + "/api/v1/rack/" + rackUuid + "/layout",
                  layoutBody);
    if (code != 200) {
        server.sendContent("<div class='alert alert-e'>Rack layout fetch failed (HTTP " +
            String(code) + ").</div></body></html>");
        return;
    }

    // Layout doc — 16 KB handles a 10×10 rack comfortably; 400-cell racks may
    // need more heap but the ESP32's 520 KB SRAM is usually sufficient.
    JsonDocument layoutDoc;
    if (deserializeJson(layoutDoc, layoutBody) != DeserializationError::Ok ||
        !layoutDoc["success"].as<bool>()) {
        server.sendContent(F("<div class='alert alert-e'>Could not parse rack layout."
            "</div></body></html>"));
        return;
    }

    int cols = layoutDoc["cols"] | 1;

    // ── Render rack grid ──────────────────────────────────────────────────
    server.sendContent("<div class='card'>"
        "<div class='card-header' style='background:" + rackColor + ";'>"
        "&#129695; " + htmlEsc(rackName) + "</div>"
        "<div class='rack-scroll'>"
        "<div class='rack-grid' style='grid-template-columns:repeat(" +
        String(cols) + ",minmax(68px,1fr));'>");

    for (JsonObject cell : layoutDoc["cells"].as<JsonArray>()) {
        const char* state = cell["state"]      | "empty";
        const char* cid   = cell["cell_id"]    | "";
        const char* si    = cell["short_info"] | "";
        int r             = cell["row"]        | 0;
        int c             = cell["col"]        | 0;
        int itemCount     = cell["item_count"] | 0;
        int rowSpan       = cell["row_span"]   | 1;
        int colSpan       = cell["col_span"]   | 1;
        const char* grpM  = cell["group_master"]| "";

        // merged_away cells are hidden slaves of rectangular merges — skip them
        if (strcmp(state, "merged_away") == 0) continue;

        bool highlight = (r == drawerRow && c == drawerCol);

        server.sendContent("<div class='");
        server.sendContent(cellCss(state, highlight));
        server.sendContent("'");

        // CSS Grid span for merged master cells
        if (rowSpan > 1 || colSpan > 1) {
            server.sendContent(" style='grid-row:span ");
            server.sendContent(String(rowSpan));
            server.sendContent(";grid-column:span ");
            server.sendContent(String(colSpan));
            server.sendContent(";'");
        }
        server.sendContent(">");

        // Cell ID
        server.sendContent("<span class='cid'>");
        server.sendContent(cid);
        server.sendContent("</span>");

        // Short info label
        if (si && strlen(si) > 0) {
            server.sendContent("<span class='si'>");
            server.sendContent(htmlEsc(si));
            server.sendContent("</span>");
        }

        // Status badge / item count
        server.sendContent("<span class='cnt'>");
        if (highlight) {
            server.sendContent(F("<span class='badge bg-pri'>&#9733; HERE</span>"));
        } else if (strcmp(state, "unavailable") == 0) {
            server.sendContent(F("<span class='badge bg-sec'>N/A</span>"));
        } else if (strcmp(state, "group_slave") == 0 && strlen(grpM) > 0) {
            server.sendContent("<span style='font-size:9px;color:#adb5bd;'>&#8594;");
            server.sendContent(grpM);
            server.sendContent("</span>");
        } else if (itemCount > 0) {
            server.sendContent("<span class='badge bg-suc'>");
            server.sendContent(String(itemCount));
            server.sendContent("</span>");
        } else {
            server.sendContent(F("<span style='font-size:9px;color:#adb5bd;'>Empty</span>"));
        }
        server.sendContent("</span>");  // cnt

        server.sendContent("</div>");
    }

    server.sendContent(F("</div></div>"));  // rack-grid + rack-scroll

    // Legend
    server.sendContent(F("<div class='legend'>"
        "<div class='leg'><div class='leg-box' style='background:#ffc107;border-color:#fd7e14;'></div>Target</div>"
        "<div class='leg'><div class='leg-box' style='background:#cfe2ff;border-color:#9ec5fe;'></div>Has items</div>"
        "<div class='leg'><div class='leg-box' style='background:#f8f9fa;'></div>Empty</div>"
        "<div class='leg'><div class='leg-box' style='background:#d1e7dd;border-color:#a3cfbb;'></div>Grouped</div>"
        "<div class='leg'><div class='leg-box' style='background:#cfe2ff;border-style:dashed;border-color:#0d6efd;'></div>Merged</div>"
        "<div class='leg'><div class='leg-box' style='background:#6c757d;'></div>Unavailable</div>"
        "</div></div>"));  // legend + card

    // ── Optional: LED highlight ───────────────────────────────────────────
#if ENABLE_LEDS
    ledHighlight(drawerRow, drawerCol, cols);
#endif

    server.sendContent(F("</body></html>"));
}

// ─────────────────────────────────────────────────────────────────────────
// Optional LED functions (compiled out when ENABLE_LEDS = 0)
// ─────────────────────────────────────────────────────────────────────────
#if ENABLE_LEDS

void ledHighlight(int row, int col, int cols) {
    fill_solid(leds, NUM_LEDS, CRGB::Black);
    int idx = LED_MAP_FN(row, col, cols);
    if (idx >= 0 && idx < NUM_LEDS) {
        leds[idx] = CRGB(255, 160, 0);   // amber
    }
    FastLED.show();
    Serial.printf("[LED] Row %d Col %d → LED index %d lit amber\n", row, col, idx);
}

void ledClear() {
    fill_solid(leds, NUM_LEDS, CRGB::Black);
    FastLED.show();
}

#endif  // ENABLE_LEDS

// ─────────────────────────────────────────────────────────────────────────
// setup / loop
// ─────────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\nElectroManager – Rack Finder");
    Serial.println("=============================");

#if ENABLE_LEDS
    FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
    FastLED.setBrightness(80);
    ledClear();
    Serial.printf("LED strip: %d LEDs on pin %d\n", NUM_LEDS, LED_PIN);
#endif

    // Connect WiFi
    Serial.printf("Connecting to %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    unsigned long t = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - t > 20000) {
            Serial.println("\n[ERROR] WiFi timeout. Check SSID/password.");
            return;
        }
        Serial.print(".");
        delay(500);
    }
    Serial.printf("\nConnected.  IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.println("Open in browser:  http://" + WiFi.localIP().toString() + "/");

    server.on("/",     HTTP_GET, handleRoot);
    server.on("/find", HTTP_GET, handleFind);
    server.begin();
    Serial.println("Web server started on port 80.");
}

void loop() {
    server.handleClient();
}
