
## 9.5 Hardware Assembly

**Step-by-Step Assembly Procedure:**

1. **ESP32 Preparation:** Flash firmware with WiFi credentials and calibration constants
2. **Sensor Integration:** Connect soil moisture sensor to GPIO4, DHT22 to GPIO21/22, flow sensor to GPIO23
3. **Actuator Wiring:** Connect relay module to GPIO5; route pump through relay contacts
4. **Power Configuration:** Connect 5V supply to ESP32 and sensors; 12V supply to relay/pump circuit
5. **Enclosure Installation:** Mount in IP65-rated enclosure for field protection
6. **Field Deployment:** Bury soil sensor at 15cm depth; position pump at water source

**Safety Considerations:**
- Use electrical isolation between low-voltage (5V) and high-voltage (12V) circuits
- Implement ground fault protection for pump circuit
- Weatherproof all outdoor connections
- Install emergency stop button for manual system shutdown

---

# 10. SOFTWARE ARCHITECTURE

## 10.1 System Software Stack

The software architecture follows a layered design pattern (Fig. 5) separating concerns into distinct functional layers, enabling maintainability and scalability.

![Fig. 5: Software Architecture Layers](figures/fig5_software_architecture.png)
**Fig. 5: Software Architecture Layers** - Four-layer design showing presentation (web dashboard), application (Flask API), business logic (AI/ML models, decision engine), and data (SQLite, file storage) layers.

**Layer Description:**
1. **Presentation Layer:** HTML5/CSS3/JavaScript dashboard, Chart.js visualizations, responsive mobile interface
2. **Application Layer:** Flask web framework handling HTTP requests, RESTful API endpoints, session management
3. **Business Logic Layer:** ML inference engine (TensorFlow Lite), threshold-based decision logic, alert system
4. **Data Layer:** SQLite database for time-series storage, JSON configuration files, image storage for disease detection

## 10.2 Web Dashboard Architecture

**Technology Stack:**
- **Backend:** Flask (Python 3.8+) - Lightweight WSGI framework
- **Frontend:** HTML5, CSS3, vanilla JavaScript, Bootstrap 5
- **Data Visualization:** Chart.js 3.0 for real-time charts
- **Real-time Communication:** Server-Sent Events (SSE) for live updates
- **Database:** SQLite (development), PostgreSQL (production scaling)

**Dashboard Components (Fig. 6):**

![Fig. 6: Web Dashboard Interface](figures/fig6_dashboard_interface.png)
**Fig. 6: Web Dashboard Interface** - Screenshot showing moisture gauge, real-time trend chart, system controls (manual/auto mode, start/stop buttons), irrigation log, and current status indicators.

### 10.2.1 Dashboard Layout
The dashboard interface (Fig. 6) provides comprehensive system monitoring:
- **Top Bar:** System status, connection health, current moisture level
- **Left Panel:** Circular moisture gauge showing percentage with color-coded zones
- **Center Panel:** Real-time line chart (24h history) with zoom/pan capabilities
- **Right Panel:** Control buttons (Start/Stop irrigation), mode selector (Auto/Manual)
- **Bottom Panel:** Recent irrigation events log with timestamps

### 10.2.2 API Endpoints

