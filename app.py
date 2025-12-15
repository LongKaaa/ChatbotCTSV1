import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash 
from datetime import datetime
from docx import Document
from pypdf import PdfReader
import markdown
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {
    "origins": [
        "https://hcmusaibybopcteam.netlify.app",  # <-- Thay bằng link Netlify thật của bạn
        "http://127.0.0.1:5500"              # <-- Để test trên máy
    ],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True  # <--- QUAN TRỌNG NHẤT: Cho phép nhận Cookie
}})

# CẤU HÌNH COOKIE ĐỂ CHẠY ĐƯỢC TRÊN HTTPS (RENDER)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    # Lấy toàn bộ tin nhắn của user hiện tại, sắp xếp theo thời gian
    messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.timestamp).all()
    
    history_data = []
    for msg in messages:
        history_data.append({
            "role": msg.role,
            "content": msg.content,
            # Chỉ lấy 30 ký tự đầu làm tiêu đề cho sidebar nếu là tin nhắn user
            "preview": msg.content[:30] + "..." if len(msg.content) > 30 else msg.content
        })
    
    return jsonify(history_data)

# --- 1. CẤU HÌNH DATABASE ---
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Fix lỗi nhỏ: Render/Supabase trả về "postgres://" nhưng thư viện cần "postgresql://"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(">>> Đang sử dụng PostgreSQL (Online)")
else:
    # Nếu không tìm thấy (tức là đang chạy trên máy tính), dùng SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
    print(">>> Đang sử dụng SQLite (Local)")

app.config['SECRET_KEY'] = 'khoa-cntt-hcmus-secret-key-2024'
db = SQLAlchemy(app)

# --- THÊM: CẤU HÌNH LOGIN MANAGER ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Không dùng route này nhưng cần khai báo

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# --- 2. CẤU HÌNH AI GEMINI ---
# ⚠️ QUAN TRỌNG: Thay API Key MỚI của bạn vào đây
MY_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=MY_API_KEY)

# Dùng model chuẩn 2.5-flash
model = genai.GenerativeModel('gemini-2.5-flash')

# Đọc dữ liệu
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
   - Sử dụng dấu gạch đầu dòng (-) cho các ý thay vì (*) (Quan trọng). Chỉ sử dụng (*) khi trong câu trả lời có Lưu Ý hoặc ý quan trọng


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
    - Khi tiếp nhận câu hỏi về điểm chuẩn, hệ thống cần xác định rõ Ngành học và Phương thức xét tuyển. Nếu người dùng chưa cung cấp tên ngành, hãy hỏi lại để làm rõ. Nếu đã có tên ngành nhưng thiếu phương thức xét tuyển, hãy cung cấp bảng điểm của tất cả các phương thức. Chỉ trả lời kết quả cụ thể khi đã có đầy đủ hai thông tin trên.
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

9. QUY ĐỊNH VỀ CÁCH TRẢ LỜI VỀ REVIEW NGÀNH (ví dụ: em muốn tìm hiểu về ngành thị giác máy tính ạ)
    - Hãy hỏi bổ sung những câu hỏi dẫn dắt để có thể đưa ra câu trả lời trọng tâm hơn, tức hỏi người dùng muốn hỏi cụ thể về cái gì (nói chung về ngành, học cái gì, làm cái gì, chương trình đào tạo, nội dung học...).
    - Nếu người dùng vẫn insist việc hỏi như vậy (tức chỉ xin review hoặc tương tự), hoặc người dùng không biết, thì hãy TÓM TẮT CHÍNH XÁC và TỔNG QUÁT về ngành học, KHÔNG ĐƯỢC GHI HẾT TOÀN BỘ THÔNG TIN TRONG 1 LẦN (trừ khi người dùng yêu cầu).

10. VỀ TÌNH HUỐNG KHI NGƯỜI DÙNG HỎI VỀ CHƯƠNG TRÌNH ĐÀO TẠO
    - Vì hiện tại thông tin của bạn chưa đầy đủ và khách quan, hãy trả lời như sau: "Bạn vui lòng tham khảo chương trình đào tạo tại trang web của Trường hoặc Khoa Công nghệ thông tin".
    - Nếu người dùng hỏi những câu như "học có khó ko", "học môn vi tích phân có khó ko", "học đại cương nặng ko", thì hãy trả lời theo hướng KHÔNG TRẢ LỜI TRỰC TIẾP, mà chỉ trả lời là chương trình đào tạo tốt, đạt chuẩn quốc tế, và quá trình học tùy thuộc theo tố chất và nỗ lực của từng cá nhân
    
11. QUY ĐỊNH KHÁC
    - Cố gắng đưa ra thêm câu hỏi dẫn dắt để có thể có câu trả lời trọng tâm và ngắn gọn hơn, hạn chế việc ghi hết toàn bộ thông tin trong một tin nhắn (tạo ra wall of text).
    - Không được bình luận về trường khác. Khi được hỏi so sánh với trường khác (ví dụ, UIT, HCMUT/BKU, HUST, UET,...) thì không được trả lời BẤT CỨ GÌ liên quan đến các trường đó, cũng như KHÔNG ĐƯA RA BÌNH LUẬN về các trường đó. Hãy từ chối trả lời câu hỏi trên và nói rằng "Khoa CNTT tại ... là môi trường đào tạo tốt, thuộc hàng đầu cả nước".
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

