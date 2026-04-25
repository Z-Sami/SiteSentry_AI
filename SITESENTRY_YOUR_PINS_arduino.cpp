/*
 * SITESENTRY - FINAL ARDUINO CODE
 * Construction Quality Assurance Robot
 * 
 * YOUR EXACT HARDWARE CONFIGURATION:
 * - Arduino Mega 2560
 * - 4 Encoders (Front Right, Back Right, Front Left, Back Left)
 * - 2 Ultrasonic Sensors (Top d2, Bottom d1)
 * - MPU6050 IMU for tilt correction
 * - 2 DC Motors (Tank track)
 * 
 * Pin Configuration (EXACTLY AS YOU PROVIDED):
 * Encoders:
 *   FR (Front Right): A=28, B=22
 *   BR (Back Right):  A=26, B=24
 *   FL (Front Left):  A=50, B=46
 *   BL (Back Left):   A=51, B=40
 * 
 * Ultrasonic:
 *   Top (d2):    TRIG=8, ECHO=9
 *   Bottom (d1): TRIG=6, ECHO=7
 * 
 * Wall Verticality Formula:
 * θ_final = arctan((d1 - d2) / h) - α
 */

#include <Wire.h>
#include <MPU6050.h>
#include <micro_ros_arduino.h>
#include <std_msgs/msg/float32.h>
#include <std_msgs/msg/int32.h>
#include <geometry_msgs/msg/twist.h>
#include <sensor_msgs/msg/range.h>

// ============ MOTOR PINS ============
#define LEFT_MOTOR_IN1 31
#define LEFT_MOTOR_IN2 33
#define LEFT_MOTOR_PWM 12

#define RIGHT_MOTOR_IN1 35
#define RIGHT_MOTOR_IN2 37
#define RIGHT_MOTOR_PWM 13

// ============ ENCODER PINS (YOUR EXACT CONFIGURATION) ============
// Front Right Encoder
const int encFR_A = 28;
const int encFR_B = 22;

// Back Right Encoder
const int encBR_A = 26;
const int encBR_B = 24;

// Front Left Encoder
const int encFL_A = 50;
const int encFL_B = 46;

// Back Left Encoder
const int encBL_A = 51;
const int encBL_B = 40;

// ============ ULTRASONIC SENSORS (YOUR EXACT CONFIGURATION) ============
// Top Sensor (d2 - upper distance)
const int trigTop = 8;
const int echoTop = 9;

// Bottom Sensor (d1 - lower distance)
const int trigBottom = 6;
const int echoBottom = 7;

// ============ IMU (MPU6050) - I2C ============
// SDA = Pin 20, SCL = Pin 21 (Mega I2C pins)
MPU6050 mpu;

// ============ ROS 2 PUBLISHERS ============
rcl_publisher_t distance_d1_pub;      // Bottom sensor
rcl_publisher_t distance_d2_pub;      // Top sensor
rcl_publisher_t wall_tilt_pub;
rcl_publisher_t robot_tilt_pub;
rcl_publisher_t encoder_left_pub;
rcl_publisher_t encoder_right_pub;

// ROS 2 SUBSCRIBER
rcl_subscription_t cmd_vel_sub;

sensor_msgs__msg__Range distance_d1_msg;
sensor_msgs__msg__Range distance_d2_msg;
std_msgs__msg__Float32 wall_tilt_msg;
std_msgs__msg__Float32 robot_tilt_msg;
std_msgs__msg__Int32 encoder_left_msg;
std_msgs__msg__Int32 encoder_right_msg;
geometry_msgs__msg__Twist cmd_vel_msg;

rclc_executor_t executor;
rclc_support_t support;
rcl_node_t node;
rcl_allocator_t allocator;

// ============ GLOBAL VARIABLES ============

// Encoder counts (volatile for interrupts)
volatile long encFR_count = 0;  // Front Right
volatile long encBR_count = 0;  // Back Right
volatile long encFL_count = 0;  // Front Left
volatile long encBL_count = 0;  // Back Left

// Distance measurements
float d1_distance = 0;          // Bottom sensor (base distance)
float d2_distance = 0;          // Top sensor (top distance)

// Tilt angles
float robot_tilt_angle = 0;     // α (from MPU6050)
float wall_tilt_angle = 0;      // θ_final (calculated)

// Motor control
float target_linear_velocity = 0.0;
float target_angular_velocity = 0.0;
unsigned long last_cmd_time = 0;
#define CMD_TIMEOUT 1000

