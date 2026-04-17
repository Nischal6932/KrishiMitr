#!/usr/bin/env python3
"""
Test script to simulate ESP32 sending moisture data to the web backend
"""

import requests
import json
import time
import random

def test_esp32_integration():
    """Test the ESP32 integration endpoints"""
    
    base_url = "http://localhost:10000"
    
    print("🌱 Testing ESP32 Integration with SmartFarm AI")
    print("=" * 50)
    
    # Test 1: Send moisture data (simulating ESP32)
    print("\n1. Testing moisture data submission...")
    moisture_data = {
        "moisture": random.randint(20, 80),
        "device_id": "test_esp32_01",
        "raw_adc": random.randint(1200, 3500),
        "timestamp": int(time.time() * 1000)
    }
    
    try:
        response = requests.post(
            f"{base_url}/update_moisture",
            json=moisture_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print(f"✅ Moisture data sent successfully: {moisture_data['moisture']}%")
            print(f"   Server response: {response.json()}")
        else:
            print(f"❌ Failed to send moisture data: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error sending moisture data: {e}")
    
    # Test 2: Get current moisture data
    print("\n2. Testing moisture data retrieval...")
    try:
        response = requests.get(f"{base_url}/get_moisture")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Current moisture: {data['moisture']}%")
            print(f"   Status: {data['status']}")
            print(f"   Time since update: {data['time_since_update']}s")
        else:
            print(f"❌ Failed to get moisture data: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error getting moisture data: {e}")
    
    # Test 3: Check IoT status
    print("\n3. Testing IoT status endpoint...")
    try:
        response = requests.get(f"{base_url}/iot_status")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Device status: {data['device_status']}")
            print(f"   Current moisture: {data['current_moisture']}%")
            print(f"   Uptime: {data['uptime_percentage']}%")
        else:
            print(f"❌ Failed to get IoT status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error getting IoT status: {e}")
    
    # Test 4: Simulate continuous updates
    print("\n4. Simulating continuous moisture updates...")
    for i in range(5):
        moisture_value = random.randint(15, 85)
        test_data = {
            "moisture": moisture_value,
            "device_id": "sim_esp32_01",
            "raw_adc": int((moisture_value / 100) * 4095),
            "timestamp": int(time.time() * 1000)
        }
        
        try:
            response = requests.post(
                f"{base_url}/update_moisture",
                json=test_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"   Update {i+1}: {moisture_value}% ✅")
            else:
                print(f"   Update {i+1}: Failed ❌")
                
        except Exception as e:
            print(f"   Update {i+1}: Error {e}")
        
        time.sleep(2)  # Wait 2 seconds between updates
    
    print("\n" + "=" * 50)
    print("🎉 ESP32 Integration Test Complete!")
    print("\nNext steps:")
    print("1. Update serverUrl in esp32_soil_monitor.ino")
    print("2. Upload the Arduino code to your ESP32")
    print("3. Open http://localhost:10000 in your browser")
    print("4. Watch the moisture value update in real-time!")

if __name__ == "__main__":
    test_esp32_integration()
