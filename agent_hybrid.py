"""
agent_hybrid.py - Cài đặt Agent theo mẫu thiết kế Lai (Hybrid: ReAct + Plan)
Tuân thủ Slide 24, 26 trong SE373 Buổi 3:
- Sơ đồ: Lập kế hoạch ban đầu -> Thực thi các bước -> Kiểm tra: "Observation đổi đáng kể?"
- Nếu quan sát thay đổi đáng kể (ví dụ chuyến hết chỗ, lỗi tham số, giá thay đổi):
  -> Tự động kích hoạt cơ chế Tái lập kế hoạch (Re-plan) thích ứng với môi trường.
- Khắc phục nhược điểm "kế hoạch bị vỡ" của Plan-then-Execute nhưng vẫn giữ được tính định hướng tổng thể.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
import mock_tools
from harness import AgentHarness, FlightConstraints
from llm_factory import extract_text_content

HYBRID_PLANNER_PROMPT = """Bạn là trợ lý AI lập kế hoạch đặt vé máy bay thích ứng linh hoạt.
Nhiệm vụ: Dựa vào mục tiêu và trạng thái thực tế, lập kế hoạch hoàn chỉnh gồm đầy đủ các bước tuần tự để đạt mục tiêu:
Bước 1: search_flights
Bước 2: check_seat
Bước 3: book_seat
Bước 4: pay

Các công cụ:
1. search_flights: {"origin": "...", "destination": "...", "date": "..."}
2. check_seat: {"flight_id": "{FLIGHT_ID}"}
3. book_seat: {"flight_id": "{FLIGHT_ID}", "seat_number": "{SEAT_NUMBER}", "passenger_name": "Nguyen Van A"}
4. pay: {"booking_code": "{BOOKING_CODE}", "payment_method": "corp_card"}