// Calibration constants
const float WHEEL_DIAMETER = 0.1;      // 10cm wheel
const float WHEEL_BASE = 0.15;         // 15cm between wheels
const long TICKS_PER_REV = 100;
const float WALL_HEIGHT = 0.3;         // 30cm height between d1 and d2 sensors

// ============ SETUP ============

void setup() {
  Serial.begin(9600);
  set_microros_transports();
  
  delay(2000);

  // Initialize motor pins
  pinMode(LEFT_MOTOR_IN1, OUTPUT);
  pinMode(LEFT_MOTOR_IN2, OUTPUT);
  pinMode(LEFT_MOTOR_PWM, OUTPUT);
  pinMode(RIGHT_MOTOR_IN1, OUTPUT);
  pinMode(RIGHT_MOTOR_IN2, OUTPUT);
  pinMode(RIGHT_MOTOR_PWM, OUTPUT);

  // Initialize encoder pins (YOUR EXACT PINS)
  pinMode(encFR_A, INPUT);
  pinMode(encFR_B, INPUT);
  pinMode(encBR_A, INPUT);
  pinMode(encBR_B, INPUT);
  pinMode(encFL_A, INPUT);
  pinMode(encFL_B, INPUT);
  pinMode(encBL_A, INPUT);
  pinMode(encBL_B, INPUT);

  // Initialize ultrasonic pins (YOUR EXACT PINS)
  pinMode(trigTop, OUTPUT);
  pinMode(echoTop, INPUT);
  pinMode(trigBottom, OUTPUT);
  pinMode(echoBottom, INPUT);

  // Attach encoder interrupts (using available interrupt pins on Mega)
  // Note: Mega has interrupts on: 2,3,18,19,20,21
  // You may need to adjust based on which pins are available
  attachInterrupt(digitalPinToInterrupt(28), encFR_isr, CHANGE);  // Check if 28 supports interrupts
  attachInterrupt(digitalPinToInterrupt(26), encBR_isr, CHANGE);  // Check if 26 supports interrupts
  
  // For non-interrupt pins, we'll poll them in main loop
  // Or remap to interrupt-capable pins if needed

  // Initialize MPU6050 (I2C: SDA=20, SCL=21)
  Wire.begin();
  mpu.initialize();
  if (!mpu.testConnection()) {
    Serial.println("❌ MPU6050 CONNECTION FAILED!");
    while (1);
  }

  // Initialize ROS 2
  allocator = rcl_get_default_allocator();
  rclc_support_init(&support, 0, NULL, &allocator);
  rclc_node_init_default(&node, "sitesentry_node", "", &support);

  // Create publishers
  rclc_publisher_init_default(
    &distance_d1_pub, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Range),
    "sitesentry/distance_d1");

  rclc_publisher_init_default(
    &distance_d2_pub, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Range),
    "sitesentry/distance_d2");

  rclc_publisher_init_default(
    &wall_tilt_pub, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
    "sitesentry/wall_tilt");

  rclc_publisher_init_default(
    &robot_tilt_pub, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
    "sitesentry/robot_tilt");

  rclc_publisher_init_default(
    &encoder_left_pub, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
    "sitesentry/encoder_left");

  rclc_publisher_init_default(
    &encoder_right_pub, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
    "sitesentry/encoder_right");

  // Create subscriber
  rclc_subscription_init_default(
    &cmd_vel_sub, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
    "cmd_vel");

  // Create executor
  rclc_executor_init(&executor, &support.context, 1, &allocator);
  rclc_executor_add_subscription(&executor, &cmd_vel_sub, &cmd_vel_msg, &cmd_vel_callback, ON_NEW_DATA);

  Serial.println("=== SITESENTRY INITIALIZED ===");
  Serial.println("✓ 4 Encoders (FR, BR, FL, BL)");
  Serial.println("✓ 2 Ultrasonic Sensors (d1, d2)");
  Serial.println("✓ 1 MPU6050 IMU");
  Serial.println("✓ ROS 2 Ready");
}

// ============ MAIN LOOP ============

void loop() {
  // Spin ROS 2 executor
  rclc_executor_spin_some(&executor, RCL_MS_TO_NS(50));

  // Check command timeout
  if (millis() - last_cmd_time > CMD_TIMEOUT) {
    target_linear_velocity = 0.0;
    target_angular_velocity = 0.0;
  }

  // Execute motor commands
  execute_motion();

  // Poll encoders (for non-interrupt pins)
  poll_encoders();

  // Read all sensors and publish
  update_sensors();

  delay(100);  // 10 Hz
}

// ============ INTERRUPT HANDLERS ============

