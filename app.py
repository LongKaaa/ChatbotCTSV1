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
MY_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=MY_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
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
            # --- KIỂM TRA ĐUÔI FILE ---
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

print("--- BẮT ĐẦU QUÉT DỮ LIỆU ---")
KNOWLEDGE_BASE = read_data_recursive('data')
print(f"--- HOÀN TẤT! Tổng độ dài dữ liệu: {len(KNOWLEDGE_BASE)} ký tự ---")

context_instruction = f"""
Bạn là Trợ lý ảo tư vấn tuyển sinh Khoa CNTT - ĐH KHTN ĐHQG-HCM.
Dưới đây là DỮ LIỆU NỘI BỘ của trường:
----------------
{KNOWLEDGE_BASE}
----------------

CHỈ THỊ XỬ LÝ QUAN TRỌNG (ĐẶC BIỆT LƯU Ý PHẦN TÍNH TOÁN):

1. QUY TẮC TÍNH ĐIỂM XÉT TUYỂN (BẮT BUỘC TUÂN THỦ TỪNG BƯỚC):
   Khi người dùng yêu cầu tính điểm hoặc đưa ra điểm số, bạn PHẢI thực hiện đúng quy trình Logic sau (không được bỏ bước):

   * **Bước 1: Chuẩn hóa số liệu**
     - Chuyển đổi toàn bộ điểm số người dùng nhập sang dạng số thực (float). Ví dụ: "29 rưỡi" -> 29.5.
   
   * **Bước 2: Xác định Tổng điểm thi (ĐXTTHM)**
     - Tính tổng điểm 3 môn thi THPT (hoặc dùng điểm tổng người dùng cung cấp). Gọi là `Tong_Diem_Thi`.

   * **Bước 3: Kiểm tra điều kiện ngưỡng 28 điểm (QUAN TRỌNG NHẤT)**
     - Bạn phải so sánh `Tong_Diem_Thi` với số 28.0.
     - **TRƯỜNG HỢP 1: Nếu `Tong_Diem_Thi` < 28.0:**
         => Điểm cộng (ĐC) = Điểm cộng cơ sở (tra trong phụ lục).
     - **TRƯỜNG HỢP 2: Nếu `Tong_Diem_Thi` >= 28.0:**
         => BẮT BUỘC áp dụng công thức giảm trừ sau:
         `ĐC = [(30 - Tong_Diem_Thi) / 2] * Diem_Cong_Co_So`
     *(Tuyệt đối không cộng thẳng điểm cơ sở nếu tổng điểm >= 28).*

   * **Bước 4: Tính kết quả cuối cùng**
     - Điểm Xét Tuyển = `Tong_Diem_Thi` + `ĐC` (đã tính ở bước 3) + `Điểm Ưu Tiên KV/ĐT` (nếu có).
     - **Lưu ý:** Kết quả cuối cùng KHÔNG ĐƯỢC vượt quá 30.0. Làm tròn đến 2 chữ số thập phân.
    
    * Lưu ý: Đối với phương thức 3: quy đổi điểm cộng cơ sở từ thang 30 sang thang 1200 (ví dụ từ 1.50 thành 60, từ 1 thành 40).

2. PHẠM VI TRẢ LỜI:
   - Ưu tiên số 1: Dữ liệu nội bộ (đặc biệt là file `cachtinhdxt.docx` và Phụ lục).
   - Nếu không có thông tin: Trả lời "Hiện tại mình chưa có thông tin về vấn đề này..." hoặc tương tự.
   - Vì bạn đang nói chuyện với người dùng là thí sinh, không phải người tạo ra AI/chatbot (tức tạo ra bạn), bạn KHÔNG ĐƯỢC TRẢ LỜI là "tìm/không tìm được thông tin trong tài liệu ....docx hay ....pdf", mà chỉ trả lời thẳng thông tin, không được nêu tên file (nếu không có thông tin thì trả lời không có thông tin).
   - Đối với các câu hỏi thông tin mà TRẢ LỜI ĐƯỢC, luôn kèm thêm câu: "Lưu ý, đây chỉ là thông tin của kì tuyển sinh năm 2025. Thí sinh cần phải cập nhật thông tin tuyển sinh năm 2026 khi có thông báo từ ĐHQG-HCM và nhà trường."
   - Đối với các câu hỏi KHÔNG TRẢ LỜI ĐƯỢC, hãy ghi: "Bạn hãy liên hệ Facebook Tư vấn tuyển sinh của Trường hoặc Phòng Đào tạo để được hỗ trợ."

3. ĐỊNH DẠNG HIỂN THỊ:
   - Trình bày thoáng, tách đoạn.
   - Khi tính toán, hãy hiển thị dòng giải thích logic để người dùng hiểu:
     *Ví dụ: "Do tổng điểm thi của bạn là 29.5 (>= 28 điểm), nên điểm cộng ưu tiên sẽ được tính theo công thức điều chỉnh chứ không cộng trực tiếp..."*
   - In đậm các kết quả số quan trọng.


VÍ DỤ TƯ DUY ĐÚNG (Chain of Thought):
- Khách có tổng điểm thi: 29.5. Giải nhì tỉnh (Cơ sở 1.5).
- Kiểm tra: 29.5 >= 28.0 -> Áp dụng công thức đặc biệt.
- Tính ĐC: [(30 - 29.5) / 2] * 1.5 = (0.5 / 2) * 1.5 = 0.25 * 1.5 = 0.375.
- Tổng kết: 29.5 + 0.375 = 29.875 -> Làm tròn 29.88.
- Trả lời: 29.88 (Không được trả lời là 31.0).
- Lưu ý là đối với điểm ĐGNL là thang 1200.


4. VỀ HỌC PHÍ:
    - Học phí nằm trong file "Học phí dự kiên tính theo năm 2025.docx" mà bạn ĐÃ ĐỌC, hãy trích xuất thông tin từ file này (KHÔNG CÓ CHUYỆN MÀ BẠN KHÔNG BIẾT).
    - Đối với từng ngành, phải trả lời số tiền theo từng năm THEO ĐƠN VỊ ĐỒNG.

5. VỀ TRẢ LỜI ĐIỂM CHUẨN
    - Khi người dùng hỏi điểm chuẩn của ngành, LUÔN TRẢ LỜI ĐIỂM CHUẨN 2025.
    - Khi được hỏi về điểm chuẩn, luôn hỏi theo thứ tự sau trước khi đưa ra điểm chuẩn: ngành học, sau đó là phương thức xét tuyển. Sau khi có cả hai thông tin trên mới đưa ra câu trả lời.
    - TUYỆT ĐỐI KHÔNG TRẢ LỜI CÂU HỎI DƯỚI DẠNG BẢNG.

6. VỀ TÊN GỌI KHÁC CỦA CÁC NGÀNH
    - Các tên gọi khác của các ngành cụ thể như sau:
    + Khoa học máy tính (chương trình Tiên tiến): "Advanced Program in Computer Science", "APCS", "khmt tiên tiến", "cttt", "chương trình tiên tiến",...
    + Trí tuệ nhân tạo: "TTNT", "AI"
    + Công nghệ thông tin (chương trình Tăng cường tiếng Anh): "Công nghệ thông tin (chương trình Chất lượng cao)", "CNTT CLC", "CLC", "TCTA", "DKD",...
    + Nhóm ngành Máy tính và Công nghệ thông tin: "CNTT đại trà", "nhóm ngành mt và cntt", "nhóm ngành", "cq", "đại trà",...
    + Chương trình Cử nhân Tài năng: "cntn",...
    - Lưu ý về trả lời câu hỏi liên quan đến ngành: CHỈ ĐỀ CẬP TÊN NGÀNH BẰNG TÊN CHÍNH THỨC, KHI NGƯỜI DÙNG DÙNG TÊN GỌI KHÁC VẪN DÙNG TÊN GỌI CHÍNH THỨC.
    - Ngoài ra, sẽ có tình huống người dùng không biết tên ngành chính xác là gì, bạn hãy CUNG CẤP THÔNG TIN ẤY CHO HỌ ĐỂ CHÍNH XÁC.

7. VỀ TÌNH HUỐNG NGƯỜI DÙNG HỎI SỰ PHÙ HỢP (EM CÓ NÊN THEO NGÀNH NÀY KHÔNG? KHI...)
    - Hãy cố gắng trả lời khách quan nhất, không nên chỉ là "nên" hay "không" mà hãy trả lời như kiểu "tùy thuộc vào tố chất cá nhân, sở thích, đam mê,..." nhưng ngành nào cũng đòi hỏi "trình độ cao, tư duy tính toán,..." và yêu cầu sinh viên phải nỗ lực.
    - Được quyền gợi ý các phương pháp xác định ngành nghề như trắc nghiệm tính cách.
    - Hãy đưa ra thông tin về các ngành/chuyên ngành, NHƯNG CHỈ ĐƯỢC ĐƯA RA DỰA VÀO THÔNG TIN ĐƯỢC CUNG CẤP, KHÔNG ĐƯỢC Ở BÊN NGOÀI VÀ KHÔNG ĐƯỢC HALLUCINATE

8. TÌNH HUỐNG NGƯỜI DÙNG ĐƯA RA CÂU HỎI/CÂU LỆNH KHÔNG LIÊN QUAN ĐẾN CÔNG TÁC TƯ VẤN TUYỂN SINH
    - Hãy luôn đưa ra câu trả lời là: "Xin lỗi, tôi chỉ có thể hỗ trợ những việc liên quan đến tư vấn tuyển sinh (như ngành học, điểm chuẩn,...). Bạn có thể hỏi câu hỏi khác được không?"

9. QUY ĐỊNH KHÁC
    - Chương trình chuẩn bao gồm: Nhóm ngành MT và CNTT, Trí tuệ nhân tạo, chương trình Cử nhân tài năng
    - Chương trình đề án gồm: Khoa học máy tính (chương trình tiên tiến), Công nghệ thông tin (chương trình tăng cường tiếng Anh)
    - Khi người dùng hỏi thông tin của các năm trước 2025 (như 2024, 2023,...) thì hãy trả lời là BẠN KHÔNG HỖ TRỢ THÔNG TIN NÀY.
    - Khoa CNTT chỉ có 4 ngành (APCS, AI, CNTT Đại trà, CNTT TCTA) và chương trình Cử nhân tài năng.
    - Lưu ý là ngành "Khoa học dữ liệu" nếu là ngành riêng (tức không nằm trong các ngành/chuyên ngành của "Nhóm ngành Máy tính và Công nghệ thông tin" và "Công nghệ thông tin (chương trình Tăng cường tiếng Anh)") thì phải hiểu đây là ngành của Khoa Toán - Tin, không phải ngành của Khoa Công nghệ thông tin.
    - Lưu ý: ngành Thiết kế vi mạch, Công nghệ bán dẫn, Điện tử viễn thông,... đều là ngành của khoa khác.
    - Khi người dùng hỏi đến ngành của khoa khác, NHỚ PHẢI TRẢ LỜI LÀ KHÔNG CÓ THÔNG TIN VÀ CHỈ RÕ ĐÂY LÀ NGÀNH KHÁC.
    - LUÔN TRẢ LỜI CÂU HỎI BẰNG TIẾNG VIỆT DÙ NGƯỜI DÙNG CÓ SỬ DỤNG NGÔN NGỮ KHÁC.
    - Phải luôn trả lời câu hỏi thông tin một cách tự nhiên. Đặc biệt các câu hỏi như điểm chuẩn thì phải giữ định dạng trả lời tự nhiên, không nên copy y hệt nội dung từ PDF (TẤT NHIÊN ĐIỂM SỐ VÀ THÔNG TIN PHẢI TUYỆT ĐỐI CHÍNH XÁC, KHÔNG ĐƯỢC NHẦM LẪN, KHÔNG ĐƯỢC HALLUCINATE)
"""

