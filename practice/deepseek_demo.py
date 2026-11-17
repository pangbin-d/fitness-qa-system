import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DEEPSEEK_API_KEY")

url = "https://api.deepseek.com/chat/completions"
headers = {     #headers字典，告诉服务器我是谁，发的什么格式
    "Authorization": f"Bearer {api_key}",    #相当于服务器门禁卡，没有会401，Bearer是固定前缀
    "Content-Type": "application/json"      #没有的话服务器不知道你的body是什么格式
}
data = {
    "model": "deepseek-chat",
    "messages": [           #相当于一个回答的结构体，包含“谁说的+说了什么”也是列表套字典结构
        {"role": "user", "content": "用一句话介绍你自己"}
    ]
}

resp = requests.post(url, headers=headers, json=data, timeout=30)
print("状态码：", resp.status_code)

answer = resp.json()["choices"][0]["message"]["content"]#resp.json（）把服务器返回的json字符串转换成字典，
                                # choices是一个列表，取出第0个元素，取出message这个字典，content是最终那句话:我是一个大语言模型
print("AI 回的：", answer)