### **Table 3: RESTful API Endpoints**

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/health` | GET | System health check | - | `{"status": "healthy", "uptime": 12345}` |
| `/api/moisture/current` | GET | Current moisture reading | - | `{"moisture": 45.5, "timestamp": "2024-01-15T10:30:00Z"}` |
| `/api/moisture/history` | GET | Historical data | `?hours=24&interval=5min` | Array of readings |
| `/api/control/irrigation` | POST | Manual irrigation control | `{"action": "start"}` | `{"status": "success", "duration": 300}` |
| `/api/control/mode` | POST | Set control mode | `{"mode": "auto"}` | `{"mode": "auto", "thresholds": {...}}` |
| `/api/settings` | GET | System configuration | - | Full settings object |
| `/api/settings` | PUT | Update settings | `{"dry_threshold": 30}` | Updated settings |
| `/api/ml/predict` | POST | Get ML prediction | `{"hours_ahead": 2}` | `{"predicted_moisture": 42.3, "confidence": 0.89}` |
| `/api/disease/detect` | POST | Detect plant disease | Image file | `{"disease": "Tomato_Early_blight", "confidence": 0.85}` |

### 10.2.3 Data Flow Implementation

**ESP32 to Server Communication:**
```cpp
// ESP32 sends data every 5 seconds via HTTP POST
void sendSensorData() {
    HTTPClient http;
    http.begin("http://192.168.1.100:10000/api/moisture/update");
    http.addHeader("Content-Type", "application/json");
    
    StaticJsonDocument<256> doc;
    doc["moisture"] = currentMoisture;
    doc["temperature"] = dht.readTemperature();
    doc["humidity"] = dht.readHumidity();
    doc["flow_rate"] = flowRate;
    doc["motor_state"] = motorState;
    doc["timestamp"] = timeClient.getEpochTime();
    doc["device_id"] = "ESP32_FARM_01";
    
    String requestBody;
    serializeJson(doc, requestBody);
    int httpResponseCode = http.POST(requestBody);
    http.end();
}
```

**Server-Side Processing:**
```python
# Flask API Endpoint - Sensor Data Reception
@app.route('/api/moisture/update', methods=['POST'])
def update_moisture():
    """Receive and process sensor data from ESP32"""
    data = request.get_json()
    
    # Validate required fields
    if 'moisture' not in data:
        return jsonify({'error': 'Missing moisture value'}), 400
    
    # Store reading in database (SQLAlchemy ORM)
    reading = MoistureReading(
        moisture_level=data['moisture'],
        temperature=data.get('temperature'),
        humidity=data.get('humidity'),
        flow_rate=data.get('flow_rate'),
        motor_state=data.get('motor_state', False),
        control_reason=data.get('control_reason', 'UNKNOWN'),
        ml_confidence=data.get('ml_confidence'),
        ml_prediction=data.get('ml_prediction'),
        device_id=data.get('device_id', 'ESP32_01'),
        timestamp=datetime.fromtimestamp(data.get('timestamp', 0))
    )
    db.session.add(reading)
    db.session.commit()
    
    # Run ML prediction for proactive irrigation scheduling
    prediction = ml_service.predict_moisture(
        current_reading=data['moisture'],
        temperature=data.get('temperature'),
        humidity=data.get('humidity'),
        hours_ahead=2
    )
    
    # Check thresholds and trigger automation if needed
    control_result = check_automation_thresholds(
        current_moisture=data['moisture'],
        ml_prediction=prediction
    )
    
    return jsonify({
        'success': True,
        'id': reading.id,
        'ml_prediction': prediction['value'],
        'ml_confidence': prediction['confidence'],
        'motor_state': control_result['motor_state'],
        'control_reason': control_result['reason']
    })

# Database Model Definition
class MoistureReading(db.Model):
    """SQLAlchemy model for sensor readings"""
    __tablename__ = 'moisture_readings'
    
    id = db.Column(db.Integer, primary_key=True)
    moisture_level = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    motor_state = db.Column(db.Boolean, default=False)
    control_reason = db.Column(db.String(50))
    ml_confidence = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'moisture': self.moisture_level,
            'temperature': self.temperature,
            'motor_state': self.motor_state,
            'timestamp': self.timestamp.isoformat()
        }
```

## 10.3 Backend Architecture (Flask)

**Application Structure:**
```
backend/
├── app.py                 # Main Flask application factory
├── config.py             # Environment configuration
├── models.py             # SQLAlchemy database models
├── routes/
│   ├── __init__.py
│   ├── main.py           # Dashboard and pages
│   ├── api.py            # REST API endpoints
│   ├── control.py        # Irrigation control
│   └── ml.py             # ML inference endpoints
├── services/
│   ├── moisture_service.py   # Moisture data management
│   ├── motor_service.py      # Pump control logic
│   ├── ml_service.py         # ML model loading/inference
│   └── alert_service.py      # Notification system
├── ml_models/
│   ├── moisture_predictor.pkl    # Random Forest model
│   ├── disease_detector.tflite # Quantized CNN
│   └── lstm_forecaster.h5        # LSTM model
├── static/
│   ├── css/              # Bootstrap + custom styles
│   ├── js/               # Chart.js visualizations
│   └── images/           # Uploaded disease images
├── templates/
│   ├── index.html        # Main dashboard
│   ├── history.html      # Historical data view
│   └── settings.html     # Configuration page
└── utils/
    ├── validators.py     # Input validation
    └── helpers.py        # Utility functions
