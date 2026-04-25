#!/usr/bin/env python3
"""
TELEGRAM BOT + WEB DASHBOARD FOR CONSTRUCTION ROBOT
Controls robot movement, receives sensor data, and shares live camera feed
"""

import asyncio
import logging
from typing import Optional
import json
from datetime import datetime
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.error import TelegramError
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image, Range
from std_msgs.msg import String
import cv2
from cv_bridge import CvBridge

# ============================================================
# PART 1: ROS 2 INTEGRATION NODE
# ============================================================

class TelegramRobotNode(Node):
    def __init__(self, telegram_app):
        super().__init__('telegram_robot_node')
        
        self.telegram_app = telegram_app
        self.bridge = CvBridge()
        
        # Create publishers
        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.cad_file_pub = self.create_publisher(String, 'start_inspection', 10)
        
        # Create subscribers
        self.left_distance_sub = self.create_subscription(
            Range, 'sensor/distance_left', self.left_distance_callback, 10)
        self.right_distance_sub = self.create_subscription(
            Range, 'sensor/distance_right', self.right_distance_callback, 10)
        self.left_encoder_sub = self.create_subscription(
            String, 'encoder/left_ticks', self.left_encoder_callback, 10)
        self.right_encoder_sub = self.create_subscription(
            String, 'encoder/right_ticks', self.right_encoder_callback, 10)
        self.camera_sub = self.create_subscription(
            Image, '/camera/image_raw', self.camera_callback, 5)
        
        # Store latest sensor data
        self.sensor_data = {
            'left_distance': 0.0,
            'right_distance': 0.0,
            'left_encoder': 0,
            'right_encoder': 0,
            'last_image': None,
        }
        
        # Timer for sensor publishing
        self.timer = self.create_timer(0.1, self.publish_sensor_updates)
        
        self.get_logger().info('Telegram Robot Node initialized')
    
    def left_distance_callback(self, msg):
        self.sensor_data['left_distance'] = msg.range
    
    def right_distance_callback(self, msg):
        self.sensor_data['right_distance'] = msg.range
    
    def left_encoder_callback(self, msg):
        self.sensor_data['left_encoder'] = int(msg.data)
    
    def right_encoder_callback(self, msg):
        self.sensor_data['right_encoder'] = int(msg.data)
    
    def camera_callback(self, msg):
        """Receive camera frame and store latest"""
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            self.sensor_data['last_image'] = cv_image
        except Exception as e:
            self.get_logger().error(f"Failed to convert image: {e}")
    
    def publish_cmd_vel(self, linear_x, angular_z):
        """Send motor command to robot"""
        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z
        self.cmd_vel_pub.publish(msg)
    
    def publish_sensor_updates(self):
        """Periodically publish sensor data"""
        # This is called every 100ms but Telegram updates come separately
        pass
    
    def get_sensor_status(self):
        """Return formatted sensor data"""
        return {
            'timestamp': datetime.now().isoformat(),
            'left_distance': float(self.sensor_data['left_distance']),
            'right_distance': float(self.sensor_data['right_distance']),
            'left_ticks': self.sensor_data['left_encoder'],
            'right_ticks': self.sensor_data['right_encoder'],
        }


# ============================================================
# PART 2: TELEGRAM BOT
# ============================================================

