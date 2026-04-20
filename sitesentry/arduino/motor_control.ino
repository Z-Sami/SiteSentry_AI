#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

Adafruit_MPU6050 mpu;

// دبابيس المواتير (L298N)
const int enA = 10; const int in1 = 32; const int in2 = 34; 
const int in3 = 36; const int in4 = 45; const int enB = 12; 

// دبابيس الإنكودرز
const int encFR_A = 28; const int encFR_B = 22; 
const int encBR_A = 26; const int encBR_B = 24; 
const int encFL_A = 50; const int encFL_B = 46; 
const int encBL_A = 51; const int encBL_B = 40; 

// دبابيس الألتراسونيك
const int trigTop = 8;  const int echoTop = 9;   
const int trigBottom = 6; const int echoBottom = 7;

long countFR = 0, countBR = 0, countFL = 0, countBL = 0;
int lastFR_A, lastBR_A, lastFL_A, lastBL_A;
unsigned long lastPrintTime = 0;

void setup() {
  Serial.begin(9600); 
  
  pinMode(enA, OUTPUT); pinMode(in1, OUTPUT); pinMode(in2, OUTPUT);
  pinMode(enB, OUTPUT); pinMode(in3, OUTPUT); pinMode(in4, OUTPUT);

  pinMode(encFR_A, INPUT_PULLUP); pinMode(encFR_B, INPUT_PULLUP);
  pinMode(encBR_A, INPUT_PULLUP); pinMode(encBR_B, INPUT_PULLUP);
  pinMode(encFL_A, INPUT_PULLUP); pinMode(encFL_B, INPUT_PULLUP);
  pinMode(encBL_A, INPUT_PULLUP); pinMode(encBL_B, INPUT_PULLUP);

  pinMode(trigTop, OUTPUT); pinMode(echoTop, INPUT);
  pinMode(trigBottom, OUTPUT); pinMode(echoBottom, INPUT);

  lastFR_A = digitalRead(encFR_A); lastBR_A = digitalRead(encBR_A);
  lastFL_A = digitalRead(encFL_A); lastBL_A = digitalRead(encBL_A);

  if (!mpu.begin()) {
    Serial.println("Error: MPU6050 not found!");
  } else {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  }
  
  Serial.println("Robot starting in 5 seconds...");
  delay(5000); // 5 ثواني عشان تلحق تحطه عالأرض براحتك
  
  moveForward(); // الأمر المباشر للحركة!
}

void loop() {
  // قراءة الإنكودرز
  int currFR_A = digitalRead(encFR_A); int currBR_A = digitalRead(encBR_A);
  int currFL_A = digitalRead(encFL_A); int currBL_A = digitalRead(encBL_A);

  if (currFR_A != lastFR_A) { if (digitalRead(encFR_B) != currFR_A) countFR++; else countFR--; lastFR_A = currFR_A; }
  if (currBR_A != lastBR_A) { if (digitalRead(encBR_B) != currBR_A) countBR++; else countBR--; lastBR_A = currBR_A; }
  if (currFL_A != lastFL_A) { if (digitalRead(encFL_B) != currFL_A) countFL++; else countFL--; lastFL_A = currFL_A; }
  if (currBL_A != lastBL_A) { if (digitalRead(encBL_B) != currBL_A) countBL++; else countBL--; lastBL_A = currBL_A; }

  // إرسال التقرير كل نص ثانية
  if (millis() - lastPrintTime > 500) {
    float distTop = getDistance(trigTop, echoTop);
    delay(20); 
    float distBottom = getDistance(trigBottom, echoBottom);
    float wallTilt = distTop - distBottom;

    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    float robotAngle = atan2(a.acceleration.x, sqrt(a.acceleration.y * a.acceleration.y + a.acceleration.z * a.acceleration.z)) * 180.0 / PI;

    Serial.print(distTop); Serial.print(",");
    Serial.print(distBottom); Serial.print(",");
    Serial.print(wallTilt); Serial.print(",");
    Serial.print(countFR); Serial.print(",");
    Serial.print(countFL); Serial.print(",");
    Serial.println(robotAngle);
    
    lastPrintTime = millis();
  }
}

void moveForward() {
  digitalWrite(in1, LOW); digitalWrite(in2, HIGH); analogWrite(enA, 150); 
  digitalWrite(in3, HIGH); digitalWrite(in4, LOW); analogWrite(enB, 150); 
}

void moveBackward() {
  digitalWrite(in1, HIGH); digitalWrite(in2, LOW); analogWrite(enA, 150); 
  digitalWrite(in3, LOW); digitalWrite(in4, HIGH); analogWrite(enB, 150); 
}

void stopMotors() {
  digitalWrite(in1, LOW); digitalWrite(in2, LOW); analogWrite(enA, 0); 
  digitalWrite(in3, LOW); digitalWrite(in4, LOW); analogWrite(enB, 0); 
}

float getDistance(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW); delayMicroseconds(2);
  digitalWrite(trigPin, HIGH); delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 12000); 
  if (duration == 0) return 999.0; 
  return (duration * 0.0343) / 2.0;
}
