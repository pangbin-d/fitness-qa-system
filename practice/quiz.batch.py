import os
import time
import requests
import json
from dotenv import load_dotenv

load_dotenv()
api_key=os.getenv("DEEPSEEK_API_KEY")
url="https://api.deepseek.com/chat/completions"
headers={
    "Authorization":f"Bearer {api_key}",
    "Content-Type":"application/json"
}
SYS={"role":"system","content":"你是专业健身教练，回答不超过50个字"}
#读题库
with open ('questions.txt',"r",encoding="utf-8") as f:
    questions=[line.strip()for line in f if line.strip()]
results=[]                  #先建立空列表
#逐个问AI,可以加上先查本地的缓存逻辑，防止每次调用都调API消耗token
if os.path.exists("results.json"):             #先读旧问题，读不到从空列表开始
    with open("results.json","r",encoding="utf-8")as f:
        results=json.load(f)
else:
    results=[]
done_questions=(item["question"]for item in results)  #收集已经问过的问题
for q in questions:
    if q in done_questions:
        print("这题问过了，跳过：",q)
        continue                            #直接进下一圈，不发请求
    print("正在问：",q)
    data={
        "model":"deepseek-chat",
        "messages":[SYS,{"role":"user","content":q}]
    }
    #绿色注释部分是不加异常处理的代码，如果出现循环故障则程序全崩，一条也存不进去，非常耗时耗力
    '''resp=requests.post(url,headers=headers,json=data,timeout=20)
    answer=resp.json()["choices"][0]["message"]['content']
    results.append({"question":q,"answer":answer})     #每次成功问完一个，就把字典追加进列表，成功十次就有十个字典
    print("搞定一条\n")'''
    try:                               #试着发请求，扣回答
        resp = requests.post(url, headers=headers, json=data, timeout=20)
        resp.raise_for_status()      #这行负责出事抛出异常，try/except负责处理异常
        answer = resp.json()["choices"][0]["message"]['content']
        results.append({"question": q, "answer": answer})  # 每次成功问完一个，就把字典追加进列表，成功十次就有十个字典
        print("搞定一条\n")
    except requests.exceptions.RequestException as e:   #出事了，打印一下这条跳过。继续下一条，循环不停止，把异常对象起名为e，方便后边引用
       print('这条出问题了，跳过：',e)
       print("服务器原话：",resp.text[:100],'\n')
       time.sleep(2)       #让程序停两秒，不触发限速，防止请求频繁
#存成JSON文件
with open ('results.json','w',encoding="utf-8")as f:
    json.dump(results,f,ensure_ascii=False,indent=2)    #循环结束，把整个列表装进JSON文件
print("全部完成，共存了",len(results),"条")             #数数几条，只打印成功的条数，中途崩一条可判断有漏掉的

