import ezdxf
import json

def extract_sockets(filename):
    try:
        # فتح ملف الكاد
        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()
        
        mission_data = {"project": "SiteSentry_Task", "targets": []}
        
        # البحث عن الدوائر في طبقة SOCKETS
        query = msp.query('CIRCLE[layer=="SOCKETS"]')
        
        for i, circle in enumerate(query):
            center = circle.dxf.center
            # تحويل الإحداثيات لقاموس بسيط
            target = {
                "id": f"Socket_{i+1}",
                "x": round(center.x, 2),
                "y": round(center.y, 2),
                "status": "pending"
            }
            mission_data["targets"].append(target)
            
        # حفظ النتائج في ملف JSON
        with open('mission.json', 'w') as f:
            json.dump(mission_data, f, indent=4)
            
        print(f"تم بنجاح استخراج {len(query)} أهداف وحفظها في mission.json")
        
    except Exception as e:
        print(f"خطأ في قراءة الملف: {e}")

if __name__ == "__main__":
    extract_sockets("site_map.dxf")