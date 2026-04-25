"""
AI CODEBASE ANALYSIS PROMPT
Use this prompt with any AI to analyze and understand the complete robot system
Copy and paste everything between the === lines ===
"""

===================================================
START OF PROMPT - COPY THIS ENTIRE SECTION
===================================================

You are a robotics software expert analyzing a complete ROS 2 construction robot system.

I have downloaded a codebase with these files in one folder:
1. arduino_microros_robot.cpp - Arduino firmware
2. docker_setup_instructions.md - Docker configuration
3. ros2_launch_files.py - ROS 2 launch configuration
4. telegram_bot.py - Telegram remote control bot
5. web_dashboard.html - Web monitoring dashboard
6. COMPLETE_SETUP_GUIDE.md - Setup instructions

PLEASE ANALYZE AND EXPLAIN:

## PART 1: ARCHITECTURE OVERVIEW
1. Draw a diagram showing how all 6 files connect together
2. What does each file do?
3. What is the communication flow between components?
4. What are the main processes/threads/services?

## PART 2: HARDWARE INTEGRATION
1. How does the Arduino connect to Raspberry Pi?
2. What communication protocol is used?
3. How does sensor data flow from Arduino to ROS 2?
4. How do motor commands flow from ROS 2 to Arduino?

## PART 3: ROS 2 TOPICS & SERVICES
1. List all ROS 2 topics that these files publish/subscribe to
2. What data type does each topic use?
3. What is the communication direction for each topic?
4. Which file(s) interact with each topic?

## PART 4: FILE-BY-FILE BREAKDOWN
For EACH file, explain:
- What is its purpose?
- What does it depend on?
- What other files does it interact with?
- What are the key functions/classes?
- What happens when you run/execute it?

## PART 5: EXECUTION FLOW
Step by step, what happens when you:
1. Power on the robot?
2. Start the Docker container?
3. Launch the ROS 2 system?
4. Send a motor command from the web dashboard?
5. Upload a CAD file via Telegram?
6. Read sensor data?

## PART 6: ERROR HANDLING & DEBUGGING
1. What are the most likely failure points?
2. How would you debug each component if it fails?
3. What error messages indicate what problems?
4. How to verify each component is working?

## PART 7: KEY CODE SECTIONS
For each file, identify and explain:
- The most important functions/classes
- The main loop or entry point
- Critical initialization code
- Main logic/decision points

## PART 8: DATA FLOW EXAMPLES
Provide concrete examples of:
1. How does motor speed data flow from Arduino → ROS 2 → Web Dashboard?
2. How does a user command flow from Telegram → ROS 2 → Arduino → Motor?
3. How does camera data flow from Pi camera → ROS 2 → Web Dashboard?
4. How do sensor readings reach the Telegram bot?

## PART 9: DEPENDENCIES & REQUIREMENTS
1. What Python packages are needed?
2. What ROS 2 packages are needed?
3. What Arduino libraries are needed?
4. What system dependencies are needed?
5. What are the version requirements?

## PART 10: CONFIGURATION & PARAMETERS
1. What are all the configurable parameters?
2. Where are these parameters defined?
3. How to change them?
4. What is the impact of changing each parameter?

## PART 11: COMMON TASKS
Provide step-by-step instructions for:
1. How to make the robot move forward 2 meters?
2. How to read sensor values programmatically?
3. How to add a new sensor to the system?
4. How to create a new ROS 2 node?
5. How to debug a communication issue?
6. How to modify the web dashboard?
7. How to add a new Telegram command?

## PART 12: TESTING CHECKLIST
For someone who just downloaded the files:
1. How do I know each component is working?
2. What tests should I run in what order?
3. What commands should I execute to verify functionality?
4. What output should I expect for each test?

## PART 13: TROUBLESHOOTING GUIDE
Create a decision tree for common problems:
- "Robot doesn't move" → What are 10 possible causes?
- "Web dashboard shows no data" → Debugging steps
- "Telegram bot not responding" → What to check?
- "SLAM not mapping" → Verification steps

## PART 14: INTEGRATION POINTS
Identify all the "connection points" where:
- Files interact with each other
- External systems connect (Arduino, Pi camera, Lidar, etc.)
- Network connections happen (Telegram API, Web socket, etc.)
- File I/O happens (config files, saved maps, etc.)

## AFTER ANALYSIS, PROVIDE:

1. **System Architecture Diagram** (in text format)
2. **Data Flow Diagram** (show how data moves through system)
3. **Component Interaction Matrix** (which files interact with which)
4. **Topic/Service Map** (what connects to what)
5. **Quick Reference Guide** (1-page summary)
6. **Beginner's Walkthrough** (step-by-step for first-time user)

===================================================
END OF PROMPT
===================================================

---

## HOW TO USE THIS PROMPT:

