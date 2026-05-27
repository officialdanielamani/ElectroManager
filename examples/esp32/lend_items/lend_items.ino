/*
 * ElectroManager API – Lending Example
 * Board   : ESP32 (any variant)
 * IDE     : Arduino IDE 2.x
 * Libraries required (install via Library Manager):
 *   - ArduinoJson  by Benoit Blanchon  (v6 or v7)
 *   - HTTPClient   built-in with ESP32 Arduino core
 *
 * Who is the borrower?
 *   The borrower is always the user who OWNS the API key.
 *   To lend on behalf of a specific user, use that user's API key.
 *   There is no separate lend_to_id parameter in the request.
 *
 * Setup (in ElectroManager web UI):
 *   Admin  → System Settings → Enable "Lending & Return" API scope
 *   User   → Settings → User API → Enable API + enable Lending & Return scope
 *   Copy the API key shown and paste it into API_KEY below.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── Configure these before uploading ─────────────────────────
const char* WIFI_SSID     = "YourSSID";
const char* WIFI_PASS     = "YourPassword";

const char* SERVER        = "http://192.168.1.100:5000";  // no trailing slash

// API key of the user who will be recorded as the borrower
const char* API_KEY       = "your_api_key_here";

// Standard batch item  (copy the Batch UID from the item page, e.g. "ABC-B001")
const char* BATCH_ID      = "ABC-B001";
const int   BATCH_QTY     = 5;

// Serial-tracked item  (full ISN, e.g. "ABC-B002-SN0001") — qty is always 1
const char* ISN           = "ABC-B002-SN0001";

// Due date (ISO 8601).  Leave empty string "" for no due date.
const char* DUE_DATE      = "2026-06-30T23:59:59";
// ─────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\nElectroManager – Lending Example");
    Serial.println("==================================");

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
        Serial.printf("✓ Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("✗ WiFi Failed - Starting AP");
        WiFi.softAP("MyESP32", "12345678");
        Serial.printf("AP IP: %s\n", WiFi.softAPIP().toString().c_str());
    }

    doLend();
}

void loop() {}

// ── Build request, send it, print result ─────────────────────
void doLend() {
    Serial.println("\n─── Lending Request ─────────────────────────────");

    // --- Build JSON body ---
    JsonDocument doc;
    doc["note"]    = "ESP32 lend request";
    doc["notify"]  = false;
    doc["dry_run"] = false;
    if (strlen(DUE_DATE) > 0) {
        doc["due_date"] = DUE_DATE;
    }

    JsonArray items = doc["items"].to<JsonArray>();

    // Standard batch: provide batch_id + qty
    JsonObject item1 = items.add<JsonObject>();
    item1["batch_id"] = BATCH_ID;
    item1["qty"]      = BATCH_QTY;

    // Serial-tracked: provide isn only (quantity is always 1 per ISN)
    JsonObject item2 = items.add<JsonObject>();
    item2["isn"] = ISN;

    String body;
    serializeJson(doc, body);
    Serial.println("Payload : " + body);

    // --- Send HTTP POST ---
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[ERROR] WiFi disconnected.");
        return;
    }

    HTTPClient http;
    http.begin(String(SERVER) + "/api/v1/lend");
    http.addHeader("Content-Type",  "application/json");
    http.addHeader("Authorization", String("Bearer ") + API_KEY);
    http.setTimeout(10000);

    int httpCode = http.POST(body);
    String response = http.getString();
    http.end();

    Serial.printf("HTTP %d\n", httpCode);
    Serial.println("Raw response : " + response);
    Serial.println();

    // --- Parse response ---
    JsonDocument res;
    DeserializationError parseErr = deserializeJson(res, response);
    if (parseErr) {
        Serial.println("[ERROR] JSON parse failed: " + String(parseErr.c_str()));
        return;
    }

    bool success = res["success"] | false;

    if (success) {
        Serial.println("RESULT : SUCCESS");
        Serial.println("  Session ID : " + String(res["session_id"].as<const char*>()));
        Serial.println("  Lend start : " + String(res["lend_start"].as<const char*>()));
        const char* due = res["due_date"];
        Serial.println("  Due date   : " + String(due ? due : "(none)"));
        Serial.println("  Items:");
        for (JsonObject it : res["items"].as<JsonArray>()) {
            Serial.printf("    [%d] %-30s  status=%s\n",
                it["index"].as<int>(),
                it["item_name"].as<const char*>(),
                it["status"].as<const char*>());
        }

    } else {
        Serial.println("RESULT : FAILED");
        Serial.println("  Code    : " + String(res["code"].as<const char*>()));
        Serial.println("  Message : " + String(res["message"].as<const char*>()));

        // Per-item errors (present when code == CART_VALIDATION_FAILED)
        if (res["items"].is<JsonArray>()) {
            Serial.println("  Per-item detail:");
            for (JsonObject it : res["items"].as<JsonArray>()) {
                const char* status = it["status"] | "?";
                if (strcmp(status, "error") == 0) {
                    Serial.printf("    [%d] query=%-20s  code=%s  msg=%s\n",
                        it["index"].as<int>(),
                        it["query"].as<const char*>(),
                        it["code"].as<const char*>(),
                        it["message"].as<const char*>());
                }
            }
        }
    }

    Serial.println("─────────────────────────────────────────────────");
}
