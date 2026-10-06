"""
agent_react.py - Cài đặt Agent theo mẫu thiết kế ReAct (Reasoning + Acting)
Tuân thủ Slide 18, 19, 20, 21 trong SE373 Buổi 3:
- Vòng lặp: Suy luận (Thought) -> Hành động (Action) -> Quan sát (Observation) -> Suy luận tiếp
- Dữ kiện môi trường đi vào giữa chuỗi suy luận
- Kết nối chặt chẽ với AgentHarness để kiểm soát quyền hạn, lặp và điều kiện dừng
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import mock_tools
from harness import AgentHarness, FlightConstraints
from llm_factory import extract_text_content

REACT_SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên đặt vé máy bay thông minh theo chu trình ReAct.
Mục tiêu: Tự chủ hoàn tất quy trình đặt vé máy bay theo đúng yêu cầu của người dùng.

Quy tắc tự chủ:
- Khi tìm thấy các chuyến bay phù hợp, hãy tự động chọn chuyến bay tốt nhất (ưu tiên chuyến bay buổi sáng thỏa mãn điều kiện và có giá rẻ nhất).
- Tiếp tục gọi check_seat -> book_seat -> pay để hoàn tất đặt vé.
- KHÔNG dừng lại hỏi người dùng trừ khi không tìm thấy chuyến bay nào.

QUY TẮC REACTION BẮT BUỘC:
1. Mỗi lượt bạn CHỈ ĐƯỢC sinh đúng 1 cặp Thought, Action và Action Input.
2. DỪNG LẠI NGAY LẬP TỨC sau khi sinh Action Input.
3. TUYỆT ĐỐI KHÔNG tự viết từ khóa 'Observation:' và KHÔNG tự bịa ra kết quả! Hệ thống sẽ thực thi tool thực tế và gửi lại Observation thật cho bạn.

Các công cụ có sẵn:
1. search_flights(origin, destination, date): Tìm chuyến bay (ngày định dạng YYYY-MM-DD).
2. check_seat(flight_id): Kiểm tra chỗ trống và giá vé của chuyến bay.
3. book_seat(flight_id, seat_number, passenger_name): Đặt giữ chỗ vé máy bay.
4. pay(booking_code, payment_method): Thanh toán vé máy bay để xác nhận thành công.

Quy trình suy luận ReAct bắt buộc theo định dạng:
Thought: <Phân tích tình hình hiện tại và suy nghĩ bước tiếp theo>
Action: <Tên công cụ: search_flights, check_seat, book_seat, hoặc pay>
Action Input: <Tham số JSON cho công cụ>

Chỉ khi nào đã thanh toán (pay) thành công thì mới được trả lời:
Final Answer: <Tóm tắt mã vé đã đặt thành công>
"""

