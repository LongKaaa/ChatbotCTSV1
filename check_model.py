import google.generativeai as genai

# Dán API Key của bạn vào đây
MY_API_KEY = "AIzaSyAaJQ9rUiyLbw1st-4p8wooVU_67OhVmIA"
genai.configure(api_key=MY_API_KEY)

print("Danh sách các model bạn được dùng:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)