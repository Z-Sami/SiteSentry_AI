# 📁 ROBOT CODEBASE - FOLDER STRUCTURE & QUICK REFERENCE

## DOWNLOAD AND ORGANIZE YOUR FILES LIKE THIS:

```
robot_project/
│
├── README.md (create this with the info below)
│
├── ARDUINO/
│   ├── arduino_microros_robot.cpp  ← Upload to Arduino IDE
│   └── README_ARDUINO.md
│
├── RASPBERRY_PI/
│   ├── docker/
│   │   ├── Dockerfile              ← Build Docker image
│   │   ├── docker-compose.yml      ← Start container
│   │   └── .env                    ← Configuration
│   │
│   ├── ros2_ws/                    ← ROS 2 workspace
│   │   ├── src/
│   │   │   └── robot_bringup/
│   │   │       ├── launch/
│   │   │       │   └── robot_bringup.launch.py  ← Main launch file
│   │   │       ├── config/
│   │   │       │   ├── slam.yaml
│   │   │       │   ├── lidar.yaml
│   │   │       │   └── navigation.yaml
│   │   │       └── README.md
│   │   └── README.md
│   │
│   ├── telegram_bot/
│   │   ├── telegram_bot.py         ← Run: python3 telegram_bot.py
│   │   └── README.md
│   │
│   └── web_dashboard/
│       ├── web_dashboard.html      ← Open in browser
│       └── README.md
│
├── DOCUMENTATION/
│   ├── COMPLETE_SETUP_GUIDE.md     ← Main setup guide
│   ├── AI_CODEBASE_ANALYSIS_PROMPT.md  ← For AI analysis
│   ├── HARDWARE_CONNECTIONS.md     ← Wiring diagram
│   └── TROUBLESHOOTING.md          ← Common issues
│
└── SCRIPTS/
    ├── setup_docker.sh             ← Run on Pi: bash setup_docker.sh
    ├── install_dependencies.sh     ← Run: bash install_dependencies.sh
    └── test_all_components.sh      ← Verification script


```

---

## 🔑 KEY FILES EXPLAINED (Quick Reference)

### 1️⃣ ARDUINO FIRMWARE
**File**: `arduino_microros_robot.cpp`
```
What it does: Controls motors, reads sensors, sends data to Raspberry Pi

Runs on: Arduino Mega 2560

Talks to: L298N motor driver, HC-SR04 sensors, wheel encoders

Publishes (sends to ROS 2):
  - /sensor/distance_left      (ultrasonic readings)
  - /sensor/distance_right     (ultrasonic readings)
  - /encoder/left_ticks        (wheel encoder counts)
  - /encoder/right_ticks       (wheel encoder counts)

Subscribes (listens to ROS 2):
  - /cmd_vel                   (motor commands: forward/backward/turn)

Key Functions:
  - moveForward()              → Motors go forward
  - execute_motion()           → Apply ROS 2 cmd_vel to motors
  - read_ultrasonic()          → Get distance from sensors
  - left_encoder_isr()         → Count wheel rotations
  - publish_sensor_data()      → Send data to Pi
```

---

### 2️⃣ DOCKER SETUP (Containerization)
**File**: `docker_setup_instructions.md`
```
What it does: Packages ROS 2 environment for Raspberry Pi

Contains: Dockerfile + docker-compose.yml

Why you need it:
  - ROS 2 doesn't officially support Debian on Pi
  - Docker runs ROS 2 in isolated environment
  - Makes it portable and reproducible

Commands:
  docker-compose up -d        → Start system
  docker-compose down         → Stop system
  docker logs ros2_robot      → View output
  docker exec -it ros2_robot bash  → Access container
```

---

### 3️⃣ ROS 2 LAUNCH FILES
**File**: `ros2_launch_files.py`
```
What it does: Starts all ROS 2 nodes at once

Starts these nodes:
  ✓ micro_ros_agent           → Bridges Arduino to ROS 2
  ✓ slam_toolbox              → Maps the environment
  ✓ sllidar_node              → Reads RPLidar sensor
  ✓ camera_node               → Captures video
  ✓ yolo_detection            → Detects electrical outlets
  ✓ motor_controller          → Handles motor commands
  ✓ odometry                  → Calculates position from encoders
  ✓ rosbridge_websocket       → Allows web dashboard to connect
  ✓ telegram_bot              → Remote control via Telegram
  ✓ rviz2                     → 3D visualization

How to run:
  ros2 launch robot_bringup robot_bringup.launch.py
```

---

