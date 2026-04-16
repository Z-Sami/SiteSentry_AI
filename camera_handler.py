import cv2
import time

def capture_image(save_path="side_capture.jpg"):
    """
    يقوم بفتح الكاميرا، التقاط صورة، وحفظها في المسار المحدد.
    """
    print("📸 Initializing camera...")
    # الرقم 0 يعني الكاميرا الافتراضية الأولى الموصولة بالجهاز
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Error: Cannot access the camera. Check connections!")
        return False
        
    # إعطاء الكاميرا ثانية واحدة لتضبط الإضاءة (الفوكس)
    time.sleep(1) 
    
    # التقاط الصورة
    ret, frame = cap.read()
    
    if ret:
        # حفظ الصورة
        cv2.imwrite(save_path, frame)
        print(f"✅ Image successfully captured and saved as: {save_path}")
        cap.release()
        return True
    else:
        print("❌ Error: Failed to capture frame.")
        cap.release()
        return False

# --- تجربة سريعة ---
if __name__ == "__main__":
    capture_image()