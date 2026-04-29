# 🤖 COMPLETE ROBOT SETUP & DEPLOYMENT GUIDE

## PROJECT OVERVIEW

This is a **construction site inspection robot** system with:
- **Arduino + L298N motors** → Tank treads movement
- **2x Ultrasonic sensors** → Wall tilt measurement
- **2x Wheel encoders** → Position tracking
- **RPLidar A1** → SLAM mapping (Raspberry Pi)
- **USB Camera** → Object detection
- **YOLOv8** → Electrical fixture detection
- **Telegram Bot** → Remote control
- **Web Dashboard** → Real-time monitoring
- **ROS 2 Humble** → Core communication framework

---

## 🔧 HARDWARE REQUIREMENTS

### Arduino Side
- Arduino Mega 2560 (recommended, more pins than Uno)
- L298N Motor Driver (PWM control for 2 DC motors)
- 2x DC Motors (with gearbox for torque)
- Tank tread kit or caterpillar tread assembly
- 2x HC-SR04 Ultrasonic sensors
- 2x Wheel encoders (quadrature encoders)
- 12V LiPo battery
- Connecting cables & jumpers

### Raspberry Pi 5 Side
- Raspberry Pi 5 (8GB RAM recommended)
- 128GB microSD card (Debian Bookworm OS)
- RPLidar A1 (USB connection)
- USB Camera (640x480, ~30fps)
- Power supply (27W+ for full system)
- USB hub (for multiple USB devices)
- Ethernet cable (or WiFi)

### Power Distribution
```
12V LiPo Battery (3-4S recommended)
├─ Direct to L298N (12V input) → Motors
├─ 12V to 9V Regulator → Arduino Vin
├─ 12V to 5V Regulator → Sensors (Ultrasonics)
└─ USB Power Bank → Raspberry Pi (separate for stability)
```

---

## 📝 STEP 1: ARDUINO SETUP

### 1.1 Install Arduino IDE
```bash
# On Windows/Mac: Download from arduino.cc
# On Linux:
sudo apt-get install arduino
```

### 1.2 Install micro-ROS Libraries
1. Open Arduino IDE
2. Go to: Sketch → Include Library → Manage Libraries
3. Search and install:
   - `micro_ros_arduino` (by Micro Robotics Lab)
   - Install dependencies when prompted

### 1.3 Wire Hardware
Follow the pin definitions in `arduino_microros_robot.cpp`:
```
Motors:
  LEFT:  PWM=5,  IN1=8,  IN2=9
  RIGHT: PWM=6,  IN1=10, IN2=11

Sensors:
  Left Ultrasonic:  TRIG=A0, ECHO=A1
  Right Ultrasonic: TRIG=A2, ECHO=A3

Encoders:
  Left:  A=2 (INT0), B=3
  Right: A=20 (INT3), B=21
```

### 1.4 Upload Code
1. Copy `arduino_microros_robot.cpp` to Arduino IDE
2. Select Board: Arduino Mega 2560
3. Select Port: COM3 (or /dev/ttyUSB0)
4. Click Upload
5. Open Serial Monitor (9600 baud) to verify

**Expected Output:**
```
Arduino ROS 2 Node Initialized!
L: 1.25m R: 1.30m Enc: 234 235
```

---

## 🐋 STEP 2: RASPBERRY PI 5 DOCKER SETUP

### 2.1 Initial Pi Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
rm get-docker.sh

sudo usermod -aG docker $USER
sudo apt-get install -y docker-compose

# Create workspace
mkdir -p ~/robot_ws/ros2_ws/src
mkdir -p ~/robot_ws/shared_data
cd ~/robot_ws
```

### 2.2 Create Dockerfile and docker-compose.yml
Copy the files from `docker_setup_instructions.md`:
```bash
# Save Dockerfile in ~/robot_ws/
# Save docker-compose.yml in ~/robot_ws/
# Create .env file with configuration
```

### 2.3 Build and Start Container
```bash
cd ~/robot_ws

# Build Docker image (takes 15-30 minutes on Pi)
docker-compose build

# Start container
docker-compose up -d

# Verify
docker ps
docker logs ros2_robot
```

### 2.4 Set up udev Rules (for USB device access)
```bash
# Create udev rules file
cat > /etc/udev/rules.d/99-robot-devices.rules << 'EOF'
# Arduino (CH340 USB adapter)
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", \
MODE="0666", SYMLINK+="ttyArduino"

# RPLidar A1
SUBSYSTEMS=="usb", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", \
MODE="0666", SYMLINK+="ttyLidar"

