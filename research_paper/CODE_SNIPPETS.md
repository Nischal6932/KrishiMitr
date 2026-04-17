# Code Snippets Appendix

## A.1 ESP32 Firmware (Arduino/C++)

### A.1.1 Complete Main Loop Implementation
```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <TensorFlowLite.h>
#include "model_data.h"  // Quantized CNN model

// Pin Definitions
#define SOIL_SENSOR_PIN     4   // ADC2_CH0
#define RELAY_PIN           5   // Pump control
#define DHT_PIN             21  // Temperature/Humidity
#define FLOW_SENSOR_PIN     23  // Water flow
#define MANUAL_SWITCH_PIN   18  // Manual override

// Calibration Constants (stored in flash)
#define DRY_CALIBRATION     3500
#define WET_CALIBRATION     1200
#define DRY_THRESHOLD       30
#define WET_THRESHOLD       70

// Timing Constants
#define SAMPLING_INTERVAL   5000    // 5 seconds
#define SENSOR_STABILIZE    100     // ms
#define RELAY_SETTLE        50      // ms

// Global Variables
DHT dht(DHT_PIN, DHT22);
float currentMoisture = 50.0;
bool motorState = false;
bool manualOverride = false;
uint32_t lastSampleTime = 0;

// ML Model (TensorFlow Lite Micro)
tflite::MicroInterpreter* interpreter = nullptr;
tflite::MicroAllocator* allocator = nullptr;
tflite::MicroErrorReporter error_reporter;

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    // Initialize GPIO
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(FLOW_SENSOR_PIN, INPUT);
    pinMode(MANUAL_SWITCH_PIN, INPUT_PULLUP);
    digitalWrite(RELAY_PIN, LOW);
    
    // Initialize sensors
    dht.begin();
    analogReadResolution(12);  // 12-bit ADC (0-4095)
    analogSetAttenuation(ADC_11db);  // Full voltage range
    
    // Initialize WiFi
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi Connected");
    
    // Initialize TensorFlow Lite
    initMLModel();
    
    Serial.println("System Ready");
}

void loop() {
    uint32_t currentTime = millis();
    
    // Check if it's time to sample
    if (currentTime - lastSampleTime >= SAMPLING_INTERVAL) {
        lastSampleTime = currentTime;
        
        // Read all sensors
        SensorData data = readSensors();
        
        // Run ML prediction
        MLPrediction prediction = runMLInference(data);
        
        // Make control decision
        ControlDecision decision = makeDecision(data, prediction);
        
        // Apply motor control
        applyMotorControl(decision.motorState);
        
        // Send data to server
        sendDataToServer(data, decision, prediction);
        
        // Log locally
        logEvent(data, decision);
    }
    
    // Brief yield to allow background tasks
    delay(10);
}

// Sensor Reading Function
SensorData readSensors() {
    SensorData data;
    
    // Read soil moisture (averaged over 10 samples)
    uint32_t adcSum = 0;
    for (int i = 0; i < 10; i++) {
        adcSum += analogRead(SOIL_SENSOR_PIN);
        delay(10);
    }
    uint16_t adcValue = adcSum / 10;
    data.moisture = calculateMoisturePercentage(adcValue);
    
    // Apply temperature compensation
    data.temperature = dht.readTemperature();
    data.humidity = dht.readHumidity();
    data.moisture = temperatureCompensate(data.moisture, data.temperature);
    
    // Check manual override
    data.manualOverride = (digitalRead(MANUAL_SWITCH_PIN) == LOW);
    
    // Read flow sensor (pulse count in last interval)
    data.flowRate = readFlowSensor();
    
    data.timestamp = getEpochTime();
    
    return data;
}

// Moisture Calculation with Calibration
float calculateMoisturePercentage(uint16_t adcValue) {
    // Clamp to calibration range
    if (adcValue > DRY_CALIBRATION) adcValue = DRY_CALIBRATION;
    if (adcValue < WET_CALIBRATION) adcValue = WET_CALIBRATION;
    
    // Linear interpolation (Eq. 6 from paper)
    float moisture = ((float)(DRY_CALIBRATION - adcValue) / 
                     (DRY_CALIBRATION - WET_CALIBRATION)) * 100.0;
    
    return constrain(moisture, 0.0, 100.0);
}

// Temperature Compensation (Eq. 7 from paper)
float temperatureCompensate(float moisture, float temperature) {
    const float TEMP_COEFFICIENT = -0.27;  // % per degree C
    const float REF_TEMP = 25.0;
    
    float correction = TEMP_COEFFICIENT * (temperature - REF_TEMP);
    return moisture - correction;
}

// Hybrid Decision Logic (Algorithm 1 from paper)
ControlDecision makeDecision(SensorData& data, MLPrediction& pred) {
    ControlDecision decision;
    decision.timestamp = data.timestamp;
    
    // Check manual override first
    if (data.manualOverride) {
        decision.motorState = true;  // Manual switch ON
        decision.reason = "MANUAL_OVERRIDE";
        decision.mlConfidence = 0.0;
        return decision;
    }
    
    // High-confidence ML prediction
    if (pred.confidence > 0.85 && pred.predictedMoisture < 25.0) {
        decision.motorState = true;
        decision.reason = "AI_PREDICTIVE";
        decision.mlConfidence = pred.confidence;
        return decision;
    }
    
    // Threshold-based control (fallback)
    if (data.moisture < DRY_THRESHOLD) {
        decision.motorState = true;
        decision.reason = "THRESHOLD_DRY";
    } else if (data.moisture > WET_THRESHOLD) {
        decision.motorState = false;
        decision.reason = "THRESHOLD_WET";
    } else {
        // Hysteresis: maintain current state
        decision.motorState = motorState;
        decision.reason = "HYSTERESIS";
    }
    
    decision.mlConfidence = pred.confidence;
    return decision;
}

// Apply motor control with debouncing
void applyMotorControl(bool newState) {
    if (newState != motorState) {
        digitalWrite(RELAY_PIN, newState ? HIGH : LOW);
        delay(RELAY_SETTLE);  // Wait for relay to settle
        motorState = newState;
        
        Serial.printf("Motor %s (Reason: %s)\n", 
                     newState ? "ON" : "OFF", 
                     decision.reason.c_str());
    }
}

// Send data to Flask server
void sendDataToServer(SensorData& data, ControlDecision& decision, 
                      MLPrediction& prediction) {
    if (WiFi.status() != WL_CONNECTED) {
        // Queue for later transmission
        queueLocalData(data, decision);
        return;
    }
    
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    
    StaticJsonDocument<512> doc;
    doc["moisture"] = data.moisture;
    doc["temperature"] = data.temperature;
    doc["humidity"] = data.humidity;
    doc["flow_rate"] = data.flowRate;
    doc["motor_state"] = motorState;
    doc["control_reason"] = decision.reason;
    doc["ml_confidence"] = decision.mlConfidence;
    doc["ml_prediction"] = prediction.predictedMoisture;
    doc["timestamp"] = data.timestamp;
    doc["device_id"] = DEVICE_ID;
    
    String requestBody;
    serializeJson(doc, requestBody);
    
    int httpCode = http.POST(requestBody);
    
    if (httpCode != 200) {
        Serial.printf("HTTP Error: %d\n", httpCode);
        queueLocalData(data, decision);
    }
    
    http.end();
}

// ML Inference (TensorFlow Lite Micro)
MLPrediction runMLInference(SensorData& data) {
    MLPrediction pred;
    
    // Prepare input tensor
    TfLiteTensor* input = interpreter->input(0);
    
    // Feature vector: [moisture, temp, humidity, hour_sin, hour_cos]
    float hour = (data.timestamp % 86400) / 3600.0;
    input->data.f[0] = data.moisture;
    input->data.f[1] = data.temperature;
    input->data.f[2] = data.humidity;
    input->data.f[3] = sin(2 * PI * hour / 24.0);
    input->data.f[4] = cos(2 * PI * hour / 24.0);
    
    // Run inference
    TfLiteStatus status = interpreter->Invoke();
    
    if (status == kTfLiteOk) {
        TfLiteTensor* output = interpreter->output(0);
        pred.predictedMoisture = output->data.f[0];
        
        // Calculate confidence from prediction variance
        pred.confidence = calculateConfidence(output);
    } else {
        pred.predictedMoisture = data.moisture;  // Fallback
        pred.confidence = 0.0;
    }
    
    return pred;
}
```

