import os
import json
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
EXTRACT_SYS = """你是一个健身咨询信息抽取器。
从用户的健身描述中抽取信息，只输出一个JSON对象，字段如下：

{
  "goal": 健身目标，只能取 "增肌"、"减脂"、"塑形" 或 null,
  "weight_kg": 体重数字，单位统一为kg，或 null,
  "injuries": 伤病部位列表，如 ["膝盖", "腰部"],
  "equipment": 可使用的器械列表，如 ["哑铃", "杠铃"],
  "days_per_week": 每周训练天数，整数，或 null
}

抽取规则：
1. 没提到的字段：单值字段填 null，列表字段填 []，不许编造
2. goal 只能四选一：想变壮/练块儿/长肉/练宽 → "增肌"；
   减肥/瘦/燃脂/掉秤 → "减脂"；线条/紧致/体态 → "塑形"；判断不了就 null
3. injuries、equipment 永远是数组，只有一项也要用 [] 包起来
4. 体重统一换算成公斤：1公斤=1kg，1斤=0.5kg，只输出数字
5. days_per_week 给范围（如"四五次"）取较小的数字
6. 只抽说话人本人的信息，别把别人（如室友）的算进来
7. 只输出JSON，不要任何解释和markdown代码块"""
FEW_SHOT = [
    {
        "role": "user",
        "content": "我140斤，最近想减肥瘦肚子，腰有时候不舒服，家里有瑜伽垫和哑铃，一周大概练三四次吧",
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "goal": "减脂",
            "weight_kg": 70,
            "injuries": ["腰部"],
            "equipment": ["瑜伽垫", "哑铃"],
            "days_per_week": 3,
        }, ensure_ascii=False),
    },
    {
        "role": "user",
        "content": "我想把肩膀练宽练壮，没啥伤，学校健身房杠铃哑铃都有，周一到周五都能去",
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "goal": "增肌",
            "weight_kg": None,
            "injuries": [],
            "equipment": ["杠铃", "哑铃"],
            "days_per_week": 5,
        }, ensure_ascii=False),
    },
]
def make_client():
    return OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com")
    )
def extract_info(client,paragraph):
    messages=([{
        "role":"system",'content':EXTRACT_SYS
    }]+FEW_SHOT+[{                        #FEW_SHOT是可复用的题目例子，所以写在[]外面每次循环都调用一次。
        "role":"user","content":paragraph
    }]
              )
    resp=client.chat.completions.create(
        model='deepseek-chat',
        messages=messages,
        temperature=0,
        response_format={"type":"json_object"}
    )
    raw=resp.choices[0].message.content
    return json.loads(raw)
def main():
    client=make_client()
    tests=[ "我140斤，想练大块头，以前膝盖受过伤，宿舍只有一对哑铃，每周能练4天",
        "我就想随便活动活动，身体没啥毛病",
        "想减肥，130斤，膝盖和腰都不太好，有弹力带和瑜伽垫，一周练个四五次吧",
        "我室友180斤想增肌，我自己60公斤，就想瘦腿，没有器械，一周在家跟视频练3次",
    ]
    for text in tests:
        print(f"原文{text}")
        result=extract_info(client,text)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        print("="*50)
if __name__=="__main__":
    main()