# --- 3. MODELS (CẬP NHẬT CẤU TRÚC MỚI) ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    conversations = db.relationship('Conversation', backref='owner', lazy=True)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), default="Cuộc trò chuyện mới")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.relationship('ChatMessage', backref='conversation', lazy=True, cascade="all, delete-orphan")

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(10), nullable=False) # 'user' hoặc 'bot'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)



# --- 4. ROUTES ---

@app.route('/')
def home():
    return "Backend is running"

# AUTHENTICATION APIs
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"success": False, "message": "Tên đăng nhập đã tồn tại"})
    hashed_pw = generate_password_hash(data['password'])
    new_user = User(username=data['username'], password=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"success": True, "message": "Đăng ký thành công"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password, data['password']):
        login_user(user)
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Sai tên đăng nhập hoặc mật khẩu"})

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    response = jsonify({"success": True})
    response.set_cookie('session', '', expires=0, secure=True, samesite='None')
    return response

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    if current_user.is_authenticated:
        return jsonify({"is_logged_in": True, "username": current_user.username})
    return jsonify({"is_logged_in": False})

# --- CONVERSATION APIs (MỚI) ---

# 1. Lấy danh sách các cuộc hội thoại
@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    convs = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.timestamp.desc()).all()
    return jsonify([{ "id": c.id, "title": c.title } for c in convs])

# 2. Tạo cuộc hội thoại mới
@app.route('/api/conversation/new', methods=['POST'])
@login_required
def new_conversation():
    new_conv = Conversation(user_id=current_user.id, title="Cuộc trò chuyện mới")
    db.session.add(new_conv)
    db.session.commit()
    return jsonify({"success": True, "id": new_conv.id})

# 3. Lấy nội dung tin nhắn của 1 hội thoại
@app.route('/api/conversation/<int:conv_id>', methods=['GET'])
@login_required
def get_conversation_content(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.user_id != current_user.id:
        return jsonify({"error": "Không có quyền truy cập"}), 403
    
    messages = ChatMessage.query.filter_by(conversation_id=conv.id).order_by(ChatMessage.timestamp).all()
    return jsonify([{ "role": m.role, "content": m.content } for m in messages])
# 4. API Xóa cuộc hội thoại
@app.route('/api/conversation/delete/<int:conv_id>', methods=['DELETE'])
@login_required
def delete_conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.user_id != current_user.id:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    db.session.delete(conv)
    db.session.commit()
    return jsonify({"success": True})
@app.after_request
def add_header(response):
    # Yêu cầu trình duyệt không bao giờ cache các API
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response
# 5. API Đổi tên cuộc hội thoại
@app.route('/api/conversation/rename/<int:conv_id>', methods=['PUT'])
@login_required
def rename_conversation(conv_id):
    data = request.json
    new_title = data.get('title')
    
    conv = Conversation.query.get_or_404(conv_id)
    if conv.user_id != current_user.id:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    conv.title = new_title
    db.session.commit()
    return jsonify({"success": True})
# 4. Gửi tin nhắn (Cập nhật để hỗ trợ conversation_id)
@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    user_question = data.get('message')
    conv_id = data.get('conversation_id')

    if not user_question: return jsonify({"response": "Rỗng"})

    # ... (giữ nguyên phần xử lý conversation_id) ...
    if not conv_id:
        new_conv = Conversation(user_id=current_user.id, title=user_question[:30])
        db.session.add(new_conv)
        db.session.commit()
        conv_id = new_conv.id
    else:
        conv = Conversation.query.get(conv_id)
        if conv and conv.title == "Cuộc trò chuyện mới":
            conv.title = user_question[:40] + "..." if len(user_question) > 40 else user_question
            db.session.commit()

    try:
        response = chat_session.send_message(user_question)
        bot_reply = markdown.markdown(
            response.text, 
            extensions=['extra', 'nl2br', 'sane_lists']
        )
        user_msg = ChatMessage(content=user_question, role='user', conversation_id=conv_id)
        bot_msg = ChatMessage(content=bot_reply, role='bot', conversation_id=conv_id)
        db.session.add_all([user_msg, bot_msg])
        db.session.commit()

        return jsonify({
            "response": bot_reply,
            "conversation_id": conv_id,
            "new_title": conv.title 
        })

    except Exception as e:
        print(f"Lỗi chat: {e}")
        return jsonify({"response": "Hệ thống đang bận, vui lòng thử lại sau."})


# --- 5. CHẠY ỨNG DỤNG ---
@app.route('/ping')
def ping():
    return "Pong", 200
# --- THÊM ĐOẠN NÀY RA NGOÀI ĐỂ RENDER CHẠY ĐƯỢC ---
with app.app_context():
    db.create_all()
    print(">>> Đã khởi tạo Database trên Render thành công!")
# -----------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True, port=8080)