---

## A.2 Flask Backend (Python)

### A.2.1 Complete Application Factory
```python
# app.py - Main Flask Application
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import logging
from threading import Lock

# Initialize extensions
db = SQLAlchemy()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_name='development'):
    """Application factory pattern"""
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', 'sqlite:///irrigation.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)
    
    # Register blueprints
    from routes.main import main_bp
    from routes.api import api_bp
    from routes.control import control_bp
    from routes.ml import ml_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(control_bp, url_prefix='/control')
    app.register_blueprint(ml_bp, url_prefix='/ml')
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=10000, debug=False)
```

### A.2.2 Database Models
```python
# models.py - SQLAlchemy Models
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class MoistureReading(db.Model):
    """Soil moisture sensor readings"""
    __tablename__ = 'moisture_readings'
    
    id = db.Column(db.Integer, primary_key=True)
    moisture_level = db.Column(db.Float, nullable=False)  # Percentage 0-100
    temperature = db.Column(db.Float)  # Celsius
    humidity = db.Column(db.Float)  # Percentage 0-100
    flow_rate = db.Column(db.Float)  # L/min
    device_id = db.Column(db.String(50), default='ESP32_01')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Control information
    motor_state = db.Column(db.Boolean, default=False)
    control_reason = db.Column(db.String(50))  # AI_PREDICTIVE, THRESHOLD_DRY, etc.
    ml_confidence = db.Column(db.Float)  # 0-1
    ml_prediction = db.Column(db.Float)  # Predicted future moisture
    
    def to_dict(self):
        return {
            'id': self.id,
            'moisture': self.moisture_level,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'flow_rate': self.flow_rate,
            'motor_state': self.motor_state,
            'control_reason': self.control_reason,
            'ml_confidence': self.ml_confidence,
            'ml_prediction': self.ml_prediction,
            'timestamp': self.timestamp.isoformat(),
            'device_id': self.device_id
        }

class IrrigationEvent(db.Model):
    """Irrigation start/stop events"""
    __tablename__ = 'irrigation_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(20))  # START, STOP
    duration_seconds = db.Column(db.Integer)
    water_volume_liters = db.Column(db.Float)
    trigger_reason = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class SystemSettings(db.Model):
    """System configuration"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    dry_threshold = db.Column(db.Float, default=30.0)
    wet_threshold = db.Column(db.Float, default=70.0)
    ml_enabled = db.Column(db.Boolean, default=True)
    manual_override = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### A.2.3 API Routes
```python
# routes/api.py - REST API Endpoints
from flask import Blueprint, request, jsonify
from models import db, MoistureReading, IrrigationEvent, SystemSettings
from services.ml_service import MLService
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)
ml_service = MLService()

