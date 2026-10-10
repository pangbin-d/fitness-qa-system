'''命令行聊天机器人v0.1
功能：基于deepseekAPI的多轮对话，支持上下文记忆
作者：pangbin-d
'''
import os                         #读环境变量
#import requests                   #发送HTTP请求,换成openaiSDk格式
from openai import OpenAI
from build_api_config import build_api_config
from dotenv import load_dotenv    #把.env里的key加载进来
load_dotenv()
API_KEY=os.getenv("DEEPSEEK_API_KEY")
#API_URL="https://api.deepseek.com/chat/completions"
client=OpenAI(
    api_key=API_KEY,
    base_url="https://api.deepseek.com"
)
#将”网络请求“单独封装成一个函数(调用request版)
# def chat(messages):                #把消息列表发给deepseek返回模型回复文本
#     headers={
#         "Authorization":f"Bearer {API_KEY}",
#         "Content-Type":"application/json"
#     }
#     #函数封装
#     data=build_api_config('deepseek-chat',0.7,512)
#     data['messages']=messages
#     '''data={                          列字典写法：
#         "model":"deepseek-chat",
#         "messages":messages,
#         "temperature":0.7,         #表示回答的随机性0.7是默认值，1.5＋适用于创作，0表示答案不变
#         "max_tokens":512   }       #token是模型切文本的最小单位，一个字约等于1.5~2token，聊天一般是512~1024'''
#     response=requests.post(url=API_URL,headers=headers,json=data)
#     response.raise_for_status()
#     result=response.json()         #.json表示转换，将json文件转换成python字典塞进变量里
#     return result["choices"][0]["message"]["content"]
def chat(messages):
    data=build_api_config('deepseek-chat',0.7,512)
    data['messages']=messages
    data['stream']=True              #总开关，开启水流模式
    #网络挂了抛出异常，让main好接收
    try:
        stream=client.chat.completions.create(**data)#一个水流对象，相当于管子，数据顺着管子流出来
    except Exception as e:
        raise RuntimeError(f"API请求失败：{e}")

    reply=""               #准备一个空字符串当篮子，让存进messages里的碎片信息拼接完整
    for chunk in stream:    #流式输出是来一个小包转一圈，普通写法调一次API拿一个结果，流式写法要循环接N个小包
        delta=chunk.choices[0].delta.content #delta代表增量，不是普通版message，每个包只装新冒出来的几个字，不是一整句话
        if delta:
            print(delta,end="",flush=True)  #end“”的意思是print的自动换行改成末尾用空字符串代替；flush=True意思是不要积攒，立刻显示
            reply +=delta
    print()                       #流式输出结束单独补一个换行不然提示符和下一轮的“我：”会挤在同一行
    return reply

def main():
    print("===文武的健身AI助手V1.0===")
    print("输入/help查看命令，输入/quit 退出\n")
    messages=[]
    while True:                    #因为机器人要一轮接一轮的对话
        user_input=input("\n我：").strip()
        if not user_input:      #空输出直接进下一轮，不发请求
            continue
        if user_input.startswith('/'):
            if user_input=='/quit':
               print("再见")
               break
            elif user_input=='/help':
                print("支持的命令")
                print("/help - 显示本帮助")
                print("/reset - 清空对话历史")
                print("/quit - 退出程序")
                pass
            elif user_input=='/reset':
                messages.clear()
                print("对话已重置")
                pass
            else:
                print("未知命令，输入/help 查看支持的命令")
                continue
        messages.append({"role":"user","content":user_input})
        print("助手：",end="")

        #上下文裁剪，当对话堆积过多，进行清除旧对话以减少token损耗
        MAX_TURNS=10
        if len(messages)>MAX_TURNS*2+1:
            messages=[messages[0]]+messages[-MAX_TURNS*2:]#messages[0]是取出来的一个字典，要用[]把它包成一个列表API才认
            #流式输出的顺序是按照屏幕显示的先后排，不是按照数据处理排的。先print，再接reply；messages.append相当于把完整回复存进上下文

        try:      #API挂了不让整个程序死
            reply=chat(messages)
            messages.append({"role":"assistant","content":reply})
        except Exception as e:
            print(f"\n请求出错：{e}")
            messages.pop()       #把这轮刚append的user消息拿走
            pass
if __name__=="__main__":           #文件被直接调用时才用到main（），被别的模块import时代码不会自动执行。
    main()                         #调用一下让代码真的跑起来


