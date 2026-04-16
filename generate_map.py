import ezdxf
import json
import os

def generate_as_built_map(original_dxf, report_json, output_dxf="Final_Inspection_Report.dxf"):
    if not os.path.exists(report_json):
        print(f"❌ Error: Report file '{report_json}' not found.")
        return

    # 1. تحميل بيانات التقرير
    with open(report_json, 'r') as f:
        report_data = json.load(f)

    # 2. فتح ملف الكاد الأصلي
    try:
        if os.path.exists(original_dxf):
            doc = ezdxf.readfile(original_dxf)
            print(f"📂 Opening original plan: {original_dxf}")
        else:
            doc = ezdxf.new('R2010')
            print("⚠️ Original plan not found. Creating a new blank map.")
        
        msp = doc.modelspace()
    except Exception as e:
        print(f"❌ Error loading DXF: {e}")
        return

    # 3. إعداد الألوان والطبقات الجديدة للنتائج
    if "INSPECTION_RESULTS" not in doc.layers:
        doc.layers.add("INSPECTION_RESULTS", color=3) # أخضر افتراضي

    print("🖋️ Drawing inspection results on map...")

    for item in report_data['details']:
        x = item['target_coords']['x']
        y = item['target_coords']['y']
        status = item['status']
        target_id = item['id']
        target_type = item.get('type', 'socket')

        # تحديد اللون بناءً على الحالة (3 = أخضر، 1 = أحمر)
        result_color = 3 if status == "Verified" or status == "Recorded" else 1

        if target_type == "socket":
            # رسم دائرة حول المقبس ووضع نص النتيجة
            msp.add_circle((x, y), radius=0.2, dxfattribs={'layer': 'INSPECTION_RESULTS', 'color': result_color})
            msp.add_text(f"{target_id}: {status}", dxfattribs={'height': 0.15, 'color': result_color}).set_placement((x + 0.3, y))
            
        elif target_type == "wall_tilt":
            # رسم علامة X لمكان فحص الميلان وكتابة القراءة
            tilt_val = item.get('tilt_degrees', 'N/A')
            # رسم شكل X بسيط
            msp.add_line((x-0.1, y-0.1), (x+0.1, y+0.1), dxfattribs={'color': result_color})
            msp.add_line((x-0.1, y+0.1), (x+0.1, y-0.1), dxfattribs={'color': result_color})
            
            # كتابة درجة الميلان بجانب النقطة
            msp.add_text(f"{tilt_val}°", dxfattribs={'height': 0.12, 'color': result_color}).set_placement((x + 0.2, y))

    # 4. حفظ المخطط النهائي
    doc.saveas(output_dxf)
    print(f"✅ FINAL MAP GENERATED: {output_dxf}")

# --- الكود الأصلي في generate_map.py ---
    doc.saveas(output_dxf)
    print(f"✅ FINAL MAP GENERATED: {output_dxf}")

    # ==========================================
    # الإضافة الجديدة: إرسال الملفات عبر تليجرام
    # ==========================================
    try:
        from telegram_bot import send_results_to_user
        print("📱 Sending files to Telegram...")
        send_results_to_user()
    except Exception as e:
        print(f"Failed to send telegram message: {e}")

if __name__ == "__main__":
    generate_as_built_map("site_plan.dxf", "final_site_report.json")