class ReActFlightAgent:
    def __init__(self, llm, harness: Optional[AgentHarness] = None):
        self.llm = llm
        self.harness = harness or AgentHarness()
        self.tool_map = {
            "search_flights": mock_tools.search_flights,
            "check_seat": mock_tools.check_seat,
            "book_seat": mock_tools.book_seat,
            "pay": mock_tools.pay,
            "get_booking": mock_tools.get_booking
        }

    def _parse_action(self, response: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        # 1. Kiểm tra native tool_calls nếu có
        if hasattr(response, "tool_calls") and response.tool_calls:
            tc = response.tool_calls[0]
            return tc.get("name"), tc.get("args", {}), None

        raw_text = extract_text_content(response)
        # Cắt bỏ phần bịa đặt Observation nếu model lỡ sinh vượt lượt (Slide 58, 60)
        text = re.split(r"\nObservation:", raw_text, flags=re.IGNORECASE)[0].strip()

        action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)", text, re.IGNORECASE)
        tool_name = action_match.group(1).strip() if action_match else None

        # Trích xuất JSON từ Action Input (kể cả khi model bọc trong ```json ... ```)
        input_match = re.search(r"Action Input:\s*```(?:json)?\s*({.*?})\s*```", text, re.DOTALL | re.IGNORECASE)
        if not input_match:
            input_match = re.search(r"Action Input:\s*({.*?})", text, re.DOTALL | re.IGNORECASE)

        tool_args = {}
        if input_match:
            try:
                tool_args = json.loads(input_match.group(1).strip())
            except Exception:
                pass

        final_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
        final_answer = final_match.group(1).strip() if final_match else None
        return tool_name, tool_args, final_answer

    def run(self, user_goal: str) -> Dict[str, Any]:
        """Thực thi chu trình ReAct gửi lại toàn bộ lịch sử (Slide 21)"""
        self.harness.start_session()
        
        # Ngữ cảnh tích lũy theo chu trình ReAct chuẩn (Slide 20, 21)
        react_prompt = f"{REACT_SYSTEM_PROMPT}\n\nYêu cầu của người dùng: {user_goal}\n"

        trace_logs = []
        progress_score = 0  # Đại lượng tiến triển để LoopDetector theo dõi

        while not self.harness.terminated:
            # 1. Gọi model sinh suy luận & hành động
            response = self.llm.invoke(react_prompt)
            content = extract_text_content(response)

            # Nếu model trả về chuỗi rỗng do sự cố MALFORMED_RESPONSE, thử nhắc lại 1 lần
            if not content.strip():
                retry_prompt = react_prompt + "\nHãy tiếp tục bước kế tiếp. Viết rõ Thought, Action và Action Input:"
                try:
                    response = self.llm.invoke(retry_prompt)
                    content = extract_text_content(response)
                except Exception:
                    pass

            tool_name, tool_args, final_answer = self._parse_action(response)

            log_entry = {
                "turn": self.harness.turn_count + 1,
                "thought_content": content,
                "tool_called": tool_name,
                "tool_args": tool_args
            }

            # Nếu mô hình tuyên bố Final Answer hoặc không gọi tool
            if not tool_name:
                if final_answer:
                    log_entry["status"] = "Model tuyên bố hoàn thành"
                else:
                    log_entry["status"] = "Model không đề xuất tool nào"
                trace_logs.append(log_entry)
                break

            # 2. Checklist #0: Harness kiểm tra quyền trước khi chạy tool (Slide 35, 41)
            allowed, reason, prompt_q = self.harness.pre_tool_check(tool_name, tool_args)
            if not allowed:
                log_entry["status"] = f"Harness chặn lại: {reason}"
                log_entry["handoff_report"] = self.harness.generate_handoff_report(prompt_q or reason)
                trace_logs.append(log_entry)
                break

            # 3. Thực thi tool
            tool_fn = self.tool_map.get(tool_name)
            if not tool_fn:
                observation = json.dumps({"status": "error", "message": f"Tool '{tool_name}' không tồn tại."})
            else:
                try:
                    observation = tool_fn(**tool_args)
                except Exception as e:
                    observation = json.dumps({"status": "error", "message": str(e)})

            # Cập nhật đại lượng tiến triển
            if tool_name == "search_flights" and "flights" in observation:
                progress_score = max(progress_score, 1)
            elif tool_name == "book_seat" and "held" in observation:
                progress_score = max(progress_score, 2)
            elif tool_name == "pay" and "confirmed" in observation:
                progress_score = max(progress_score, 3)

            # 4. Checklist #1, #2, #3, #4: Harness kiểm tra sau khi có Observation (Slide 35)
            harness_ok, step_status = self.harness.post_tool_check(tool_name, tool_args, observation, progress_metric=progress_score)
            log_entry["observation"] = observation
            log_entry["harness_check"] = step_status
            trace_logs.append(log_entry)

            if not harness_ok:
                # Bị ngắt do lặp hoặc bế tắc
                log_entry["handoff_report"] = self.harness.generate_handoff_report(self.harness.termination_reason)
                break

            if step_status == "COMPLETED":
                # Sensor computational xác nhận hoàn thành
                break

            # 5. Tích lũy chuỗi ReAct cho vòng suy luận tiếp theo (Slide 20, 21)
            clean_content = re.split(r"\nObservation:", content, flags=re.IGNORECASE)[0].strip()
            react_prompt += f"\n{clean_content}\nObservation: {observation}\n"

        return {
            "agent_type": "ReAct",
            "success": self.harness.termination_type.startswith("Đạt mục tiêu"),
            "turns": self.harness.turn_count,
            "termination_type": self.harness.termination_type,
            "termination_reason": self.harness.termination_reason,
            "trace_logs": trace_logs,
            "booking_code": self.harness.active_booking_code
        }
