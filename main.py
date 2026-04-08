from google import genai

# Your verified working key
API_KEY = "AIzaSyBetTv86zaTGNbcxINPARXAmb5-wIW3Nt4"

# Initialize client
client = genai.Client(api_key=API_KEY)


# Professional English comments for SiteSentry logic
def run_sitesentry_check():
    try:
        # Using the model that worked for you: gemini-3-flash-preview
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Confirm your role as SiteSentry AI and give me a tip for wall inspection.",
            config={
                'system_instruction': "You are the AI brain of SiteSentry, a construction inspection robot. Be technical and precise."
            }
        )

        print("--- Robot Status ---")
        print(response.text)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    run_sitesentry_check()