### Option 1: Claude (claude.ai)
1. Go to claude.ai
2. Create new conversation
3. Copy and paste the entire prompt above
4. Also upload/attach your files:
   - arduino_microros_robot.cpp
   - docker_setup_instructions.md
   - ros2_launch_files.py
   - telegram_bot.py
   - web_dashboard.html
   - COMPLETE_SETUP_GUIDE.md
5. Send the message
6. Claude will analyze everything

### Option 2: ChatGPT (openai.com)
1. Go to chat.openai.com
2. Create new chat
3. Copy and paste the prompt
4. Upload files (GPT-4 with file upload)
5. Ask follow-up questions as needed

### Option 3: Claude with Web Interface
1. Go to claude.ai
2. Paste the prompt
3. Use "Upload files" button to add all 6 files
4. Submit and Claude will analyze the complete codebase

### Option 4: Local AI (Llama, etc.)
If you're using a local AI model:
1. Copy the prompt and all file contents
2. Create a single text file with everything
3. Load into your local AI system

---

## FOLLOW-UP PROMPTS TO ASK THE AI:

After the initial analysis, ask these questions:

### Understanding Questions:
```
"Explain the micro-ROS communication between Arduino and Raspberry Pi like I'm a 5-year-old"

"Draw me a step-by-step flowchart of what happens when I press the 'Forward' button on the web dashboard"

"What is the absolute minimum I need to do to make the robot move? Start from zero assumptions"

"Where exactly does the sensor data come from and where does it go?"
```

### Modification Questions:
```
"How do I add a new ultrasonic sensor to the system? Show me every file that needs to change"

"How do I change the robot speed from 0.3 m/s to 0.5 m/s? Where is this configured?"

"How do I make the web dashboard bigger and add a new gauge?"

"How do I add a new Telegram command like /calibrate?"
```

### Debugging Questions:
```
"The motor doesn't spin when I send a command. Walk me through step-by-step how to debug this"

"The web dashboard shows no sensor data. What could be wrong and how do I fix it?"

"The Telegram bot doesn't respond. What might be broken?"
```

### Integration Questions:
```
"How do I integrate a new type of sensor (e.g., temperature sensor)?"

"Can you show me the exact code changes needed to add a new ROS 2 subscriber?"

"How do I add data logging to save all sensor readings to a file?"
```

---

## EXAMPLE OUTPUT YOU'LL GET:

The AI will produce something like:

```
SYSTEM ARCHITECTURE

┌─────────────────────────────────────────────────────┐
│                  RASPBERRY PI 5                      │
│  ┌──────────────────────────────────────────────┐  │
│  │        ROS 2 (Docker Container)              │  │
│  │  ├─ micro_ros_agent (serial bridge)          │  │
│  │  ├─ motor_controller (cmd_vel listener)      │  │
│  │  ├─ camera_node (image publisher)            │  │
│  │  ├─ slam_toolbox (SLAM processing)           │  │
│  │  ├─ yolo_detector (object detection)         │  │
│  │  ├─ telegram_bot (remote control)            │  │
│  │  ├─ rosbridge_websocket (web interface)      │  │
│  │  └─ nav2 (path planning)                     │  │
│  └──────────────────────────────────────────────┘  │
│         ↓ (ROS 2 Topics)        ↓ (WebSocket)     │
└─────────────────────────────────────────────────────┘
      ↓ Serial (9600 baud)              ↓
      │                        ┌─────────────────┐
      │                        │ Web Browser     │
      │                        │ Dashboard       │
      │                        └─────────────────┘
      │
┌─────────────────────────────────────────────┐
│         ARDUINO MEGA 2560                    │
│  ├─ Motor Control (L298N driver)            │
│  ├─ Ultrasonic Sensor Reading               │
│  ├─ Encoder Reading (quadrature)            │
│  └─ micro-ROS Publisher/Subscriber          │
└─────────────────────────────────────────────┘
      ↓ PWM/GPIO
┌─────────────────────────────────────────────┐
│      HARDWARE (Motors, Sensors)              │
└─────────────────────────────────────────────┘
```

---

## TIPS FOR BEST RESULTS:

1. **Be specific**: Use the exact file names from your folder
2. **Include all files**: Upload all 6 files so AI can see connections
3. **Ask follow-ups**: The initial analysis opens doors for deeper questions
4. **Request examples**: Ask for code examples of modifications
5. **Get diagrams**: AI can create text-based diagrams and flowcharts
6. **Test knowledge**: Ask "if X breaks, how would I debug it?"
7. **Request checklists**: Get step-by-step checklists for common tasks

---

## WHAT YOU'LL UNDERSTAND AFTER THIS:

✅ How all 6 files work together  
✅ What each component does and why  
✅ How data flows through the entire system  
✅ How to debug when something breaks  
✅ How to modify the system for your needs  
✅ Where to make changes for specific features  
✅ What happens at every step of operation  
✅ How to add new sensors/features  
✅ How to integrate new components  
✅ Complete system architecture  

---

**SAVE THIS PROMPT** - You can reuse it with different AI systems or come back to it later with updated questions!
