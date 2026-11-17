import json
import os
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()
client=OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)
prompt="""你是健身解析专家，请解析用户给出的动作，只输出一个JSON对象，包含：
- action: 动作名称（字符串）
- muscle: 主要目标肌肉群（字符串）
- beginner-friendly: 新手是否适合（布尔值true/false）
- tips: 1-3条动作要点组成的列表
严格要求:
1.只输出JSON本身，禁止输出"好的""以下是"等多余文字
2.禁止使用markdown代码块
3.信息不足时，对应字段填null，禁止编造
"""
#将‘调用＋解析’包成一个函数，user内容从参数传进去
def parse_action(user_text):
    messages=[{"role":"system","content":prompt},
              {"role":"user","content":user_text}
              ]
    data={"model":"deepseek-chat",
          'messages':messages,
          "temperature":0,
          }
    #这行代码是把data字典里的参数发给Deepseek服务器然后等待服务器把完整回复发送过来存进response变量，**表示解包，相当于把字典拆开
    response=client.chat.completions.create(**data)
    #这行代码是把模型说的话掏出来，最后要的content是消息正文，是一个长得像字典但本质还是字符串的东西，需要json.loads把他转换成字典，第35行
    content=response.choices[0].message.content
    #将第30行得到的content字符串内容转变为字典内容。
    result=json.loads(content)
    return result
test_inputs = [
    "杠铃深蹲",                    # 1. 正常复合动作
    "引体向上",                    # 2. 正常动作
    "今天天气真好啊",              # 3. 不是动作 → 该填 null，看它编不编
    "就是那个躺着往上推的",        # 4. 含糊描述 → 幻觉考验
    "deadlift",                    # 5. 英文输入
]
for text in test_inputs:
    print(f"\n-----输入：{text}-----")
    try:
       result=parse_action(text)
       print(result)
    except json.JSONDecodeError:
        print("解析失败！模型没老实输出JSON")
    except KeyError as e:
        print(f"键名又被偷改：{e}")