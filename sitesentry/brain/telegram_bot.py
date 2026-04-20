#!/usr/bin/env python3
"""
SiteSentry Telegram Bot
=======================
User-facing interface for mission planning and result delivery.

Commands:
  /start   - Show help and current status
  /run     - Upload .dxf file and start mission
  /status  - Show mission progress
  /report  - Generate and send final report

Architecture:
  - Receives .dxf from user
  - Calls cad_to_json.py to parse → mission.json
  - Sends UDP "START_MISSION" to state_machine_node (port 5005)
  - Polls for "MISSION_COMPLETE" from robot_brain (port 5006)
  - Generates PDF report via report_generator.py
  - Sends results back to user
"""

import os
import sys
import json
import socket
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from telegram import Update, Document
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
except ImportError:
    print("ERROR: python-telegram-bot not installed. Run: pip install 'python-telegram-bot[all]'")
    sys.exit(1)

# ===== CONFIGURATION =====
CONFIG = {
    "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "admin_chat_id": int(os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "0")),
    "cad_to_json_script": os.path.join(os.path.dirname(__file__), "cad_to_json.py"),
    "report_generator_script": os.path.join(os.path.dirname(__file__), "report_generator.py"),
    "mission_file": os.path.join(os.path.dirname(__file__), "../../mission.json"),
    "report_file": os.path.join(os.path.dirname(__file__), "../../results/final_site_report.json"),
    "state_machine_host": "127.0.0.1",
    "state_machine_port": 5005,
    "robot_brain_host": "127.0.0.1",
    "robot_brain_port": 5006,
    "udp_timeout": 0.5,
    "dxf_upload_dir": "/tmp/sitesentry_uploads",
}

# Conversation states
WAITING_FOR_DXF = 1

