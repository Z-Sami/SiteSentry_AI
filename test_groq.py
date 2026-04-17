import os
import base64
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# تأكد من وجود الصورة في نفس المجلد
image_path = "test.png" 

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# تشغيل الفحص
base64_image = encode_image(image_path)

completion = client.chat.completions.create(
    model="meta-llama/llama-4-scout-17b-16e-instruct", # الموديل الجديد
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "You are looking at a wall from a side-mounted camera on a moving robot. Your goal is to find an electrical socket. Because the robot stops at a specific coordinate, the socket should be centered. If it is too far to the left or right, report the estimated displacement in centimeters."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ],
        }
    ],
)

print("\n--- SITESENTRY VISION REPORT ---")
print(completion.choices[0].message.content)