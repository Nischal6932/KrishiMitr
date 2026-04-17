#!/usr/bin/env python3
"""Get your local IP address for ESP32 configuration"""

import socket

def get_local_ip():
    try:
        # Create a socket to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Connect to Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"  # Fallback to localhost

if __name__ == "__main__":
    ip = get_local_ip()
    print(f"🌐 Your Server IP: {ip}")
    print(f"\nUpdate this line in esp32_soil_monitor.ino:")
    print(f'const char* serverUrl = "http://{ip}:10000/update_moisture";')