class SiteSentryBot:
    def __init__(self):
        """Initialize Telegram bot"""
        if not CONFIG["telegram_bot_token"]:
            print("ERROR: TELEGRAM_BOT_TOKEN not set")
            sys.exit(1)
        
        self.token = CONFIG["telegram_bot_token"]
        self.app = None
        self.mission_active = False
        self.current_chat_id = None
        self.mission_file = Path(CONFIG["mission_file"])
        self.report_file = Path(CONFIG["report_file"])
        
        # Create upload directory
        Path(CONFIG["dxf_upload_dir"]).mkdir(parents=True, exist_ok=True)
    
    def send_udp_message(self, host, port, message):
        """Send UDP message to state machine or robot brain"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(CONFIG["udp_timeout"])
            sock.sendto(message.encode(), (host, port))
            sock.close()
            return True
        except Exception as e:
            print(f"ERROR: UDP send failed: {e}")
            return False
    
    def recv_udp_message(self, port, timeout=None):
        """Receive UDP message (for mission complete signal)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sock.settimeout(timeout or CONFIG["udp_timeout"])
            data, addr = sock.recvfrom(256)
            sock.close()
            return data.decode().strip()
        except socket.timeout:
            return None
        except Exception as e:
            print(f"ERROR: UDP recv failed: {e}")
            return None
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        self.current_chat_id = update.effective_chat.id
        
        welcome_text = """
🤖 *SiteSentry - Autonomous Construction Inspector*

Welcome! I'll help you plan and execute building inspections.

*Available Commands:*
🏗️ /run - Upload a CAD (.dxf) file and start inspection mission
📊 /status - Check current mission progress
📄 /report - Generate and download final inspection report
❓ /help - Show this message

*How it works:*
1. Upload your site plan (.dxf) with inspection targets
2. I'll parse the file and create a mission
3. The robot will navigate and inspect automatically
4. Results will be delivered as PDF + annotated CAD

*For Support:*
Contact the SiteSentry team if you have questions.
        """
        
        await update.message.reply_text(welcome_text, parse_mode="Markdown")
    
    async def cmd_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /run command - ask for DXF file"""
        self.current_chat_id = update.effective_chat.id
        
        await update.message.reply_text(
            "📁 Please upload your site plan (.dxf file) to start the mission.\n"
            "The file should contain:\n"
            "  • ROBOT_PATH layer: navigation route\n"
            "  • ELECTRICAL_SOCKETS layer: socket targets\n"
            "  • TILT_* layers: wall inspection points",
            parse_mode="Markdown"
        )
        
        return WAITING_FOR_DXF
    
    async def handle_dxf_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle DXF file upload"""
        document = update.message.document
        
        if not document.file_name.lower().endswith('.dxf'):
            await update.message.reply_text(
                "❌ Please upload a .dxf file (CAD format)"
            )
            return WAITING_FOR_DXF
        
        try:
            # Download file
            file = await context.bot.get_file(document.file_id)
            dxf_path = Path(CONFIG["dxf_upload_dir"]) / document.file_name
            await file.download_to_drive(dxf_path)
            
            await update.message.reply_text(
                f"✅ Received: {document.file_name}\n"
                f"📝 Parsing CAD file..."
            )
            
            # Parse CAD
            mission_path = self.mission_file
            result = self._parse_cad_file(str(dxf_path), str(mission_path))
            
            if not result:
                await update.message.reply_text(
                    "❌ Failed to parse CAD file. Check format and try again."
                )
                return ConversationHandler.END
            
            # Show mission summary
            with open(mission_path, 'r') as f:
                mission = json.load(f)
            
            targets = mission.get("targets", [])
            summary = f"""
✅ *Mission Created*

📋 *Summary:*
  • Targets: {len(targets)}
  • Project: {mission['project']}
  • Timestamp: {mission['timestamp']}

*Targets to inspect:*
"""
            for target in targets[:5]:  # Show first 5
                summary += f"\n  • {target['label']} @ ({target['x']}, {target['y']})"
            
            if len(targets) > 5:
                summary += f"\n  ... and {len(targets) - 5} more"
            
            summary += "\n\n🚀 Starting mission now..."
            
            await update.message.reply_text(summary, parse_mode="Markdown")
            
            # Send START_MISSION to state machine
            self.mission_active = True
            if self.send_udp_message(
                CONFIG["state_machine_host"],
                CONFIG["state_machine_port"],
                "START_MISSION"
            ):
                await update.message.reply_text(
                    "🤖 Mission started! Robot is navigating to first target...\n"
                    "Use /status to check progress."
                )
            else:
                await update.message.reply_text(
                    "⚠️ Warning: Could not reach state machine.\n"
                    "Make sure ROS nodes are running."
                )
            
            return ConversationHandler.END
        
        except Exception as e:
            print(f"ERROR in DXF upload: {e}")
            await update.message.reply_text(f"❌ Error: {e}")
            return ConversationHandler.END
    
    def _parse_cad_file(self, dxf_path, output_path):
        """Call cad_to_json.py to parse DXF"""
        try:
            result = subprocess.run(
                ["python3", CONFIG["cad_to_json_script"], dxf_path, "-o", output_path],
                capture_output=True,
                timeout=30,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✓ CAD parsing successful")
                return True
            else:
                print(f"CAD parsing failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"ERROR: CAD parsing error: {e}")
            return False
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            # Try to load mission
            if not self.mission_file.exists():
                await update.message.reply_text(
                    "📊 No active mission. Use /run to upload a site plan."
                )
                return
            
            with open(self.mission_file, 'r') as f:
                mission = json.load(f)
            
            # Try to load report
            report = None
            if self.report_file.exists():
                with open(self.report_file, 'r') as f:
                    report = json.load(f)
            
            # Build status message
            targets = mission.get("targets", [])
            status_msg = f"""
📊 *Mission Status*

*Targets:* {len(targets)}
"""
            
            if report:
                summary = report.get("summary", {})
                status_msg += f"""
✅ Completed: {summary.get('completed', 0)}/{len(targets)}
🟢 Passed: {summary.get('passed', 0)}
🔴 Failed: {summary.get('failed', 0)}
🟡 Warnings: {summary.get('warnings', 0)}

Last update: {summary.get('start_time', 'N/A')}
"""
            else:
                status_msg += "\n⏳ Mission in progress..."
            
            await update.message.reply_text(status_msg, parse_mode="Markdown")
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    
    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command"""
        try:
            if not self.report_file.exists():
                await update.message.reply_text(
                    "📄 Report not ready yet. Mission may still be in progress.\n"
                    "Use /status to check."
                )
                return
            
            # Generate PDF
            await update.message.reply_text(
                "📄 Generating PDF report..."
            )
            
            pdf_path = self._generate_pdf_report()
            
            if pdf_path and Path(pdf_path).exists():
                # Send PDF
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=pdf_file,
                        filename="SiteSentry_Inspection_Report.pdf"
                    )
                
                # Send JSON report as text
                with open(self.report_file, 'r') as f:
                    report = json.load(f)
                
                summary = report.get("summary", {})
                report_text = f"""
✅ *Inspection Complete*

📊 *Summary:*
  • Total Targets: {summary.get('total_targets', 0)}
  • Completed: {summary.get('completed', 0)}
  • Passed: {summary.get('passed', 0)}
  • Failed: {summary.get('failed', 0)}
  • Warnings: {summary.get('warnings', 0)}

📋 Detailed report has been sent above (PDF).
Raw data (JSON) available in system.
"""
                
                await update.message.reply_text(report_text, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "❌ Failed to generate PDF report."
                )
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    
    def _generate_pdf_report(self):
        """Call report_generator.py to create PDF"""
        try:
            output_path = Path(CONFIG["dxf_upload_dir"]) / "SiteSentry_Report.pdf"
            
            result = subprocess.run(
                ["python3", CONFIG["report_generator_script"],
                 str(self.report_file), "-o", str(output_path)],
                capture_output=True,
                timeout=60,
                text=True
            )
            
            if result.returncode == 0 and output_path.exists():
                return str(output_path)
            else:
                print(f"Report generation failed: {result.stderr}")
                return None
        except Exception as e:
            print(f"ERROR: Report generation error: {e}")
            return None
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await self.cmd_start(update, context)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation"""
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        print(f"ERROR: {context.error}")
    
    def setup_handlers(self):
        """Setup message handlers"""
        # Conversation handler for DXF upload
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("run", self.cmd_run)],
            states={
                WAITING_FOR_DXF: [
                    MessageHandler(filters.Document.FileExtension("dxf"), self.handle_dxf_upload),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_dxf_upload),
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("report", self.cmd_report))
        self.app.add_handler(conv_handler)
        
        self.app.add_error_handler(self.error_handler)
    
    async def run(self):
        """Start the bot"""
        self.app = Application.builder().token(self.token).build()
        self.setup_handlers()
        
        print("🤖 SiteSentry Telegram Bot started")
        
        # Start bot
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

def main():
    bot = SiteSentryBot()
    asyncio.run(bot.run())

if __name__ == "__main__":
    main()
