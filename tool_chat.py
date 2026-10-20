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
#工具函数；模型不执行也不认识，只有在本地电脑才会执行
def get_current_time():
    now=datetime.now()
    return now.strftime('当前时间：%Y-%m-%d %H:%M:%S')
def calc_bmi(arguments):
    height=arguments['height']
    weight=arguments['weight']
    bmi=weight/(height**2)
    if bmi<18.5:
        advice="偏瘦"
    elif bmi<24:
        advice="正常"
    elif bmi<28:
        advice="超重"
    else :
        advice="肥胖"
    return f"你的BMI是{bmi:.1f},属于{advice}范围"
#说明书；模型只看得到这个，然后决定调用什么工具
tools=[                                      #tools字典里所有东西都是数据，不是代码，所以都要写成字符串形式
    {

        'type':'function',
        'function':{
            'name':'get_current_time',       #这是模型返回时写的名字
            'description':'当用户想知道现在的日期或时间时调用。',   #模型全靠它判断该不该调用，最重要。
            #本质schema
            'parameters':{                   #parameters描述的是函数参数长什么样
                'type':'object',             #函数参数本质是一堆键值对，在JSON里键值对的容器就叫：object，所以根节点必须声明type':'object
                'properties':{}              #在properties里列每个参数
            }
        }
    },
    {   'type':'function',                   #两个type工具要分别在两个{}里！tools是个列表套字典
        'function':{
            'name':'calc_bmi',
            'description':'当用户提供身高体重，想计算BMI或判断胖瘦时调用。',
            'parameters':{
                'type':'object',
                'properties':{
                    'height':{
                        'type':'number',
                        'description':'身高，单位米，例如1.75'
                    },
                    'weight':{
                        'type':'number',
                        'description':'体重，单位千克，例如70'
                    },
                },
                'required':['height','weight']  #是个列表，里面写必填参数的名字，而且名字必须和properties一字不差
            }
        }
    }
]
#相当于登记册：从名字->真函数
function_mapper={
    'get_current_time':get_current_time,
    'calc_bmi':calc_bmi
                 }
#历史信息列表
test_questions=[
    '我身高1.75米，体重70公斤，算下BMI',
    '现在几点',
    '你好',
]
for question in test_questions:
    print(f"\n=====测试：{question}=====")
    messages=[
        {
            'role':'system',
            'content':'你是一个能查看本地时间、计算BMI的助手。'
        },
        {
            'role':'user',
            'content':question,
        }
    ]
#第一次请求：老板开tool_calls条子
    response=client.chat.completions.create(
        model='deepseek-chat',
        messages=messages,
        tools=tools,
        extra_body={'thinking':{'type':'disabled'}}
    )
    msg=response.choices[0].message
    print('模型第一次返回的content：',repr(msg.content))    #repr是返回一个值的调试专用长相，可显示空字符串和None
    print('模型第一次返回的tool_calls:',msg.tool_calls)
    #拆条子
    if msg.tool_calls:
        #先将条子加到；历史列表里
        messages.append(msg)
        #遍历每个条子
        for call in msg.tool_calls:
            #取名字，先知道模型要谁
            func_name=call.function.name
            #arguments是JSON文本，不是字典，所以要.loads。再知道模型给的参数
            arguments=json.loads(call.function.arguments)
            print(f"本地执行：{func_name},参数：{arguments}")
            #从登记册查到真函数，按照名字找到真人
            func=function_mapper[func_name]
            #执行，找到真人才动手
            result=func() if arguments=={} else func(arguments)
            #将结果作为tool消息返回，多条结果时靠tool_call_id对号入座。干完凭id交回执
            messages.append({'role':'tool','tool_call_id':call.id,'content':result})
    #第二次请求，拿结果换人话。写在for循环外面，必须等所有回执全部入袋才同意发给模型总结。
        response2=client.chat.completions.create(
            model='deepseek-chat',
            messages=messages,
            tools=tools,
            extra_body={'thinking':{'type':'disabled'}}
        )
        print('机器人',response2.choices[0].message.content)