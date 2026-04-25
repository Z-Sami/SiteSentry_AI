"""
SITESENTRY - Complete ROS 2 Launch Configuration
Launches all nodes: micro-ROS, Vision, SLAM, Navigation, Telegram
"""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    
    config_dir = FindPackageShare(package='sitesentry_bringup').find('sitesentry_bringup')
    
    return LaunchDescription([
        
        # ========== MICRO-ROS AGENT (Arduino Bridge) ==========
        ExecuteProcess(
            cmd=['ros2', 'run', 'micro_ros_agent', 'micro_ros_agent', 'serial',
                 '--dev', '/dev/ttyUSB0', '-b', '115200'],
            output='screen',
            emulate_tty=True,
        ),
        
        # ========== SITESENTRY VISION NODE (YOLO + ArUco) ==========
        Node(
            package='sitesentry_vision',
            executable='vision_node',
            name='sitesentry_vision',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'yolo_model': 'yolov8n.pt',
                'confidence_threshold': 0.5,
                'aruco_dict': 'DICT_6X6_250',
                'socket_tolerance': 0.10,  # 10cm
            }],
        ),
        
        # ========== RPLidar Node ==========
        Node(
            package='sllidar_ros2',
            executable='sllidar_node',
            name='lidar',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'channel_type': 'serial',
                'serial_port': '/dev/ttyUSB1',
                'serial_baudrate': 115200,
                'frame_id': 'lidar_link',
                'angle_compensate': True,
            }],
        ),
        
        # ========== SLAM (Simultaneous Localization and Mapping) ==========
        Node(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            emulate_tty=True,
            parameters=[PathJoinSubstitution([config_dir, 'config', 'slam.yaml'])],
        ),
        
        # ========== ODOMETRY NODE (from wheel encoders) ==========
        Node(
            package='sitesentry_odometry',
            executable='odometry_node',
            name='odometry',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'wheel_diameter': 0.1,
                'wheel_base': 0.15,
                'ticks_per_revolution': 100,
            }],
        ),
        
        # ========== MOTOR CONTROLLER NODE ==========
        Node(
            package='sitesentry_controller',
            executable='motor_controller',
            name='motor_controller',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'max_linear_speed': 0.5,
                'max_angular_speed': 2.0,
                'cmd_vel_timeout': 1.0,
            }],
        ),
        
        # ========== VERTICALITY CHECKER NODE ==========
        # Analyzes IMU + ultrasonic data to determine wall tilt
        Node(
            package='sitesentry_analyzer',
            executable='verticality_checker',
            name='verticality_checker',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'wall_height': 0.3,  # Distance between d1 and d2 sensors
                'tilt_threshold': 0.5,  # degrees (SiteSentry spec)
                'publish_interval': 0.5,  # seconds
            }],
        ),
        
        # ========== NAVIGATION NODE (Nav2) ==========
        Node(
            package='nav2_bringup',
            executable='nav2_bringup',
            name='nav2',
            output='screen',
            parameters=[PathJoinSubstitution([config_dir, 'config', 'nav2_params.yaml'])],
        ),
        
        # ========== ROSBRIDGE (Web Interface) ==========
        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            name='rosbridge',
            output='screen',
            parameters=[{
                'address': '0.0.0.0',
                'port': 9090,
            }],
        ),
        
        # ========== TELEGRAM BOT NODE ==========
        Node(
            package='sitesentry_teleop',
            executable='telegram_bot',
            name='telegram_bot',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'bot_token': 'YOUR_BOT_TOKEN',  # Set via environment variable
                'chat_id': 'YOUR_CHAT_ID',      # Set via environment variable
                'report_interval': 5.0,  # seconds
            }],
        ),
        
        # ========== TF2 STATIC TRANSFORMS ==========
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=['0', '0', '0.1', '0', '0', '0', 'base_link', 'lidar_link'],
            output='screen',
        ),
        
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=['0', '0', '0.05', '0', '0', '0', 'base_link', 'camera_link'],
            output='screen',
        ),
        
        # ========== RVIZ2 (3D Visualization) ==========
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', PathJoinSubstitution([config_dir, 'rviz', 'sitesentry.rviz'])],
            output='screen',
        ),
    ])


# Alternative: Simple launch for testing individual components

def generate_simple_launch_description():
    """Minimal launch file for testing"""
    
    return LaunchDescription([
        
        # Only essential components
        ExecuteProcess(
            cmd=['ros2', 'run', 'micro_ros_agent', 'micro_ros_agent', 'serial',
                 '--dev', '/dev/ttyUSB0', '-b', '115200'],
            output='screen',
        ),
        
        Node(
            package='sitesentry_vision',
            executable='vision_node',
            name='vision',
            output='screen',
        ),
        
        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            output='screen',
        ),
    ])
