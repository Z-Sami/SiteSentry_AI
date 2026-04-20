/*
 * SiteSentry Motor Control - Arduino Mega
 * ========================================
 * - Skid-steer 4-motor control via L298N dual H-bridge
 * - ROS integration via rosserial (cmd_vel → motor commands)
 * - Encoder-based odometry publishing
 * - HC-SR04 ultrasonic wall alignment
 * 
 * Hardware:
 *   L298N Dual H-bridge: motor pins (PWM + DIR) on pins 3,4,5,6,9,10,11,12
 *   Encoders (interrupts): pins 2, 18, 19, 20 (A2-A5 on Mega)
 *   HC-SR04: TRIG=22, ECHO=23
 *   Serial3: rosserial communication
 */

#include <ros.h>
#include <geometry_msgs/Twist.h>
#include <nav_msgs/Odometry.h>
#include <std_msgs/Float32.h>
#include <tf/tf.h>

// ===== MOTOR PIN DEFINITIONS (L298N) =====
// Front-Left Motor (FL)
#define FL_PWM 3
#define FL_DIR 4

// Front-Right Motor (FR)
#define FR_PWM 5
#define FR_DIR 6

// Back-Left Motor (BL)
#define BL_PWM 9
#define BL_DIR 10

// Back-Right Motor (BR)
#define BR_PWM 11
#define BR_DIR 12

// ===== ENCODER PIN DEFINITIONS =====
#define FL_ENCODER 2      // Interrupt 4 on Mega
#define FR_ENCODER 18     // Interrupt 5 on Mega
#define BL_ENCODER 19     // Interrupt 2 on Mega
#define BR_ENCODER 20     // Interrupt 3 on Mega

// ===== ULTRASONIC PINS (HC-SR04) =====
#define ULTRASONIC_TRIG 22
#define ULTRASONIC_ECHO 23

// ===== MOTOR PARAMETERS =====
#define MAX_RPM 100           // Max motor RPM
#define WHEEL_DIAMETER 0.1    // meters (10cm wheel)
#define TRACK_WIDTH 0.35      // meters (distance between left and right wheels)
#define ENCODER_PPR 20        // Encoder pulses per revolution
#define MOTOR_SAMPLES 1000000 // Loop count for timing

// ===== CONTROL MODES =====
enum ControlMode {
  MODE_NORMAL,
  MODE_ALIGN
};

// ===== GLOBAL VARIABLES =====
ros::NodeHandle nh;
volatile long encoder_counts[4] = {0, 0, 0, 0};  // FL, FR, BL, BR
float motor_speeds[4] = {0, 0, 0, 0};            // Current speed setpoints
ControlMode current_mode = MODE_NORMAL;
unsigned long last_odom_time = 0;
float odom_x = 0.0, odom_y = 0.0, odom_theta = 0.0;
float last_linear_x = 0.0, last_angular_z = 0.0;
int align_target_distance = 50;  // Target 50cm for wall alignment

// ===== ROS MESSAGE CALLBACKS =====
void cmd_vel_callback(const geometry_msgs::Twist& msg) {
  if (current_mode != MODE_NORMAL) return;
  
  float linear_x = msg.linear.x;   // Forward/backward (m/s)
  float angular_z = msg.angular.z; // Rotation (rad/s)
  
  last_linear_x = linear_x;
  last_angular_z = angular_z;
  
  // Skid-steer kinematics: convert linear + angular to 4 wheel speeds
  // Left wheels = linear - (track_width/2) * angular
  // Right wheels = linear + (track_width/2) * angular
  
  float left_speed = linear_x - (TRACK_WIDTH / 2.0) * angular_z;
  float right_speed = linear_x + (TRACK_WIDTH / 2.0) * angular_z;
  
  motor_speeds[0] = left_speed;   // FL
  motor_speeds[1] = right_speed;  // FR
  motor_speeds[2] = left_speed;   // BL
  motor_speeds[3] = right_speed;  // BR
  
  set_motor_speeds(motor_speeds);
}

ros::Subscriber<geometry_msgs::Twist> cmd_vel_sub("cmd_vel", &cmd_vel_callback);
ros::Publisher odom_pub("odom", &nav_msgs::Odometry);
ros::Publisher distance_pub("ultrasonic_distance", &std_msgs::Float32);

// ===== ENCODER INTERRUPT HANDLERS =====
void isr_fl_encoder() {
  encoder_counts[0]++;
}

