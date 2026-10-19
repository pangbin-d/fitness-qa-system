import os
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()
client=OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url='https://api.deepseek.com'
)

def get_current_time():
    now=datetime.now()
    return now.strftime('当前时间：%Y-%m-%d %H:%M:%S')

tools=[
    {
        'type':'function',
        'function':{
            'name':'get_current_time',
            'description':'当用户想知道现在的日期或时间时调用。',
            'parameters':{
                'type':'object',
                'properties':{}
            }
        }
    }
]

function_mapper={'get_current_time':get_current_time,}

messages=[
    {
        'role':'system',
        'content':'你是一个能查看本地时间的助手，回答简洁友好。'
    },
    {
        'role':'user',
        'content':'现在几点了？'
    }
]

response=client.chat.completions.create(
    model='deepseek-chat',
    messages=messages,
    tools=tools,
    extra_body={'thinking':{'type':'disabled'}}
)
msg=response.choices[0].message
print('模型第一次返回的content：',repr(msg.content))
print('模型第一次返回的tool_calls:',msg.tool_calls)

if msg.tool_calls:
    messages.append(msg)
    for call in msg.tool_calls:
        func_name=call.function.name
        arguments=json.loads(call.function.arguments)
        print(f"本地执行：{func_name},参数：{arguments}")
        func=function_mapper[func_name]
        result=func() if arguments=={} else func(arguments)
        messages.append({'role':'tool','tool_call_id':call.id,'content':result})

    response2=client.chat.completions.create(
        model='deepseek-chat',
        messages=messages,
        tools=tools,
        extra_body={'thinking':{'type':'disabled'}}
    )
    print('机器人',response2.choices[0].message.content)
    print('机器人：',msg.content)