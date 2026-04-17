import os
import json
import base64
import time
from groq import Groq
from dotenv import load_dotenv
from lidar_receiver import LidarReceiver
from camera_handler import capture_image

# 1. إعدادات الاتصال
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# تشغيل قناة الاستماع لليدار
receiver = LidarReceiver()
receiver.start()

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_robot_position():
    return receiver.get_position()

def get_wall_tilt():
    """محاكاة قراءة حساس الميلان من كود بتول"""
    import random
    return round(random.uniform(0.1, 0.9), 2) # قراءة عشوائية للتجربة

def inspect_with_ai(image_path, socket_id):
    try:
        if not os.path.exists(image_path):
            return "Error: Image capture failed."
            
        base64_image = encode_image(image_path)
        prompt = (
            f"You are a QA Engineer checking Target ID: {socket_id}. "
            f"Verify if the socket box is installed. Keep it concise.\n"
            f"Format:\n- **Status:** [Pass/Warning/Fail]\n- **Details:** [Explanation]\n- **Defects:** [List defects or 'None']"
        )

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}],
            timeout=10
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"\n[NETWORK ALERT] No Internet! Saving {socket_id} to offline queue...")
        offline_task = {"id": socket_id, "image": image_path, "timestamp": time.ctime()}
        queue_file = 'offline_queue.json'
        queue_data = []
        if os.path.exists(queue_file):
            with open(queue_file, 'r') as f:
                queue_data = json.load(f)
        queue_data.append(offline_task)
        with open(queue_file, 'w') as f:
            json.dump(queue_data, f, indent=4)
        return "OFFLINE MODE: Image saved locally. Pending cloud sync."

def run_site_mission(mission_file):
    if not os.path.exists(mission_file):
        print(f"Error: {mission_file} missing. Please run your CAD parser first.")
        return

    with open(mission_file, 'r') as f:
        mission_data = json.load(f)

    project_name = mission_data.get('project', 'SiteSentry_Task')
    print(f"--- SITESENTRY MISSION START: {project_name} ---")
    results = []

    for target in mission_data['targets']:
        current_x, current_y = get_robot_position()
        target_type = target.get('type', 'socket') # الافتراضي هو مقبس
        
        print(f"\nEvaluating Target: {target['id']} [Type: {target_type.upper()}] at ({target['x']}, {target['y']})")
        
        deviation_x = abs(current_x - target['x'])
        deviation_y = abs(current_y - target['y'])
        
        # الهيكلة الأساسية لسجل الهدف
        log_entry = {
            "id": target['id'],
            "type": target_type,
            "target_coords": {"x": target['x'], "y": target['y']},
            "status": "Pending"
        }
        
        # إذا كان نوع المهمة "ميلان جدار"، نضيف اسم الجدار للسجل
        if target_type == "wall_tilt":
            log_entry["wall_name"] = target.get("wall_name", "Unknown_Wall")

        if deviation_x <= 0.15 and deviation_y <= 0.15:
            print(f"STATUS: Reached target {target['id']}. Handing over to ROS for alignment...")
            
            # ========================================================
            # 1. إيقاف المسار وطلب المحاذاة (تُرسل لمحمد)
            # ========================================================
            # ملاحظة: يمكنك برمجة دالة send_ros_command لاحقاً لترسل رسالة UDP لمحمد
            print(">> COMMAND: ROS_PAUSE_AND_ALIGN")
            
            # ========================================================
            # 2. انتظار إشارة "تمت المحاذاة" من محمد
            # ========================================================
            print("⏳ Waiting for LiDAR alignment to complete...")
            # هنا سنضع تأخير وهمي للتجربة (في الحقيقة ستنتظر رسالة من محمد)
            time.sleep(3) 
            print("✅ LiDAR Alignment Confirmed (Robot is parallel and at 50cm).")
            
            # ========================================================
            # 3. الفحص (الكود الخاص بك يعمل هنا بأمان تام)
            # ========================================================
            if target_type == "socket":
                print("Triggering Camera and AI...")
                image_to_check = f"capture_{target['id']}.jpg" 
                camera_success = capture_image(image_to_check)
                
                if camera_success:
                    ai_analysis = inspect_with_ai(image_to_check, target['id'])
                    status_val = "Verified" if "Pass" in ai_analysis else "Issue Detected"
                else:
                    ai_analysis = "Error: Camera hardware failed."
                    status_val = "Camera Error"
                
                log_entry.update({
                    "status": status_val,
                    "ai_report": ai_analysis
                })
                
            elif target_type == "wall_tilt":
                print("Measuring Wall Tilt (Fast Mode)...")
                tilt = get_wall_tilt()
                log_entry.update({
                    "status": "Recorded",
                    "tilt_degrees": tilt
                })
                
            # ========================================================
            # 4. إعطاء الأمر لمحمد بإكمال المسار
            # ========================================================
            print(">> COMMAND: ROS_RESUME_NAVIGATION")
            print("-" * 40)
            
            # ----------------------------------------------------
            # التفريع المنطقي بناءً على نوع المهمة (هنا يكمن سحر التحديث)
            # ----------------------------------------------------
            if target_type == "socket":
                print("Triggering Camera and AI...")
                image_to_check = f"capture_{target['id']}.jpg" 
                camera_success = capture_image(image_to_check)
                
                if camera_success:
                    ai_analysis = inspect_with_ai(image_to_check, target['id'])
                    status_val = "Verified" if "Pass" in ai_analysis else "Issue Detected"
                else:
                    ai_analysis = "Error: Camera hardware failed."
                    status_val = "Camera Error"
                
                log_entry.update({
                    "status": status_val,
                    "ai_report": ai_analysis
                })
                
            elif target_type == "wall_tilt":
                print("Measuring Wall Tilt (Fast Mode)...")
                tilt = get_wall_tilt()
                log_entry.update({
                    "status": "Recorded",
                    "tilt_degrees": tilt
                })
            # ----------------------------------------------------

        else:
            print(f"STATUS: Out of range (Dist X: {deviation_x:.2f}m, Y: {deviation_y:.2f}m). Skipping.")
            log_entry.update({
                "status": "Missed (Out of Range)",
                "error": f"Robot position ({current_x:.2f}, {current_y:.2f}) too far."
            })

        results.append(log_entry)

    # حفظ التقرير النهائي
    final_report = {
        "summary": {
            "project_name": project_name,
            "total_targets": len(mission_data['targets']),
            "completed": len([r for r in results if "Missed" not in r['status']]),
            "timestamp": time.ctime()
        },
        "details": results
    }

    with open('final_site_report.json', 'w') as f:
        json.dump(final_report, f, indent=4)
    
    print("\n--- Mission Complete. Data ready for Dashboard and Map Generation ---")
    receiver.stop()

if __name__ == "__main__":
    run_site_mission("mission.json")