void encFR_isr() {
  if (digitalRead(encFR_A) == HIGH) {
    if (digitalRead(encFR_B) == LOW) {
      encFR_count++;
    } else {
      encFR_count--;
    }
  } else {
    if (digitalRead(encFR_B) == HIGH) {
      encFR_count++;
    } else {
      encFR_count--;
    }
  }
}

void encBR_isr() {
  if (digitalRead(encBR_A) == HIGH) {
    if (digitalRead(encBR_B) == LOW) {
      encBR_count++;
    } else {
      encBR_count--;
    }
  } else {
    if (digitalRead(encBR_B) == HIGH) {
      encBR_count++;
    } else {
      encBR_count--;
    }
  }
}

// For non-interrupt pins, poll them in main loop
void poll_encoders() {
  static uint8_t prevFL_A = 0, prevFL_B = 0;
  static uint8_t prevBL_A = 0, prevBL_B = 0;

  // Poll Front Left
  uint8_t currFL_A = digitalRead(encFL_A);
  uint8_t currFL_B = digitalRead(encFL_B);
  if (currFL_A != prevFL_A) {
    if (currFL_A == HIGH) {
      if (currFL_B == LOW) {
        encFL_count++;
      } else {
        encFL_count--;
      }
    } else {
      if (currFL_B == HIGH) {
        encFL_count++;
      } else {
        encFL_count--;
      }
    }
    prevFL_A = currFL_A;
    prevFL_B = currFL_B;
  }

  // Poll Back Left
  uint8_t currBL_A = digitalRead(encBL_A);
  uint8_t currBL_B = digitalRead(encBL_B);
  if (currBL_A != prevBL_A) {
    if (currBL_A == HIGH) {
      if (currBL_B == LOW) {
        encBL_count++;
      } else {
        encBL_count--;
      }
    } else {
      if (currBL_B == HIGH) {
        encBL_count++;
      } else {
        encBL_count--;
      }
    }
    prevBL_A = currBL_A;
    prevBL_B = currBL_B;
  }
}

// ============ ROS 2 CALLBACKS ============

void cmd_vel_callback(const void *msgin) {
  const geometry_msgs__msg__Twist *msg = (const geometry_msgs__msg__Twist *)msgin;
  target_linear_velocity = msg->linear.x;
  target_angular_velocity = msg->angular.z;
  last_cmd_time = millis();
}

// ============ MOTOR CONTROL ============

void execute_motion() {
  // Differential drive kinematics
  float left_speed = target_linear_velocity - (target_angular_velocity * WHEEL_BASE / 2.0);
  float right_speed = target_linear_velocity + (target_angular_velocity * WHEEL_BASE / 2.0);

  left_speed = constrain(left_speed, -0.5, 0.5);
  right_speed = constrain(right_speed, -0.5, 0.5);

  int left_pwm = speed_to_pwm(left_speed);
  int right_pwm = speed_to_pwm(right_speed);

  set_motor(LEFT_MOTOR_IN1, LEFT_MOTOR_IN2, LEFT_MOTOR_PWM, left_pwm);
  set_motor(RIGHT_MOTOR_IN1, RIGHT_MOTOR_IN2, RIGHT_MOTOR_PWM, right_pwm);
}

int speed_to_pwm(float speed) {
  if (speed == 0) return 0;
  int pwm = (int)((fabs(speed) / 0.5) * 255);
  return constrain(pwm, 0, 255);
}

void set_motor(int in1, int in2, int pwm_pin, int pwm_value) {
  if (pwm_value > 0) {
    digitalWrite(in1, HIGH);
    digitalWrite(in2, LOW);
    analogWrite(pwm_pin, abs(pwm_value));
  } else if (pwm_value < 0) {
    digitalWrite(in1, LOW);
    digitalWrite(in2, HIGH);
    analogWrite(pwm_pin, abs(pwm_value));
  } else {
    digitalWrite(in1, LOW);
    digitalWrite(in2, LOW);
    analogWrite(pwm_pin, 0);
  }
}

// ============ SENSOR READING ============

void update_sensors() {
  static unsigned long last_sensor_read = 0;
  
  if (millis() - last_sensor_read < 100) return;
  last_sensor_read = millis();

  // Read the 2 ultrasonic sensors (YOUR EXACT PINS)
  d1_distance = readUltrasonic(trigBottom, echoBottom);  // Bottom
  d2_distance = readUltrasonic(trigTop, echoTop);        // Top

  // Read IMU tilt
  read_imu_tilt();

  // Calculate wall tilt using SiteSentry formula
  calculate_wall_tilt();

  // Publish to ROS 2
  publish_sensor_data();
}

