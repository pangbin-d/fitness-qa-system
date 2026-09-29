'''命令行聊天机器人v0.1
功能：基于deepseekAPI的多轮对话，支持上下文记忆
作者：pangbin-d
'''
import os                         #读环境变量
import requests                   #发送HTTP请求
from dotenv import load_dotenv    #把.env里的key加载进来
load_dotenv()
API_KEY=os.getenv("DEEPSEEK_API_KEY")
API_URL="https://api.deepseek.com/chat/completions"

#将”网络请求“单独封装成一个函数
def chat(messages):                #把消息列表发给deepseek返回模型回复文本
    headers={
        "Authorization":f"Bearer {API_KEY}",
        "Content-Type":"application/json"
    }
    data={
        "model":"deepseek-chat",
        "messages":messages,
        "temperature":0.7,         #表示回答的随机性0.7是默认值，1.5＋适用于创作，0表示答案不变
        "max_tokens":512          #token是模型切文本的最小单位，一个字约等于1.5~2token，聊天一般是512~1024
    }
    response=requests.post(url=API_URL,headers=headers,json=data)
    response.raise_for_status()
    result=response.json()         #.json表示转换，将json文件转换成python字典塞进变量里
    return result["choices"][0]["message"]["content"]
def main():
    print("聊天机器人已启动，输入exit退出")
    messages=[{
        "role":"system",
        "content":"你是一个专业靠谱的健身教练，回答不超过30字"
              }]
    while True:                    #因为机器人要一轮接一轮的对话
        user_input=input("我：")
        if user_input.strip().lower()=="exit":
        #给用户输入清洗干净的方法，strip（）去掉首尾空格，换行;lower()全转小写。防止用户输入成Exit之类的，属于防御性编程。
            print("再见")
            break
        messages.append({"role":"user","content":user_input})
        reply=chat(messages)
        messages.append({"role":"assistant","content":reply})
        print("机器人：",reply)
if __name__=="__main__":           #文件被直接调用时才用到main（），被别的模块import时代码不会自动执行。
    main()                         #调用一下让代码真的跑起来


