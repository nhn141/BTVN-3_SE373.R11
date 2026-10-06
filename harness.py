"""
harness.py - Lớp Harness quản lý và giám sát Agent (Agent Harness)
Tuân thủ đầy đủ các Slide 10, 11, 15, 34, 35, 36, 41, 43, 44, 46, 48, 63 (SE373 Buổi 3):

Bao gồm 4 lớp Harness bắt buộc theo đề bài:
1. Ràng buộc là dữ liệu (Data Constraints - Slide 63)
2. Kiểm quyền trước khi gọi tool (Permission / Human Approval - Slide 35, 41)
3. Tiêu chí hoàn thành kiểm bằng code (Computational Sensor - Slide 36, 43, 44)
4. Bàn giao cho con người (Handoff Report trong 30s - Slide 48)

Kèm theo các cơ chế an toàn:
- Bộ phát hiện lặp và bế tắc (LoopDetector - Slide 46)
- Ngân sách cứng (Hard Limits: Max Turns, Tokens, Timeout - Slide 15, 38)
"""

import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from mock_tools import DB

@dataclass
class FlightConstraints:
    """
    Lớp 1: RÀNG BUỘC LÀ DỮ LIỆU (Slide 63)
    Ghi yêu cầu và ràng buộc thành dữ liệu cấu trúc, không phụ thuộc vào trí nhớ model.
    """
    origin: str = "SGN"
    destination: str = "DAD"
    date: str = "2026-10-07"
    depart_before: str = "12:00"      # Phải bay vào buổi sáng (< 12:00)
    max_price: int = 2_000_000        # Ngân sách trần của người dùng (2 triệu)

    def is_flight_valid(self, flight: Dict[str, Any]) -> Tuple[bool, str]:
        """Kiểm tra một chuyến bay có đáp ứng tiêu chí dữ liệu không"""
        if flight.get("price", 0) > self.max_price:
            return False, f"Giá {flight.get('price'):,}đ vượt trần ngân sách {self.max_price:,}đ."
        if flight.get("depart_time", "23:59") >= self.depart_before:
            return False, f"Giờ bay {flight.get('depart_time')} không trước {self.depart_before}."
        return True, "Thỏa mãn ràng buộc"


