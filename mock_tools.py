"""
mock_tools.py - Hệ thống Mock Tools & Mock Database đặt vé máy bay
Tuân thủ Slide 12-13, 56, 66 (SE373 Buổi 3):
- Dữ liệu trả về là Structured JSON rõ ràng (status, data, error, hint)
- Có mã lỗi chi tiết để Agent biết đường xử lý
- Mock Database lưu trữ trạng thái chuyến bay và thông tin đặt vé
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime

class FlightDatabase:
    """Mock Database quản lý chuyến bay và danh sách vé đã đặt"""
    def __init__(self):
        self.reset()

    def reset(self):
        # Danh mục các chuyến bay mẫu SGN -> DAD ngày 2026-10-07
        self.flights = {
            "VN122": {
                "flight_id": "VN122",
                "airline": "Vietnam Airlines",
                "origin": "SGN",
                "destination": "DAD",
                "date": "2026-10-07",
                "depart_time": "08:10",
                "arrival_time": "09:35",
                "price": 1850000,
                "available_seats": ["12A", "12B", "14C"],
                "refundable": False
            },
            "VJ604": {
                "flight_id": "VJ604",
                "airline": "Vietjet Air",
                "origin": "SGN",
                "destination": "DAD",
                "date": "2026-10-07",
                "depart_time": "09:30",
                "arrival_time": "10:50",
                "price": 1450000,
                "available_seats": ["5A", "5B"],
                "refundable": True
            },
            "QH118": {
                "flight_id": "QH118",
                "airline": "Bamboo Airways",
                "origin": "SGN",
                "destination": "DAD",
                "date": "2026-10-07",
                "depart_time": "15:40",
                "arrival_time": "17:00",
                "price": 1640000,
                "available_seats": ["10A", "10B"],
                "refundable": True
            },
            "VN134": {
                "flight_id": "VN134",
                "airline": "Vietnam Airlines",
                "origin": "SGN",
                "destination": "DAD",
                "date": "2026-10-07",
                "depart_time": "11:15",
                "arrival_time": "12:40",
                "price": 2350000,
                "available_seats": ["2A", "2C"],
                "refundable": True
            }
        }
        # Sổ lưu trữ các booking
        self.bookings: Dict[str, Dict[str, Any]] = {}
        self.booking_counter = 100

        # Cờ giả lập kịch bản biến động (dùng cho Benchmark / Evaluation)
        self.simulated_errors = {
            "out_of_stock_flights": set(),  # Danh sách chuyến giả lập hết chỗ
            "timeout_search": False,        # Giả lập lỗi timeout mạng
        }

# Khởi tạo singleton database để dùng chung
DB = FlightDatabase()


def search_flights(origin: str, destination: str, date: str, **kwargs) -> str:
    """
    Tìm kiếm danh sách các chuyến bay phù hợp theo điểm đi, điểm đến và ngày bay.
    Đầu vào: origin (vd 'SGN'), destination (vd 'DAD'), date (định dạng 'YYYY-MM-DD').
    """
    if DB.simulated_errors["timeout_search"]:
        return json.dumps({
            "status": "error",
            "error_code": "TIMEOUT",
            "message": "Dịch vụ tìm kiếm chuyến bay đang quá tải, vui lòng thử lại sau.",
            "hint": "Chờ một khoảng thời gian hoặc kiểm tra lại kết nối"
        }, ensure_ascii=False)

    # Slide 56: Bắt lỗi định dạng tham số ngày rõ ràng
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return json.dumps({
            "status": "invalid_param",
            "param": "date",
            "error_code": "INVALID_DATE_FORMAT",
            "message": f"Ngày '{date}' không đúng định dạng. Cần dùng YYYY-MM-DD (ví dụ 2026-10-07).",
            "hint": "Chuyển đổi ngày sang định dạng YYYY-MM-DD"
        }, ensure_ascii=False)

    results = []
    for f in DB.flights.values():
        if f["origin"].upper() == origin.upper() and f["destination"].upper() == destination.upper() and f["date"] == date:
            results.append({
                "flight_id": f["flight_id"],
                "airline": f["airline"],
                "depart_time": f["depart_time"],
                "price": f["price"],
                "seats_count": len(f["available_seats"]),
                "refundable": f["refundable"]
            })

    if not results:
        # Slide 66: Không trả chuỗi rỗng mà trả JSON status rõ ràng
        return json.dumps({
            "status": "empty",
            "flights": [],
            "message": f"Không tìm thấy chuyến bay nào từ {origin} đến {destination} vào ngày {date}."
        }, ensure_ascii=False)

    return json.dumps({
        "status": "ok",
        "total": len(results),
        "flights": results
    }, ensure_ascii=False)


def check_seat(flight_id: str, **kwargs) -> str:
    """
    Kiểm tra tình trạng chỗ ngồi và chi tiết giá của một chuyến bay cụ thể.
    Đầu vào: flight_id (vd 'VN122').
    """
    flight = DB.flights.get(flight_id.upper())
    if not flight:
        return json.dumps({
            "status": "not_found",
            "error_code": "FLIGHT_NOT_FOUND",
            "message": f"Chuyến bay {flight_id} không tồn tại trong hệ thống."
        }, ensure_ascii=False)

    # Giả lập trường hợp chuyến bay bị hết vé đột ngột
    if flight_id in DB.simulated_errors["out_of_stock_flights"]:
        return json.dumps({
            "status": "sold_out",
            "flight_id": flight_id,
            "available_seats": [],
            "message": f"Chuyến bay {flight_id} vừa hết chỗ ngồi trống."
        }, ensure_ascii=False)

    return json.dumps({
        "status": "available",
        "flight_id": flight["flight_id"],
        "airline": flight["airline"],
        "date": flight["date"],
        "depart_time": flight["depart_time"],
        "price": flight["price"],
        "refundable": flight["refundable"],
        "available_seats": flight["available_seats"]
    }, ensure_ascii=False)


def book_seat(flight_id: str, seat_number: str = "12A", passenger_name: str = "Nguyen Van A", **kwargs) -> str:
    """
    Giữ chỗ và đặt vé tạm thời trên chuyến bay.
    Đầu vào: flight_id (vd 'VN122'), seat_number (vd '12A'), passenger_name.
    """
    flight = DB.flights.get(flight_id.upper())
    if not flight:
        return json.dumps({
            "status": "error",
            "error_code": "FLIGHT_NOT_FOUND",
            "message": f"Không thể đặt vé vì chuyến bay {flight_id} không tồn tại."
        }, ensure_ascii=False)

    if flight_id in DB.simulated_errors["out_of_stock_flights"] or seat_number not in flight["available_seats"]:
        return json.dumps({
            "status": "seat_unavailable",
            "error_code": "SEAT_NOT_AVAILABLE",
            "message": f"Ghế {seat_number} trên chuyến {flight_id} không còn trống.",
            "hint": "Chọn ghế khác hoặc chuyến bay khác."
        }, ensure_ascii=False)

    # Sinh mã đặt chỗ và lưu trạng thái tạm 'held'
    DB.booking_counter += 1
    booking_code = f"BK-{flight_id}-{DB.booking_counter}"
    booking_record = {
        "booking_code": booking_code,
        "flight_id": flight_id,
        "airline": flight["airline"],
        "seat": seat_number,
        "passenger_name": passenger_name,
        "price": flight["price"],
        "depart_date": flight["date"],
        "depart_time": flight["depart_time"],
        "refundable": flight["refundable"],
        "status": "held",
        "paid": False
    }
    DB.bookings[booking_code] = booking_record
    # Tạm gỡ ghế khỏi danh sách trống
    flight["available_seats"].remove(seat_number)

    return json.dumps({
        "status": "held",
        "booking_code": booking_code,
        "price": flight["price"],
        "seat": seat_number,
        "message": f"Đã giữ chỗ thành công mã {booking_code}. Vui lòng thanh toán để xác nhận."
    }, ensure_ascii=False)


def pay(booking_code: str, payment_method: str = "corp_card", **kwargs) -> str:
    """
    Thực hiện thanh toán tiền cho mã đặt chỗ đã giữ.
    Đầu vào: booking_code (vd 'BK-VN122-101'), payment_method (vd 'corp_card').
    """
    booking = DB.bookings.get(booking_code)
    if not booking:
        return json.dumps({
            "status": "error",
            "error_code": "BOOKING_NOT_FOUND",
            "message": f"Không tìm thấy thông tin đặt chỗ với mã {booking_code}."
        }, ensure_ascii=False)

    if booking["status"] == "confirmed" and booking["paid"]:
        return json.dumps({
            "status": "already_paid",
            "booking_code": booking_code,
            "message": "Mã đặt chỗ này đã được thanh toán trước đó."
        }, ensure_ascii=False)

    # Chuyển trạng thái xác nhận và đã thanh toán
    booking["status"] = "confirmed"
    booking["paid"] = True
    booking["payment_method"] = payment_method

    return json.dumps({
        "status": "confirmed",
        "booking_code": booking_code,
        "paid": True,
        "amount": booking["price"],
        "message": f"Thanh toán thành công {booking['price']} VND cho mã {booking_code} qua {payment_method}."
    }, ensure_ascii=False)


def get_booking(booking_code: str, **kwargs) -> str:
    """
    Kiểm tra trạng thái xác nhận và thông tin chi tiết của một mã đặt vé trong hệ thống.
    Đầu vào: booking_code.
    """
    booking = DB.bookings.get(booking_code)
    if not booking:
        return json.dumps({
            "status": "not_found",
            "error_code": "BOOKING_NOT_FOUND",
            "message": f"Không tìm thấy mã {booking_code}."
        }, ensure_ascii=False)

    return json.dumps({
        "status": "found",
        "booking": booking
    }, ensure_ascii=False)
