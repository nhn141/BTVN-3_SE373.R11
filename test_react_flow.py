import os
import sys
import json
from dotenv import load_dotenv
load_dotenv(override=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from llm_factory import create_chat_model, extract_text_content
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from agent_react import REACT_SYSTEM_PROMPT

llm = create_chat_model()
messages = [
    SystemMessage(content=REACT_SYSTEM_PROMPT),
    HumanMessage(content="Đặt giúp tôi vé máy bay từ SGN đi DAD vào sáng ngày 2026-10-07, giá dưới 2.000.000đ.")
]

r1 = llm.invoke(messages)
text1 = extract_text_content(r1)
print("Turn 1 content:", text1)
print("Turn 1 tool_calls:", getattr(r1, "tool_calls", None))

# Chuẩn hóa AI text có Action
ai_turn1 = f"{text1}\nAction: search_flights\nAction Input: {{\"origin\": \"SGN\", \"destination\": \"DAD\", \"date\": \"2026-10-07\"}}"
messages.append(AIMessage(content=ai_turn1))

obs = '{"status": "ok", "total": 4, "flights": [{"flight_id": "VN122", "airline": "Vietnam Airlines", "depart_time": "08:10", "price": 1850000, "seats_count": 3, "refundable": false}, {"flight_id": "VJ604", "airline": "Vietjet Air", "depart_time": "09:30", "price": 1450000, "seats_count": 2, "refundable": true}]}'
prompt_next = f"Observation: {obs}\n\nDựa vào kết quả trên, hãy tiếp tục bước tiếp theo theo đúng định dạng:\nThought: <suy luận chọn chuyến bay>\nAction: <tên công cụ: check_seat / book_seat / pay>\nAction Input: <JSON tham số>"
messages.append(HumanMessage(content=prompt_next))

r2 = llm.invoke(messages)
text2 = extract_text_content(r2)
print("\nTurn 2 content:", text2)
print("Turn 2 tool_calls:", getattr(r2, "tool_calls", None))