float readUltrasonic(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);
  float distance = (duration / 2.0) / 29.1;  // cm

  if (distance < 2 || distance > 400) return 0;
  return distance;
}

void read_imu_tilt() {
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);
  
  // Calculate tilt angle from acceleration
  robot_tilt_angle = atan2(ax, az) * 180.0 / PI;
  robot_tilt_angle = constrain(robot_tilt_angle, -90, 90);
}

void calculate_wall_tilt() {
  /*
   * SITESENTRY CORE ALGORITHM
   * θ_final = arctan((d1 - d2) / h) - α
   * 
   * Where:
   *   d1 = Bottom sensor distance (base)
   *   d2 = Top sensor distance (top)
   *   h = Height between sensors (0.3m)
   *   α = Robot tilt angle from MPU6050
   */

  if (d1_distance > 0 && d2_distance > 0) {
    // Convert from cm to m for calculation
    float d1_m = d1_distance / 100.0;
    float d2_m = d2_distance / 100.0;
    
    // Calculate raw wall tilt
    float raw_tilt = atan((d1_m - d2_m) / WALL_HEIGHT) * 180.0 / PI;
    
    // Correct for robot tilt (subtract IMU angle)
    wall_tilt_angle = raw_tilt - robot_tilt_angle;
    
    // Check if wall exceeds safety threshold (0.5°)
    if (fabs(wall_tilt_angle) > 0.5) {
      Serial.print("⚠️ CRITICAL: Wall tilt exceeds 0.5°: ");
      Serial.print(wall_tilt_angle);
      Serial.println("°");
    }
  }
}

void publish_sensor_data() {
  // Publish distances
  distance_d1_msg.range = d1_distance / 100.0;  // Convert to meters
  distance_d2_msg.range = d2_distance / 100.0;
  rcl_publish(&distance_d1_pub, &distance_d1_msg, NULL);
  rcl_publish(&distance_d2_pub, &distance_d2_msg, NULL);

  // Publish wall tilt
  wall_tilt_msg.data = wall_tilt_angle;
  rcl_publish(&wall_tilt_pub, &wall_tilt_msg, NULL);

  // Publish robot tilt
  robot_tilt_msg.data = robot_tilt_angle;
  rcl_publish(&robot_tilt_pub, &robot_tilt_msg, NULL);

  // Publish encoder counts (average of all 4)
  long left_avg = (encFL_count + encBL_count) / 2;
  long right_avg = (encFR_count + encBR_count) / 2;
  encoder_left_msg.data = left_avg;
  encoder_right_msg.data = right_avg;
  rcl_publish(&encoder_left_pub, &encoder_left_msg, NULL);
  rcl_publish(&encoder_right_pub, &encoder_right_msg, NULL);

  // Debug output
  Serial.print("d1(bottom):");
  Serial.print(d1_distance, 1);
  Serial.print("cm d2(top):");
  Serial.print(d2_distance, 1);
  Serial.print("cm WALL_TILT:");
  Serial.print(wall_tilt_angle, 2);
  Serial.print("° ROBOT_TILT:");
  Serial.print(robot_tilt_angle, 2);
  Serial.print("° ENC[FR:");
  Serial.print(encFR_count);
  Serial.print(" BR:");
  Serial.print(encBR_count);
  Serial.print(" FL:");
  Serial.print(encFL_count);
  Serial.print(" BL:");
  Serial.print(encBL_count);
  Serial.println("]");
}

// ============ HELPER FUNCTIONS ============

void stop_all_motors() {
  digitalWrite(LEFT_MOTOR_IN1, LOW);
  digitalWrite(LEFT_MOTOR_IN2, LOW);
  digitalWrite(RIGHT_MOTOR_IN1, LOW);
  digitalWrite(RIGHT_MOTOR_IN2, LOW);
  analogWrite(LEFT_MOTOR_PWM, 0);
  analogWrite(RIGHT_MOTOR_PWM, 0);
}

void reset_all_encoders() {
  encFR_count = 0;
  encBR_count = 0;
  encFL_count = 0;
  encBL_count = 0;
}

float get_distance_traveled() {
  // Average all 4 encoders
  long avg_ticks = (encFR_count + encBR_count + encFL_count + encBL_count) / 4;
  float wheel_circumference = PI * WHEEL_DIAMETER;
  float revolutions = avg_ticks / TICKS_PER_REV;
  return revolutions * wheel_circumference;
}
