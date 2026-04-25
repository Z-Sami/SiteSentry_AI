# ============================================================
# DOCKER SETUP FOR RASPBERRY PI 5 + ROS 2 HUMBLE
# ============================================================

---
# FILE 1: docker-compose.yml
---

version: '3.8'

services:
  ros2:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ros2_robot
    privileged: true
    network_mode: host
    
    # Mount volumes for code and data
    volumes:
      - ./ros2_ws:/root/ros2_ws
      - ./shared_data:/shared_data
      - /dev:/dev  # Access to serial and USB devices
      - /run/udev:/run/udev  # udev for device discovery
    
    # Device access for Arduino and RPLidar
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0  # Arduino serial port
      - /dev/ttyUSB1:/dev/ttyUSB1  # RPLidar serial port
      - /dev/bus/usb:/dev/bus/usb  # USB camera access
    
    # Environment variables
    environment:
      - ROS_DOMAIN_ID=1
      - ROS_LOCALHOST_ONLY=0
      - PYTHONUNBUFFERED=1
    
    # Keep container running
    stdin_open: true
    tty: true
    
    # Restart policy
    restart: unless-stopped
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '3.0'
          memory: 1G
        reservations:
          cpus: '2.0'
          memory: 512M

---
# FILE 2: Dockerfile
---

FROM ros:humble-ros-core

# Set locale and environment
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Update system packages
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y \
    # Essential tools
    build-essential \
    git \
    cmake \
    python3-pip \
    python3-colcon-common-extensions \
    python3-dev \
    curl \
    wget \
    nano \
    htop \
    \
    # ROS 2 tools
    ros-humble-rclpy \
    ros-humble-std-msgs \
    ros-humble-geometry-msgs \
    ros-humble-sensor-msgs \
    ros-humble-nav-msgs \
    ros-humble-tf2 \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    \
    # SLAM and Navigation
    ros-humble-slam-toolbox \
    ros-humble-nav2 \
    ros-humble-nav2-bringup \
    \
    # Lidar support
    ros-humble-perception-pcl \
    \
    # micro-ROS (Arduino bridge)
    ros-humble-micro-ros-setup \
    ros-humble-micro-ros-agent \
    \
    # Web interface (rosbridge)
    ros-humble-rosbridge-suite \
    \
    # Serial communication
    python3-pyserial \
    \
    # USB/Video support
    libusb-1.0-0-dev \
    libusb-dev \
    uvccapture \
    ffmpeg \
    v4l-utils \
    \
    # Python packages
    numpy \
    opencv-python \
    && \
    rm -rf /var/lib/apt/lists/*

# Install YOLOv8 for object detection
RUN pip3 install --no-cache-dir \
    ultralytics \
    torch \
    torchvision \
    onnx \
    onnxruntime

# Install python-telegram-bot
RUN pip3 install --no-cache-dir python-telegram-bot

# Create ROS 2 workspace
RUN mkdir -p /root/ros2_ws/src && \
    cd /root/ros2_ws && \
    source /opt/ros/humble/setup.bash && \
    colcon build --symlink-install

# Set up entrypoint
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
source /root/ros2_ws/install/setup.bash\n\
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-1}\n\
exec "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash"]

---
# FILE 3: setup_docker.sh (Run this on Pi)
---

#!/bin/bash

# Install Docker on Raspberry Pi 5
echo "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
rm get-docker.sh

# Add current user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt-get install -y docker-compose

# Create directory structure
mkdir -p ~/robot_ws/ros2_ws/src
mkdir -p ~/robot_ws/shared_data
cd ~/robot_ws

# Create udev rules for Arduino and RPLidar
cat > 99-robot-devices.rules << 'EOF'
# Arduino (CH340 USB adapter)
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", \
MODE="0666", SYMLINK+="ttyArduino"

# RPLidar A1 (USB adapter)
SUBSYSTEMS=="usb", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", \
MODE="0666", SYMLINK+="ttyLidar"
EOF

sudo cp 99-robot-devices.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Docker setup complete! Run: docker-compose up -d"

---
# FILE 4: .env file (Configuration)
---

# ROS Configuration
ROS_DOMAIN_ID=1
ROS_LOCALHOST_ONLY=0

# Serial Ports
ARDUINO_PORT=/dev/ttyUSB0
LIDAR_PORT=/dev/ttyUSB1

# Robot Configuration
WHEEL_DIAMETER=0.1
WHEEL_BASE=0.15
MAX_LINEAR_SPEED=0.5
MAX_ANGULAR_SPEED=2.0

# Camera Configuration
CAMERA_ID=0
CAMERA_WIDTH=640
CAMERA_HEIGHT=480
CAMERA_FPS=30

# SLAM Configuration
SLAM_MODE=asynchronous
MAP_UPDATE_INTERVAL=1.0

---
# FILE 5: docker-entrypoint.sh (Start script)
---

#!/bin/bash

set -e

echo "Starting ROS 2 Robot System on Raspberry Pi 5"

# Load environment
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-1}

# Wait for Arduino to be ready
echo "Waiting for Arduino connection..."
sleep 2

# Start micro-ROS agent (bridges Arduino to ROS 2)
echo "Starting micro-ROS agent..."
ros2 run micro_ros_agent micro_ros_agent serial \
    --dev ${ARDUINO_PORT:-/dev/ttyUSB0} \
    -b 115200 &
MICRO_ROS_PID=$!

sleep 2

# Start RPLidar node
echo "Starting RPLidar..."
# (Will be launched via ROS 2 launch file)

# Start rosbridge for web interface
echo "Starting rosbridge..."
# (Will be launched via ROS 2 launch file)

# Start SLAM
echo "Starting SLAM..."
# (Will be launched via ROS 2 launch file)

# Keep container running
echo "Robot system ready!"
wait $MICRO_ROS_PID
