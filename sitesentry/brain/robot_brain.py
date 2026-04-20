#!/usr/bin/env python3
"""
SiteSentry Robot Brain
======================
Autonomous inspection AI running outside ROS.
- Listens on UDP 5006 for TARGET_REACHED from state_machine
- Captures images from USB camera
- Sends to Groq Vision API for defect analysis
- Builds inspection report (final_site_report.json)
- Sends INSPECTION_DONE back to state_machine

Communication:
  - UDP 5005: Send INSPECTION_DONE to state_machine
  - UDP 5006: Receive TARGET_REACHED from state_machine
  - /dev/video0: USB camera for image capture
  - Groq API: Vision-based inspection
"""

import os
import sys
import json
import socket
import cv2
import base64
import time
from pathlib import Path
from datetime import datetime
from threading import Thread, Lock
import queue

# Try importing Groq
try:
    from groq import Groq
except ImportError:
    print("ERROR: groq-python not installed. Run: pip install groq")
    sys.exit(1)

# ===== CONFIGURATION =====
CONFIG = {
    "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
    "groq_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "groq_vision_model": "llava-v1.5-7b",  # Vision model; verify at console.groq.com/docs/models
    "camera_device": "/dev/video0",
    "camera_index": 0,
    "image_quality": 90,              # JPEG quality
    "max_image_width": 1280,          # Resize large images
    "udp_listen_port": 5006,
    "udp_state_machine_port": 5005,
    "udp_state_machine_host": "127.0.0.1",
    "udp_timeout": 0.5,
    "output_dir": os.path.join(os.path.dirname(__file__), "../../results"),
    "report_file": "final_site_report.json",
    "captures_dir": "captures",
}

# Groq inspection system prompt
GROQ_SYSTEM_PROMPT = """You are SiteSentry, a Civil Engineering QA Inspector AI.
The camera is mounted 50cm from the wall, facing it directly and parallel to the surface.
Your task is to inspect the construction quality and identify any defects.

Inspection criteria:
1. CRACKS: Any visible cracks in surface (hairline, structural)
2. MISALIGNMENT: Uneven surfaces, gaps, poor fitting
3. POOR WORKMANSHIP: Surface finish, paint quality, joint quality
4. EXPOSED WIRES: Electrical hazards
5. SAFETY HAZARDS: Anything that poses immediate safety risk

You MUST respond with ONLY a valid JSON object (no markdown, no extra text):
{
  "inspection_status": "PASS" | "FAIL" | "WARNING",
  "defects_found": ["defect1", "defect2"],
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "ai_recommendation": "Brief actionable recommendation",
  "confidence": 0.0-1.0
}

Rules:
- PASS: No defects, good workmanship
- WARNING: Minor defects, cosmetic issues
- FAIL: Significant defects requiring rework
- Always prioritize safety (exposed wires, structural issues)
"""

