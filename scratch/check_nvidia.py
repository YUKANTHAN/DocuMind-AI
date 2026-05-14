import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

try:
    print("Checking NVIDIA NIM models...")
    models = client.models.list()
    for m in models.data[:5]:
        print(f"- {m.id}")
except Exception as e:
    print(f"Error: {e}")