```

## 10.4 AI Integration in Backend

**ML Service Architecture:**
```python
class MLService:
    def __init__(self):
        self.moisture_model = joblib.load('ml_models/moisture_predictor.pkl')
        self.disease_model = tf.lite.Interpreter('ml_models/disease_detector.tflite')
        self.disease_model.allocate_tensors()
    
    def predict_moisture(self, current_reading, temperature, humidity, hour):
        """Predict moisture 2 hours ahead using Random Forest"""
        features = np.array([[
            current_reading,
            temperature,
            humidity,
            np.sin(2 * np.pi * hour / 24),  # Cyclical hour encoding
            np.cos(2 * np.pi * hour / 24)
        ]])
        prediction = self.moisture_model.predict(features)[0]
        confidence = np.mean([
            tree.predict(features)[0] 
            for tree in self.moisture_model.estimators_
        ])
        return prediction, confidence
    
    def detect_disease(self, image_array):
        """Classify plant disease using CNN"""
        input_details = self.disease_model.get_input_details()
        output_details = self.disease_model.get_output_details()
        
        self.disease_model.set_tensor(input_details[0]['index'], image_array)
        self.disease_model.invoke()
        predictions = self.disease_model.get_tensor(output_details[0]['index'])
        
        class_idx = np.argmax(predictions[0])
        confidence = predictions[0][class_idx]
        return CLASS_NAMES[class_idx], confidence
```

---

# 11. ALGORITHMS AND CONTROL LOGIC

## 11.1 Moisture Level Calculation Algorithm

**Raw Sensor Value to Percentage Conversion:**

```python
def calculate_moisture_percentage(raw_adc_value, dry_calibration, wet_calibration):
    """
    Convert ADC reading to moisture percentage with linear interpolation.
    Based on two-point calibration methodology [19][31].
    
    Parameters:
    - raw_adc_value: 12-bit ADC reading (0-4095)
    - dry_calibration: ADC value in completely dry soil
    - wet_calibration: ADC value in saturated soil
    
    Returns:
    - moisture_percentage: 0-100% with ±2% accuracy
    """
    # Clamp values to calibration range
    raw_adc_value = max(wet_calibration, min(dry_calibration, raw_adc_value))
    
    # Linear interpolation (Eq. 1)
    moisture_percentage = ((dry_calibration - raw_adc_value) / 
                          (dry_calibration - wet_calibration)) * 100
    
    return round(max(0, min(100, moisture_percentage)), 2)
```

**Temperature Compensation:**
```python
def temperature_compensate(moisture, temperature, temp_coefficient=-0.27):
    """
    Apply temperature compensation based on sensor characteristics [19].
    Reference temperature: 25°C
    """
    temp_offset = (temperature - 25) * temp_coefficient
    return moisture - temp_offset
```

**Sensor Reading Smoothing (Exponential Moving Average):**
```python
def exponential_smooth(reading, previous_ema, alpha=0.3):
    """
    Apply EMA filter to reduce sensor noise.
    Alpha = 0.3 provides good noise reduction while maintaining responsiveness.
    """
    return alpha * reading + (1 - alpha) * previous_ema
```

## 11.2 Hybrid AI-Control Algorithm

The hybrid control algorithm (Fig. 7) combines threshold-based reliability with ML-based prediction intelligence.

![Fig. 7: Hybrid AI-Control Algorithm Flowchart](figures/fig7_hybrid_algorithm.png)
**Fig. 7: Hybrid AI-Control Algorithm Flowchart** - Decision tree showing flow from sensor input through ML prediction, confidence check, threshold fallback, hysteresis logic, to final motor control decision.

**Algorithm 1: Hybrid Irrigation Control (Pseudocode)**
```
INPUT: current_moisture, predicted_moisture, ml_confidence, 
       dry_threshold, wet_threshold, manual_override

1:  IF manual_override == TRUE THEN
2:      motor_state ← manual_switch_position
3:      control_mode ← "MANUAL"
4:  ELSE IF ml_confidence > 0.85 AND predicted_moisture < 25 THEN
5:      # High-confidence ML prediction of dry condition
6:      motor_state ← ON
7:      control_mode ← "AI_PREDICTIVE"
8:  ELSE IF current_moisture < dry_threshold THEN
9:      # Threshold-based control (fallback)
10:     motor_state ← ON
11:     control_mode ← "THRESHOLD"
12: ELSE IF current_moisture > wet_threshold THEN
13:     motor_state ← OFF
14:     control_mode ← "THRESHOLD"
15: ELSE
16:     # Hysteresis: maintain current state
17:     motor_state ← previous_motor_state
18:     control_mode ← "HYSTERESIS"
19: END IF

