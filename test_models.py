import os
import sys
from dotenv import load_dotenv
load_dotenv(override=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

prompt_conversation = [
    {"role": "user", "parts": [{"text": "Bạn là AI đặt vé. Người dùng: Đặt vé SGN đi DAD sáng 07/10 giá dưới 2tr. Hãy suy luận Thought và đề xuất Action / Action Input."}]},
    {"role": "model", "parts": [{"text": "Thought: Tôi cần tìm chuyến bay.\nAction: search_flights\nAction Input: {\"origin\": \"SGN\", \"destination\": \"DAD\", \"date\": \"2026-10-07\"}"}]},
    {"role": "user", "parts": [{"text": "Observation: Tìm thấy chuyến VN122 (08:10, 1.850.000đ, 3 ghế trống), VJ604 (09:30, 1.450.000đ). Hãy suy luận Thought và Action tiếp theo."}]}
]

for model_name in ["gemini-2.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite"]:
    try:
        res = client.models.generate_content(
            model=model_name,
            contents=prompt_conversation
        )
        cand = res.candidates[0]
        print(f"\n[Model: {model_name}]")
        print("FinishReason:", cand.finish_reason)
        print("Text:", cand.content.parts[0].text if cand.content and cand.content.parts else "EMPTY")
    except Exception as e:
        print(f"\n[Model: {model_name}] Lỗi: {e}")