@api_bp.route('/health', methods=['GET'])
def health_check():
    """System health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'ml_model_loaded': ml_service.is_model_loaded(),
        'database_connected': True
    })

@api_bp.route('/moisture/current', methods=['GET'])
def get_current_moisture():
    """Get most recent moisture reading"""
    reading = MoistureReading.query.order_by(
        MoistureReading.timestamp.desc()).first()
    
    if not reading:
        return jsonify({'error': 'No data available'}), 404
    
    return jsonify(reading.to_dict())

@api_bp.route('/moisture/history', methods=['GET'])
def get_moisture_history():
    """Get historical moisture data"""
    hours = request.args.get('hours', 24, type=int)
    interval = request.args.get('interval', 5, type=int)  # minutes
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    readings = MoistureReading.query\
        .filter(MoistureReading.timestamp >= cutoff)\
        .order_by(MoistureReading.timestamp.asc())\
        .all()
    
    # Downsample if needed
    if len(readings) > 1000:
        step = len(readings) // 1000
        readings = readings[::step]
    
    return jsonify([r.to_dict() for r in readings])

@api_bp.route('/moisture/update', methods=['POST'])
def update_moisture():
    """Receive sensor data from ESP32"""
    data = request.get_json()
    
    # Validate required fields
    if 'moisture' not in data:
        return jsonify({'error': 'Missing moisture value'}), 400
    
    # Create reading
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
    
    # Run ML prediction for response
    prediction = ml_service.predict_moisture(reading.moisture_level)
    
    return jsonify({
        'success': True,
        'id': reading.id,
        'ml_prediction': prediction['value'],
        'ml_confidence': prediction['confidence']
    })

@api_bp.route('/control/irrigation', methods=['POST'])
def control_irrigation():
    """Manual irrigation control"""
    data = request.get_json()
    action = data.get('action')  # 'start' or 'stop'
    duration = data.get('duration', 300)  # seconds, default 5 min
    
    if action not in ['start', 'stop']:
        return jsonify({'error': 'Invalid action'}), 400
    
    # Log the event
    event = IrrigationEvent(
        event_type=action.upper(),
        trigger_reason='MANUAL_API',
        timestamp=datetime.utcnow()
    )
    db.session.add(event)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'action': action,
        'duration': duration if action == 'start' else 0,
        'event_id': event.id
    })

@api_bp.route('/settings', methods=['GET', 'PUT'])
def system_settings():
    """Get or update system settings"""
    settings = SystemSettings.query.first()
    
    if not settings:
        settings = SystemSettings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'GET':
        return jsonify({
            'dry_threshold': settings.dry_threshold,
            'wet_threshold': settings.wet_threshold,
            'ml_enabled': settings.ml_enabled,
            'manual_override': settings.manual_override,
            'updated_at': settings.updated_at.isoformat()
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        if 'dry_threshold' in data:
            settings.dry_threshold = data['dry_threshold']
        if 'wet_threshold' in data:
            settings.wet_threshold = data['wet_threshold']
        if 'ml_enabled' in data:
            settings.ml_enabled = data['ml_enabled']
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'settings': settings.to_dict()})
```

### A.2.4 ML Service Implementation
```python
# services/ml_service.py - Machine Learning Service
import joblib
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MLService:
    """Machine Learning service for moisture prediction"""
    
    def __init__(self):
        self.moisture_model = None
        self.disease_model = None
        self.model_loaded = False
        self.load_models()
    
    def load_models(self):
        """Load pre-trained ML models"""
        try:
            # Load Random Forest model for moisture prediction
            self.moisture_model = joblib.load('ml_models/moisture_predictor.pkl')
            logger.info("Random Forest model loaded successfully")
            
            # Load CNN model for disease detection (if available)
            try:
                import tensorflow as tf
                self.disease_model = tf.keras.models.load_model(
                    'ml_models/disease_detector.h5')
                logger.info("CNN disease model loaded successfully")
            except Exception as e:
                logger.warning(f"Disease model not loaded: {e}")
            
            self.model_loaded = True
            
        except Exception as e:
            logger.error(f"Failed to load ML models: {e}")
            self.model_loaded = False
    
    def is_model_loaded(self):
        return self.model_loaded
    
    def predict_moisture(self, current_moisture, temperature=None, 
                        humidity=None, hours_ahead=2):
        """
        Predict soil moisture 2 hours ahead using Random Forest
        
        Returns dict with 'value' and 'confidence'
        """
        if not self.model_loaded or self.moisture_model is None:
            return {'value': current_moisture, 'confidence': 0.0}
        
        try:
            # Prepare features
            hour = datetime.now().hour
            features = np.array([[
                current_moisture,
                temperature if temperature else 25.0,
                humidity if humidity else 60.0,
                np.sin(2 * np.pi * hour / 24),
                np.cos(2 * np.pi * hour / 24),
                hours_ahead
            ]])
            
            # Make prediction
            prediction = self.moisture_model.predict(features)[0]
            
            # Calculate confidence from tree variance
            predictions = [tree.predict(features)[0] 
                          for tree in self.moisture_model.estimators_]
            std = np.std(predictions)
            confidence = max(0, 1 - (std / 10))  # Normalize to 0-1
            
            return {
                'value': float(prediction),
                'confidence': float(confidence)
            }
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {'value': current_moisture, 'confidence': 0.0}
    
    def detect_disease(self, image_array):
        """
        Detect plant disease using CNN
        
        Args:
            image_array: Preprocessed image (160x160x3)
        
        Returns:
            dict with 'disease' name and 'confidence'
        """
        if self.disease_model is None:
            return {'disease': 'UNKNOWN', 'confidence': 0.0}
        
        try:
            predictions = self.disease_model.predict(image_array)
            class_idx = np.argmax(predictions[0])
            confidence = float(predictions[0][class_idx])
            
            # Class names mapping
            class_names = [
                'Pepper_bell_Bacterial_spot', 'Pepper_bell_healthy',
                'Potato_Early_blight', 'Potato_Late_blight', 'Potato_healthy',
                'Tomato_Bacterial_spot', 'Tomato_Early_blight',
                'Tomato_Late_blight', 'Tomato_Leaf_Mold',
                'Tomato_Septoria_leaf_spot', 'Tomato_Spider_mites',
                'Tomato_Target_Spot', 'Tomato_Yellow_Leaf_Curl_Virus',
                'Tomato_mosaic_virus', 'Tomato_healthy'
            ]
            
            return {
                'disease': class_names[class_idx],
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"Disease detection error: {e}")
            return {'disease': 'ERROR', 'confidence': 0.0}
```

---

## A.3 Frontend Dashboard (JavaScript)

### A.3.1 Real-time Chart Implementation
```javascript
// static/js/dashboard.js - Chart.js Implementation

class IrrigationDashboard {
    constructor() {
        this.moistureChart = null;
        this.gaugeChart = null;
        this.updateInterval = 5000; // 5 seconds
        this.apiBaseUrl = '/api';
        
        this.init();
    }
    
    init() {
        this.initMoistureChart();
        this.initGaugeChart();
        this.startRealTimeUpdates();
        this.bindControlButtons();
    }
    
    initMoistureChart() {
        const ctx = document.getElementById('moistureChart').getContext('2d');
        
        this.moistureChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Soil Moisture (%)',
                    data: [],
                    borderColor: '#1f77b4',
                    backgroundColor: 'rgba(31, 119, 180, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3
                }, {
                    label: 'ML Prediction',
                    data: [],
                    borderColor: '#ff7f0e',
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Moisture (%)'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                },
                plugins: {
                    annotation: {
                        annotations: {
                            optimalZone: {
                                type: 'box',
                                yMin: 40,
                                yMax: 60,
                                backgroundColor: 'rgba(0, 255, 0, 0.1)',
                                label: {
                                    content: 'Optimal Zone',
                                    enabled: true
                                }
                            }
                        }
                    }
                }
            }
        });
    }
    
    initGaugeChart() {
        const ctx = document.getElementById('gaugeChart').getContext('2d');
        
        this.gaugeChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Moisture', 'Dry'],
                datasets: [{
                    data: [50, 50],
                    backgroundColor: [
                        this.getMoistureColor(50),
                        '#e0e0e0'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                circumference: 180,
                rotation: 270,
                cutout: '60%',
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                }
            },
            plugins: [{
                id: 'gaugeText',
                afterDraw: (chart) => {
                    const ctx = chart.ctx;
                    const centerX = chart.chartArea.left + 
                                   (chart.chartArea.right - chart.chartArea.left) / 2;
                    const centerY = chart.chartArea.bottom - 20;
                    
                    ctx.save();
                    ctx.font = 'bold 36px Arial';
                    ctx.fillStyle = '#333';
                    ctx.textAlign = 'center';
                    ctx.fillText(`${chart.data.datasets[0].data[0]}%`, centerX, centerY);
                    ctx.restore();
                }
            }]
        });
    }
    
    async updateData() {
        try {
            // Fetch current reading
            const response = await fetch(`${this.apiBaseUrl}/moisture/current`);
            const data = await response.json();
            
            // Update gauge
            this.updateGauge(data.moisture);
            
            // Update status indicators
            this.updateStatusIndicators(data);
            
            // Fetch history for chart
            const historyResponse = await fetch(
                `${this.apiBaseUrl}/moisture/history?hours=24`
            );
            const history = await historyResponse.json();
            
            this.updateChart(history);
            
        } catch (error) {
            console.error('Update error:', error);
            this.showConnectionError();
        }
    }
    
    updateGauge(moisture) {
        this.gaugeChart.data.datasets[0].data = [moisture, 100 - moisture];
        this.gaugeChart.data.datasets[0].backgroundColor[0] = 
            this.getMoistureColor(moisture);
        this.gaugeChart.update('none'); // Update without animation
    }
    
    getMoistureColor(moisture) {
        if (moisture < 30) return '#d62728';      // Red - Dry
        if (moisture < 40) return '#ff7f0e';      // Orange - Low
        if (moisture <= 60) return '#2ca02c';     // Green - Optimal
        if (moisture <= 70) return '#1f77b4';     // Blue - High
        return '#9467bd';                          // Purple - Wet
    }
    
    updateChart(history) {
        const labels = history.map(r => 
            new Date(r.timestamp).toLocaleTimeString()
        );
        const data = history.map(r => r.moisture);
        const predictions = history.map(r => r.ml_prediction);
        
        this.moistureChart.data.labels = labels;
        this.moistureChart.data.datasets[0].data = data;
        this.moistureChart.data.datasets[1].data = predictions;
        this.moistureChart.update();
    }
    
    async startIrrigation() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/control/irrigation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'start', duration: 300 })
            });
            
            const result = await response.json();
            if (result.success) {
                this.showNotification('Irrigation started', 'success');
            }
        } catch (error) {
            this.showNotification('Failed to start irrigation', 'error');
        }
    }
    
    startRealTimeUpdates() {
        this.updateData(); // Initial load
        setInterval(() => this.updateData(), this.updateInterval);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new IrrigationDashboard();
});
```

---

## A.4 Configuration Examples

### A.4.1 ESP32 Configuration Header
```cpp
// config.h - System Configuration
#ifndef CONFIG_H
#define CONFIG_H

// WiFi Credentials
#define WIFI_SSID           "Your_WiFi_SSID"
#define WIFI_PASSWORD       "Your_WiFi_Password"

// Server Configuration
#define SERVER_URL          "http://192.168.1.100:10000/api/moisture/update"
#define DEVICE_ID           "ESP32_FARM_01"

// Sensor Calibration (update after calibration)
#define DRY_CALIBRATION     3500    // ADC value in dry soil
#define WET_CALIBRATION     1200    // ADC value in wet soil

// Control Thresholds (%)
#define DRY_THRESHOLD       30      // Start irrigation below this
#define WET_THRESHOLD       70      // Stop irrigation above this

// Timing (milliseconds)
#define SAMPLING_INTERVAL   5000    // 5 seconds
#define TRANSMISSION_RETRY  3       // Number of retries
#define DEBOUNCE_TIME       200     // Button debounce

// ML Configuration
#define ML_INPUT_SIZE       5       // Feature vector size
#define ML_USE_QUANTIZED    true    // Use INT8 quantized model

// Debug Options
#define DEBUG_SERIAL        true
#define DEBUG_LEVEL         2       // 0=none, 1=errors, 2=info, 3=verbose

#endif
```

### A.4.2 Flask Application Configuration
```python
# config.py - Flask Configuration Classes
import os

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ML Model Paths
    MOISTURE_MODEL_PATH = 'ml_models/moisture_predictor.pkl'
    DISEASE_MODEL_PATH = 'ml_models/disease_detector.h5'
    
    # Irrigation Settings
    DEFAULT_DRY_THRESHOLD = 30.0
    DEFAULT_WET_THRESHOLD = 70.0
    MAX_IRRIGATION_DURATION = 1800  # 30 minutes

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///irrigation_dev.db'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///irrigation.db'
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 3600

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
```

---

**End of Code Snippets Appendix**
