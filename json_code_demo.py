import json
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client=OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url='https://api.deepseek.com'
)
# 层级	                             管什么	                 强制吗	 什么时候用
# json_object	                外壳是合法 JSON	            ✅ 强制	  默认开启
# prompt + schema + few-shot	字段名/类型/枚举	            ❌ 约定	  绝大多数场景够用
# json_schema + strict	        字段名/类型/枚举/必填/禁止多余	✅ 真强制  字段多、枚举复杂、必须稳
system_prompt = """
你是健身问答评审专家。对用户给出的"问题"和"回答"从四个维度打分，
每个维度1-5分，并给出总体评语。必须输出JSON格式。              #在prompt中写死schema

EXAMPLE JSON OUTPUT:                                   #在prompt中加few shot                    
{
    "accuracy": 4,
    "completeness": 3,
    "safety": 5,
    "relevance": 4,
    "comment": "回答基本正确，但缺少动作细节。"
}
"""
user_prompt = '问题：深蹲膝盖能不能超过脚尖？\n回答：不能，超过脚尖就会伤膝盖。'
messages=[
    {'role':'system','content':system_prompt},
    {'role':'user','content':user_prompt}
]
response=client.chat.completions.create(
    model='deepseek-chat',
    messages=messages,
    response_format={'type':'json_object'}          #结构化输出的关键代码，但是只管是不是合法JSON结构，不管里面装啥
)
content=response.choices[0].message.content
if not content:
    raise  ValueError("模型返回空内容。需要重试")
result=json.loads(content)
#将pyth字典转换为json字符串，每层缩进俩空格，让中文原样显示。
# 给人看/调试：dumps（indent）美化；存文件备份也可以用
# 给程序用：loads成字典直接干活，打印都不用
print(json.dumps(result,indent=2,ensure_ascii=False))
print(result['comment'])                                #单独把评测行拿出来