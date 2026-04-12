import os
import json
import base64
import time
from groq import Groq
from dotenv import load_dotenv

# 1. Configuration & API Setup
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Using the specialized 2026 Vision Model for high-accuracy inspection
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

def encode_image(image_path):
    """Encodes an image to base64 for Groq API."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_robot_position():
    """
    Placeholder for LiDAR/SLAM data.
    Integration: Mohammad will link this to the ROS/Nav2 coordinate stream.
    """
    # Simulated current position (stays near the first socket for testing)
    return 10.05, 9.95 

def get_wall_tilt():
    """
    Placeholder for IR/Ultrasonic tilt measurement.
    Integration: Batool will link this to the GPIO hardware signal.
    """
    return 0.8 # Simulated tilt value

def inspect_with_ai(image_path, socket_id):
    """Sends the captured image to Groq for detailed construction analysis."""
    try:
        if not os.path.exists(image_path):
            return "Error: Image capture failed - File not found."
            
        base64_image = encode_image(image_path)
        
        prompt = (
            f"Analyze the electrical socket area for Target ID: {socket_id}. "
            "Verify if the socket box is installed and check for any debris or missing faceplates. "
            "Keep the response concise and formatted in bullet points."
        )

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI connection error: {str(e)}"

def run_site_mission(mission_file):
    """Main Mission Loop: Processes every target from the CAD data."""
    if not os.path.exists(mission_file):
        print(f"Error: {mission_file} missing. Please run your CAD parser first.")
        return

    with open(mission_file, 'r') as f:
        mission_data = json.load(f)

    print(f"--- SITESENTRY MISSION START: {mission_data['project']} ---")
    results = []
    
    # Get initial robot position from Mohammad's LiDAR module
    current_x, current_y = get_robot_position()

    for target in mission_data['targets']:
        print(f"\nEvaluating Target: {target['id']} at ({target['x']}, {target['y']})")
        
        # Calculate deviation from the target coordinates
        deviation_x = abs(current_x - target['x'])
        deviation_y = abs(current_y - target['y'])
        
        # Prepare the log entry for the engineer's report
        log_entry = {
            "id": target['id'],
            "target_coords": {"x": target['x'], "y": target['y']},
            "status": "Pending",
            "tilt_degrees": 0.0,
            "ai_report": "N/A"
        }

        # Check the 15cm (0.15m) accuracy requirement
        if deviation_x <= 0.15 and deviation_y <= 0.15:
            print(f"STATUS: Within range. Triggering side-view sensors...")
            
            # 1. Measure wall tilt
            tilt = get_wall_tilt()
            
            # 2. Perform Vision AI Analysis (Assumes image is captured by camera)
            # In production, Mohammad's script triggers the camera here
            image_to_check = "side_capture.jpg" 
            ai_analysis = inspect_with_ai(image_to_check, target['id'])
            
            log_entry.update({
                "status": "Verified" if "Found" in ai_analysis or "present" in ai_analysis.lower() else "Issue Detected",
                "tilt_degrees": tilt,
                "ai_report": ai_analysis
            })
        else:
            print(f"STATUS: Out of range (Dist: {deviation_x:.2f}m). Skipping inspection.")
            log_entry.update({
                "status": "Missed (Out of Range)",
                "ai_report": f"Robot current position ({current_x}, {current_y}) was too far from target."
            })

        results.append(log_entry)

    # Final Aggregation and JSON Generation
    final_report = {
        "summary": {
            "project_name": mission_data['project'],
            "total_targets": len(mission_data['targets']),
            "completed": len([r for r in results if "Missed" not in r['status']]),
            "timestamp": time.ctime()
        },
        "details": results
    }

    with open('final_site_report.json', 'w') as f:
        json.dump(final_report, f, indent=4)
    
    print("\n--- Mission Complete. Data ready for PDF Generation ---")

if __name__ == "__main__":
    run_site_mission("mission.json")