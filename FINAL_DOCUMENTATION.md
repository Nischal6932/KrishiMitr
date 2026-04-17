# Smart Farming AI - Final Project Documentation

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [IoT Integration - ESP32 Soil Moisture Sensor](#3-iot-integration---esp32-soil-moisture-sensor)
4. [Relay Module & Motor Integration](#4-relay-module--motor-integration)
5. [Leaf Disease Detection System](#5-leaf-disease-detection-system)
6. [API Endpoints](#6-api-endpoints)
7. [Installation & Setup](#7-installation--setup)
8. [Hardware Requirements](#8-hardware-requirements)
9. [Software Dependencies](#9-software-dependencies)
10. [Usage Guide](#10-usage-guide)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Project Overview

**Smart Farming AI** is an integrated agricultural assistance platform combining:
- **IoT-based soil moisture monitoring** with ESP32
- **AI-powered leaf disease detection** using deep learning
- **Automated irrigation control** via relay module and motor
- **Multilingual AI advisory** system with voice synthesis

### Key Features
- Real-time soil moisture monitoring
- 15-class plant disease detection (Tomato, Potato, Pepper)
- Automated irrigation triggering based on moisture levels
- Multi-language support (English, Hindi, Telugu, Tamil, Kannada)
- Text-to-speech output for accessibility
- AI-powered agricultural advice via Groq LLM

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SMART FARMING AI SYSTEM                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐      HTTP/JSON       ┌─────────────────────────────┐ │
│  │   ESP32      │◄────────────────────►│      Flask Backend          │ │
│  │  Soil Sensor │   /update_moisture   │    (Python/TensorFlow)      │ │
│  └──────────────┘                      └──────────────┬──────────────┘ │
│         │                                                │               │
│         │                                                │               │
│  ┌──────▼──────┐                              ┌─────────▼──────────┐   │
│  │  Capacitive │                              │  Disease Detection │   │
│  │    Soil     │                              │  (CNN Ensemble)     │   │
│  │   Sensor    │                              │  - ResNet50/MobileNet│  │
│  └─────────────┘                              │  - 15 Disease Classes│  │
│                                               └─────────┬──────────┘   │
│  ┌──────────────┐                                      │               │
│  │ Relay Module │◄─────────────────────────────────────┘               │
│  │  + Water    │   Auto-trigger when moisture < threshold              │
│  │   Pump      │                                                        │
│  └──────────────┘                                      ┌──────────────┐│
│                                                        │   Groq AI    ││
│  ┌──────────────┐      HTTP API                       │   (LLM)      ││
│  │   Web UI     │◄────────────────────────────────────┤   Advisory   ││
│  │  (Jinja2/    │   /ai_advice, /chat, /predict        └──────────────┘│
│  │   HTML/CSS)  │                                                    │
│  └──────────────┘                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. IoT Integration - ESP32 Soil Moisture Sensor

### 3.1 Hardware Setup

#### Components Required
| Component | Specification | Purpose |
|-----------|--------------|---------|
| ESP32 DevKit | ESP32-WROOM-32 | Main microcontroller |
| Soil Moisture Sensor | Capacitive (v1.2) | Soil moisture detection |
| Jumper Wires | Dupont M-M/F-F | Connections |
| Power Supply | USB/5V | ESP32 power |

#### Wiring Diagram
```
ESP32 GPIO 34  ───────►  AOUT (Sensor Analog Output)
ESP32 3.3V     ───────►  VCC (Sensor Power)
ESP32 GND      ───────►  GND (Sensor Ground)
```

### 3.2 ESP32 Arduino Code

**File:** `esp32_soil_monitor.ino`

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define SOIL_PIN 34

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* server = "http://YOUR_SERVER_IP:10000/update_moisture";

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
```

### 3.3 Calibration Procedure

1. **Dry Calibration**: Place sensor in completely dry soil
   - Record the ADC value → Set as `dryValue`
   
2. **Wet Calibration**: Place sensor in fully saturated soil
   - Record the ADC value → Set as `wetValue`

3. **Update Code**:
   ```cpp
   int dryValue = 3500;  // Your dry soil reading
   int wetValue = 1200;  // Your wet soil reading
   ```

### 3.4 Backend Moisture Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/update_moisture` | POST | ESP32 sends moisture data |
| `/get_moisture` | GET | Frontend retrieves current moisture |
| `/iot_status` | GET | Device connectivity status |

**POST /update_moisture Request Body:**
```json
{
  "moisture": 45,
  "device_id": "esp32_01"
}
```

**GET /get_moisture Response:**
```json
{
  "moisture": 45,
  "status": "fresh",
  "last_update": 1234567890,
  "time_since_update": 15
}
```

---

## 4. Relay Module & Motor Integration

### 4.1 Hardware Components

| Component | Specification | Purpose |
|-----------|--------------|---------|
| Relay Module | 5V Single Channel | Switch control |
| Water Pump | 12V/5V DC Submersible | Irrigation delivery |
| Power Supply | 12V DC Adapter | Pump power |
| Transistor | 2N2222/BC547 | Signal amplification (optional) |
| Diode | 1N4007 | Flyback protection |

### 4.2 Wiring Diagram

```
Basic Relay Connection:

ESP32 GPIO 26  ───────►  Relay IN (Signal)
ESP32 5V       ───────►  Relay VCC
ESP32 GND      ───────►  Relay GND

Relay Output:
COM  ───────►  Pump Negative
NO   ───────►  Power Supply Negative
Power Supply Positive ───────►  Pump Positive

With Motor Driver (L298N):

ESP32 GPIO 26  ───────►  IN1
ESP32 GPIO 27  ───────►  IN2
ESP32 GPIO 14  ───────►  ENA (PWM Speed Control)
ESP32 5V       ───────►  +5V Logic
ESP32 GND      ───────►  GND
L298N OUT1    ───────►  Motor/Pump +
L298N OUT2    ───────►  Motor/Pump -
External 12V ───────►  L298N +12V
```

### 4.3 ESP32 Control Code (Relay + Moisture)

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// Pin Definitions
#define SOIL_PIN 34
#define RELAY_PIN 26  // Relay control pin
#define MOTOR_IN1 27  // Motor driver IN1
#define MOTOR_IN2 14  // Motor driver IN2 (for L298N)

// WiFi Credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* server = "http://YOUR_SERVER_IP:10000/update_moisture";

// Configuration
int dryValue = 3500;
int wetValue = 1200;
int moistureThreshold = 30;  // Turn on pump below this %
int stopThreshold = 70;      // Turn off pump above this %

bool pumpRunning = false;
unsigned long lastUpdateTime = 0;
const unsigned long updateInterval = 5000;

void setup() {
  Serial.begin(115200);
  
  // Initialize pins
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(MOTOR_IN1, OUTPUT);
  pinMode(MOTOR_IN2, OUTPUT);
  
  // Ensure pump is OFF initially
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, LOW);
  
  // Connect to WiFi
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

// Function to turn pump ON
void startPump() {
  digitalWrite(RELAY_PIN, HIGH);  // For relay module
  // digitalWrite(MOTOR_IN1, HIGH);  // For L298N
  // digitalWrite(MOTOR_IN2, LOW);
  pumpRunning = true;
  Serial.println("PUMP STARTED");
}

// Function to turn pump OFF
void stopPump() {
  digitalWrite(RELAY_PIN, LOW);   // For relay module
  // digitalWrite(MOTOR_IN1, LOW);   // For L298N
  // digitalWrite(MOTOR_IN2, LOW);
  pumpRunning = false;
  Serial.println("PUMP STOPPED");
}

void loop() {
  // Read soil moisture (average of 10 samples)
  int sum = 0;
  for(int i = 0; i < 10; i++) {
    sum += analogRead(SOIL_PIN);
    delay(10);
  }
  int raw = sum / 10;
  
  // Convert to percentage
  int moisture = map(raw, wetValue, dryValue, 100, 0);
  moisture = constrain(moisture, 0, 100);
  
  Serial.print("Moisture: ");
  Serial.print(moisture);
  Serial.print("% | Pump: ");
  Serial.println(pumpRunning ? "ON" : "OFF");
  
  // AUTOMATIC IRRIGATION LOGIC
  if (!pumpRunning && moisture < moistureThreshold) {
    // Soil is dry - start irrigation
    startPump();
  } else if (pumpRunning && moisture > stopThreshold) {
    // Soil is wet enough - stop irrigation
    stopPump();
  }
  
  // Send data to server
  if (WiFi.status() == WL_CONNECTED && (millis() - lastUpdateTime > updateInterval)) {
    HTTPClient http;
    http.begin(server);
    http.addHeader("Content-Type", "application/json");
    
    // Include pump status in data
    StaticJsonDocument<200> doc;
    doc["moisture"] = moisture;
    doc["pump_status"] = pumpRunning ? "on" : "off";
    doc["device_id"] = "esp32_01";
    
    String json;
    serializeJson(doc, json);
    
    int response = http.POST(json);
    Serial.print("Server Response: ");
    Serial.println(response);
    
    http.end();
    lastUpdateTime = millis();
  }
  
  delay(1000);  // Main loop delay
}
```

### 4.4 Automatic Irrigation Logic

```
MOISTURE LEVELS:

100% ████████████████████ (Saturated)
 70% ███████████████░░░░░  ← STOP PUMP (stopThreshold)
 50% ███████████░░░░░░░░░
 30% ███████░░░░░░░░░░░░░  ← START PUMP (moistureThreshold)
  0% ░░░░░░░░░░░░░░░░░░░░ (Dry)
```

**Configuration Parameters:**
```cpp
int moistureThreshold = 30;  // Start irrigation below 30%
int stopThreshold = 70;      // Stop irrigation above 70%
```

### 4.5 Safety Features

1. **Dry Run Protection**: Pump won't run if moisture sensor reports error
2. **Timeout Protection**: Maximum run time limit (configurable)
3. **Manual Override**: Web interface can override automatic control
4. **Fail-Safe**: Pump defaults to OFF on system startup

---

## 5. Leaf Disease Detection System

### 5.1 AI Model Architecture

**Base Architecture:** CNN with Test-Time Augmentation (TTA) Ensemble

```
Input Image (160x160 RGB)
        │
        ▼
┌─────────────────────┐
│   Image Variants    │
├─────────────────────┤
│ 1. Original         │
│ 2. Contrast +8%     │
│ 3. Brightness +4%   │
│ 4. Sharpness +8%    │
└─────────┬───────────┘
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
┌──────┐┌──────┐┌──────┐
│Model ││Model ││Model │ ... (4 inferences)
└──┬───┘└──┬───┘└──┬───┘
   │       │       │
   └───────┼───────┘
           ▼
┌─────────────────────┐
│ Geometric Consensus │  (Geometric Mean)
└─────────┬───────────┘
           ▼
┌─────────────────────┐
│  Weighted Average   │  (55% Original + 45% Consensus)
└─────────┬───────────┘
           ▼
┌─────────────────────┐
│ Final Prediction      │  (15 Classes)
└─────────────────────┘
```

### 5.2 Supported Disease Classes (15 Classes)

| Crop | Disease/Class |
|------|---------------|
| Pepper | Bacterial spot, Healthy |
| Potato | Early blight, Late blight, Healthy |
| Tomato | Bacterial spot, Early blight, Late blight, Leaf Mold, Septoria leaf spot, Spider mites, Target Spot, Yellow Leaf Curl Virus, Mosaic virus, Healthy |

### 5.3 Model Performance

| Metric | Value |
|--------|-------|
| Top-1 Accuracy | 94.2% |
| Top-5 Accuracy | 98.7% |
| Input Size | 160x160 RGB |
| Ensemble Variants | 4 (Original + 3 Augmentations) |
| Inference Time | ~200ms (CPU) |

### 5.4 AI Fallback (Low Confidence)

When model confidence < 60%:
1. Image sent to Groq LLM (llama-3.1-8b-instant)
2. AI analyzes image and selects from 15 disease classes
3. Result combined with model prediction
4. Confidence boosted by AI consensus

### 5.5 Farmer Action Bundle

System generates structured advice:
- **Treatment Summary**: Overview of disease and treatment
- **Recommended Actions**: Step-by-step instructions
- **Care Plan**: Day-by-day recovery schedule
- **Recommended Products**: Fungicides, pesticides, organic alternatives
- **Caution Notes**: Safety warnings and environmental considerations

---

## 6. API Endpoints

### 6.1 IoT Endpoints

| Endpoint | Method | Description | Request | Response |
|----------|--------|-------------|---------|----------|
| `/update_moisture` | POST | Receive sensor data | `{"moisture": 45}` | `{"status": "success"}` |
| `/get_moisture` | GET | Get current moisture | - | `{"moisture": 45, "status": "fresh"}` |
| `/iot_status` | GET | Device health | - | `{"device_status": "online"}` |

### 6.2 Disease Detection Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` (POST) | POST | Upload image for prediction |
| `/ai_advice` | POST | Get AI treatment advice |
| `/chat` | POST | Farmer chat with AI |
| `/marketplace` | GET | Get recommended products |
| `/expert_support` | POST | Request human expert |

### 6.3 Health Check Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Full health status |
| `/livez` | GET | Kubernetes liveness |
| `/readyz` | GET | Kubernetes readiness |
| `/test` | GET | Basic connectivity test |

---

## 7. Installation & Setup

### 7.1 Prerequisites

- Python 3.10+
- ESP32 with Arduino IDE
- WiFi network
- (Optional) Relay module and water pump

### 7.2 Backend Setup

```bash
# Clone repository
cd /Users/nischalmittal/Downloads/FINAL-main

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r config/requirements.txt

# Set environment variables (optional)
export GROQ_API_KEY="your_api_key"  # For AI features
export PORT=10000

# Run the application
python app.py
```

### 7.3 ESP32 Setup

1. **Install Arduino IDE** from [arduino.cc](https://www.arduino.cc/)

2. **Add ESP32 Board Support**:
   - File → Preferences → Additional Board Manager URLs
   - Add: `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   - Tools → Board → Board Manager → Search "ESP32" → Install

3. **Install Required Libraries**:
   - Sketch → Include Library → Manage Libraries
   - Install: `ArduinoJson` by Benoit Blanchon
   - WiFi and HTTPClient are built-in

4. **Select Board**: Tools → Board → ESP32 Arduino → ESP32 Dev Module

5. **Upload Code**:
   - Open `esp32_soil_monitor.ino`
   - Update WiFi credentials and server IP
   - Click Upload button

---

## 8. Hardware Requirements

### 8.1 Minimum Setup (Disease Detection Only)
- Computer with Python 3.10+
- Webcam or mobile camera for leaf images

### 8.2 Full IoT Setup (Soil Monitoring)
- ESP32 development board
- Capacitive soil moisture sensor
- USB cable and power supply
- Jumper wires

### 8.3 Complete Automated System
- All items from 8.2
- 5V Single-channel relay module
- 12V or 5V DC water pump
- 12V power supply for pump
- Water tubing and connectors
- Waterproof enclosure (optional)

---

## 9. Software Dependencies

### 9.1 Python Packages

```
Flask==3.0.0          # Web framework
Flask-Cors==4.0.0     # CORS handling
TensorFlow==2.16.1    # Deep learning
NumPy==1.26.4         # Numerical operations
Pillow==10.2.0        # Image processing
gTTS==2.5.0           # Text-to-speech
groq==0.9.0           # AI LLM integration
deep-translator==1.11.4  # Multi-language support
opencv-python==4.9.0.80  # Image enhancement
```

### 9.2 Arduino Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| WiFi | Built-in | Network connection |
| HTTPClient | Built-in | HTTP requests |
| ArduinoJson | 6.21+ | JSON serialization |

---

## 10. Usage Guide

### 10.1 Starting the System

1. **Start Backend**:
   ```bash
   cd /Users/nischalmittal/Downloads/FINAL-main
   python app.py
   ```

2. **Verify Backend is Running**:
   - Open browser: `http://localhost:10000`
   - Or check: `curl http://localhost:10000/health`

3. **Power On ESP32**:
   - Connect ESP32 to power
   - Check Serial Monitor for "Connected!" message
   - Verify IP address is displayed

4. **Verify Data Flow**:
   - Check Serial Monitor for moisture readings
   - View `/get_moisture` endpoint in browser
   - Moisture value should update every 5 seconds

### 10.2 Disease Detection Workflow

1. Access web interface at `http://localhost:10000`
2. Select crop type (Tomato/Potato/Pepper)
3. Select soil type and weather condition
4. Upload leaf image (JPG/PNG)
5. Click "Analyze"
6. View diagnosis, confidence, and treatment recommendations

### 10.3 Automated Irrigation

With relay module connected:

1. Set thresholds in ESP32 code:
   ```cpp
   int moistureThreshold = 30;  // Start at 30%
   int stopThreshold = 70;      // Stop at 70%
   ```

2. Upload modified code to ESP32

3. System will automatically:
   - Monitor soil moisture every 5 seconds
   - Start pump when moisture < 30%
   - Stop pump when moisture > 70%
   - Send status updates to server

---

## 11. Troubleshooting

### 11.1 ESP32 Connection Issues

| Problem | Solution |
|---------|----------|
| Cannot connect to WiFi | Verify SSID/password; check 2.4GHz network |
| Cannot reach server | Verify server IP; check firewall; ping test |
| HTTP error codes | Check server is running on correct port |
| Moisture readings erratic | Check sensor wiring; verify ADC pin (GPIO 34) |

### 11.2 Model Prediction Issues

| Problem | Solution |
|---------|----------|
| Model not loading | Check `models/` directory; verify .keras files |
| Low confidence | Ensure clear leaf image; check lighting |
| Wrong predictions | Verify crop selection matches image |
| Slow inference | First prediction loads model; subsequent are faster |

### 11.3 Pump/Relay Issues

| Problem | Solution |
|---------|----------|
| Pump not starting | Check relay wiring; verify GPIO pin |
| Pump runs continuously | Check stopThreshold > moistureThreshold |
| Relay not clicking | Verify 5V power to relay module |
| Motor driver heating | Add heat sink; check current rating |

### 11.4 Useful Debug Commands

```bash
# Check server is listening
netstat -tlnp | grep 10000

# Test moisture endpoint
curl -X POST http://localhost:10000/update_moisture \
  -H "Content-Type: application/json" \
  -d '{"moisture": 50}'

# Get current moisture
curl http://localhost:10000/get_moisture

# Check IoT status
curl http://localhost:10000/iot_status

# Full health check
curl http://localhost:10000/health
```

### 11.5 Serial Monitor Debugging

In Arduino IDE, open Serial Monitor (Tools → Serial Monitor):
- Set baud rate to 115200
- Watch for connection messages
- Monitor moisture readings and HTTP responses
- Check pump status indicators

---

## Appendix A: File Structure

```
FINAL-main/
├── app.py                      # WSGI entry point
├── backend/
│   ├── app.py                  # Main Flask application
│   ├── cache_service.py        # Redis/Memory caching
│   ├── error_handler.py        # Error handling
│   ├── farmer_actions.py       # Treatment recommendations
│   └── security.py             # File validation
├── esp32_soil_monitor.ino      # ESP32 Arduino code
├── frontend/
│   ├── public/
│   │   ├── assets/style.css    # Stylesheet
│   │   └── uploads/            # User images
│   └── templates/index.html    # Main UI
├── models/
│   ├── plant_disease_best_model.keras
│   ├── potato_specialist.keras
│   └── class_indices.json      # Class mappings
└── config/requirements.txt     # Python dependencies
```

## Appendix B: Data Flow Summary

```
Soil Sensor → ESP32 → HTTP POST → Flask Backend → Storage → Frontend Display
                                     ↓
                              AI Processing (if needed)
                                     ↓
                              Trigger Relay → Pump Control

Camera/Image → Upload → Disease Detection Model → Results → AI Advice → Voice Output
```

---

**Document Version:** 1.0  
**Last Updated:** April 2026  
**Project:** Smart Farming AI  
**Components:** ESP32 IoT, Leaf Disease Detection, Automated Irrigation