# USB Camera
SUBSYSTEMS=="usb", ATTRS{bInterfaceClass}=="0e", \
MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## 🚀 STEP 3: ROS 2 LAUNCH

### 3.1 Inside Docker Container
```bash
# Access container
docker exec -it ros2_robot bash

# Build workspace
cd /root/ros2_ws
colcon build

# Source setup files
source install/setup.bash
```

### 3.2 Start micro-ROS Agent (bridges Arduino)
```bash
# In one terminal
ros2 run micro_ros_agent micro_ros_agent serial \
    --dev /dev/ttyUSB0 -b 115200
```

**Expected output:**
```
Creating agent node named: robot_node
Listening on port 8888 (serial port: /dev/ttyUSB0, baudrate: 115200)
```

### 3.3 Start Complete System
```bash
# In another terminal
source install/setup.bash
ros2 launch robot_bringup robot_bringup.launch.py
```

**Expected nodes:**
- `micro_ros_agent` (Arduino bridge)
- `lidar_node` (RPLidar)
- `slam_toolbox` (SLAM)
- `odometry` (Odometry from encoders)
- `camera` (Camera node)
- `yolo_detector` (Object detection)
- `motor_controller` (Motor commands)
- `rosbridge_websocket` (Web interface)
- `telegram_bot` (Telegram remote control)

### 3.4 Verify Topics
```bash
ros2 topic list

# Should show:
# /sensor/distance_left
# /sensor/distance_right
# /encoder/left_ticks
# /encoder/right_ticks
# /cmd_vel
# /scan (from Lidar)
# /map (from SLAM)
# /tf (Transforms)
# /detections (YOLOv8 output)
```

---

## 📱 STEP 4: TELEGRAM BOT SETUP

### 4.1 Create Telegram Bot
1. Open Telegram
2. Chat with **@BotFather**
3. Send `/newbot`
4. Follow prompts → Get **BOT_TOKEN**
5. Send `/mybots` → Select your bot → Get **CHAT_ID** (your user ID)

### 4.2 Deploy Bot
```bash
# Inside container
cd /root/ros2_ws

# Set environment variables
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
export TELEGRAM_CHAT_ID="YOUR_CHAT_ID_HERE"

# Run bot
python3 telegram_bot.py
```

### 4.3 Test Commands
In Telegram:
- `/start` → Show menu
- `/status` → Get sensor readings
- `/camera` → Get camera frame
- `/stop` → Emergency stop
- Upload `.dxf` or `.cad` file → Start inspection from file

---

## 🌐 STEP 5: WEB DASHBOARD

### 5.1 Start ROSBridge
```bash
# Usually started by launch file, but can run manually:
ros2 run rosbridge_server rosbridge_websocket --address 0.0.0.0 --port 9090
```

### 5.2 Access Dashboard
1. Open web browser
2. Navigate to: `http://RASPBERRY_PI_IP:9090`
3. Or open `web_dashboard.html` locally

**Features:**
- 📊 Real-time sensor data
- 📹 Live camera feed
- 🎮 Manual controls (arrow buttons)
- 🗺️ SLAM map visualization
- 📋 Event log
- 🛑 Emergency stop button

---

## 🧪 STEP 6: TESTING CHECKLIST

### Motor Test
```bash
# Manually send command
ros2 topic pub /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.3, y: 0, z: 0}, angular: {x: 0, y: 0, z: 0}}"

# Expected: Robot moves forward
```

### Sensor Test
```bash
# Monitor distance sensors
ros2 topic echo /sensor/distance_left

# Expected: Values between 0.02 - 4.0 meters
```

### Camera Test
```bash
# List camera topics
ros2 topic list | grep camera

# Show camera stream
ros2 run image_tools showimage --ros-args -r image:=/camera/image_raw
```

### SLAM Test
```bash
# Monitor SLAM status
ros2 topic echo /map

# Check transform tree
ros2 run tf2_tools view_frames
```

### YOLOv8 Test
```bash
# Monitor detections
ros2 topic echo /detections

# Expected: Array of detected objects with bounding boxes
```

---

## 🎯 OPERATION GUIDE

### Normal Operation Sequence

1. **Power Up**
   ```
   - Connect 12V battery
   - Wait 10 seconds for Pi boot
   - Check LED indicators
   ```

2. **Start System**
   ```
   docker-compose up -d
   docker exec -it ros2_robot bash
   ros2 launch robot_bringup robot_bringup.launch.py
   ```

3. **Open Dashboard**
   ```
   - Web: http://pi_ip:9090
   - Telegram: @YourRobotBot
   ```

