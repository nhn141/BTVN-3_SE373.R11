"""
main.py - Chương trình chính thực thi Agent Đặt Vé Máy Bay
SE373: Agentic AI Engineering · Buổi 03
Cho phép:
1. Chạy thử nghiệm từng Agent đơn lẻ (ReAct / Plan-then-Execute / Hybrid) với log trace chi tiết
2. Chạy toàn diện Benchmark đánh giá so sánh 3 mẫu thiết kế
"""

import sys
import os
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from mock_tools import DB
from harness import AgentHarness, FlightConstraints
from llm_factory import create_chat_model, get_api_key, get_model_name
from agent_react import ReActFlightAgent
from agent_plan_execute import PlanThenExecuteFlightAgent
from agent_hybrid import HybridFlightAgent
import evaluate

def print_banner():
    api_key_status = "ĐÃ KẾT NỐI (Gemini Live)" if get_api_key() else "CHƯA CÓ API KEY (Sử dụng Mock LLM chuẩn hóa)"
    model_name = get_model_name()
    print("═" * 80)
    print("      HỆ THỐNG AGENT ĐẶT VÉ MÁY BAY - BÀI TẬP VỀ NHÀ #03 (SE373 - UIT)      ")
    print(f"      Mô hình: {model_name} | Trạng thái: {api_key_status}")
    print("═" * 80)

def run_single_agent(choice: int):
    DB.reset()
    llm = create_chat_model()
    harness = AgentHarness(
        constraints=FlightConstraints(origin="SGN", destination="DAD", date="2026-10-07", depart_before="12:00", max_price=2_000_000),
        max_turns=8,
        auto_approve=True
    )

    goal = "Đặt giúp tôi vé máy bay từ SGN đi DAD vào sáng ngày 2026-10-07, giá dưới 2.000.000đ."
    print(f"\n[Yêu cầu]: {goal}\n")

    if choice == 1:
        agent = ReActFlightAgent(llm, harness)
        print(">>> Đang chạy Agent Mẫu 1: ReAct (Reasoning + Acting)...")
    elif choice == 2:
        agent = PlanThenExecuteFlightAgent(llm, harness)
        print(">>> Đang chạy Agent Mẫu 2: Plan-then-Execute...")
    else:
        agent = HybridFlightAgent(llm, harness)
        print(">>> Đang chạy Agent Mẫu 3: Mẫu Lai (ReAct + Plan)...")

    result = agent.run(goal)

    print("\n" + "-"*50 + " TRACE NHẬT KÝ VÒNG LẶP (SLIDE 10, 20) " + "-"*50)
    for log in result["trace_logs"]:
        turn = log.get("turn", log.get("step"))
        tool = log.get("tool_called")
        args = log.get("tool_args")
        obs = log.get("observation")
        status = log.get("status", log.get("harness_check"))
        print(f"\n[Vòng {turn}] Gọi tool: {tool}")
        print(f"  - Tham số (Args) : {args}")
        if "thought_content" in log:
            first_line = log["thought_content"].split("\n")[0]
            print(f"  - Suy luận       : {first_line}")
        print(f"  - Quan sát (Obs) : {obs}")
        print(f"  - Harness Check  : {status}")

    print("\n" + "="*50 + " KẾT QUẢ CUỐI CÙNG " + "="*50)
    print(f"Kiểu Agent   : {result['agent_type']}")
    print(f"Thành công   : {'CÓ (Đạt mục tiêu)' if result['success'] else 'KHÔNG (Chưa hoàn thành)'}")
    print(f"Số vòng lặp  : {result['turns']}")
    print(f"Loại kết thúc: {result['termination_type']}")
    print(f"Lý do chi tiết: {result['termination_reason']}")
    print(f"Mã vé đã tạo : {result.get('booking_code')}")
    print("="*105)


def main():
    print_banner()
    while True:
        print("\nChọn chức năng muốn thực hiện:")
        print("1. Chạy Agent Mẫu 1 (ReAct)")
        print("2. Chạy Agent Mẫu 2 (Plan-then-Execute)")
        print("3. Chạy Agent Mẫu 3 (Mẫu Lai: Plan + ReAct)")
        print("4. Chạy toàn bộ Benchmark Đánh Giá So Sánh 3 Mẫu (4 Kịch Bản - Yêu cầu 3)")
        print("0. Thoát chương trình")
        
        try:
            choice = input("\nNhập lựa chọn (0-4): ").strip()
            if choice == "0":
                print("Tạm biệt!")
                break
            elif choice in ["1", "2", "3"]:
                run_single_agent(int(choice))
            elif choice == "4":
                evaluate.main()
            else:
                print("Lựa chọn không hợp lệ, vui lòng chọn lại!")
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()