class RobotBrain:
    def __init__(self):
        """Initialize Robot Brain"""
        # Groq client
        if not CONFIG["groq_api_key"]:
            print("ERROR: GROQ_API_KEY environment variable not set")
            sys.exit(1)
        
        self.groq_client = Groq(api_key=CONFIG["groq_api_key"])
        
        # State
        self.current_target = None
        self.report = {
            "summary": {
                "project_name": "SiteSentry_Inspection",
                "start_time": datetime.now().isoformat(),
                "total_targets": 0,
                "completed": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
            },
            "details": []
        }
        self.report_lock = Lock()
        
        # Communication
        self.udp_sock = None
        self.keep_running = True
        
        # Setup output directory
        self.output_dir = Path(CONFIG["output_dir"])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.captures_dir = self.output_dir / CONFIG["captures_dir"]
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✓ Output directory: {self.output_dir}")
    
    def setup_udp(self):
        """Setup UDP socket for listening"""
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_sock.bind(("0.0.0.0", CONFIG["udp_listen_port"]))
            self.udp_sock.settimeout(CONFIG["udp_timeout"])
            print(f"✓ UDP listening on port {CONFIG['udp_listen_port']}")
            return True
        except Exception as e:
            print(f"ERROR: UDP setup failed: {e}")
            return False
    
    def send_inspection_done(self, target_id):
        """Send INSPECTION_DONE to state machine"""
        try:
            msg = f"INSPECTION_DONE,{target_id}"
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(msg.encode(), (CONFIG["udp_state_machine_host"], CONFIG["udp_state_machine_port"]))
            sock.close()
            print(f"✓ Sent INSPECTION_DONE for target {target_id}")
            return True
        except Exception as e:
            print(f"ERROR: Failed to send INSPECTION_DONE: {e}")
            return False
    
    def recv_target_reached(self, timeout=None):
        """Receive TARGET_REACHED message from state machine"""
        if not self.udp_sock:
            return None
        
        old_timeout = self.udp_sock.gettimeout()
        if timeout:
            self.udp_sock.settimeout(timeout)
        
        try:
            data, addr = self.udp_sock.recvfrom(256)
            msg = data.decode().strip()
            self.udp_sock.settimeout(old_timeout)
            return msg
        except socket.timeout:
            self.udp_sock.settimeout(old_timeout)
            return None
        except Exception as e:
            print(f"ERROR: UDP receive failed: {e}")
            self.udp_sock.settimeout(old_timeout)
            return None
    
    def capture_image(self, target_id):
        """Capture image from USB camera"""
        try:
            cap = cv2.VideoCapture(CONFIG["camera_index"])
            if not cap.isOpened():
                print(f"ERROR: Cannot open camera {CONFIG['camera_device']}")
                return None
            
            # Warm up (skip first few frames)
            for _ in range(5):
                cap.read()
            
            # Capture frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                print("ERROR: Failed to capture frame")
                return None
            
            # Resize if necessary
            height, width = frame.shape[:2]
            if width > CONFIG["max_image_width"]:
                ratio = CONFIG["max_image_width"] / width
                new_size = (CONFIG["max_image_width"], int(height * ratio))
                frame = cv2.resize(frame, new_size)
            
            # Save to disk
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"target_{target_id}_{timestamp}.jpg"
            filepath = self.captures_dir / filename
            
            cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, CONFIG["image_quality"]])
            print(f"✓ Captured image: {filepath}")
            
            return filepath
        
        except Exception as e:
            print(f"ERROR: Image capture failed: {e}")
            return None
    
    def encode_image_to_base64(self, image_path):
        """Convert image to base64 for Groq API"""
        try:
            with open(image_path, 'rb') as f:
                return base64.standard_b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"ERROR: Failed to encode image: {e}")
            return None
    
    def inspect_with_groq(self, image_path):
        """Send image to Groq Vision API for inspection"""
        try:
            # Encode image
            image_base64 = self.encode_image_to_base64(image_path)
            if not image_base64:
                return None
            
            print(f"Sending image to Groq API ({CONFIG['groq_vision_model']})...")
            
            # Call Groq API with vision model
            response = self.groq_client.chat.completions.create(
                model=CONFIG["groq_vision_model"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": GROQ_SYSTEM_PROMPT
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                }
                            }
                        ]
                    }
                ],
                temperature=0.3,
                max_tokens=500,
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            print(f"ERROR: Groq API call failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def parse_inspection_response(self, response_text):
        """Parse JSON response from Groq"""
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            result = json.loads(response_text)
            
            # Validate required fields
            required_fields = ["inspection_status", "defects_found", "severity", "ai_recommendation"]
            for field in required_fields:
                if field not in result:
                    print(f"WARNING: Missing field '{field}' in response")
                    result[field] = None
            
            return result
        
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to parse JSON response: {e}")
            print(f"Response was: {response_text[:200]}")
            return None
        except Exception as e:
            print(f"ERROR: Response parsing failed: {e}")
            return None
    
    def perform_inspection(self, target_id, x, y):
        """Full inspection workflow for a single target"""
        print(f"\n{'='*50}")
        print(f"INSPECTING TARGET {target_id}: ({x}, {y})")
        print(f"{'='*50}")
        
        # Capture image
        image_path = self.capture_image(target_id)
        if not image_path:
            print("ERROR: Failed to capture image")
            return None
        
        # Send to Groq for analysis
        response_text = self.inspect_with_groq(image_path)
        if not response_text:
            print("ERROR: Groq inspection failed")
            return None
        
        # Parse response
        result = self.parse_inspection_response(response_text)
        if not result:
            print("ERROR: Failed to parse inspection result")
            return None
        
        # Build result record
        record = {
            "id": target_id,
            "timestamp": datetime.now().isoformat(),
            "coordinates": {"x": x, "y": y},
            "image_file": str(image_path.relative_to(self.output_dir)),
            "inspection_status": result.get("inspection_status", "UNKNOWN"),
            "defects_found": result.get("defects_found", []),
            "severity": result.get("severity", "UNKNOWN"),
            "ai_recommendation": result.get("ai_recommendation", ""),
            "confidence": result.get("confidence", 0.0),
            "raw_response": response_text,
        }
        
        print(f"\nResult:")
        print(f"  Status: {record['inspection_status']}")
        print(f"  Severity: {record['severity']}")
        if record['defects_found']:
            print(f"  Defects: {', '.join(record['defects_found'])}")
        
        # Update report
        with self.report_lock:
            self.report["details"].append(record)
            self.report["summary"]["completed"] += 1
            
            if record["inspection_status"] == "PASS":
                self.report["summary"]["passed"] += 1
            elif record["inspection_status"] == "FAIL":
                self.report["summary"]["failed"] += 1
            elif record["inspection_status"] == "WARNING":
                self.report["summary"]["warnings"] += 1
        
        # Save report to disk
        self.save_report()
        
        return record
    
    def save_report(self):
        """Save final_site_report.json to disk"""
        try:
            with self.report_lock:
                report_path = self.output_dir / CONFIG["report_file"]
                with open(report_path, 'w') as f:
                    json.dump(self.report, f, indent=2)
            
            print(f"✓ Report saved: {report_path}")
        except Exception as e:
            print(f"ERROR: Failed to save report: {e}")
    
    def listen_and_inspect(self):
        """Main loop: listen for targets and perform inspections"""
        print("Robot Brain listening for targets...")
        
        while self.keep_running:
            # Wait for TARGET_REACHED message
            msg = self.recv_target_reached(timeout=1.0)
            if not msg:
                continue
            
            # Parse message: "TARGET_REACHED,target_id,x,y"
            try:
                parts = msg.split(",")
                if len(parts) < 4:
                    continue
                
                target_id = parts[1]
                x = float(parts[2])
                y = float(parts[3])
            except ValueError:
                print(f"ERROR: Malformed TARGET_REACHED: {msg}")
                continue
            
            # Perform inspection
            result = self.perform_inspection(target_id, x, y)
            
            # Send INSPECTION_DONE back to state machine
            self.send_inspection_done(target_id)
    
    def run(self):
        """Start Robot Brain"""
        if not self.setup_udp():
            return
        
        try:
            print("SiteSentry Robot Brain started")
            self.listen_and_inspect()
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.udp_sock:
                self.udp_sock.close()
            
            # Final report
            self.save_report()
            print(f"\nFinal Report:")
            print(f"  Completed: {self.report['summary']['completed']}")
            print(f"  Passed: {self.report['summary']['passed']}")
            print(f"  Failed: {self.report['summary']['failed']}")
            print(f"  Warnings: {self.report['summary']['warnings']}")

def main():
    brain = RobotBrain()
    brain.run()

if __name__ == "__main__":
    main()
