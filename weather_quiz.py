import requests
import json
import time
import os


with open("cities.txt",'r',encoding="utf-8")as f:
    cities=[line.strip()for line in f if line.strip()]
results=[]


for city in cities:
    try:
        resp=requests.get(f"https://wttr.in/{city}",params={"format":"j1","lang":"zh"},timeout=15)
        resp.raise_for_status()


        data=resp.json()
        print(data.keys())
        cur=data['current_condition'][0]
        print(cur.keys())


        weather={"city":city,"humidity":cur["humidity"],"temp_C":cur["temp_C"],"desc":cur['lang_zh'][0]['value']}
        results.append(weather)
        print(weather,"\n")


    except requests.exceptions.RequestException as e:
        print("这条出问题了，跳过",e)
        if resp is not None:
            print("服务器原话",resp.text[:100],"\n")
        time.sleep(2)


with open("weather.json",'w',encoding="utf-8")as f:
        json.dump(results,f,ensure_ascii=False,indent=2)     #results管存的内容，相当于快递；f是文件通道相当于快递员。这里是dump，直接写进文件，要加f。
        print("完成，共存了",len(results),"个城市")