void isr_fr_encoder() {
  encoder_counts[1]++;
}

void isr_bl_encoder() {
  encoder_counts[2]++;
}

void isr_br_encoder() {
  encoder_counts[3]++;
}

// ===== MOTOR CONTROL FUNCTIONS =====
void set_motor_speed(int motor_idx, float speed_m_per_s) {
  /*
   * Input: speed in m/s (-1.0 to +1.0 normalized)
   * Converts to PWM value (0-255)
   */
  int pins_pwm[4] = {FL_PWM, FR_PWM, BL_PWM, BR_PWM};
  int pins_dir[4] = {FL_DIR, FR_DIR, BL_DIR, BR_DIR};
  
  // Clamp speed
  speed_m_per_s = constrain(speed_m_per_s, -1.0, 1.0);
  
  // Convert to PWM (0-255)
  int pwm_val = abs(speed_m_per_s * 255);
  
  // Set direction and PWM
  if (speed_m_per_s > 0) {
    digitalWrite(pins_dir[motor_idx], HIGH);  // Forward
  } else if (speed_m_per_s < 0) {
    digitalWrite(pins_dir[motor_idx], LOW);   // Backward
  }
  
  analogWrite(pins_pwm[motor_idx], pwm_val);
}

void set_motor_speeds(float speeds[4]) {
  for (int i = 0; i < 4; i++) {
    set_motor_speed(i, speeds[i]);
  }
}

void stop_motors() {
  float zero_speeds[4] = {0, 0, 0, 0};
  set_motor_speeds(zero_speeds);
}

// ===== ULTRASONIC SENSOR FUNCTIONS =====
long measure_distance() {
  /*
   * Measure distance using HC-SR04
   * Returns distance in cm
   * Using timing: distance(cm) = duration(µs) / 58
   */
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);
  
  long duration = pulseIn(ULTRASONIC_ECHO, HIGH, 30000);  // 30ms timeout
  
  if (duration == 0) return -1;  // Timeout
  
  return duration / 58;  // Convert to cm
}

long get_median_distance() {
  /*
   * Take 5 readings and return median
   */
  long distances[5];
  for (int i = 0; i < 5; i++) {
    distances[i] = measure_distance();
    delay(50);
  }
  
  // Simple bubble sort (5 elements)
  for (int i = 0; i < 5; i++) {
    for (int j = i + 1; j < 5; j++) {
      if (distances[i] > distances[j]) {
        long temp = distances[i];
        distances[i] = distances[j];
        distances[j] = temp;
      }
    }
  }
  
  return distances[2];  // Return median (3rd element)
}

// ===== ODOMETRY CALCULATION =====
void update_odometry() {
  unsigned long current_time = millis();
  float dt = (current_time - last_odom_time) / 1000.0;  // seconds
  last_odom_time = current_time;
  
  if (dt <= 0) return;
  
  // Convert encoder counts to distance (m)
  float wheel_circumference = M_PI * WHEEL_DIAMETER;
  float distance_per_pulse = wheel_circumference / ENCODER_PPR;
  
  // Calculate wheel velocities
  float fl_dist = encoder_counts[0] * distance_per_pulse;
  float fr_dist = encoder_counts[1] * distance_per_pulse;
  float bl_dist = encoder_counts[2] * distance_per_pulse;
  float br_dist = encoder_counts[3] * distance_per_pulse;
  
  // Average left and right distances (skid-steer)
  float left_dist = (fl_dist + bl_dist) / 2.0;
  float right_dist = (fr_dist + br_dist) / 2.0;
  
  // Calculate linear and angular displacement
  float linear_dist = (left_dist + right_dist) / 2.0;
  float angular_dist = (right_dist - left_dist) / TRACK_WIDTH;  // radians
  
  // Update pose
  odom_theta += angular_dist;
  odom_x += linear_dist * cos(odom_theta);
  odom_y += linear_dist * sin(odom_theta);
  
  // Reset encoder counts
  encoder_counts[0] = 0;
  encoder_counts[1] = 0;
  encoder_counts[2] = 0;
  encoder_counts[3] = 0;
}

