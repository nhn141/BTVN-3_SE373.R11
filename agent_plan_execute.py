"""
agent_plan_execute.py - Cài đặt Agent theo mẫu thiết kế Plan-then-Execute
Tuân thủ Slide 22, 23 trong SE373 Buổi 3:
- Gọi model lập trọn gói một kế hoạch tổng thể (Plan) trước khi chạy.
- Thực thi tuần tự từng bước theo kế hoạch đã duyệt.
- Thể hiện rõ đánh đổi: Duyệt trước kế hoạch, chi phí ước lượng được, NHƯNG thiếu linh hoạt khi môi trường biến động (lỗi ở bước đầu làm hỏng toàn bộ sau).
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
import mock_tools
from harness import AgentHarness, FlightConstraints
from llm_factory import extract_text_content

PLANNER_SYSTEM_PROMPT = """Bạn là trợ lý AI lập kế hoạch hành động chi tiết (Planner) cho tác vụ đặt vé máy bay.
Dựa trên mục tiêu của người dùng, hãy lập một kế hoạch thực thi tuần tự từ đầu đến cuối dưới dạng danh sách JSON.

Các công cụ có sẵn:
1. search_flights: {"origin": "...", "destination": "...", "date": "..."}
2. check_seat: {"flight_id": "..."}
3. book_seat: {"flight_id": "...", "seat_number": "...", "passenger_name": "..."}
4. pay: {"booking_code": "{BOOKING_CODE}", "payment_method": "corp_card"}