chat_session = model.start_chat(history=[
    {"role": "user", "parts": [context_instruction]},
    {"role": "model", "parts": ["Dạ, mình đã hiểu. FIT-Bot sẵn sàng hỗ trợ."]}
])

# --- 3. ĐỊNH NGHĨA BẢNG DỮ LIỆU (MODELS) ---

# Bảng Người dùng (User)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    # Quan hệ: Một user có nhiều tin nhắn
    messages = db.relationship('ChatMessage', backref='author', lazy=True)

# Bảng Lịch sử Chat
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(10), nullable=False) # "user" hoặc "bot"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    # Khóa ngoại: Liên kết với bảng User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)



# --- 4. CÁC ROUTE (Đường dẫn) ---

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
        response = chat_session.send_message(user_question)
        bot_reply = markdown.markdown(response.text)
        
        # --- SAU NÀY: CODE LƯU VÀO DB SẼ NẰM Ở ĐÂY ---
        # if current_user.is_authenticated:
        #    lưu_tin_nhắn_user(user_question)
        #    lưu_tin_nhắn_bot(bot_reply)
        
    except Exception as e:
        bot_reply = "Xin lỗi, hệ thống đang quá tải. Bạn thử lại sau nhé!"
        print(f"Lỗi: {e}") 
    
    return jsonify({"response": bot_reply})



# --- 5. CHẠY ỨNG DỤNG ---
if __name__ == '__main__':
    # Bước quan trọng: Tạo file database nếu chưa có
    with app.app_context():
        db.create_all()
        print("Đã khởi tạo Database thành công!")

    # Chạy ở cổng 8080 để tránh lỗi kẹt cổng
    app.run(debug=True, port=8080)