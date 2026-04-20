# SiteSentry - Autonomous Construction Inspection Robot

Full-stack autonomous robot system for inspecting construction sites using ROS1 Noetic, Raspberry Pi, AI vision analysis, and remote Telegram control.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SITESENTRY STACK                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  USER INTERFACE (Telegram)                                   │
│    ├─ /run: Upload .dxf → Parse mission → Start robot      │
│    ├─ /status: Check progress                               │
│    └─ /report: Download PDF + DXF results                  │
│                │                                             │
│                ├─ UDP:5005 ────────────────────┐            │
│                                                 ↓            │
│  ROS NAVIGATION STACK                   STATE MACHINE NODE   │
│    ├─ rplidar_ros (LIDAR)              ├─ IDLE              │
│    ├─ map_server (static map)          ├─ NAVIGATING        │
│    ├─ amcl (localization)              ├─ ALIGNING          │
│    ├─ move_base (path planning)        ├─ WAITING           │
│    └─ rosserial (Arduino comms)        └─ DONE              │
│                                                               │
│                          │                                   │
│                          ├─ UDP:5006 ────┐                  │
│                          ↓                ↓                  │
│  ROBOT BRAIN (AI Inspector)                                 │
│    ├─ Camera capture                                        │
│    ├─ Groq Vision API                                      │
│    ├─ Defect analysis                                      │
│    └─ Report generation → final_site_report.json           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## System Requirements

### Hardware

- **Robot**: Skid-steer 4-motor drive with encoders
- **Lidar**: RPLIDAR A1 (USB, 115200 baud)
- **Compute**: Raspberry Pi 4 (2GB+ RAM)
- **Motor Control**: Arduino Mega + L298N dual H-bridge
- **Sensors**:
  - USB Camera (1080p+)
  - HC-SR04 Ultrasonic (wall alignment)
  - Wheel encoders (interrupt-based)
- **Networking**: WiFi (for Telegram + Groq API)

### Software Stack

- **OS**: Ubuntu 20.04 LTS (on Raspberry Pi)
- **ROS**: ROS1 Noetic
- **Python**: 3.8+
- **Build**: catkin, rosdep

## Installation

### 1. ROS1 Noetic Setup (Raspberry Pi)

```bash
# Add ROS repository
sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list'
curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -
sudo apt update

# Install ROS Desktop
sudo apt install ros-noetic-desktop -y
sudo apt install ros-noetic-navigation ros-noetic-move-base -y
sudo apt install ros-noetic-rplidar-ros -y
sudo apt install ros-noetic-rosserial ros-noetic-rosserial-python -y

# Source ROS setup
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### 2. SiteSentry Workspace Setup

```bash
# Create workspace
cd ~
mkdir -p sitesentry_ws/src
cd sitesentry_ws

# Initialize catkin
catkin_init_workspace src/

# Copy SiteSentry package
cp -r /path/to/sitesentry/ros_ws/src/sitesentry src/

# Install Python dependencies
pip3 install \
  groq \
  ezdxf \
  opencv-python \
  python-telegram-bot \
  reportlab \
  pyserial

# Build workspace
catkin_make
source devel/setup.bash

# Create map directory (required for move_base)
mkdir -p ~/sitesentry_ws/maps
# Place your site plan map here: maps/site_plan.yaml + site_plan.pgm
```

### 3. Environment Configuration

Create `~/.sitesentry_env`:

```bash
export GROQ_API_KEY="your_groq_api_key_here"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
export TELEGRAM_ADMIN_CHAT_ID="your_chat_id_here"
```

Load before running:

```bash
source ~/.sitesentry_env
```

### 4. Hardware Configuration

#### Arduino Setup

1. Upload `arduino/motor_control.ino` to Arduino Mega using Arduino IDE
2. Set serial port: `/dev/ttyUSB0` (or use `dmesg | grep ttyUSB` to find)
3. Verify: `cat /dev/ttyUSB0` should show Arduino startup messages

#### RPLIDAR Setup

1. Connect via USB
2. Check port: `ls /dev/ttyUSB*`
3. Grant permissions: `sudo usermod -a -G dialout $USER`

#### Robot Calibration

Run calibration script:

```bash
python3 calibrate_robot.py --wheel-diameter 0.1 --track-width 0.35
```

## Quick Start

### 1. Launch ROS Navigation Stack

```bash
cd ~/sitesentry_ws
source devel/setup.bash
source ~/.sitesentry_env

# Terminal 1: Start ROS core + navigation
roslaunch sitesentry bringup.launch \
  map_file:=$(pwd)/maps/site_plan.yaml \
  lidar_port:=/dev/ttyUSB0 \
  arduino_port:=/dev/ttyUSB1