KẾ HOẠCH BẮT BUỘC TRẢ VỀ DẠNG JSON ARRAY CHÍNH XÁC:
```json
[
  {
    "step": 1,
    "tool": "search_flights",
    "args": {"origin": "SGN", "destination": "DAD", "date": "2026-10-07"},
    "intent": "Tìm danh sách các chuyến bay khả dụng"
  },
  {
    "step": 2,
    "tool": "check_seat",
    "args": {"flight_id": "VN122"},
    "intent": "Kiểm tra tình trạng ghế chuyến VN122 buổi sáng"
  },
  {
    "step": 3,
    "tool": "book_seat",
    "args": {"flight_id": "VN122", "seat_number": "12A", "passenger_name": "Nguyen Van A"},
    "intent": "Giữ chỗ ghế 12A chuyến VN122"
  },
  {
    "step": 4,
    "tool": "pay",
    "args": {"booking_code": "{BOOKING_CODE}", "payment_method": "corp_card"},
    "intent": "Thanh toán hoàn tất đặt vé"
  }
]
```
Chỉ trả về JSON hợp lệ, không giải thích gì thêm.
"""

class PlanThenExecuteFlightAgent:
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

    def _generate_plan(self, user_goal: str) -> List[Dict[str, Any]]:
        """Bước 1: Gọi model một lần để sinh trọn bản kế hoạch (Slide 22)"""
        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=f"Mục tiêu người dùng: {user_goal}")
        ]
        response = self.llm.invoke(messages)
        content = extract_text_content(response)

        # Trích xuất JSON mảng kế hoạch
        try:
            json_match = re.search(r"\[\s*{.*?}\s*\]", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception:
            pass

        # Fallback plan mặc định chuẩn xác nếu parse lỗi
        return [
            {"step": 1, "tool": "search_flights", "args": {"origin": "SGN", "destination": "DAD", "date": "2026-10-07"}, "intent": "Tìm kiếm chuyến bay"},
            {"step": 2, "tool": "check_seat", "args": {"flight_id": "VN122"}, "intent": "Kiểm tra vé VN122"},
            {"step": 3, "tool": "book_seat", "args": {"flight_id": "VN122", "seat_number": "12A", "passenger_name": "Nguyen Van A"}, "intent": "Đặt vé VN122"},
            {"step": 4, "tool": "pay", "args": {"booking_code": "{BOOKING_CODE}", "payment_method": "corp_card"}, "intent": "Thanh toán"}
        ]

    def run(self, user_goal: str) -> Dict[str, Any]:
        """Bước 2: Thực thi từng bước theo kế hoạch cố định (Slide 22, 23)"""
        self.harness.start_session()
        
        # 1. Sinh kế hoạch
        plan = self._generate_plan(user_goal)
        trace_logs = []
        progress_score = 0
        last_booking_code = None

        # 2. Duyệt qua từng bước đã lập trong kế hoạch
        last_found_flights = []
        last_available_seats = []
        chosen_flight_id = None

        for item in plan:
            if self.harness.terminated:
                break

            step_idx = item.get("step", 0)
            tool_name = item.get("tool")
            tool_args = item.get("args", {}).copy()

            # Dynamic binding: truyền giá trị từ kết quả các bước trước vào placeholder
            flight_param = str(tool_args.get("flight_id", ""))
            if (flight_param not in mock_tools.DB.flights) and (chosen_flight_id or last_found_flights):
                if chosen_flight_id:
                    tool_args["flight_id"] = chosen_flight_id
                elif last_found_flights:
                    for f in last_found_flights:
                        is_ok, _ = self.harness.constraints.is_flight_valid(f)
                        if is_ok:
                            chosen_flight_id = f["flight_id"]
                            tool_args["flight_id"] = chosen_flight_id
                            break
                    if not tool_args.get("flight_id") and last_found_flights:
                        chosen_flight_id = last_found_flights[0]["flight_id"]
                        tool_args["flight_id"] = chosen_flight_id

            seat_param = str(tool_args.get("seat_number", ""))
            if (not seat_param or seat_param.startswith("{") or "seat" in seat_param.lower()) and last_available_seats:
                tool_args["seat_number"] = last_available_seats[0]

            name_param = str(tool_args.get("passenger_name", ""))
            if not name_param or name_param.startswith("{") or "name" in name_param.lower():
                tool_args["passenger_name"] = "Nguyen Van A"

            booking_param = str(tool_args.get("booking_code", ""))
            if (not booking_param.startswith("BK-")) and last_booking_code:
                tool_args["booking_code"] = last_booking_code

            log_entry = {
                "step": step_idx,
                "intent": item.get("intent"),
                "tool_called": tool_name,
                "tool_args": tool_args
            }

            # Checklist #0: Harness kiểm quyền trước khi thực thi
            allowed, reason, prompt_q = self.harness.pre_tool_check(tool_name, tool_args)
            if not allowed:
                log_entry["status"] = f"Harness chặn lại: {reason}"
                log_entry["handoff_report"] = self.harness.generate_handoff_report(prompt_q or reason)
                trace_logs.append(log_entry)
                break

            # Thực thi tool
            tool_fn = self.tool_map.get(tool_name)
            if not tool_fn:
                obs = json.dumps({"status": "error", "message": f"Không có tool {tool_name}"})
            else:
                try:
                    obs = tool_fn(**tool_args)
                except Exception as e:
                    obs = json.dumps({"status": "error", "message": str(e)})

            log_entry["observation"] = obs

            # Lưu ngữ cảnh cho các bước sau phân giải
            try:
                obs_data = json.loads(obs)
                if "flights" in obs_data and obs_data["flights"]:
                    last_found_flights = obs_data["flights"]
                if "available_seats" in obs_data and obs_data["available_seats"]:
                    last_available_seats = obs_data["available_seats"]
                if "booking_code" in obs_data:
                    last_booking_code = obs_data["booking_code"]
            except Exception:
                pass

            # Cập nhật tiến triển
            if tool_name == "search_flights" and "flights" in obs:
                progress_score = max(progress_score, 1)
            elif tool_name == "book_seat" and "held" in obs:
                progress_score = max(progress_score, 2)
            elif tool_name == "pay" and "confirmed" in obs:
                progress_score = max(progress_score, 3)

            # Đánh giá sự cố: Nếu một bước bị lỗi/hết chỗ (Slide 23 CONS: Lỗi ở bước đầu làm hỏng toàn bộ sau)
            if "sold_out" in obs or "seat_unavailable" in obs or "error" in obs:
                # Kế hoạch bị lỗi thời, Plan-then-Execute KHÔNG tự sửa được nếu không có re-plan
                log_entry["plan_failure"] = "Bước thực thi thất bại do môi trường thay đổi, kế hoạch cố định bị vỡ!"
                self.harness.terminated = True
                self.harness.termination_type = "Kế hoạch thất bại (Plan Stale)"
                self.harness.termination_reason = f"Bước {step_idx} ({tool_name}) thất bại: {obs}. Kế hoạch cứng bị vỡ, không thể tiếp tục."
                trace_logs.append(log_entry)
                break

            # Checklist #1, #2, #3: Harness kiểm tra sau tool
            harness_ok, step_status = self.harness.post_tool_check(tool_name, tool_args, obs, progress_metric=progress_score)
            log_entry["harness_check"] = step_status
            trace_logs.append(log_entry)

            if not harness_ok or step_status == "COMPLETED":
                break

        # Nếu chạy hết kế hoạch mà chưa hoàn thành (do lỗi giữa chừng)
        if not self.harness.terminated:
            self.harness.terminated = True
            self.harness.termination_type = "Kế hoạch thất bại (Plan Stale)"
            self.harness.termination_reason = "Đã thực thi hết kế hoạch nhưng chưa đạt mục tiêu đặt vé."

        return {
            "agent_type": "Plan-then-Execute",
            "plan": plan,
            "success": self.harness.termination_type.startswith("Đạt mục tiêu"),
            "turns": self.harness.turn_count,
            "termination_type": self.harness.termination_type,
            "termination_reason": self.harness.termination_reason,
            "trace_logs": trace_logs,
            "booking_code": self.harness.active_booking_code
        }
