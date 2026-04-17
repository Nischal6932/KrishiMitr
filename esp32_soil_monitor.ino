#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ========== PIN CONFIGURATION ==========
#define SOIL_PIN 34        // Soil moisture sensor (analog)
#define RELAY_PIN 26       // Relay module for pump control
#define LED_PIN 2          // Built-in LED for status

// ========== WIFI CONFIGURATION ==========
// UPDATE THESE WITH YOUR CREDENTIALS
const char* ssid = "NISCHAL MITTAL";
const char* password = "S1M8N23H26";

// ========== SERVER CONFIGURATION ==========
// UPDATE THIS AFTER DEPLOYMENT
// Format: "http://YOUR_DOMAIN/update_moisture"
const char* server = "https://krishimitr-ta7b.onrender.com/update_moisture";
const char* deviceId = "esp32_field_01";

// ========== CALIBRATION VALUES ==========
// Adjust these based on your sensor readings
// Dry soil in air should read around 3500
// Wet soil in water should read around 1200
int dryValue = 3500;
int wetValue = 1200;

// ========== THRESHOLDS ==========
// Moisture percentage to trigger pump
int pumpStartThreshold = 30;  // Turn ON pump when below 30%
int pumpStopThreshold = 70;   // Turn OFF pump when above 70%

// ========== TIMING ==========
const unsigned long updateInterval = 10000;    // Send data every 10 seconds
const unsigned long wifiTimeout = 30000;       // WiFi connection timeout (30s)
const unsigned long httpTimeout = 5000;        // HTTP request timeout (5s)
const int maxRetries = 3;                      // Max WiFi reconnect attempts

// ========== GLOBAL VARIABLES ==========
unsigned long lastUpdateTime = 0;
bool pumpState = false;
int retryCount = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== KrishiMitr ESP32 Starting ===");
  
  // Initialize pins
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);  // Pump OFF initially (LOW = OFF for most relay modules)
  digitalWrite(LED_PIN, LOW);
  
  // Connect to WiFi
  connectWiFi();
  
  Serial.println("=== Setup Complete ===\n");
}

void loop() {
  // Check WiFi and reconnect if needed
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected! Reconnecting...");
    connectWiFi();
  }
  
  unsigned long currentTime = millis();
  
  // Send data at intervals
  if (currentTime - lastUpdateTime >= updateInterval) {
    lastUpdateTime = currentTime;
    
    // Read moisture
    int moisture = readMoisture();
    
    // Control pump based on moisture
    controlPump(moisture);
    
    // Send to server
    sendData(moisture);
    
    // Blink LED to show activity
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
  }
}

int readMoisture() {
  // Take 10 readings and average for stability
  long sum = 0;
  for(int i = 0; i < 10; i++) {
    sum += analogRead(SOIL_PIN);
    delay(10);
  }
  int raw = sum / 10;
  
  // Convert to percentage (inverted - wet = 100%)
  int moisture = map(raw, wetValue, dryValue, 100, 0);
  moisture = constrain(moisture, 0, 100);
  
  Serial.print("Raw: ");
  Serial.print(raw);
  Serial.print(" | Moisture: ");
  Serial.print(moisture);
  Serial.println("%");
  
  return moisture;
}

void controlPump(int moisture) {
  // Auto-control pump based on moisture thresholds
  if (moisture < pumpStartThreshold && !pumpState) {
    digitalWrite(RELAY_PIN, HIGH);  // Turn ON pump
    pumpState = true;
    Serial.println("[PUMP] ON - Soil too dry");
  } 
  else if (moisture > pumpStopThreshold && pumpState) {
    digitalWrite(RELAY_PIN, LOW);   // Turn OFF pump
    pumpState = false;
    Serial.println("[PUMP] OFF - Soil sufficiently wet");
  }
  
  Serial.print("[PUMP] State: ");
  Serial.println(pumpState ? "ON" : "OFF");
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < wifiTimeout) {
    delay(500);
    Serial.print(".");
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected!");
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
    retryCount = 0;
  } else {
    Serial.println("\n[WiFi] Connection failed!");
    retryCount++;
    if (retryCount >= maxRetries) {
      Serial.println("[WiFi] Max retries reached. Restarting...");
      ESP.restart();
    }
  }
}

void sendData(int moisture) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] WiFi not connected, skipping send");
    return;
  }
  
  HTTPClient http;
  http.setTimeout(httpTimeout);
  
  // Create JSON payload
  StaticJsonDocument<256> doc;
  doc["moisture"] = moisture;
  doc["device_id"] = deviceId;
  doc["pump_state"] = pumpState ? "on" : "off";
  doc["rssi"] = WiFi.RSSI();
  
  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  Serial.print("[HTTP] Sending: ");
  Serial.println(jsonPayload);
  
  http.begin(server);
  http.addHeader("Content-Type", "application/json");
  
  int httpCode = http.POST(jsonPayload);
  
  if (httpCode > 0) {
    Serial.print("[HTTP] Response: ");
    Serial.println(httpCode);
    
    if (httpCode == HTTP_CODE_OK) {
      String response = http.getString();
      Serial.print("[HTTP] Server says: ");
      Serial.println(response);
    }
  } else {
    Serial.print("[HTTP] Error: ");
    Serial.println(http.errorToString(httpCode));
  }
  
  http.end();
}
