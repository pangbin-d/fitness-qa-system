import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
#零件一：三个角色的system prompt
COACH_SYS = """你是一名有10年经验的健身教练，服务增肌减脂人群。

职责：
1. 只回答训练相关问题：动作要领、训练计划、疲劳恢复。
2. 建议必须具体可执行，包含动作、组数、次数。

边界：
1. 不回答疾病诊断、用药、医疗问题，遇到时回复：
"这个超出我的范围，建议先咨询医生。"
2. 饮食可以给一句通用建议，再说："详细方案建议咨询营养师。"

语气：直接、鼓励、像带训的教练，回答不超过150字。"""


NUTRITIONIST_SYS = """你是一名注册营养师，擅长健身人群的饮食搭配。

职责：
1. 只回答饮食与营养问题：热量、三大营养素、食谱调整。
2. 建议要落到具体食物和份量。

边界：
1. 不回答疾病、过敏治疗、用药问题，遇到时回复：
"这个超出我的范围，建议先咨询医生。"
2. 训练动作和计划问题不展开，只说："训练部分建议咨询健身教练。"

语气：温和、专业，回答不超过150字。"""


REVIEWER_SYS = """你是一名健身问答质量评审专家，只评测问答质量，不直接回答健身问题。

职责：
1. 只对"给定的用户问题和系统回答"做质量评测。
2. 从四个维度打分（每项0-10分）：正确性、相关性、可执行性、安全性。

边界：
1. 用户直接向你提问健身问题时，不回答，回复：
"我是评审，不直接回答健身问题，请把需要评测的问答发给我。"
2. 只输出 JSON，不输出多余解释。

输出格式：
{"correctness": x, "relevance": x, "actionability": x, "safety": x, "comment": "一句话总评"}"""
#零件二：客户端＋调用函数
#造工具，即客户端对象
def make_client():
    return OpenAI(               #return把造好的对象交到调用者手里，让main里的client=make_client（）接收到
        api_key=os.getenv('DEEPSEEK_API_KEY'),
        base_url=os.getenv("DEEPSEEK_BASE_URL",'https://api.deepseek.com')
    )
#调用一次工具的标准动作
def ask(client,system_prompt,user_content,temperature=0.7):
    """同一次请求 = system 立规矩 + user 提问题"""
    resp=client.chat.completions.create(   #client.chat.completions.create是把请求发出去，返回值塞进resp
        model="deepseek-chat",
        messages=[
            {
                'role':'system',
                'content':system_prompt
             },
            {
                'role':"user",
                "content":user_content
            },
        ],
        temperature=temperature
    )
    return resp.choices[0].message.content        #return的是最后的content（字符串内容），作用是交出正文
#零件三，四：同一个问题跑三个角色，再让评审干活
def main():                                 #main只管安排不干活，没有return，任务是跑完整个流程并打印结果。
    client=make_client()                    #先造好对象
    question="我膝盖有点疼，还能练深蹲嘛？练完吃什么能长肌肉？"
    roles=[                                  #列表装元组
        ("健身教练",COACH_SYS,0.7),
        ("营养师",NUTRITIONIST_SYS,0.7),
        ("评审专家",REVIEWER_SYS,0.3),
    ]
    # 空字典当仓库
    answers={}
    for name,sys_prompt,temp in roles:      #相当于解包
        print("="*50)
        print(f"[{name}]")
        answer=ask(client,sys_prompt,question,temperature=temp)   #question不变，变的只有sys_prompt和temp
        print(answer)
        #回答存进仓库，每次回答按照角色名字存进字典，目的是把教练回答翻出来给评审
        answers[name]=answer
    review_input=(f"用户问题：{question}\n\n"
                  f"教练回答{answers["健身教练"]}\n\n"
                  "请按格式输出JSON"
                  )
    print("="*50)
    print('[评审专家评测教练回答]')
    #评审二次上岗，ask把content字符串return回来，print打印到屏幕。
    print(ask(client,REVIEWER_SYS,review_input,temperature=0.3))

if __name__=="__main__":
    main()