### 4️⃣ TELEGRAM BOT
**File**: `telegram_bot.py`
```
What it does: Remote control robot via Telegram app

Features:
  ✓ Send motor commands (forward, backward, turn)
  ✓ Get sensor readings
  ✓ Receive camera frames
  ✓ Upload CAD files to start inspection
  ✓ Emergency stop button

Environment variables needed:
  TELEGRAM_BOT_TOKEN    → From @BotFather
  TELEGRAM_CHAT_ID      → Your Telegram user ID

How to run:
  export TELEGRAM_BOT_TOKEN="your_token"
  python3 telegram_bot.py

ROS 2 interactions:
  Publishes to:
    - /cmd_vel            → Motor commands
    - /start_inspection   → Start mission

  Subscribes to:
    - /sensor/distance_*  → Distance readings
    - /encoder/*          → Position data
    - /camera/*           → Camera images
```

---

### 5️⃣ WEB DASHBOARD
**File**: `web_dashboard.html`
```
What it does: Real-time monitoring in web browser

Features:
  ✓ Shows sensor readings
  ✓ Live camera feed
  ✓ Manual joystick controls
  ✓ SLAM map visualization
  ✓ Event logging

How to use:
  1. Open in web browser: http://raspberry_pi_ip:9090
  2. Or double-click on file: web_dashboard.html
  3. Click buttons or use arrow keys

Technologies:
  - ROSBridge (WebSocket) for ROS 2 connection
  - Chart.js for gauges
  - Plain JavaScript (no build step needed)

Connects to ROS 2 topics:
  - /sensor/distance_left        (subscribe)
  - /sensor/distance_right       (subscribe)
  - /encoder/left_ticks          (subscribe)
  - /encoder/right_ticks         (subscribe)
  - /cmd_vel                     (publish - send commands)
```

---

### 6️⃣ SETUP GUIDE
**File**: `COMPLETE_SETUP_GUIDE.md`
```
What it does: Step-by-step instructions to get everything working

Covers:
  1. Arduino setup and upload
  2. Raspberry Pi Docker configuration
  3. ROS 2 launch and testing
  4. Telegram bot setup
  5. Web dashboard access
  6. Hardware testing procedures
  7. Troubleshooting common issues
  8. Performance tuning

This is your "Bible" - refer to it constantly
```

---

## 📊 HOW FILES COMMUNICATE

```
┌──────────────────────────────────┐
│        TELEGRAM USER              │
└──────────────────────────────────┘
           │ (HTTP)
           ↓
┌──────────────────────────────────┐
│ telegram_bot.py                  │
│ (listens for user commands)       │
└──────────────────────────────────┘
           │ (ROS 2 topics)
           ↓
┌──────────────────────────────────┐
│ ROS 2 (ros2_launch_files.py)     │
│ running in Docker container      │
│ ├─ /cmd_vel (motor commands)     │
│ ├─ /sensor/distance_*            │
│ └─ /encoder/* (position)         │
└──────────────────────────────────┘
    │              │
    │ (Serial)     │ (USB/Network)
    ↓              ↓
┌──────────────────────────────────┐     ┌──────────────────────────────────┐
│ Arduino                          │     │ WEB DASHBOARD                     │
│ (arduino_microros_robot.cpp)     │     │ (web_dashboard.html)             │
├─ Reads sensors                  │     ├─ Shows sensor values             │
├─ Controls motors                │     ├─ Displays camera                 │
└─ Publishes to ROS 2             │     ├─ Manual controls                 │
                                  │     └─ Connects via ROSBridge         │
                                  │            (WebSocket)
┌──────────────────────────────────┐
│ HARDWARE                          │
├─ Motors (L298N driver)           │
├─ Ultrasonic sensors (HC-SR04)    │
├─ Wheel encoders                  │
├─ RPLidar (connected to Pi)       │
└─ USB Camera (connected to Pi)    │
└──────────────────────────────────┘
```

---

## 🚀 QUICK START SEQUENCE

### Day 1: Assembly & Arduino
```
1. Wire all hardware according to COMPLETE_SETUP_GUIDE.md
2. Open arduino_microros_robot.cpp in Arduino IDE
3. Upload to Arduino Mega 2560
4. Verify Serial Monitor shows sensor readings
```

### Day 2: Raspberry Pi Setup
```
1. Copy docker files from docker_setup_instructions.md
2. Run setup_docker.sh on Raspberry Pi
3. Build Docker image (takes 20-30 minutes)
4. Start container with docker-compose up -d
```

### Day 3: ROS 2 Launch
```
1. Inside Docker container, run:
   ros2 launch robot_bringup robot_bringup.launch.py

2. Verify all topics:
   ros2 topic list

3. Test motor command:
   ros2 topic pub /cmd_vel geometry_msgs/Twist ...
```

