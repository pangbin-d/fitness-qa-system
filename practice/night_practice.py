#system人设，让AI扮演健身教练
import os
import requests
from dotenv import load_dotenv
load_dotenv()
api_key=os.getenv(("DEEPSEEK_API_KEY"))
url="https://api.deepseek.com/chat/completions"
headers={
    "Authorization":f"Bearer {api_key}",     #Bearer和key之间要有空格，不然会和API key连起来，程序无法识别key
         "Content-Type":"application/json"
}
SYS={"role":"system","content":"你是专业健身教练，回答不超过50个字"}   #将system人设单独提取出来定义一个变量，实现复用
messages=[
          SYS,{"role":"user","content":"卧推肩膀疼怎么回事？"}
]


resp=requests.post(url,headers=headers,json={"model":"deepseek-chat","messages":messages,},timeout=20)
print("第一问：",resp.json()["choices"][0]["message"]["content"])


#多轮对话，把AI的回答塞回去，验证“记忆”
reply1=resp.json()["choices"][0]["message"]["content"]
messages.append(
    {"role":"assistant","content":reply1}
)
messages.append(
    {"role":"user","content":"那热身该怎么做？"}              #第二次请求带着完整历史，AI才知道“那”指的是卧推肩膀疼
)
resp2=requests.post(url,headers=headers,json={"model":"deepseek-chat","messages":messages},timeout=20)
print("第二问：",resp2.json()["choices"][0]["message"]["content"])


#for循环批量调用（逐个调API原型）
questions = ["卧推肩膀疼怎么办？", "一天吃多少蛋白质?", "减脂期能喝奶茶吗？"]
for q in questions:
    m = [SYS,{"role": "user", "content": q}]             #把问题包成messages
    r = requests.post(url, headers=headers, json={"model": "deepseek-chat", "messages": m}, timeout=20)
    print(f"问：{q}")
    print(f"答：{r.json()['choices'][0]['message']['content']}")