20: apply_motor_control(motor_state)
21: log_event(timestamp, moisture, motor_state, control_mode)
22: RETURN motor_state
```

**Implementation (C++ on ESP32):**
```cpp
// Hybrid AI-Control Decision Logic Implementation
ControlDecision makeDecision(SensorData& data, MLPrediction& pred) {
    ControlDecision decision;
    decision.timestamp = data.timestamp;
    
    // Priority 1: Check manual override switch
    if (data.manualOverride) {
        decision.motorState = true;  // Manual switch ON position
        decision.reason = "MANUAL_OVERRIDE";
        decision.mlConfidence = 0.0;
        return decision;
    }
    
    // Priority 2: High-confidence ML prediction (proactive)
    // If model predicts drought in 2 hours with 85%+ confidence
    if (pred.confidence > 0.85 && pred.predictedMoisture < 25.0) {
        decision.motorState = true;  // Start irrigation early
        decision.reason = "AI_PREDICTIVE";
        decision.mlConfidence = pred.confidence;
        return decision;
    }
    
    // Priority 3: Threshold-based reactive control (fallback)
    if (data.moisture < DRY_THRESHOLD) {
        decision.motorState = true;
        decision.reason = "THRESHOLD_DRY";
    } else if (data.moisture > WET_THRESHOLD) {
        decision.motorState = false;
        decision.reason = "THRESHOLD_WET";
    } else {
        // Hysteresis: prevent rapid switching
        // Maintain current state if moisture is in "dead band"
        decision.motorState = motorState;  // Previous state
        decision.reason = "HYSTERESIS";
    }
    
    decision.mlConfidence = pred.confidence;
    return decision;
}

// Hysteresis Controller Class
class HysteresisController {
private:
    bool motorState = false;
    std::deque<float> moistureHistory;
    
public:
    bool update(float currentMoisture, float predictedMoisture, 
                float mlConfidence) {
        // Maintain rolling window for smoothing
        moistureHistory.push_back(currentMoisture);
        if (moistureHistory.size() > 10) {
            moistureHistory.pop_front();
        }
        
        float avgMoisture = std::accumulate(
            moistureHistory.begin(), moistureHistory.end(), 0.0
        ) / moistureHistory.size();
        
        // Hybrid decision logic
        if (mlConfidence > 0.85 && predictedMoisture < 25) {
            motorState = true;  // AI predicts upcoming dry condition
        } else if (avgMoisture < DRY_THRESHOLD) {
            motorState = true;
        } else if (avgMoisture > WET_THRESHOLD) {
            motorState = false;
        }
        // Else: maintain current state (hysteresis)
        
        return motorState;
    }
};
```

**Hysteresis Implementation:**
```python
class HysteresisController:
    def __init__(self, dry_threshold=30, wet_threshold=70):
        self.dry_threshold = dry_threshold      # Turn ON below this
        self.wet_threshold = wet_threshold      # Turn OFF above this
        self.motor_state = False
        self.history = deque(maxlen=10)         # Last 10 readings
    
    def update(self, current_moisture, predicted_moisture, ml_confidence):
        self.history.append(current_moisture)
        avg_moisture = np.mean(self.history)
        
        # Hybrid decision logic
        if ml_confidence > 0.85 and predicted_moisture < 25:
            # AI predicts upcoming dry condition
            self.motor_state = True
            reason = "AI_PREDICTION"
        elif avg_moisture < self.dry_threshold:
            self.motor_state = True
            reason = "THRESHOLD_DRY"
        elif avg_moisture > self.wet_threshold:
            self.motor_state = False
            reason = "THRESHOLD_WET"
        # Else: maintain current state (hysteresis)
        
        return self.motor_state, reason