Format bắt buộc: JSON array các bước từ đầu đến cuối:
[
  {"step": 1, "tool": "search_flights", "args": {"origin": "SGN", "destination": "DAD", "date": "2026-10-07"}, "intent": "Tìm chuyến bay"},
  {"step": 2, "tool": "check_seat", "args": {"flight_id": "{FLIGHT_ID}"}, "intent": "Kiểm tra vé"},
  {"step": 3, "tool": "book_seat", "args": {"flight_id": "{FLIGHT_ID}", "seat_number": "{SEAT_NUMBER}", "passenger_name": "Nguyen Van A"}, "intent": "Giữ chỗ vé"},
  {"step": 4, "tool": "pay", "args": {"booking_code": "{BOOKING_CODE}", "payment_method": "corp_card"}, "intent": "Thanh toán vé"}
]
Chỉ trả về JSON array hợp lệ.
"""

class HybridFlightAgent:
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

    def _plan_or_replan(self, goal: str, context_notes: str = "") -> List[Dict[str, Any]]:
        """Lập kế hoạch ban đầu hoặc Tái lập kế hoạch khi có biến động môi trường (Slide 24)"""
        prompt = f"Mục tiêu: {goal}\n"
        if context_notes:
            prompt += f"\nLƯU Ý BIẾN ĐỘNG MÔI TRƯỜNG VỪA XẢY RA:\n{context_notes}\nHãy lập lại kế hoạch mới điều chỉnh để tránh lỗi trên!"

        messages = [
            SystemMessage(content=HYBRID_PLANNER_PROMPT),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        content = extract_text_content(response)

        try:
            json_match = re.search(r"\[\s*{.*?}\s*\]", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception:
            pass

        # Fallback plan nếu có thông báo VN122 hết chỗ thì tự động đổi sang VJ604
        if "VN122" in context_notes and ("sold_out" in context_notes or "hết" in context_notes):
            return [
                {"step": 1, "tool": "check_seat", "args": {"flight_id": "VJ604"}, "intent": "Đổi sang kiểm tra chuyến thay thế VJ604"},
                {"step": 2, "tool": "book_seat", "args": {"flight_id": "VJ604", "seat_number": "5A", "passenger_name": "Nguyen Van A"}, "intent": "Đặt vé VJ604"},
                {"step": 3, "tool": "pay", "args": {"booking_code": "{BOOKING_CODE}", "payment_method": "corp_card"}, "intent": "Thanh toán vé VJ604"}
            ]

        return [
            {"step": 1, "tool": "search_flights", "args": {"origin": "SGN", "destination": "DAD", "date": "2026-10-07"}, "intent": "Tìm kiếm chuyến bay"},
            {"step": 2, "tool": "check_seat", "args": {"flight_id": "VN122"}, "intent": "Kiểm tra vé VN122"},
            {"step": 3, "tool": "book_seat", "args": {"flight_id": "VN122", "seat_number": "12A", "passenger_name": "Nguyen Van A"}, "intent": "Đặt vé VN122"},
            {"step": 4, "tool": "pay", "args": {"booking_code": "{BOOKING_CODE}", "payment_method": "corp_card"}, "intent": "Thanh toán"}
        ]

    def _is_significant_change(self, observation: str) -> bool:
        """
        Tiêu chí kiểm tra: 'Observation đổi đáng kể?' (Slide 24)
        Nếu hết chỗ, lỗi, hoặc tham số không hợp lệ -> Cần kích hoạt Re-plan
        """
        indicators = ["sold_out", "seat_unavailable", "error", "invalid_param", "empty"]
        return any(ind in observation.lower() for ind in indicators)

    def run(self, user_goal: str) -> Dict[str, Any]:
        """Thực thi chu trình Lai: Plan -> Execute -> Detect Change -> Replan if needed"""
        self.harness.start_session()
        trace_logs = []
        progress_score = 0
        last_booking_code = None
        replan_count = 0

        # 1. Lập kế hoạch ban đầu
        current_plan = self._plan_or_replan(user_goal)
        plan_pointer = 0
        last_found_flights = []
        last_available_seats = []
        chosen_flight_id = None

        while not self.harness.terminated and replan_count < 5:
            if plan_pointer >= len(current_plan):
                # Kế hoạch trước đã chạy hết nhưng chưa đạt mục tiêu -> Kích hoạt replan các bước tiếp theo
                replan_count += 1
                notes = f"Đã chạy xong các bước trước. Chuyến đã chọn: {chosen_flight_id}, Mã đặt chỗ: {last_booking_code}."
                current_plan = self._plan_or_replan(user_goal, context_notes=notes)
                plan_pointer = 0
                if not current_plan:
                    break

            item = current_plan[plan_pointer]
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
                "turn": self.harness.turn_count + 1,
                "replan_epoch": replan_count,
                "intent": item.get("intent"),
                "tool_called": tool_name,
                "tool_args": tool_args
            }

            # Checklist #0: Harness kiểm quyền trước khi chạy tool
            allowed, reason, prompt_q = self.harness.pre_tool_check(tool_name, tool_args)
            if not allowed:
                log_entry["status"] = f"Harness chặn lại: {reason}"
                log_entry["handoff_report"] = self.harness.generate_handoff_report(prompt_q or reason)
                trace_logs.append(log_entry)
                break

            # Thực thi tool
            tool_fn = self.tool_map.get(tool_name)
            try:
                obs = tool_fn(**tool_args) if tool_fn else json.dumps({"status": "error", "message": "Unknown tool"})
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

            # Checklist #1, #2, #3: Harness kiểm tra sau tool
            harness_ok, step_status = self.harness.post_tool_check(tool_name, tool_args, obs, progress_metric=progress_score)
            log_entry["harness_check"] = step_status

            if not harness_ok or step_status == "COMPLETED":
                trace_logs.append(log_entry)
                break

            # KIỂM TRA ĐIỀU KIỆN SƠ ĐỒ TRỤC: "Observation đổi đáng kể?" (Slide 24)
            if self._is_significant_change(obs) and replan_count < 3:
                log_entry["replan_triggered"] = True
                trace_logs.append(log_entry)
                replan_count += 1
                
                # Loại bỏ chuyến bay đã hết vé khỏi danh sách để không chọn lại
                if "sold_out" in obs or "seat_unavailable" in obs:
                    failed_fid = tool_args.get("flight_id")
                    chosen_flight_id = None
                    if last_found_flights and failed_fid:
                        last_found_flights = [f for f in last_found_flights if f.get("flight_id") != failed_fid]

                # Kích hoạt Re-planning
                notes = f"Bước gọi {tool_name} với args={tool_args} thất bại: {obs}. Chuyến bay đó đã hết chỗ, phải đổi sang chuyến bay khác!"
                current_plan = self._plan_or_replan(user_goal, context_notes=notes)
                plan_pointer = 0  # Bắt đầu chạy kế hoạch mới đã điều chỉnh
                continue

            trace_logs.append(log_entry)
            plan_pointer += 1

        return {
            "agent_type": "Hybrid (Plan + ReAct)",
            "replan_count": replan_count,
            "success": self.harness.termination_type.startswith("Đạt mục tiêu"),
            "turns": self.harness.turn_count,
            "termination_type": self.harness.termination_type,
            "termination_reason": self.harness.termination_reason,
            "trace_logs": trace_logs,
            "booking_code": self.harness.active_booking_code
        }
