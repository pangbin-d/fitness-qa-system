import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DEEPSEEK_API_KEY")

print("=== 诊断信息 ===")
print("读到Key没:", api_key is not None)
print("长度:", len(api_key) if api_key else 0)
print("前4位:", api_key[:4] if api_key else "无")
print("后4位:", api_key[-4:] if api_key else "无")
print("是否带空格:", "  " in api_key if api_key else "无")
print()

url = "https://api.deepseek.com/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
# 同时试两个模型名
for model in ["deepseek-chat", "deepseek-flash"]:
    print(f"--- 尝试模型: {model} ---")
    data = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}]
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=20)
        print("状态码:", resp.status_code)
        print("原始响应:", resp.text[:300])
        if resp.status_code == 200:
            print("模型", model, "能用!")
            break
    except Exception as e:
        print("请求炸了:", e)