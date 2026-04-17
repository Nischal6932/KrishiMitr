# ESP32 Soil Moisture Integration Guide

## Overview
This guide shows how to integrate the ESP32 soil moisture sensor with your SmartFarm AI web application.

## Hardware Setup
- ESP32 development board
- Soil moisture sensor (capacitive or resistive)
- Jumper wires
- Power supply (USB or battery)

## Wiring
- Connect soil moisture sensor analog output to ESP32 GPIO 34
- Connect sensor VCC to 3.3V
- Connect sensor GND to GND

## Software Setup

### 1. Upload Arduino Code
1. Open `esp32_soil_monitor.ino` in Arduino IDE
2. Install required libraries:
   - WiFi (built-in)
   - HTTPClient (built-in)
   - ArduinoJson (install via Library Manager)
3. Update configuration:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   const char* serverUrl = "http://YOUR_SERVER_IP:10000/update_moisture";
   ```
4. Upload to ESP32

### 2. Configure Web Server
The backend already has the required endpoints:
- `/update_moisture` - Receives data from ESP32
- `/get_moisture` - Returns current moisture data
- `/iot_status` - Returns device connectivity status

### 3. Start the Web Application
```bash
cd /Users/nischalmittal/Downloads/FINAL-main
python app.py
```

## Features

### Real-time Moisture Display
- Moisture value updates automatically every 3 seconds
- Visual status indicator (green/yellow/red)
- Stale data detection and warnings

### IoT Status Monitoring
- **Green**: Device online (last update < 1 minute)
- **Yellow**: Intermittent connection (1-5 minutes)
- **Red**: Device offline (> 5 minutes)

### Automatic Slider Updates
- Moisture slider syncs with sensor readings
- Manual override available when slider is active
- Form submissions use latest sensor data

## Data Format

### ESP32 to Server (POST /update_moisture)
```json
{
  "moisture": 45,
  "device_id": "esp32_01",
  "raw_adc": 2048,
  "timestamp": 123456
}
```

### Server to Frontend (GET /get_moisture)
```json
{
  "moisture": 45,
  "status": "fresh",
  "last_update": 1234567890,
  "time_since_update": 15,
  "consecutive_failures": 0
}
```

## Troubleshooting

### ESP32 Not Connecting
1. Check WiFi credentials
2. Verify server IP address
3. Ensure firewall allows port 10000
4. Check Serial Monitor for error messages

### Moisture Values Not Updating
1. Verify ESP32 is sending data (check Serial Monitor)
2. Check browser console for JavaScript errors
3. Verify backend is running and accessible

### Sensor Reading Issues
1. Check sensor wiring
2. Calibrate dry/wet values in code:
   ```cpp
   int dryValue = 3500;  // Adjust based on your sensor
   int wetValue = 1200;  // Adjust based on your sensor
   ```

## Advanced Configuration

### Multiple Sensors
Modify the Arduino code to send multiple readings:
```cpp
doc["moisture_1"] = moisture1;
doc["moisture_2"] = moisture2;
doc["sensor_location"] = "field_a";
```

### Custom Update Intervals
Change the update frequency:
```cpp
const unsigned long updateInterval = 10000; // 10 seconds
```

### Data Logging
The backend automatically logs all moisture updates with timestamps for historical analysis.

## Security Notes
- Change default WiFi credentials
- Use HTTPS in production (modify serverUrl)
- Consider adding API key authentication
- Keep ESP32 firmware updated

## Performance
- ESP32 sends data every 5 seconds to balance real-time updates with power usage
- Frontend polls every 3 seconds for responsive UI
- Backend handles concurrent requests efficiently

## Support
For issues:
1. Check Arduino IDE Serial Monitor
2. Review browser developer console
3. Verify backend logs
4. Test endpoints manually with curl commands