class TelegramRobotBot:
    def __init__(self, token: str, ros_node: TelegramRobotNode):
        self.token = token
        self.ros_node = ros_node
        self.application = None
        self.user_chat_ids = set()
        
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user = update.effective_user
        self.user_chat_ids.add(update.effective_chat.id)
        
        keyboard = [
            [InlineKeyboardButton("🎮 Manual Control", callback_data='manual')],
            [InlineKeyboardButton("📍 Auto Patrol", callback_data='patrol')],
            [InlineKeyboardButton("📹 Camera Feed", callback_data='camera')],
            [InlineKeyboardButton("📊 Sensor Status", callback_data='status')],
            [InlineKeyboardButton("🗺️ Start Inspection", callback_data='inspection')],
            [InlineKeyboardButton("🛑 Stop Robot", callback_data='stop')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🤖 Welcome {user.first_name}! I control the inspection robot.\n\n"
            "Choose an option:",
            reply_markup=reply_markup
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button presses"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'manual':
            await self.show_manual_control(query)
        elif query.data == 'patrol':
            await self.start_patrol(query)
        elif query.data == 'camera':
            await self.send_camera_feed(query)
        elif query.data == 'status':
            await self.send_sensor_status(query)
        elif query.data == 'inspection':
            await query.edit_message_text("📄 Send me a CAD file (.dxf or .cad) to start inspection")
        elif query.data == 'stop':
            await self.stop_robot(query)
        elif query.data.startswith('move_'):
            await self.handle_movement(query, query.data.split('_')[1])
    
    async def show_manual_control(self, query):
        """Show manual control keyboard"""
        keyboard = [
            [InlineKeyboardButton("⬆️", callback_data='move_forward')],
            [
                InlineKeyboardButton("⬅️", callback_data='move_left'),
                InlineKeyboardButton("⏹️", callback_data='move_stop'),
                InlineKeyboardButton("➡️", callback_data='move_right'),
            ],
            [InlineKeyboardButton("⬇️", callback_data='move_backward')],
            [InlineKeyboardButton("🔙 Back", callback_data='back')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎮 Manual Control:\nUse arrow buttons", reply_markup=reply_markup)
    
    async def handle_movement(self, query, direction: str):
        """Handle movement commands"""
        movements = {
            'forward': (0.3, 0.0),      # linear, angular
            'backward': (-0.3, 0.0),
            'left': (0.0, 1.0),
            'right': (0.0, -1.0),
            'stop': (0.0, 0.0),
        }
        
        if direction in movements:
            linear, angular = movements[direction]
            self.ros_node.publish_cmd_vel(linear, angular)
            
            direction_names = {
                'forward': '⬆️ Moving Forward',
                'backward': '⬇️ Moving Backward',
                'left': '⬅️ Turning Left',
                'right': '➡️ Turning Right',
                'stop': '⏹️ Stopped',
            }
            
            await query.answer(direction_names[direction])
    
    async def send_camera_feed(self, query):
        """Send current camera frame"""
        try:
            image = self.ros_node.sensor_data['last_image']
            if image is None:
                await query.edit_message_text("📹 Camera not ready yet")
                return
            
            # Save image temporarily
            image_path = '/tmp/robot_camera.jpg'
            cv2.imwrite(image_path, image)
            
            with open(image_path, 'rb') as f:
                await query.edit_message_text("📹 Sending camera feed...")
                await query.message.reply_photo(f)
            
            os.remove(image_path)
        except Exception as e:
            self.logger.error(f"Failed to send camera: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
    
    async def send_sensor_status(self, query):
        """Send current sensor readings"""
        status = self.ros_node.get_sensor_status()
        
        message = (
            "📊 **Robot Status Report**\n\n"
            f"⏰ Timestamp: {status['timestamp']}\n\n"
            f"📏 **Distance Sensors (cm)**\n"
            f"  Left: {status['left_distance']*100:.1f} cm\n"
            f"  Right: {status['right_distance']*100:.1f} cm\n\n"
            f"🔄 **Encoder Ticks**\n"
            f"  Left: {status['left_ticks']}\n"
            f"  Right: {status['right_ticks']}"
        )
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def start_patrol(self, query):
        """Start autonomous patrol"""
        await query.edit_message_text("🤖 Starting autonomous patrol...\n\nRobot will now navigate autonomously!")
        
        # Publish start command
        msg = String()
        msg.data = "START_PATROL"
        self.ros_node.cad_file_pub.publish(msg)
    
    async def stop_robot(self, query):
        """Stop robot immediately"""
        self.ros_node.publish_cmd_vel(0.0, 0.0)
        await query.edit_message_text("🛑 Robot stopped!")
    
    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle CAD file upload for inspection"""
        file = await update.message.document.get_file()
        file_path = f"/tmp/{update.message.document.file_name}"
        
        await file.download_to_drive(file_path)
        
        # Publish file path to ROS 2
        msg = String()
        msg.data = file_path
        self.ros_node.cad_file_pub.publish(msg)
        
        await update.message.reply_text(
            f"✅ CAD file received: {update.message.document.file_name}\n"
            "🚀 Starting inspection mission..."
        )
    
    async def initialize_app(self):
        """Initialize Telegram application"""
        self.application = Application.builder().token(self.token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_file_upload)
        )
        self.application.add_handler(
            MessageHandler(filters.ALL, self.button_callback)
        )
        
        # Add callback query handler
        from telegram.ext import CallbackQueryHandler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        return self.application
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = (
            "🤖 **Robot Commands:**\n\n"
            "/start - Show main menu\n"
            "/status - Get sensor readings\n"
            "/camera - Get camera frame\n"
            "/stop - Emergency stop\n"
            "/help - Show this message\n\n"
            "📄 Upload CAD (.dxf/.cad) files to start inspection"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')


# ============================================================
# PART 3: MAIN ENTRY POINT
# ============================================================

async def main():
    """Main function - start bot and ROS 2 node"""
    
    # Initialize ROS 2
    rclpy.init()
    
    # Create Telegram app (placeholder)
    telegram_app = None
    
    # Create ROS 2 node
    ros_node = TelegramRobotNode(telegram_app)
    
    # Create Telegram bot
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '<YOUR_BOT_TOKEN>')
    bot = TelegramRobotBot(bot_token, ros_node)
    application = await bot.initialize_app()
    
    # Start bot
    print("🤖 Telegram Robot Bot started!")
    print("📡 Waiting for commands...")
    
    try:
        await application.run_polling()
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down...")
        rclpy.shutdown()


if __name__ == '__main__':
    # For async execution with ROS 2
    import asyncio
    
    async def ros_spin_async(node):
        """Spin ROS 2 node asynchronously"""
        executor = rclpy.executors.SingleThreadedExecutor()
        executor.add_node(node)
        
        while rclpy.ok():
            executor.spin_once(timeout_sec=0.1)
            await asyncio.sleep(0.01)
    
    # Run both ROS 2 and Telegram bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
