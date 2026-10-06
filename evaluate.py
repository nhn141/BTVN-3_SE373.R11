"""
evaluate.py - Đánh giá so sánh hiệu quả của Agent với 3 mẫu thiết kế:
1. ReAct (Reasoning + Acting)
2. Plan-then-Execute
3. Lai (Hybrid: Plan + ReAct)

Các tiêu chí đánh giá (Metrics):
- Tỷ lệ thành công (Success Rate - kiểm chứng bằng Computational Sensor)
- Số vòng lặp thực thi (Number of Turns)
- Khả năng xử lý biến động (Fault Tolerance / Adaptability)
- Tính an toàn qua Harness (Permission Check, Loop Detection, Handoff)
"""

import os
import sys
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from typing import Dict, Any, List

from mock_tools import DB
from harness import AgentHarness, FlightConstraints
from llm_factory import create_chat_model
from agent_react import ReActFlightAgent
from agent_plan_execute import PlanThenExecuteFlightAgent
from agent_hybrid import HybridFlightAgent

GOAL_NORMAL = "Đặt giúp tôi vé máy bay từ SGN đi DAD vào sáng ngày 2026-10-07, giá dưới 2.000.000đ."

def run_scenario(scenario_name: str, setup_fn, goal: str, auto_approve: bool = True):
    print(f"\n{'='*75}")
    print(f"🔬 KỊCH BẢN THỬ NGHIỆM: {scenario_name}")
    print(f"{'='*75}")

    llm = create_chat_model()
    results = []

    agents = [
        ("ReAct", lambda h: ReActFlightAgent(llm, h)),
        ("Plan-then-Execute", lambda h: PlanThenExecuteFlightAgent(llm, h)),
        ("Mẫu Lai (Hybrid)", lambda h: HybridFlightAgent(llm, h)),
    ]

    for agent_name, agent_factory in agents:
        # Reset DB và thiết lập kịch bản
        DB.reset()
        setup_fn()

        # Khởi tạo Harness riêng cho lượt chạy
        harness = AgentHarness(
            constraints=FlightConstraints(max_price=2_000_000),
            max_turns=8,
            auto_approve=auto_approve
        )
        agent = agent_factory(harness)

        start_time = time.time()
        output = agent.run(goal)
        elapsed = time.time() - start_time

        res_summary = {
            "Agent": agent_name,
            "Success": "✅ THÀNH CÔNG" if output["success"] else "❌ THẤT BẠI",
            "Turns": output["turns"],
            "Execution_Time": f"{elapsed:.2f}s",
            "Termination": output["termination_type"],
            "Booking_Code": output.get("booking_code") or "None"
        }
        results.append(res_summary)

        print(f"\n--- Kết quả chạy: [{agent_name}] ---")
        print(f"Trạng thái       : {res_summary['Success']}")
        print(f"Số vòng (Turns)  : {res_summary['Turns']}")
        print(f"Thời gian        : {res_summary['Execution_Time']}")
        print(f"Kiểu kết thúc    : {res_summary['Termination']}")
        print(f"Lý do chi tiết   : {output['termination_reason']}")
        if not output["success"] and "trace_logs" in output and output["trace_logs"]:
            last_trace = output["trace_logs"][-1]
            if "handoff_report" in last_trace:
                print(last_trace["handoff_report"])

    return results


def setup_scenario_1_happy_path():
    """Kịch bản 1: Mọi thứ thuận lợi, chuyến VN122 có sẵn và đủ điều kiện"""
    pass

def setup_scenario_2_dynamic_failure():
    """Kịch bản 2: Biến động môi trường - Chuyến VN122 đột ngột hết vé"""
    DB.simulated_errors["out_of_stock_flights"].add("VN122")

def setup_scenario_3_permission_check():
    """Kịch bản 3: Chế độ kiểm quyền nghiêm ngặt (không auto-approve)"""
    pass

def setup_scenario_4_loop_detection():
    """Kịch bản 4: Giả lập lỗi mạng khiến hành động bị lặp lại -> LoopDetector bắt lỗi"""
    DB.simulated_errors["timeout_search"] = True


def main():
    print("===========================================================================")
    print("           BẮT ĐẦU CHƯƠNG TRÌNH ĐÁNH GIÁ 3 MẪU THIẾT KẾ AGENT              ")
    print("              (Môn SE373 · Kỹ thuật Xây dựng Hệ thống Agentic AI)          ")
    print("===========================================================================")

    all_benchmarks = {}

    # 1. Chạy kịch bản 1
    bench1 = run_scenario(
        "Kịch bản 1: Môi trường thuận lợi (Happy Path)",
        setup_scenario_1_happy_path,
        GOAL_NORMAL,
        auto_approve=True
    )
    all_benchmarks["Kịch bản 1 (Thuận lợi)"] = bench1

    # 2. Chạy kịch bản 2
    bench2 = run_scenario(
        "Kịch bản 2: Biến động môi trường (Chuyến VN122 hết chỗ)",
        setup_scenario_2_dynamic_failure,
        GOAL_NORMAL,
        auto_approve=True
    )
    all_benchmarks["Kịch bản 2 (Biến động)"] = bench2

    # 3. Chạy kịch bản 3
    bench3 = run_scenario(
        "Kịch bản 3: Kích hoạt kiểm quyền & Handoff (Yêu cầu con người duyệt)",
        setup_scenario_3_permission_check,
        GOAL_NORMAL,
        auto_approve=False
    )
    all_benchmarks["Kịch bản 3 (Kiểm quyền)"] = bench3

    # 4. Chạy kịch bản 4
    bench4 = run_scenario(
        "Kịch bản 4: Phát hiện lặp & Bế tắc (Loop / Stall Detection)",
        setup_scenario_4_loop_detection,
        GOAL_NORMAL,
        auto_approve=True
    )
    all_benchmarks["Kịch bản 4 (Phát hiện lặp)"] = bench4

    # Tổng kết bảng đánh giá toàn diện
    print("\n" + "="*85)
    print("                    BẢNG TỔNG HỢP KẾT QUẢ ĐÁNH GIÁ (BENCHMARK)             ")
    print("="*85)
    header = f"{'Kịch bản':<25} | {'Mẫu Agent':<20} | {'Kết quả':<14} | {'Turns':<6} | {'Loại dừng'}"
    print(header)
    print("-" * 85)

    for sc_name, sc_results in all_benchmarks.items():
        for res in sc_results:
            print(f"{sc_name:<25} | {res['Agent']:<20} | {res['Success']:<14} | {res['Turns']:<6} | {res['Termination']}")
        print("-" * 85)


if __name__ == "__main__":
    main()
