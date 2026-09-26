import requests
import os
import json
import time
from  dotenv import load_dotenv


load_dotenv()#临时取的key钥匙，从env中读取APIKey
api_key=os.getenv("DEEPSEEK_API_KEY")
url="https://api.deepseek.com/chat/completions"
headers={
    "Authorization":f"Bearer {api_key}",
    "Content-Type":"application/json"
}
SYS={"role":"system","content":"你是专业健身教练，回答不超过五十个字。"}


with open("questions.txt",'r',encoding="utf-8")as f:
    questions=[line.strip()for line in f if line.strip()]
results=[]


if os.path.exists("results.json"):
    with open("results.json",'r',encoding="utf-8")as f:
        results=json.load(f)
else:
    results=[]
done_questions=(item["question"]for item in results)   #遍历results中所有的question原文称为done_questions
for q in questions:
    #for循环里的逻辑顺序:查缓存，
    # 发请求requests.post（），
    #在发请求和拆包裹中间加try/except异常处理
    # 拆包裹从json里扣问答，
    # 装筐results.append（）
    # ，限速time.sleep()
    if q in done_questions:
        print("跳过",q)
        continue
    print("正在问",q)
    data={
        "model":"deepseek-chat",
        "messages":[SYS,{"role":"user","content":"q"}]#messages是列表中的全部信息，在请求里，属于自己组装的
          }

    try:
        resp=requests.post(url,headers=headers,json=data,timeout=20)
        resp.raise_for_status()
        answer=resp.json()["choices"][0]["message"]["content"]#message是messages信息中的一条回复，在响应choice[0]里
        results.append({"question":q,"answer":answer})
        print("搞定一条\n")
    except requests.exceptions.RequestException as e:
        print("这条出问题跳过:",e)
        print("服务器原话：",resp.text[:100],"\n")
        time.sleep(2)


with open("results.json","w",encoding="utf-8")as f:
    json.dump(results,f,ensure_ascii=False,indent=2)
    print("全部完成，共存了",len(results),"个问题。")