class PermissionManager:
    """
    Lớp 2: KIỂM QUYỀN TRƯỚC KHI THỰC THI TOOL (Slide 35, 41)
    Kiểm quyền chạy TRƯỚC khi thực thi tool.
    Nếu hành động vượt thẩm quyền (vượt hạn mức chi tiêu, không hoàn vé, thanh toán tiền),
    chặn lại và yêu cầu phê duyệt từ con người.
    """
    AUTONOMOUS_PRICE_LIMIT = 1_500_000  # Ngưỡng tự quyết định không cần hỏi (1.5 triệu)

    def __init__(self, auto_approve: bool = True):
        # auto_approve = True: Chế độ test tự động đồng ý sau khi ghi nhận log hỏi quyền
        # auto_approve = False: Chờ người dùng thực sự nhập Y/N
        self.auto_approve = auto_approve
        self.approval_history: List[Dict[str, Any]] = []

    def check_permission(self, tool_name: str, args: Dict[str, Any], current_context: Dict[str, Any] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Kiểm tra quyền hạn.
        Trả về: (được phép thi hành: bool, lý do: str, câu hỏi con người: Optional[str])
        """
        current_context = current_context or {}

        # 1. Kiểm tra thao tác thanh toán tiền thật (pay)
        if tool_name == "pay":
            booking_code = args.get("booking_code")
            booking = DB.bookings.get(booking_code, {})
            amount = booking.get("price", 0)
            reason = f"Thao tác thanh toán tiền ({amount:,}đ) là tác vụ nhạy cảm tài chính."
            question = f"Xác nhận thanh toán {amount:,}đ cho mã đặt chỗ {booking_code}?"
            
            self.approval_history.append({"tool": tool_name, "args": args, "reason": reason})
            if not self.auto_approve:
                return False, reason, question
            return True, "Approved (Auto/Human)", None

        # 2. Kiểm tra thao tác book_seat khi giá vượt hạn mức hoặc vé không hoàn tiền
        if tool_name == "book_seat":
            flight_id = args.get("flight_id", "")
            flight = DB.flights.get(flight_id, {})
            price = flight.get("price", 0)
            refundable = flight.get("refundable", True)

            requires_approval = False
            reasons = []

            if price > self.AUTONOMOUS_PRICE_LIMIT:
                requires_approval = True
                reasons.append(f"Giá {price:,}đ vượt hạn mức tự chủ {self.AUTONOMOUS_PRICE_LIMIT:,}đ")

            if not refundable:
                requires_approval = True
                reasons.append("Vé loại không được hoàn trả (non-refundable)")

            if requires_approval:
                full_reason = " và ".join(reasons)
                question = f"Chuyến {flight_id} có {full_reason}. Bạn có duyệt đặt ghế {args.get('seat_number')} không?"
                self.approval_history.append({"tool": tool_name, "args": args, "reason": full_reason})
                
                if not self.auto_approve:
                    return False, full_reason, question
                return True, f"Approved ({full_reason})", None

        return True, "Hành động trong thẩm quyền cho phép", None


class ComputationalSensor:
    """
    Lớp 3: TIÊU CHÍ HOÀN THÀNH KIỂM BẰNG CODE (Slide 36, 43, 44)
    Vị từ chạy bằng code khách quan (Computational Sensor), độc lập hoàn toàn với việc model tự tuyên bố.
    """
    @staticmethod
    def is_booking_completed(booking_code: Optional[str], constraints: FlightConstraints) -> Tuple[bool, str]:
        """
        Code kiểm tra theo đúng công thức Slide 43:
        get_booking(code).status == 'confirmed' and paid == True
        and price <= 2_000_000
        and depart_date == '2026-10-07' and depart_time < '12:00'
        """
        if not booking_code:
            return False, "Chưa có mã đặt vé (booking_code)."

        booking = DB.bookings.get(booking_code)
        if not booking:
            return False, f"Không tìm thấy booking {booking_code} trong cơ sở dữ liệu."

        # Kiểm chứng chéo trạng thái (Slide 44)
        if booking.get("status") != "confirmed":
            return False, f"Trạng thái chưa confirmed (hiện tại: {booking.get('status')})."

        if not booking.get("paid"):
            return False, "Booking chưa được thanh toán (paid is False)."

        if booking.get("price", 0) > constraints.max_price:
            return False, f"Giá vé {booking.get('price'):,}đ vượt quá ràng buộc {constraints.max_price:,}đ."

        if booking.get("depart_date") != constraints.date:
            return False, f"Ngày bay {booking.get('depart_date')} không khớp {constraints.date}."

        if booking.get("depart_time", "23:59") >= constraints.depart_before:
            return False, f"Giờ bay {booking.get('depart_time')} không thỏa điều kiện sáng (< {constraints.depart_before})."

        return True, f"Xác nhận thành công: Booking {booking_code} hợp lệ, đã thanh toán {booking.get('price'):,}đ."


class LoopDetector:
    """
    BỘ PHÁT HIỆN LẶP VÀ BẾ TẮC (Slide 46)
    Cài đặt nguyên bản theo thuật toán trong Slide:
    - Trùng (tool, args) xuất hiện >= repeat_k lần
    - Đại lượng tiến triển (progress) đứng yên >= stall_n lần
    """
    def __init__(self, window: int = 6, repeat_k: int = 2, stall_n: int = 4):
        self.recent = deque(maxlen=window)  # Chỉ so cửa sổ gần
        self.k = repeat_k
        self.n = stall_n
        self.last = None
        self.stall = 0

    def check(self, tool: str, args: Dict[str, Any], progress: Any) -> Optional[str]:
        # Chuẩn hóa (tool, sorted(args)) để tạo fingerprint
        fp = (tool, repr(sorted(args.items())))
        if self.recent.count(fp) + 1 >= self.k:
            return "LOOP"
        self.recent.append(fp)

        # Kiểm tra bế tắc (Slide 40, 45, 46)
        if progress == self.last:
            self.stall += 1
        else:
            self.stall = 0
        self.last = progress

        if self.stall >= self.n:
            return "STALL"
        return None


class AgentHarness:
    """
    Lớp tổng thể Agent Harness kết nối toàn bộ các thành phần:
    - Quản lý vòng lặp (Loop Budget: Turns, Time - Slide 15, 38)
    - Quản lý Ràng buộc dữ liệu (Constraints - Slide 63)
    - Kiểm quyền trước khi gọi tool (Permission - Slide 41)
    - Chạy tool an toàn và bắt ngoại lệ (Slide 66)
    - Bộ phát hiện lặp (LoopDetector - Slide 46)
    - Tiêu chí hoàn thành (Computational Sensor - Slide 43)
    - Tạo báo cáo Bàn giao (Handoff 30s - Slide 48)
    """
    def __init__(
        self,
        constraints: Optional[FlightConstraints] = None,
        max_turns: int = 10,
        max_seconds: float = 30.0,
        auto_approve: bool = True
    ):
        self.constraints = constraints or FlightConstraints()
        self.max_turns = max_turns
        self.max_seconds = max_seconds
        self.permission_manager = PermissionManager(auto_approve=auto_approve)
        self.loop_detector = LoopDetector(window=6, repeat_k=2, stall_n=4)
        self.start_time = time.time()
        
        # State tracking
        self.turn_count = 0
        self.total_tokens_used = 0
        self.actions_history: List[Dict[str, Any]] = []
        self.active_booking_code: Optional[str] = None
        self.terminated = False
        self.termination_reason = ""
        self.termination_type = ""  # normal (Slide 42) vs abnormal

    def start_session(self):
        self.start_time = time.time()
        self.turn_count = 0
        self.actions_history.clear()
        self.active_booking_code = None
        self.terminated = False
        self.termination_reason = ""
        self.termination_type = ""

    def pre_tool_check(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Checklist #0 (Slide 35): Trước khi thực thi tool -> Kiểm quyền
        """
        # 1. Kiểm tra ngân sách vòng lặp
        self.turn_count += 1
        if self.turn_count > self.max_turns:
            self.terminated = True
            self.termination_type = "Hết ngân sách (Budget)"
            self.termination_reason = f"Đã chạm trần số vòng lặp tối đa ({self.max_turns} turns)."
            return False, self.termination_reason, None

        if (time.time() - self.start_time) > self.max_seconds:
            self.terminated = True
            self.termination_type = "Hết ngân sách (Timeout)"
            self.termination_reason = f"Đã vượt quá thời gian thực thi cho phép ({self.max_seconds}s)."
            return False, self.termination_reason, None

        # 2. Kiểm tra thẩm quyền (Permission)
        is_allowed, reason, prompt_question = self.permission_manager.check_permission(tool_name, args)
        if not is_allowed:
            self.terminated = True
            self.termination_type = "Cần con người (Approval)"
            self.termination_reason = reason
            return False, reason, prompt_question

        return True, "OK", None

    def post_tool_check(self, tool_name: str, args: Dict[str, Any], observation: str, progress_metric: Any) -> Tuple[bool, str]:
        """
        Checklist #1, #2, #3, #4 (Slide 35): Sau khi có observation
        - #1 Kiểm tra hoàn thành (Sensor computational)
        - #2 Phát hiện lặp (tool, args)
        - #3 Kiểm tra bế tắc (stall)
        """
        # Parse observation nếu có booking_code
        try:
            obs_json = json.loads(observation)
            if "booking_code" in obs_json:
                self.active_booking_code = obs_json["booking_code"]
        except Exception:
            pass

        # Ghi log lịch sử
        self.actions_history.append({
            "turn": self.turn_count,
            "tool": tool_name,
            "args": args,
            "observation": observation
        })

        # 1. Kiểm tra hoàn thành bằng Sensor computational (Slide 43)
        completed, msg = ComputationalSensor.is_booking_completed(self.active_booking_code, self.constraints)
        if completed:
            self.terminated = True
            self.termination_type = "Đạt mục tiêu (Success)"
            self.termination_reason = msg
            return True, "COMPLETED"

        # 2. Kiểm tra lặp và bế tắc (Slide 46)
        loop_status = self.loop_detector.check(tool_name, args, progress=progress_metric)
        if loop_status == "LOOP":
            self.terminated = True
            self.termination_type = "Phát hiện lặp (Loop)"
            self.termination_reason = f"Hành động ({tool_name}, {args}) bị lặp lại trong cửa sổ gần."
            return False, "LOOP_DETECTED"
        elif loop_status == "STALL":
            self.terminated = True
            self.termination_type = "Bế tắc (Stall)"
            self.termination_reason = f"Tiến triển bài toán đứng yên suốt {self.loop_detector.n} vòng."
            return False, "STALL_DETECTED"

        return True, "CONTINUE"

    def generate_handoff_report(self, question: str = "") -> str:
        """
        Lớp 4: BÀN GIAO CHO CON NGƯỜI (Slide 48)
        Bàn giao tốt là bàn giao mà người nhận trả lời được trong 30 giây.
        """
        side_effects = []
        if self.active_booking_code:
            booking = DB.bookings.get(self.active_booking_code, {})
            side_effects.append(f"Mã đặt chỗ: {self.active_booking_code} (Status: {booking.get('status')}, Paid: {booking.get('paid')})")
        else:
            side_effects.append("Chưa tạo booking hay giao dịch nào phát sinh chi phí.")

        history_summary = []
        for a in self.actions_history[-4:]:
            history_summary.append(f"Vòng {a['turn']}: gọi {a['tool']} với args={a['args']}")

        return f"""
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                      BÁO CÁO BÀN GIAO CHO CON NGƯỜI (HANDOFF 30S)                  ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
  1. Trạng thái hiện tại:
     - Số vòng đã chạy   : {self.turn_count} / {self.max_turns}
     - Tác dụng phụ đã tạo: {'; '.join(side_effects)}
     - Loại kết thúc     : {self.termination_type} ({self.termination_reason})

  2. Những gì đã thử (Lịch sử gần nhất):
     - {chr(10).join('     - ' + h for h in history_summary) if history_summary else 'Chưa có hành động nào'}

  3. Câu hỏi cụ thể cần con người quyết định:
     >>> "{question or 'Vui lòng kiểm tra và quyết định bước xử lý tiếp theo.'}" <<<
╚═══════════════════════════════════════════════════════════════════════════════════╝
"""
