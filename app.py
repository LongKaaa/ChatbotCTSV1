import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from docx import Document
from pypdf import PdfReader
import markdown
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# ---  CẤU HÌNH DATABASE ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = 'khoa-cntt-hcmus-secret-key-2024' 
db = SQLAlchemy(app)

# --- CẤU HÌNH AI (API KEY) ---
MY_API_KEY = "AIzaSyAJQ4fNjY9C_aI05xqH6F-XjzfpJ4uL6BY" 
genai.configure(api_key=MY_API_KEY)

# --- HÀM ĐỆ QUY ĐỌC DỮ LIỆU ---
def read_data_recursive(path):
    combined_text = ""
    if not os.path.exists(path):
        return ""

    items = os.listdir(path)

    for item in items:
        full_path = os.path.join(path, item)
        
        # 1. Nếu là Folder
        if os.path.isdir(full_path):
            print(f"📂 Đang vào folder: {item}...")
            combined_text += read_data_recursive(full_path)
        # 2. Nếu là File
        elif os.path.isfile(full_path):
            filename_lower = item.lower()
            if filename_lower.endswith('.docx'):
                try:
                    doc = Document(full_path)
                    text = "\n".join([para.text for para in doc.paragraphs if para.text.strip() != ''])
                    combined_text += f"\n[Nguồn: File Word {item}]\n{text}\n"
                    print(f"   ✅ Đã đọc file Word: {item}")
                except Exception as e:
                    print(f"   ❌ LỖI đọc file Word {item}: {e}")
            elif filename_lower.endswith('.doc'):
                print(f"   ⚠️ BỎ QUA file .doc (Hãy đổi sang .docx): {item}")
            elif filename_lower.endswith('.pdf'):
                try:
                    reader = PdfReader(full_path)
                    text = ""
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted: text += extracted + "\n"
                    combined_text += f"\n[Nguồn: File PDF {item}]\n{text}\n"
                    print(f"   ✅ Đã đọc file PDF: {item}")
                except Exception as e:
                    print(f"   ❌ LỖI đọc file PDF {item}: {e}")
            else:
                pass
    return combined_text


# --- KHỞI TẠO DỮ LIỆU ---
print("--- BẮT ĐẦU QUÉT DỮ LIỆU ---")
KNOWLEDGE_BASE = read_data_recursive('data')
print(f"--- HOÀN TẤT! Tổng độ dài dữ liệu: {len(KNOWLEDGE_BASE)} ký tự ---")

# --- THIẾT LẬP PROMPT (Đã Fix lỗi khoảng trống) ---
sys_instruction = f"""
Bạn là Trợ lý ảo tư vấn tuyển sinh chuyên nghiệp của Khoa CNTT - ĐH KHTN ĐHQG-HCM.
Nhiệm vụ của bạn là hỗ trợ thí sinh dựa trên KHO DỮ LIỆU NỘI BỘ.

----------------
DỮ LIỆU NỘI BỘ (KNOWLEDGE BASE):
{KNOWLEDGE_BASE}
----------------

### 1. NGUYÊN TẮC CỐT LÕI (BẮT BUỘC):
- **TRUNG THỰC TUYỆT ĐỐI:** Chỉ trả lời dựa trên dữ liệu cung cấp. Nếu không có thông tin, hãy báo người dùng theo dõi website trường.
- **KHÔNG BỊA ĐẶT:** Không tự ý thêm thắt thông tin bên ngoài.
**TIẾT KIỆM DÒNG:** - Tuyệt đối **KHÔNG** dùng quá 1 dòng trống giữa các đoạn văn.
   - **KHÔNG** dùng Bảng biểu (Table).
   - Nội dung phải cô đọng, viết liền mạch.

**ĐỊNH DẠNG MARKDOWN:**
   - Sử dụng **In đậm** cho các con số quan trọng.
   - Dùng gạch đầu dòng `-` cho danh sách, liệt kê.

**CẤM:**
   - Cấm viết lời chào dài dòng. Đi thẳng vào câu trả lời.
   - Cấm tự tạo khoảng trắng (indent) đầu dòng.
### 3. QUY TẮC TÍNH ĐIỂM XÉT TUYỂN:
Khi người dùng yêu cầu tính điểm, thực hiện đúng logic:
   * Bước 1: Chuẩn hóa điểm sang số thực.
   * Bước 2: Tính Tổng điểm thi (3 môn).
   * Bước 3: Kiểm tra Ngưỡng 28.0:
     - Nếu Tổng < 28.0: Cộng điểm ưu tiên bình thường.
     - Nếu Tổng >= 28.0: Áp dụng công thức giảm trừ: `ĐC = [(30 - Tong_Diem_Thi) / 2] * Diem_Cong_Co_So`.
   * Bước 4: Kết quả (Max 30.0, làm tròn 2 chữ số thập phân).
   * Giải thích: Ghi rõ lý do áp dụng công thức.

### 4. VĂN PHONG GIAO TIẾP:
- Thân thiện, ngắn gọn, súc tích.
- Xưng hô "mình" và "bạn".
"""

# --- KHỞI TẠO MODEL & CHAT SESSION (Đã sửa lỗi quan trọng tại đây) ---
# Lưu ý: Đổi tên model về 'gemini-1.5-flash' vì '2.5-flash-lite' chưa phổ biến công khai hoặc dễ gây lỗi
model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=sys_instruction)

# Tạo phiên chat toàn cục để lưu lịch sử tạm thời
chat_session = model.start_chat(history=[])


# --- 3. ĐỊNH NGHĨA BẢNG DỮ LIỆU (MODELS) ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    messages = db.relationship('ChatMessage', backref='author', lazy=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(10), nullable=False) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- 4. CÁC ROUTE ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_question = data.get('message')

    if not user_question:
        return jsonify({"response": "Bạn chưa nhập câu hỏi nào cả!"})
    
    try:
        # Gọi chat_session đã được khởi tạo ở trên
        response = chat_session.send_message(user_question)
        bot_reply = response.text
        
        # --- SỬA LỖI TẠI ĐÂY: Chuyển đổi Markdown sang HTML ---
        # Thêm extensions=['tables'] để hiển thị được bảng biểu
        bot_reply = markdown.markdown(bot_reply, extensions=['tables'])
        # ------------------------------------------------------
        
    except Exception as e:
        bot_reply = "Xin lỗi, hệ thống đang quá tải hoặc gặp lỗi kết nối. Bạn thử lại sau nhé!"
        print(f"Lỗi API: {e}") 
    
    return jsonify({"response": bot_reply})

# --- 5. CHẠY ỨNG DỤNG ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Đã khởi tạo Database thành công!")

    app.run(debug=True, port=8080)