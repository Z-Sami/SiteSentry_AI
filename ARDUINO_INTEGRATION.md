# SiteSentry Arduino Integration Guide

## Arduino Hardware Setup

The following sensors are interfaced through Arduino instead of direct GPIO/I2C:

### Pin Configuration (Arduino Mega 2560)

#### Motor Control (L298N Driver)

```
Motor Pins:
  enA = 10 (PWM) - Left motor enable
  in1 = 32 - Left motor forward
  in2 = 34 - Left motor backward
  in3 = 36 - Left motor forward
  in4 = 45 - Left motor backward
  enB = 12 (PWM) - Right motor enable
```

#### Encoders (4 Wheels)

```
Front-Right: encFR_A = 28, encFR_B = 22
Back-Right:  encBR_A = 26, encBR_B = 24
Front-Left:  encFL_A = 50, encFL_B = 46
Back-Left:   encBL_A = 51, encBL_B = 40
```

#### Ultrasonic Sensors (HC-SR04)

```
Top/Upper:    trigTop = 8,  echoTop = 9
Bottom/Lower: trigBottom = 6, echoBottom = 7
```

#### IMU (MPU6050)

```
I2C: SDA = 20, SCL = 21 (Arduino Mega I2C)
Address: 0x68
```

## Serial Communication Protocol

**Baud Rate:** 9600  
**Format:** CSV (comma-separated values)

### Arduino → Raspberry Pi (Every 500ms)

**Format:** `distTop,distBottom,wallTilt,countFR,countFL,robotAngle`

**Example:**

```
0.45,0.42,0.03,1234,1200,2.5
0.46,0.41,0.05,1245,1211,2.3
0.44,0.43,0.01,1256,1222,1.8
```

**Fields:**

- `distTop` (float): Top ultrasonic distance in meters
- `distBottom` (float): Bottom ultrasonic distance in meters
- `wallTilt` (float): Distance difference (distTop - distBottom)
- `countFR` (int): Front-right encoder ticks
- `countFL` (int): Front-left encoder ticks
- `robotAngle` (float): IMU tilt angle in degrees

### Raspberry Pi → Arduino (Optional)

**Format:** `M,leftSpeed,rightSpeed`

**Example:**

```
M,150,150    # Move forward (PWM: 0-255)
M,-150,-150  # Move backward
M,150,-150   # Turn right
M,-150,150   # Turn left
M,0,0        # Stop
```

## Python Side Setup

### Installation

```bash
cd /home/zeus/SiteSentry_AI
source venv/bin/activate
pip install pyserial
```

### Configuration (config.py)

```python
# Arduino settings
ARDUINO_SERIAL_PORT = "/dev/ttyACM0"  # USB port (check with: ls /dev/ttyACM*)
ARDUINO_BAUDRATE = 9600              # Must match Arduino code
ARDUINO_TIMEOUT = 1.0                # Serial read timeout (seconds)
```

### Find Arduino Port

```bash
# List serial ports
ls /dev/tty*

# Or use Arduino IDE
dmesg | grep ttyACM
```

### Python Usage Example

```python
from sitesentry.hardware import ArduinoHandler

# Initialize Arduino handler
arduino = ArduinoHandler(simulate=False)

# Get sensor data
sensor_data = arduino.get_sensor_data()
print(f"Distance (top): {sensor_data.dist_top} m")
print(f"Distance (bottom): {sensor_data.dist_bottom} m")
print(f"Encoder FR: {sensor_data.encoder_fr} ticks")
print(f"Encoder FL: {sensor_data.encoder_fl} ticks")
print(f"Robot angle: {sensor_data.robot_angle}°")

# Send motor command
arduino.send_command("M,150,150")  # Move forward

# Cleanup
arduino.stop()
```

## Testing

### 1. Verify Serial Connection

```bash
# Check if Arduino is connected
ls /dev/ttyACM*

# Read raw serial data (Ctrl+C to exit)
cat /dev/ttyACM0

# Or use minicom/screen
screen /dev/ttyACM0 9600
```

### 2. Test SiteSentry with Simulation

```bash
cd /home/zeus/SiteSentry_AI
source venv/bin/activate
python3 sitesentry/main.py --simulate --dry-run
```

### 3. Test with Real Arduino (dry-run only)

```bash
python3 sitesentry/main.py --dry-run
```

### 4. Full Mission Test

```bash
python3 sitesentry/main.py
```

## Troubleshooting

### Arduino Not Detected

```bash
# Check if connected
lsusb | grep Arduino

# If not showing, try restarting Arduino:
# 1. Unplug USB
# 2. Wait 2 seconds
# 3. Plug back in
```

### Serial Read Errors

- Check baud rate: `ARDUINO_BAUDRATE = 9600` (must match Arduino code)
- Check port: `ARDUINO_SERIAL_PORT = "/dev/ttyACM0"`
- Try: `sudo usermod -a -G dialout $USER` (add permissions)

### Sensors Not Reading

1. Verify Arduino code is running (check Serial Monitor in Arduino IDE)
2. Check pin configuration matches your wiring
3. Test individual sensors in Arduino IDE before Python

### Motor Not Responding

1. Verify L298N wiring and power connections
2. Test Arduino motor control code directly first
3. Check motor command format: `M,leftSpeed,rightSpeed`

## Arduino Code Reference

Your working Arduino sketch handles:

- ✅ Reading 4 encoders (A/B phase tracking)
- ✅ Reading 2 ultrasonic sensors (distance calculation)
- ✅ Reading MPU6050 tilt angle
- ✅ PWM motor control
- ✅ Serial output (500ms interval)

All Python sensor classes read from this Arduino protocol.

## Next Steps

1. Upload the working Arduino code to your Mega 2560
2. Connect to Raspberry Pi via USB
3. Update `ARDUINO_SERIAL_PORT` in config.py if needed
4. Run `python3 sitesentry/main.py --simulate --dry-run` to verify
5. Run full mission when ready
