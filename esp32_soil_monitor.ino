#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define SOIL_PIN 34

// WiFi credentials - UPDATE THESE
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Server configuration - UPDATE THIS after deployment
// Local testing: "http://192.168.1.X:10000/update_moisture"
// Deployed server: "http://your-domain.com/update_moisture"
const char* server = "http://192.168.29.142:10000/update_moisture";

// Calibration values
int dryValue = 3500;
int wetValue = 1200;

// Timing variables
unsigned long lastUpdateTime = 0;
const unsigned long updateInterval = 5000; // Send data every 5 seconds

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);

  Serial.println("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConnected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // Stable reading - average of 10 readings
  int sum = 0;
  for(int i = 0; i < 10; i++) {
    sum += analogRead(SOIL_PIN);
    delay(10);
  }
  int raw = sum / 10;

  // Convert to percentage (inverted - wet = 100%)
  int moisture = map(raw, wetValue, dryValue, 100, 0);
  moisture = constrain(moisture, 0, 100);

  Serial.print("Moisture: ");
  Serial.println(moisture);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;

    http.begin(server);
    http.addHeader("Content-Type", "application/json");

    // Proper JSON formatting
    String json = "{\"moisture\":" + String(moisture) + "}";
    
    int response = http.POST(json);

    Serial.print("Server Response: ");
    Serial.println(response);

    http.end();
  }

  delay(5000);
}
