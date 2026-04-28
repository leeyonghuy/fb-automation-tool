"""
TTS Engine - Wrapper cho VieNeu-TTS
Chuyển văn bản tiếng Việt thành giọng nói
"""

import os
import sys
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Thêm VieNeu-TTS vào path nếu cần
VIENEU_PATH = Path("D:/Contenfactory/libs/vieneu-tts/src")
if VIENEU_PATH.exists() and str(VIENEU_PATH) not in sys.path:
    sys.path.insert(0, str(VIENEU_PATH))

# Giọng đọc mặc định
DEFAULT_VOICE = "Xuân Vĩnh"  # Giọng nam miền Bắc

# Danh sách giọng có sẵn trong VieNeu-TTS
AVAILABLE_VOICES = [
    "Xuân Vĩnh",    # Nam, miền Bắc
    "Minh Thư",     # Nữ, miền Bắc  
    "Hoàng Long",   # Nam, miền Nam
    "Thu Hà",       # Nữ, miền Nam
]

_tts_instance = None


def get_tts():
    """Lazy load TTS instance (singleton)"""
    global _tts_instance
    if _tts_instance is None:
        try:
            from vieneu import Vieneu
            logger.info("Đang khởi tạo VieNeu-TTS (Turbo mode)...")
            _tts_instance = Vieneu()
            logger.info("✅ VieNeu-TTS đã sẵn sàng!")
        except ImportError:
            logger.error("❌ Chưa cài vieneu. Chạy: pip install vieneu --extra-index-url https://pnnbao97.github.io/llama-cpp-python-v0.3.16/cpu/")
            raise
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo TTS: {e}")
            raise
    return _tts_instance


def text_to_speech(
    text: str,
    output_path: str = None,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0
) -> str:
    """
    Chuyển văn bản thành file audio WAV
    
    Args:
        text: Văn bản cần đọc (tiếng Việt hoặc song ngữ Anh-Việt)
        output_path: Đường dẫn file output (.wav). Nếu None sẽ tạo file tạm
        voice: Tên giọng đọc (xem AVAILABLE_VOICES)
        speed: Tốc độ đọc (0.5 - 2.0, mặc định 1.0)
    
    Returns:
        Đường dẫn file WAV đã tạo
    """
    if not text or not text.strip():
        raise ValueError("Text không được rỗng")
    
    # Tạo file tạm nếu không có output_path
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()
    
    # Đảm bảo thư mục tồn tại
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    try:
        tts = get_tts()
        
        logger.info(f"🎙️ TTS: '{text[:50]}...' -> {output_path}")
        
        # Infer với giọng được chọn
        if voice and voice != DEFAULT_VOICE:
            audio = tts.infer(text=text, voice=voice)
        else:
            audio = tts.infer(text=text)
        
        # Lưu file
        tts.save(audio, output_path)
        
        logger.info(f"✅ Đã tạo audio: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Lỗi TTS: {e}")
        raise


def text_to_speech_batch(
    texts: list,
    output_dir: str,
    voice: str = DEFAULT_VOICE,
    prefix: str = "tts"
) -> list:
    """
    Chuyển nhiều đoạn văn bản thành audio (batch)
    
    Args:
        texts: Danh sách văn bản
        output_dir: Thư mục lưu file audio
        voice: Giọng đọc
        prefix: Tiền tố tên file
    
    Returns:
        Danh sách đường dẫn file WAV
    """
    os.makedirs(output_dir, exist_ok=True)
    output_files = []
    
    for i, text in enumerate(texts):
        if not text or not text.strip():
            output_files.append(None)
            continue
        
        output_path = os.path.join(output_dir, f"{prefix}_{i:03d}.wav")
        try:
            path = text_to_speech(text, output_path, voice)
            output_files.append(path)
        except Exception as e:
            logger.error(f"Lỗi TTS đoạn {i}: {e}")
            output_files.append(None)
    
    return output_files


def clone_voice_tts(
    text: str,
    reference_audio: str,
    output_path: str = None
) -> str:
    """
    TTS với clone giọng từ file audio mẫu (chỉ hoạt động với GPU mode)
    
    Args:
        text: Văn bản cần đọc
        reference_audio: Đường dẫn file audio mẫu (3-5 giây)
        output_path: Đường dẫn output
    
    Returns:
        Đường dẫn file WAV
    """
    if not os.path.exists(reference_audio):
        raise FileNotFoundError(f"File audio mẫu không tồn tại: {reference_audio}")
    
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()
    
    try:
        tts = get_tts()
        audio = tts.infer(text=text, ref_audio=reference_audio)
        tts.save(audio, output_path)
        logger.info(f"✅ Clone voice TTS: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"❌ Lỗi clone voice TTS: {e}")
        raise


def is_available() -> bool:
    """Kiểm tra TTS có sẵn sàng không"""
    try:
        import vieneu
        return True
    except ImportError:
        return False


# Test nhanh khi chạy trực tiếp
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    if not is_available():
        print("❌ VieNeu-TTS chưa được cài đặt!")
        print("Chạy: pip install vieneu --extra-index-url https://pnnbao97.github.io/llama-cpp-python-v0.3.16/cpu/")
        sys.exit(1)
    
    print("🎙️ Test VieNeu-TTS...")
    test_text = "Xin chào! Đây là hệ thống chuyển văn bản thành giọng nói tiếng Việt."
    output = text_to_speech(test_text, "D:/Contenfactory/test_tts.wav")
    print(f"✅ Đã tạo: {output}")
