import os
import json
import base64
import time
from groq import Groq
from dotenv import load_dotenv

# 1. إعداد الاتصال
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def run_sync():
    queue_file = 'offline_queue.json'
    report_file = 'final_site_report.json'

    # التحقق من وجود الطابور والتقرير
    if not os.path.exists(queue_file) or not os.path.exists(report_file):
        print("✅ No pending data to sync. Everything is up to date.")
        return

    with open(queue_file, 'r') as f:
        queue_data = json.load(f)

    if len(queue_data) == 0:
        print("✅ Offline queue is empty. Nothing to sync.")
        return

    with open(report_file, 'r') as f:
        report_data = json.load(f)

    print(f"🔄 Found {len(queue_data)} pending items. Starting cloud sync...")
    
    remaining_queue = [] # لحفظ العناصر التي قد تفشل مرة أخرى
    sync_count = 0

    # 2. معالجة كل عنصر في الطابور
    for task in queue_data:
        target_id = task['id']
        image_path = task['image']
        print(f"Uploading and analyzing {target_id}...")

        try:
            base64_image = encode_image(image_path)
            prompt = (
                f"You are a QA Engineer checking Target ID: {target_id}. "
                f"Verify if the socket box is installed based on this offline image. "
                f"Keep it concise. Format:\n"
                f"- **Status:** [Pass/Warning/Fail]\n"
                f"- **Details:** [Explanation]\n"
                f"- **Defects:** [List defects or 'None']"
            )

            # طلب الـ API
            response = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}],
                timeout=15 # ننتظر 15 ثانية للرفع
            )
            ai_analysis = response.choices[0].message.content

            # 3. تحديث التقرير الرئيسي
            for item in report_data['details']:
                if item['id'] == target_id:
                    # نحدث الحالة بناءً على رد الذكاء الاصطناعي
                    if "Fail" in ai_analysis:
                        item['status'] = "Issue Detected"
                    elif "Warning" in ai_analysis:
                        item['status'] = "Warning"
                    else:
                        item['status'] = "Verified"
                        
                    item['ai_report'] = f"[SYNCED OFFLINE] {ai_analysis}"
                    break
            
            sync_count += 1
            print(f"✔️ {target_id} synced successfully!")

        except Exception as e:
            print(f"❌ Failed to sync {target_id}. Will try again later. Error: {str(e)}")
            remaining_queue.append(task) # إعادته للطابور إذا فشل الإنترنت مجدداً

    # 4. تحديث ملخص التقرير (عدد المقابس المكتملة)
    if sync_count > 0:
        completed_count = len([r for r in report_data['details'] if r['status'] in ['Verified', 'Issue Detected', 'Warning']])
        report_data['summary']['completed'] = completed_count
        report_data['summary']['last_sync'] = time.ctime()

        # حفظ التقرير المحدث
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=4)

    # 5. حفظ الطابور الجديد (فارغ إذا نجح الكل، أو يحتوي على الفاشلين)
    with open(queue_file, 'w') as f:
        json.dump(remaining_queue, f, indent=4)

    print(f"\n🚀 Sync Complete: {sync_count} items uploaded to the cloud.")

if __name__ == "__main__":
    run_sync()