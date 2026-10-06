import sys
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
print("--- Response 1 ---")
print("r1.content:", r1.content)
print("r1.additional_kwargs:", getattr(r1, "additional_kwargs", None))
print("r1.response_metadata:", getattr(r1, "response_metadata", None))

text1 = extract_text_content(r1)
messages.append(AIMessage(content=text1))
obs = '{"status": "ok", "total": 4, "flights": [{"flight_id": "VN122", "airline": "Vietnam Airlines", "depart_time": "08:10", "price": 1850000, "seats_count": 3, "refundable": false}]}'
messages.append(HumanMessage(content=f"Observation: {obs}\nHãy suy luận Thought tiếp theo và đề xuất Action / Action Input."))

r2 = llm.invoke(messages)
print("\n--- Response 2 ---")
print("r2.content:", r2.content)
print("r2.additional_kwargs:", getattr(r2, "additional_kwargs", None))
print("r2.response_metadata:", getattr(r2, "response_metadata", None))