```

## 11.3 ML-Based Moisture Trend Prediction

**Feature Engineering for Prediction:**
```python
def extract_features(historical_data):
    """
    Extract time-series features for ML prediction.
    """
    features = {
        # Current state
        'current_moisture': historical_data[-1]['moisture'],
        'current_temp': historical_data[-1]['temperature'],
        'current_humidity': historical_data[-1]['humidity'],
        
        # Trend features
        'moisture_slope': calculate_slope(historical_data[-6:]),
        'moisture_mean_1h': np.mean([r['moisture'] for r in historical_data[-12:]]),
        'moisture_std_1h': np.std([r['moisture'] for r in historical_data[-12:]]),
        
        # Temporal features
        'hour_sin': np.sin(2 * np.pi * current_hour / 24),
        'hour_cos': np.cos(2 * np.pi * current_hour / 24),
        'is_daytime': 6 <= current_hour <= 18,
        
        # Historical irrigation
        'hours_since_irrigation': time_since_last_irrigation(historical_data),
        'previous_irrigation_duration': get_last_irrigation_duration(historical_data)
    }
    return features
```

## 11.4 Anomaly Detection Algorithm

**Statistical Anomaly Detection:**
```python
def detect_sensor_anomaly(current_reading, history, threshold=3):
    """
    Detect anomalous sensor readings using Z-score method.
    Flags readings for validation if they deviate significantly from recent trend.
    """
    if len(history) < 10:
        return False  # Insufficient data
    
    recent_readings = [r['moisture'] for r in history[-10:]]
    mean = np.mean(recent_readings)
    std = np.std(recent_readings)
    
    if std == 0:
        return False  # No variation
    
    z_score = abs(current_reading - mean) / std
    return z_score > threshold  # Flag if >3 standard deviations
