import ezdxf
import json
import os

def parse_autocad_to_mission(dxf_filepath, output_json="mission.json"):
    if not os.path.exists(dxf_filepath):
        print(f"❌ Error: File '{dxf_filepath}' not found.")
        return

    print(f"📂 Reading CAD file: {dxf_filepath}...")
    
    try:
        doc = ezdxf.readfile(dxf_filepath)
        msp = doc.modelspace()
    except Exception as e:
        print(f"❌ Error reading DXF: {e}")
        return

    mission_data = {
        "project": "SiteSentry_Inspection",
        "path_waypoints": [],
        "targets": []
    }

    # 1. استخراج المسار (ROBOT_PATH)
    print("🔍 Extracting Robot Path...")
    path_entities = msp.query('LWPOLYLINE[layer=="ROBOT_PATH"]')
    for entity in path_entities:
        points = entity.get_points('xy')
        for i, point in enumerate(points):
            if i == 0: wp_id = "START"
            elif i == len(points) - 1: wp_id = "END"
            else: wp_id = f"WP_{i}"
                
            mission_data["path_waypoints"].append({
                "id": wp_id,
                "x": round(point[0], 2),
                "y": round(point[1], 2)
            })
        break 

    # 2. استخراج المقابس (ELECTRICAL_SOCKETS)
    print("🔍 Extracting Electrical Sockets...")
    socket_counter = 1
    for entity in msp.query('CIRCLE[layer=="ELECTRICAL_SOCKETS"]'):
        center = entity.dxf.center
        mission_data["targets"].append({
            "id": f"Socket_{socket_counter}",
            "type": "socket",
            "x": round(center.x, 2),
            "y": round(center.y, 2)
        })
        socket_counter += 1

    # 3. استخراج نقاط الجدران (ديناميكياً بناءً على اسم الطبقة)
    print("🔍 Extracting Wall Tilt Points (Dynamic Layers)...")
    tilt_counter = 1
    
    # نبحث في كل النقاط الموجودة في المخطط
    for entity in msp.query('POINT'):
        layer_name = entity.dxf.layer
        
        # إذا كان اسم الطبقة يبدأ بكلمة TILT_
        if layer_name.startswith("TILT_"):
            # نستخرج اسم الجدار بقص أول 5 أحرف (TILT_)
            wall_name = layer_name[5:] 
            
            loc = entity.dxf.location
            mission_data["targets"].append({
                "id": f"Wall_Pt_{tilt_counter}",
                "type": "wall_tilt",
                "wall_name": wall_name,
                "x": round(loc.x, 2),
                "y": round(loc.y, 2)
            })
            tilt_counter += 1

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(mission_data, f, indent=4)
        
    print("\n✅ Mission successfully compiled!")
    print(f"📍 Waypoints found: {len(mission_data['path_waypoints'])}")
    print(f"🎯 Targets found: {len(mission_data['targets'])}")
    print(f"📄 Saved to: {output_json}")

if __name__ == "__main__":
    cad_file = "site_plan.dxf" 
    if not os.path.exists(cad_file):
        doc = ezdxf.new('R2010')
        doc.saveas(cad_file)
        print(f"⚠️ Created a blank '{cad_file}' for testing. Please replace it with a real CAD file later.")
        
    parse_autocad_to_mission(cad_file)