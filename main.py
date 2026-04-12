import os
from google import genai
from dotenv import load_dotenv # 1. Import the loader

# 2. Load the variables from the .env file
load_dotenv()

# 3. Get the key from the environment variable
api_key = os.getenv("GEMINI_API_KEY")

# 4. Setup the Client using the variable
client = genai.Client(api_key=api_key)

def test_connection():
    print("Connecting to Gemini AI using hidden key...")
    response = client.models.generate_content(
       model="gemini-2.0-flash",
        contents="Hello Gemini! This is Sami. Confirm if the system is ready."
    )
    print("\n--- AI RESPONSE ---")
    print(response.text)

if __name__ == "__main__":
    test_connection()