```

---

# 12. SYSTEM WORKFLOW

## 12.1 Complete Operational Workflow

![Fig. 8: System Workflow Diagram](figures/fig8_workflow_diagram.png)
**Fig. 8: System Workflow Diagram** - Complete operational flowchart from system boot, calibration, sensor reading, ML inference, decision making, actuator control, data logging, and server communication with error handling and sleep modes.

The system workflow diagram (Fig. 8) illustrates the complete operational sequence from power-on through continuous monitoring loop. The workflow consists of 11 major stages implemented in the ESP32 firmware:

**Main Loop Implementation:**
```cpp
// Complete ESP32 Main Loop with State Machine
void loop() {
    static uint32_t lastSampleTime = 0;
    uint32_t currentTime = millis();
    
    // State Machine Implementation
    switch (currentState) {
        case IDLE:
            // Wait for timer wake
            if (currentTime - lastSampleTime >= SAMPLING_INTERVAL) {
                currentState = READING;
                lastSampleTime = currentTime;
            }
            break;
            
        case READING:
            // Power on sensors and read data
            sensorData = readSensors();
            if (sensorData.valid) {
                currentState = PROCESSING;
            } else {
                currentState = ERROR;
            }
            break;
            
        case PROCESSING:
            // Apply calibration and filtering
            sensorData.moisture = applyCalibration(sensorData.rawADC);
            sensorData.moisture = exponentialSmooth(
                sensorData.moisture, previousMoisture, 0.3
            );
            currentState = AI_INFERENCE;
            break;
            
        case AI_INFERENCE:
            // Run TensorFlow Lite model
            if (mlEnabled) {
                prediction = runMLInference(sensorData);
            } else {
                prediction.confidence = 0.0;
            }
            currentState = DECIDING;
            break;
            
        case DECIDING:
            // Hybrid control decision
            decision = makeDecision(sensorData, prediction);
            currentState = (decision.motorState != motorState) ? 
                          IRRIGATING : TRANSMITTING;
            break;
            
        case IRRIGATING:
            // Control relay and pump
            digitalWrite(RELAY_PIN, decision.motorState ? HIGH : LOW);
            delay(RELAY_SETTLE);  // 50ms for relay
            motorState = decision.motorState;
            
            // Log irrigation event
            logIrrigationEvent(decision);
            currentState = TRANSMITTING;
            break;
            
        case TRANSMITTING:
            // Send data to Flask server
            if (WiFi.status() == WL_CONNECTED) {
                bool success = sendDataToServer(sensorData, decision);
                if (!success) {
                    queueLocalData(sensorData, decision);
                }
            } else {
                queueLocalData(sensorData, decision);
            }
            currentState = SLEEPING;
            break;
            
        case SLEEPING:
            // Enter light sleep for power saving
            esp_sleep_enable_timer_wakeup(SAMPLING_INTERVAL * 1000);
            esp_light_sleep_start();
            currentState = IDLE;
            break;
            
        case ERROR:
            // Handle sensor read error
            logError("Sensor read failed");
            delay(1000);
            currentState = TRANSMITTING;  // Continue anyway
            break;
    }
}
```

**Stage 1: System Boot (0-2 seconds)**
- ESP32 initializes peripherals (WiFi, ADC, GPIO)
- Loads calibration constants from flash memory
- Establishes WiFi connection to access point

**Stage 2: Calibration Verification (2-3 seconds)**
- Validates stored calibration values within expected ranges
- Performs quick self-test on sensors
- Initializes ML model interpreter

**Stage 3: Sensor Acquisition (100ms)**
- Activates soil moisture sensor
- Waits 100ms for signal stabilization
- Reads 12-bit ADC value (averaged over 10 samples)
- Reads DHT22 temperature/humidity
- Reads flow sensor pulse count

**Stage 4: Data Processing (10ms)**
- Converts ADC to moisture percentage using calibration curve
- Applies temperature compensation
- Updates exponential moving average
- Checks for sensor anomalies

**Stage 5: ML Inference (120ms)**
- Loads recent historical data (24 readings)
- Extracts time-series features
- Runs Random Forest prediction for 2-hour forecast
- Calculates prediction confidence
- (Optional) Runs CNN if disease detection enabled

**Stage 6: Decision Logic (5ms)**
- Checks manual override switch state
- Evaluates ML prediction confidence
- Applies hybrid threshold-ML decision algorithm
- Implements hysteresis to prevent rapid switching

**Stage 7: Actuator Control (50ms)**
- Sets GPIO output for relay control
- Activates relay coil (if motor ON)
- Waits 50ms for relay contact stabilization
- Monitors flow sensor for confirmation

**Stage 8: Data Logging (5ms)**
- Buffers reading in local circular buffer
- Adds timestamp and control decision metadata
- Maintains 24-hour rolling history for ML features

**Stage 9: Network Transmission (200-500ms)**
- Formats data as JSON payload
- Opens HTTP connection to Flask server
- Transmits sensor data and ML predictions
- Waits for server acknowledgment
- Handles transmission failures with retry logic

**Stage 10: Error Handling**
- If transmission fails: store in local queue for retry
- If sensor anomaly detected: flag for validation
- If WiFi disconnected: enter offline mode, queue locally

**Stage 11: Sleep and Repeat**
- Enter light sleep mode (2μA current draw)
- Timer wakes system after 5 seconds
- Return to Stage 3 (continuous loop)

## 12.2 State Machine Diagram

![Fig. 9: State Machine Diagram](figures/fig9_state_machine.png)
**Fig. 9: State Machine Diagram** - System state transitions showing IDLE, READING, PROCESSING, AI_INFERENCE, DECIDING, IRRIGATING, TRANSMITTING, SLEEPING states with transitions triggered by events (timer, sensor ready, prediction complete, threshold crossed, transmission complete).

The state machine (Fig. 9) formalizes system behavior:

**States:**
- **IDLE:** Waiting for timer wake
- **READING:** Acquiring sensor data
- **PROCESSING:** Converting and filtering readings
- **AI_INFERENCE:** Running ML prediction
- **DECIDING:** Evaluating control logic
- **IRRIGATING:** Controlling pump (if needed)
- **TRANSMITTING:** Sending data to server
- **SLEEPING:** Low-power mode

**Transitions:**
- Timer expiry → READING
- Sensor ready → PROCESSING
- Processing complete → AI_INFERENCE
- Prediction complete → DECIDING
- Decision made → IRRIGATING (if needed) or TRANSMITTING
- Irrigation complete → TRANSMITTING
- Transmission complete → SLEEPING
- Sleep timer → IDLE

## 12.3 Timing Specifications

### **Table 4: System Timing Specifications**

| Operation | Duration | Frequency | Cumulative per Cycle |
|-----------|----------|-----------|----------------------|
| Sensor Reading | 100ms | Every 5s | 100ms |
| ADC Processing | 10ms | Every 5s | 110ms |
| ML Inference | 120ms | Every 5s | 230ms |
| Decision Logic | 5ms | Every 5s | 235ms |
| Motor Activation | 50ms | On change only | 285ms |
| Data Transmission | 250ms | Every 5s | 535ms |
| **Total Active Time** | **~535ms** | | |
| Sleep Time | 4,465ms | | |
| **Total Cycle** | **5,000ms** | | |

**Duty Cycle:** 10.7% active, 89.3% sleep
**Average Power:** 0.4W (active: 3.6W, sleep: 0.05W)

---

[Continue with remaining sections in Part 3...]