### Day 4: Telegram & Dashboard
```
1. Get bot token from @BotFather on Telegram
2. Run telegram_bot.py
3. Open web_dashboard.html in browser
4. Test both remote control methods
```

---

## 🔌 HARDWARE PINS QUICK REFERENCE

### Arduino Mega Pinout:
```
MOTORS (L298N):
  Left Motor:   PWM=5,   IN1=8,   IN2=9
  Right Motor:  PWM=6,   IN1=10,  IN2=11

SENSORS:
  Ultrasonic Left:   TRIG=A0, ECHO=A1
  Ultrasonic Right:  TRIG=A2, ECHO=A3

ENCODERS:
  Left Encoder:  A=2 (INT0), B=3
  Right Encoder: A=20 (INT3), B=21

SERIAL:
  RX=0, TX=1 (connects to Raspberry Pi via USB)
```

---

## 📝 ROS 2 TOPICS AT A GLANCE

| Topic | Type | Direction | Published By | Subscribed By |
|-------|------|-----------|--------------|---------------|
| `/cmd_vel` | Twist | ROS 2 → Arduino | telegram_bot, web_dashboard | motor_controller |
| `/sensor/distance_left` | Range | Arduino → ROS 2 | micro_ros_agent | telegram_bot, web_dashboard |
| `/sensor/distance_right` | Range | Arduino → ROS 2 | micro_ros_agent | telegram_bot, web_dashboard |
| `/encoder/left_ticks` | Int32 | Arduino → ROS 2 | micro_ros_agent | odometry |
| `/encoder/right_ticks` | Int32 | Arduino → ROS 2 | micro_ros_agent | odometry |
| `/scan` | LaserScan | RPLidar → ROS 2 | sllidar_node | slam_toolbox |
| `/map` | OccupancyGrid | SLAM | slam_toolbox | web_dashboard, nav2 |
| `/camera/image_raw` | Image | Camera → ROS 2 | camera_node | yolo_detector, telegram_bot |
| `/detections` | Detection[] | YOLOv8 | yolo_detector | telegram_bot, web_dashboard |
| `/start_inspection` | String | Telegram | telegram_bot | nav2, mission_planner |

---

## 🛠️ COMMON MODIFICATIONS

### Change robot speed:
```cpp
// In arduino_microros_robot.cpp, line ~200
const float MAX_SPEED = 0.5;  // Change 0.5 to your desired m/s
```

### Change sensor update rate:
```cpp
// In arduino_microros_robot.cpp, line ~150
if (millis() - last_publish < 200)  // Change 200ms to desired milliseconds
```

### Add Telegram command:
```python
# In telegram_bot.py, in button_callback()
elif query.data == 'new_command':
    await query.edit_message_text("Your action here")
```

### Change web dashboard color:
```css
/* In web_dashboard.html, line ~50 */
background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
/* Change the hex colors */
```

---

## ✅ FILE CHECKLIST BEFORE STARTING

Before you begin, make sure you have:

```
□ arduino_microros_robot.cpp
□ docker_setup_instructions.md
□ ros2_launch_files.py
□ telegram_bot.py
□ web_dashboard.html
□ COMPLETE_SETUP_GUIDE.md
□ AI_CODEBASE_ANALYSIS_PROMPT.md
□ This file (QUICK_REFERENCE.md)

All in ONE folder!
```

---

## 🆘 WHERE TO LOOK WHEN THINGS BREAK

| Problem | Check File(s) | Look For |
|---------|---------------|----------|
| Arduino won't upload | arduino_microros_robot.cpp | Syntax errors, missing libraries |
| No ROS 2 topics | ros2_launch_files.py | Node launch errors, missing packages |
| Motor doesn't move | arduino_microros_robot.cpp | Motor pins, PWM values |
| Sensors show 0 | arduino_microros_robot.cpp | Sensor pins, read_ultrasonic() |
| Telegram bot unresponsive | telegram_bot.py | Bot token, async functions |
| Web dashboard blank | web_dashboard.html | ROSBridge connection, localhost URL |
| Docker won't build | docker_setup_instructions.md | Dependencies, disk space |
| SLAM not working | ros2_launch_files.py | slam.yaml parameters, lidar data |

---

## 📚 NEXT STEP

1. **Download all files** into one folder
2. **Read**: COMPLETE_SETUP_GUIDE.md (first!)
3. **Ask AI**: Use AI_CODEBASE_ANALYSIS_PROMPT.md
4. **Setup**: Follow the guide step-by-step
5. **Test**: Use COMPLETE_SETUP_GUIDE.md testing section
6. **Debug**: Use troubleshooting section when stuck

**You're ready to build! 🚀**