```

### 2. Start Robot Brain (AI Inspector)

```bash
# Terminal 2
cd ~/sitesentry_ws
source ~/.sitesentry_env
python3 src/sitesentry/brain/robot_brain.py
```

### 3. Start Telegram Bot

```bash
# Terminal 3
cd ~/sitesentry_ws
source ~/.sitesentry_env
python3 src/sitesentry/brain/telegram_bot.py
```

### 4. Send Mission

From Telegram chat with bot:

```
/run
[Upload site_plan.dxf with marked targets]
```

The system will:

1. Parse .dxf → generate mission.json
2. Start robot navigation
3. Capture images at each target
4. Analyze with Groq Vision API
5. Generate PDF + annotated DXF report
6. Send results to Telegram

## Testing Individual Components

### Test CAD Parser

```bash
python3 brain/cad_to_json.py /path/to/site_plan.dxf -o mission.json
```

Expected output:

```json
{
  "project": "SiteSentry_Inspection",
  "targets": [
    {"id": 1, "label": "SOCKET", "x": 2.4, "y": 1.1, "status": "PENDING"},
    ...
  ]
}
```

### Test Groq Vision API

```bash
export GROQ_API_KEY="your_key"
python3 brain/robot_brain.py --test-image /path/to/test.jpg
```

### Test Report Generation

```bash
python3 brain/report_generator.py results/final_site_report.json -o reports/
```

## File Structure

```
sitesentry/
├── arduino/
│   └── motor_control.ino              # Arduino firmware (L298N + encoders + ultrasonic)
├── ros_ws/src/sitesentry/
│   ├── state_machine_node.py          # ROS mission controller (5-state FSM)
│   ├── launch/
│   │   └── bringup.launch             # ROS launch file (rplidar, move_base, AMCL, etc)
│   └── config/
│       ├── costmap.yaml               # move_base costmap params
│       └── base_local_planner.yaml    # Trajectory planner params
├── brain/
│   ├── cad_to_json.py                 # DXF → mission.json parser
│   ├── robot_brain.py                 # UDP listener + Groq vision analysis
│   ├── telegram_bot.py                # Telegram user interface
│   └── report_generator.py            # PDF + annotated DXF reports
└── README.md                          # This file
```

## API Configuration

### Groq Vision API

1. Get API key from [console.groq.com](https://console.groq.com)
2. Check available vision models: https://console.groq.com/docs/models
3. Current model: `llava-v1.5-7b` (verify it's available)
4. Set env var: `export GROQ_API_KEY="your_key"`

### Telegram Bot

1. Create bot via [@BotFather](https://t.me/BotFather)
2. Get token: `/newbot`
3. Get your chat ID: Send `/start` to @userinfobot
4. Set env vars:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_token"
   export TELEGRAM_ADMIN_CHAT_ID="your_chat_id"
   ```

## Troubleshooting

### Serial Port Issues

```bash
# List devices
ls -la /dev/ttyUSB*

# Check permissions
sudo usermod -a -G dialout $USER
newgrp dialout

# Reset Arduino
stty -F /dev/ttyUSB0 hupcl  # Toggle DTR
```

### ROS Network Issues

```bash
# Verify ROS_MASTER_URI
echo $ROS_MASTER_URI

# Test connectivity
rosnode list
rostopic list
```

### Groq API Errors

```bash
# Verify key is set
echo $GROQ_API_KEY

# Test API directly
python3 -c "from groq import Groq; print(Groq(api_key='$GROQ_API_KEY').models.list())"
```

### UDP Communication

```bash
# Listen for UDP on port 5005
nc -u -l 0.0.0.0 5005

# Send test message
echo "START_MISSION" | nc -u 127.0.0.1 5005
```

## Performance Tuning

### Robot Speed

Edit `config/base_local_planner.yaml`:

```yaml
max_vel_x: 0.5 # Slower = more stable, faster = quicker
max_vel_theta: 1.0 # Rotation speed
```

### Groq Vision Timeout

Edit `robot_brain.py`:

```python
response = self.groq_client.chat.completions.create(
    ...
    timeout=60,  # Seconds
)
```

### Lidar Frequency

Edit `bringup.launch`:

```xml
<param name="angle_compensate" value="true"/>
```

## Known Limitations

1. **Map Dependency**: System requires pre-built occupancy grid map
2. **Outdoor Performance**: RPLIDAR is indoor-only (low ambient light needed)
3. **Groq Rate Limits**: Free tier may have API call limits
4. **Telegram Latency**: Mission control only via polling (no real-time comms)
5. **Arduino Latency**: Serial comms @ 57600 baud (can be upgraded to 115200)

## Safety Considerations

1. **Motor Limits**: Max speed capped at 0.5 m/s in config (adjust if needed)
2. **Collision Avoidance**: move_base costmap-based (no reactive stopping)
3. **Ultrasonic Alignment**: Only works within 50cm range
4. **Overheating**: Monitor Arduino and motors during long missions
5. **Wifi Dependency**: System halts if network drops (implement offline queue for production)

## Development Notes

### Adding New Inspection Target Types

Edit `cad_to_json.py`:

```python
CONFIG = {
    "target_types": ["SOCKET", "COLUMN", "PIPE", "YOUR_TYPE"],  # Add here
    ...
}
```

### Changing Vision Model

Edit `robot_brain.py`:

```python
CONFIG = {
    "groq_vision_model": "llava-v1.6-8b",  # Update model name
    ...
}
```

### Custom Inspection Prompts

Edit `robot_brain.py` `GROQ_SYSTEM_PROMPT`:

```python
GROQ_SYSTEM_PROMPT = """Your custom inspection criteria here..."""
```

## License

SiteSentry - 2026

## Support

- Issues: Report via issue tracker
- API Keys: Manage on respective provider dashboards
- Hardware: Check datasheets in `/docs/datasheets/`
