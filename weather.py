import requests
import os
import json
import time
#清洗函数，去掉脏数据
def norm(s):
    return s.lstrip("\ufeff").strip().casefold()      #去BOM，去空格，统一小写

with open("cities.txt",'r',encoding="utf-8")as f:
    cities=[line.strip()for line in f if line.strip()]
results=[]
if os.path.exists("weather.json"):             #先读旧天气，读不到从空列表开始
    with open("weather.json","r",encoding="utf-8")as f:
        results=json.load(f)     #从文件里读，f是通道
else:
    results=[]
#清理脏数据，去重
seen=set()
clean=[]
for item in results:
    key=norm(item["city"])
    if key not in seen:
        seen.add(key)
        clean.append(item)
results=clean
done_weather=seen
for city in cities:
    if norm(city) in done_weather:
        print("这里的天气查过了，跳过：",city)
        continue
    print("正在查",city)
    resp=None                                  #先创建resp
#注意缩进，try是否在循环里面，整体缩进用Tab+Shift
    try:
        resp=requests.get(f"https://wttr.in/{city}",params={"format":"j1","lang":"zh"},timeout=15)#params为查询参数，j1表示要JSON格式的完整数据，lang是语言，zh是要中文
        resp.raise_for_status()

        data=resp.json()                   #可以列出所有键名，方便查找一层里的所有键名,print打印
        print(data.keys())
        cur=data["current_condition"][0]  #找到一层后寻找最像的房间，发现是列表包着字典，那就取下标[0]看看有哪些键？依旧print打印
        print(cur.keys())

        weather={"city":city,"temp_C":cur["temp_C"],"humidity":cur["humidity"],"desc":cur["lang_zh"][0]["value"]}#读API返回，提取有用键值
        results.append(weather)
        done_weather.add(norm(city))
        print(weather,"\n")
    except requests.exceptions.RequestException as e:
        print("这条出问题了跳过",e)
        if resp is not None:
            print("服务器原话",resp.text[:100],"\n")
        time.sleep(2)
with open("weather.json",'w',encoding="utf-8")as f:
    json.dump(results,f,ensure_ascii=False,indent=2)
    print("完成，共存",len(results),"个城市")