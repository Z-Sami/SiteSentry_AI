#!/usr/bin/env python3
"""
SiteSentry CAD Parser
=====================
Parses .dxf CAD files and extracts inspection targets.
- Reads INSERT entities (block references)
- Filters by target types: SOCKET, COLUMN, PIPE
- Converts DXF coordinates to ROS map frame
- Outputs mission.json with waypoints and target list

Usage:
  python3 cad_to_json.py <input.dxf> [output.json]
"""

import sys
import os
import json
import argparse
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERROR: ezdxf not installed. Run: pip install ezdxf")
    sys.exit(1)

# ===== CONFIGURATION =====
CONFIG = {
    "scale_factor": 1.0,              # DXF units to meters (adjust based on your DXF)
    "origin_offset_x": 0.0,           # ROS map origin X (meters)
    "origin_offset_y": 0.0,           # ROS map origin Y (meters)
    "target_types": ["SOCKET", "COLUMN", "PIPE", "OUTLET", "PANEL"],  # Valid block names
    "waypoint_layer": "ROBOT_PATH",   # Layer containing robot navigation path
    "output_indent": 2,               # JSON formatting
}

class CADParser:
    def __init__(self, dxf_path, config=None):
        """
        Initialize CAD parser
        
        Args:
            dxf_path (str): Path to .dxf file
            config (dict): Configuration overrides
        """
        self.dxf_path = Path(dxf_path)
        self.config = {**CONFIG, **(config or {})}
        self.targets = []
        self.waypoints = []
        self.dwg = None
        self.target_id_counter = 1
        
        if not self.dxf_path.exists():
            raise FileNotFoundError(f"DXF file not found: {dxf_path}")
    
    def load_dxf(self):
        """Load DXF file using ezdxf"""
        try:
            self.dwg = ezdxf.readfile(str(self.dxf_path))
            print(f"✓ Loaded DXF: {self.dxf_path}")
        except ezdxf.DXFStructureError as e:
            print(f"ERROR: Invalid DXF file: {e}")
            sys.exit(1)
    
    def dxf_to_ros_coords(self, x, y):
        """
        Convert DXF coordinates to ROS map frame
        
        Args:
            x, y: DXF coordinates
            
        Returns:
            (ros_x, ros_y): Coordinates in ROS map frame
        """
        ros_x = x * self.config["scale_factor"] + self.config["origin_offset_x"]
        ros_y = y * self.config["scale_factor"] + self.config["origin_offset_y"]
        return round(ros_x, 3), round(ros_y, 3)
    
    def extract_insert_blocks(self):
        """
        Extract INSERT entities (block references) from DXF
        Each INSERT is a potential inspection target
        """
        mspace = self.dwg.modelspace()
        
        for entity in mspace.query('INSERT'):
            block_name = entity.dxf.name
            
            # Check if block name matches our target types
            matching_type = None
            for target_type in self.config["target_types"]:
                if target_type.upper() in block_name.upper():
                    matching_type = target_type
                    break
            
            if not matching_type:
                continue
            
            # Extract coordinates
            x = entity.dxf.insert.x
            y = entity.dxf.insert.y
            ros_x, ros_y = self.dxf_to_ros_coords(x, y)
            
            # Create target record
            target = {
                "id": self.target_id_counter,
                "label": matching_type,
                "block_name": block_name,
                "x": ros_x,
                "y": ros_y,
                "z": 0.0,
                "status": "PENDING",
                "dxf_coords": {"x": round(x, 3), "y": round(y, 3)},
            }
            
            self.targets.append(target)
            self.target_id_counter += 1
        
        print(f"✓ Extracted {len(self.targets)} inspection targets")
    
    def extract_waypoints(self):
        """
        Extract ROBOT_PATH polyline/line entities as navigation waypoints
        These define the planned robot trajectory
        """
        mspace = self.dwg.modelspace()
        
        # Find all lines and polylines on WAYPOINT_LAYER
        for entity_type in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
            for entity in mspace.query(entity_type):
                if entity.dxf.layer == self.config["waypoint_layer"]:
                    if entity_type == 'LINE':
                        # Line: start and end points
                        start = entity.dxf.start
                        end = entity.dxf.end
                        self.waypoints.append({"x": start.x, "y": start.y})
                        self.waypoints.append({"x": end.x, "y": end.y})
                    
                    elif entity_type in ['LWPOLYLINE', 'POLYLINE']:
                        # Polyline: all vertices
                        for point in entity.get_points():
                            self.waypoints.append({"x": point[0], "y": point[1]})
        
        # Convert to ROS coordinates
        ros_waypoints = []
        for i, wp in enumerate(self.waypoints):
            ros_x, ros_y = self.dxf_to_ros_coords(wp["x"], wp["y"])
            ros_waypoints.append({
                "id": i,
                "x": ros_x,
                "y": ros_y,
                "theta": 0.0
            })
        
        self.waypoints = ros_waypoints
        print(f"✓ Extracted {len(self.waypoints)} navigation waypoints")
    
    def generate_mission_json(self):
        """Generate mission.json structure"""
        mission = {
            "project": "SiteSentry_Inspection",
            "timestamp": self._get_timestamp(),
            "config": {
                "scale_factor": self.config["scale_factor"],
                "origin_offset": {
                    "x": self.config["origin_offset_x"],
                    "y": self.config["origin_offset_y"],
                }
            },
            "statistics": {
                "total_targets": len(self.targets),
                "total_waypoints": len(self.waypoints),
            },
            "targets": self.targets,
            "waypoints": self.waypoints,
        }
        
        return mission
    
    @staticmethod
    def _get_timestamp():
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def save_mission_json(self, output_path):
        """
        Save mission to JSON file
        
        Args:
            output_path (str or Path): Output file path
        """
        mission = self.generate_mission_json()
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(mission, f, indent=self.config["output_indent"])
        
        print(f"✓ Saved mission.json: {output_path}")
        print(f"  - Targets: {len(self.targets)}")
        print(f"  - Waypoints: {len(self.waypoints)}")
        
        return mission
    
    def parse(self, output_path=None):
        """
        Full parsing pipeline
        
        Args:
            output_path (str): Output JSON path (optional)
            
        Returns:
            dict: Mission dictionary
        """
        self.load_dxf()
        self.extract_insert_blocks()
        self.extract_waypoints()
        
        mission = self.generate_mission_json()
        
        if output_path:
            self.save_mission_json(output_path)
        
        return mission


def main():
    parser = argparse.ArgumentParser(
        description="SiteSentry CAD Parser: Convert .dxf to mission.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 cad_to_json.py site_plan.dxf mission.json
  python3 cad_to_json.py --scale 0.1 --offset-x 5 building.dxf
        """
    )
    
    parser.add_argument("input_dxf", help="Input .dxf file path")
    parser.add_argument("-o", "--output", default="mission.json",
                        help="Output mission.json path (default: mission.json)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Scale factor from DXF to meters (default: 1.0)")
    parser.add_argument("--offset-x", type=float, default=0.0,
                        help="ROS origin X offset (default: 0.0)")
    parser.add_argument("--offset-y", type=float, default=0.0,
                        help="ROS origin Y offset (default: 0.0)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress output messages")
    
    args = parser.parse_args()
    
    # Configure
    config = {
        "scale_factor": args.scale,
        "origin_offset_x": args.offset_x,
        "origin_offset_y": args.offset_y,
    }
    
    try:
        # Parse CAD
        cad_parser = CADParser(args.input_dxf, config)
        mission = cad_parser.parse(args.output)
        
        if not args.quiet:
            print("\n=== Mission Summary ===")
            print(json.dumps(mission, indent=2)[:500] + "...")
        
        return 0
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
