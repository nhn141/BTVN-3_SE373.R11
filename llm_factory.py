"""
llm_factory.py - Cấu hình và khởi tạo LLM cho hệ thống Agent
Chỉ sử dụng API Key thực tế của Google Gemini (Không dùng MockLLM).
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Tải biến môi trường từ .env
load_dotenv(override=True)

def get_api_key() -> str:
    """Lấy Google API Key từ biến môi trường hoặc .env"""
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    return key.strip()

def get_model_name() -> str:
    """Lấy tên mô hình Gemini từ .env (Mặc định: gemini-2.5-flash)"""
    return os.environ.get("GEMINI_MODEL") or os.environ.get("SE373_MODEL") or "gemini-2.5-flash"

def create_chat_model() -> ChatGoogleGenerativeAI:
    """Khởi tạo Chat Model Google Gemini bằng API Key thật"""
    api_key = get_api_key()
    model_name = get_model_name()

    if not api_key:
        raise ValueError(
            "\n[LỖI] Không tìm thấy API Key! Vui lòng mở file .env và điền GOOGLE_API_KEY=AIzaSy... của bạn."
        )

    # Đảm bảo set biến môi trường GOOGLE_API_KEY cho thư viện google-genai
    os.environ["GOOGLE_API_KEY"] = api_key

    print(f"[LLM Factory] Đang kết nối Google Gemini API: Model='{model_name}'...")
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.1,
        google_api_key=api_key
    )

def extract_text_content(response_or_content) -> str:
    """Trích xuất chuỗi văn bản từ phản hồi của LLM (xử lý cả trường hợp trả về list of dicts)"""
    raw = getattr(response_or_content, "content", response_or_content)
    if isinstance(raw, str):
        return raw
    elif isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", str(item)))
            elif hasattr(item, "text"):
                parts.append(str(item.text))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(raw or "")

