# Hệ Thống Agent Đặt Vé Máy Bay - Bài Tập Về Nhà #03 (SE373)

Dự án cài đặt và thực nghiệm 3 mẫu thiết kế Agentic AI (ReAct, Plan-then-Execute, Mẫu lai) kết hợp cơ chế kiểm soát an toàn **Agent Harness** cho bài toán đặt vé máy bay tự động, thuộc môn học **SE373 - Kỹ thuật Xây dựng Hệ thống Agentic AI (UIT)**.

---

## 📂 Cấu Trúc Thư Mục

| File / Thư mục | Chức năng |
| :--- | :--- |
| `mock_tools.py` | 5 Mock Tools đặt vé máy bay với cấu trúc JSON chuẩn hóa và mã lỗi rõ ràng |
| `harness.py` | Toàn bộ 5 tầng an toàn của Agent Harness (Data Constraints, Computational Sensor, Approval Check, Loop Detector, Human Handoff) |
| `agent_react.py` | Agent Mẫu 1: Vòng lặp ReAct phản ứng linh hoạt theo thời gian thực |
| `agent_plan_execute.py` | Agent Mẫu 2: Plan-then-Execute lập kế hoạch tĩnh toàn bộ trước khi chạy |
| `agent_hybrid.py` | Agent Mẫu 3: Mẫu Lai (Plan + ReAct / Dynamic Re-planning khi có biến động) |
| `llm_factory.py` | Khởi tạo mô hình Google Gemini (`gemini-3.5-flash-lite`) |
| `evaluate.py` | Benchmark đánh giá so sánh tự động 3 Agent qua 4 kịch bản thử nghiệm |
| `main.py` | Menu CLI tương tác trực tiếp chạy từng Agent hoặc chạy Benchmark |
| `BAO_CAO_BTVN3.pdf` | Báo cáo định dạng PDF hoàn chỉnh phục vụ nộp bài |

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Cài đặt môi trường
Yêu cầu Python 3.10 trở lên. Cài đặt các thư viện phụ thuộc:
```bash
pip install -r requirements.txt
```

### 2. Thiết lập biến môi trường (.env)
Tạo file `.env` từ file mẫu `.env.example`:
```bash
cp .env.example .env
```
Mở file `.env` và điền Google Gemini API Key của bạn:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

### 3. Chạy chương trình
Khởi chạy giao diện dòng lệnh:
```bash
python main.py
```
Menu tương tác sẽ hiển thị các lựa chọn:
- `1`: Chạy thử nghiệm Agent Mẫu 1 (ReAct)
- `2`: Chạy thử nghiệm Agent Mẫu 2 (Plan-then-Execute)
- `3`: Chạy thử nghiệm Agent Mẫu 3 (Mẫu Lai)
- `4`: Chạy toàn bộ Benchmark so sánh 3 mẫu trên 4 kịch bản
- `0`: Thoát chương trình

## 📊 Kết Quả Thực Nghiệm Tóm Tắt

Chi tiết đầy đủ xem tại [BAO_CAO_BTVN3.md](BAO_CAO_BTVN3.md) hoặc file [BAO_CAO_BTVN3.pdf](BAO_CAO_BTVN3.pdf).
