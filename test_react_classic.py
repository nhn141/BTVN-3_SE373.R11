import os
import sys
from dotenv import load_dotenv
load_dotenv(override=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from llm_factory import create_chat_model, extract_text_content

llm = create_chat_model()

system_instructions = """Bạn là trợ lý AI tự chủ đặt vé máy bay theo chu trình ReAct.
Mục tiêu: Hoàn tất toàn bộ quy trình đặt vé máy bay thỏa mãn yêu cầu của người dùng.
Quy tắc tự chủ: Khi tìm thấy các chuyến bay phù hợp, hãy tự động chọn chuyến bay tốt nhất (ưu tiên giá rẻ nhất trong các chuyến bay sáng), sau đó gọi check_seat, book_seat và pay. Không hỏi lại người dùng giữa chừng.

Các công cụ có sẵn:
- search_flights(origin, destination, date)
- check_seat(flight_id)
- book_seat(flight_id, seat_number, passenger_name)
- pay(booking_code, payment_method)

Định dạng trả lời bắt buộc:
Thought: <suy luận của bạn>
Action: <tên công cụ duy nhất trong 4 công cụ trên>
Action Input: <JSON tham số>
Hoặc khi đã hoàn tất thanh toán:
Final Answer: <thông tin vé đã đặt thành công>
"""

history = f"""{system_instructions}

Yêu cầu người dùng: Đặt giúp tôi vé máy bay từ SGN đi DAD vào sáng ngày 2026-10-07, giá dưới 2.000.000đ.

Thought: Tôi cần tìm các chuyến bay từ SGN đi DAD vào sáng ngày 2026-10-07 dưới 2 triệu.
Action: search_flights
Action Input: {{"origin": "SGN", "destination": "DAD", "date": "2026-10-07"}}
Observation: {{"status": "ok", "total": 2, "flights": [{{"flight_id": "VN122", "price": 1850000, "depart_time": "08:10", "seats_count": 3}}, {{"flight_id": "VJ604", "price": 1450000, "depart_time": "09:30", "seats_count": 2}}]}}
"""

res = llm.invoke(history)
print("Response text:\n", extract_text_content(res))