void publish_odometry() {
  nav_msgs::Odometry odom_msg;
  odom_msg.header.stamp = nh.now();
  odom_msg.header.frame_id = "odom";
  odom_msg.child_frame_id = "base_link";
  
  // Position
  odom_msg.pose.pose.position.x = odom_x;
  odom_msg.pose.pose.position.y = odom_y;
  odom_msg.pose.pose.position.z = 0.0;
  
  // Orientation (convert theta to quaternion)
  odom_msg.pose.pose.orientation = tf::createQuaternionFromYaw(odom_theta);
  
  // Velocity
  odom_msg.twist.twist.linear.x = last_linear_x;
  odom_msg.twist.twist.linear.y = 0.0;
  odom_msg.twist.twist.angular.z = last_angular_z;
  
  odom_pub.publish(&odom_msg);
}

// ===== ALIGN MODE (WALL ALIGNMENT) =====
void enter_align_mode() {
  current_mode = MODE_ALIGN;
  nh.loginfo("ALIGN_MODE: Starting wall alignment...");
  
  // Slow rotation: 0.1 rad/s
  float slow_angular = 0.1;
  float cmd[4] = {-slow_angular * TRACK_WIDTH / 2.0,
                  slow_angular * TRACK_WIDTH / 2.0,
                  -slow_angular * TRACK_WIDTH / 2.0,
                  slow_angular * TRACK_WIDTH / 2.0};
  
  set_motor_speeds(cmd);
  
  // Sample ultrasonic in loop
  unsigned long align_start = millis();
  bool found = false;
  
  while (millis() - align_start < 10000 && !found) {  // Max 10 seconds
    long distance = get_median_distance();
    
    if (distance > 0) {
      std_msgs::Float32 dist_msg;
      dist_msg.data = distance;
      distance_pub.publish(&dist_msg);
      
      if (distance <= align_target_distance + 2 && distance >= align_target_distance - 2) {
        found = true;
        nh.loginfo("ALIGN_MODE: Target distance found!");
      }
    }
    
    delay(100);
    nh.spinOnce();
  }
  
  stop_motors();
  current_mode = MODE_NORMAL;
  nh.loginfo("ALIGN_MODE: Complete");
}

// ===== SERIAL COMMAND HANDLER =====
void handle_serial_commands() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "ALIGN_MODE") {
      enter_align_mode();
    } else if (cmd == "STOP") {
      stop_motors();
    } else if (cmd.startsWith("DISTANCE")) {
      long dist = get_median_distance();
      Serial.print("DISTANCE:");
      Serial.println(dist);
    }
  }
}

// ===== SETUP =====
void setup() {
  // Initialize serial for ROS (Serial3 on Mega)
  Serial3.begin(57600);
  nh.getHardware()->setSerial(&Serial3);
  nh.initNode();
  
  // Subscribe and publish
  nh.subscribe(cmd_vel_sub);
  nh.advertise(odom_pub);
  nh.advertise(distance_pub);
  
  // Initialize motor pins
  for (int i = 0; i < 4; i++) {
    pinMode([3, 5, 9, 11][i], OUTPUT);  // PWM pins
    pinMode([4, 6, 10, 12][i], OUTPUT); // DIR pins
  }
  
  // Initialize encoder interrupts
  pinMode(FL_ENCODER, INPUT);
  pinMode(FR_ENCODER, INPUT);
  pinMode(BL_ENCODER, INPUT);
  pinMode(BR_ENCODER, INPUT);
  
  attachInterrupt(digitalPinToInterrupt(FL_ENCODER), isr_fl_encoder, RISING);
  attachInterrupt(digitalPinToInterrupt(FR_ENCODER), isr_fr_encoder, RISING);
  attachInterrupt(digitalPinToInterrupt(BL_ENCODER), isr_bl_encoder, RISING);
  attachInterrupt(digitalPinToInterrupt(BR_ENCODER), isr_br_encoder, RISING);
  
  // Initialize ultrasonic pins
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);
  
  // Debug serial (Serial 0)
  Serial.begin(115200);
  Serial.println("SiteSentry Motor Control initialized");
  
  last_odom_time = millis();
  delay(1000);
}

// ===== MAIN LOOP =====
void loop() {
  // Handle ROS callbacks (non-blocking, 10ms timeout)
  nh.spinOnce();
  
  // Update odometry
  update_odometry();
  
  // Publish odometry periodically (10Hz)
  static unsigned long last_odom_pub = 0;
  if (millis() - last_odom_pub > 100) {
    publish_odometry();
    last_odom_pub = millis();
  }
  
  // Handle serial debug commands
  handle_serial_commands();
  
  delay(10);  // 100Hz loop rate
}