4. **Verify Connections**
   - Green dot on dashboard = Connected
   - Sensor readings updating
   - Camera feed showing

5. **Start Inspection**
   - Via Telegram: Upload CAD file or `/start`
   - Via Dashboard: Click "Start Inspection"
   - Via Command Line:
     ```
     ros2 service call /start_inspection std_srvs/srv/Empty
     ```

### Emergency Stop
- **Dashboard**: Red button (bottom)
- **Telegram**: `/stop` command
- **Physical**: Battery disconnect

### Map Viewing
```bash
# In container:
ros2 run rviz2 rviz2 -d install/robot_bringup/share/robot_bringup/rviz/robot.rviz
```

---

## 🐛 TROUBLESHOOTING

### Arduino Not Connecting
```bash
# Check port
ls -la /dev/ttyUSB*

# Reset Arduino
# Method 1: Click reset button on board
# Method 2: Pulse DTR pin via Python
python3 -c "
import serial
port = serial.Serial('/dev/ttyUSB0', 9600)
port.setDTR(False)
port.setRTS(False)
time.sleep(0.1)
port.setDTR(True)
port.setRTS(True)
"
```

### Motors Not Moving
```bash
# Check voltages with multimeter
# L298N Input: 12V?
# L298N Outputs: 0-12V?

# Check PWM signal
# Arduino pin 5 & 6 outputting 0-255 PWM?

# Test with direct command
ros2 topic pub --once /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.5}}"
```

### Sensors Reading Zero
```bash
# Check I2C/Serial connections
# Run i2c scan if using I2C
i2cdetect -y 1

# For ultrasonic, test with simple Arduino sketch
# Connect only one sensor at a time
```

### Camera Black Screen
```bash
# Check USB connection
lsusb | grep camera_model

# Reset camera
# Method 1: Unplug and replug
# Method 2: Kill and restart node
ros2 node kill /camera
ros2 launch robot_bringup vision.launch.py
```

### Container Out of Memory
```bash
# Check memory
docker stats

# Increase swap
sudo dd if=/dev/zero of=/swapfile bs=1G count=4
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 📊 SYSTEM PERFORMANCE TARGETS

| Component | Target | Actual |
|-----------|--------|--------|
| Movement Accuracy | ±5cm/2m | --- |
| Turning Accuracy | ±5° | --- |
| Sensor Range | 2-400cm | --- |
| Camera FPS | 30 | --- |
| SLAM Update | <1s | --- |
| Web Dashboard Latency | <100ms | --- |
| Telegram Response | <2s | --- |

---

## 📚 USEFUL COMMANDS

```bash
# Container management
docker-compose up -d           # Start
docker-compose down            # Stop
docker logs -f ros2_robot      # View logs
docker exec -it ros2_robot bash # Access shell

# ROS 2 basics
ros2 topic list                # List topics
ros2 topic echo /topic_name    # Display topic
ros2 topic pub /cmd_vel ...    # Publish
ros2 service list              # List services
ros2 service call /service ... # Call service
ros2 node list                 # List nodes
ros2 param list                # List parameters

# Debugging
ros2 doctor                    # Health check
ros2 run rqt_graph rqt_graph   # Visualize node graph
ros2 run rviz2 rviz2           # 3D visualization
ros2 run tf2_tools view_frames # View transforms
```

---

## 🔐 SECURITY NOTES

- **Telegram Bot**: Never hardcode tokens - use environment variables
- **ROS Network**: Runs on localhost only by default
- **Camera Feed**: HTTPS recommended for public access
- **Password Protect**: Dashboard access (add auth middleware)
- **Firewall**: Only expose necessary ports (9090, 8080)

---

## 🎓 NEXT STEPS

1. ✅ Get hardware working and tested
2. ✅ Deploy ROS 2 system
3. ✅ Verify all sensors and actuators
4. 📍 **Create custom YOLO dataset** for your electrical fixtures
5. 📍 **Train YOLO model** on Google Colab
6. 📍 **Deploy trained model** to Raspberry Pi
7. 📍 **Create mission planner** for autonomous inspection routes
8. 📍 **Add path planning** using Nav2
9. 📍 **Integrate with CAD files** for automated routes

---

## 📞 SUPPORT RESOURCES

- ROS 2 Docs: docs.ros.org
- micro-ROS: micro.ros.org
- SLAM Toolbox: github.com/SteveMacenski/slam_toolbox
- Ultralytics YOLOv8: docs.ultralytics.com
- Python Telegram Bot: python-telegram-bot.readthedocs.io

---

**Happy Roboting! 🚀**
