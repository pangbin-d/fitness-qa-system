#这段信息抽取代码的作用： 数据持久化 + 解耦
# 持久化：单纯在终端显示，内存里的变量程序一关就死，写进文件才"活"下来
# 解耦：抽取程序和打分程序各干各的，中间用文件传话。抽取半夜跑完，你第二天再打分都行，两个程序甚至能两台电脑跑。
# 类比：print是你拿嘴报数，报完就散；jsonl是快递员把包裹**扫描入库**，后面分拣、运输、签收全靠这条入库记录。
import os
import time
from openai import (              #（）里是SDK"临时故障"的标准四件套
APITimeoutError,
APIConnectionError,
RateLimitError,
InternalServerError
)
import json
import time

from openai import OpenAI
from dotenv import load_dotenv
QUESTIONS_FILE='question_extraction.txt'
#.json是一个文件一整个大数组全跑完再写，中途崩了直接废；.jsonl是每行一个独立对象，跑完一条过一条，以后追加也方便
OUTPUT_FILE='results.jsonl'
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
MAX_RETRIES=3                    #代表第几轮尝试
RETRYABLE_ERRORS=(
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    InternalServerError
)
#这个函数不管抽取的业务，只保证一件事就是连接通没通，要么通了返回回话，要么连接尝试满四次认栽
def chat_with_retry(client,msgs,temperature=0,json_mode=True):   #msgs是要传的信息
    response_format={'type':'json_object'} if json_mode else None    #后边的if意思是：要JSON就写配置，不要就None
    for attempt in range(MAX_RETRIES+1):
        try:
            return client.chat.completions.create(
                model='deepseek-chat',
                messages=msgs,
                temperature=temperature,
                response_format=response_format,
            )
        except RETRYABLE_ERRORS as e:          #意思是只接四种临时故障
            if attempt==MAX_RETRIES:
                #type(e).__name__这个格式是点号链，先拿到e，再查它的类，再只取类型的名字（类的属性）
                print(f"连打{MAX_RETRIES+1}次全挂，放弃：{type(e).__name__}")
                raise              #连着四次都挂了就打印遗言然后raise抛出去，直接给到main里的error行
            wait=2 ** attempt
            print(f"第{attempt+1}次挂了({type(e).__name__}),{wait}秒后重拨...")
            time.sleep(wait)               #和main里的sleep区别是只有失败才睡目的是给故障恢复留时间窗口。
def extract_info(client,paragraph):
    msgs=([{
        "role":"system",'content':EXTRACT_SYS
    }]+FEW_SHOT+[{                        #FEW_SHOT是可复用的题目例子，所以写在[]外面每次循环都调用一次。
        "role":"user","content":paragraph
    }]
              )
    resp=chat_with_retry(client,msgs)
    raw=resp.choices[0].message.content
    return json.loads(raw)
def load_questions(path):
    #读题库，每行一道题，strip换掉换行符和空格，空行跳过。
    questions=[]
    with open(path,'r',encoding='utf-8')as f:
        for line in f:
            text=line.strip()
            if text:
                questions.append(text)
    return questions
def main():
    #1.开工准备（循环外只干一次）
    client=make_client()
    questions=load_questions(QUESTIONS_FILE)             #获取四道题的清单列表
    #2.打开成品仓库
    with open(OUTPUT_FILE,'w',encoding='utf-8')as out:   #想重跑新文件用w，想在旧文件后边追加用a；out是文件对象，write就是往这里边写东西
        #3.流水线，每个零件走一遍
        for i,text in enumerate(questions,start=1):      #enumerate相当于取号机，一边遍历一边发号i是号，text是段落
            print(f"[{i}/{len(questions)}抽取中...")
            try:
                result=extract_info(client,text)
                record={                                 #record相当于一个包裹把问题和回答包在一起
                    'question':text,
                    "result":result
                }
            except Exception as e:
                record={
                    'question':text,
                    "error":str(e)           #e是错误对象，str（e）是变成能让dumps转换成字典的文本格式。保证record一直存在，不会以因为异常就崩溃。
                }
            out.write(json.dumps(record,ensure_ascii=False)+"\n")   #\n是jsonl格式的灵魂，一行一件。
            out.flush()                                  #写完一条立刻保存，不在缓冲区攒着
            time.sleep(1)                                #每条之间歇一条，400条题是不会被限流
        print(f"收工，共{len(questions)}条-->{OUTPUT_FILE}")
if __name__=="__main__":
    main()