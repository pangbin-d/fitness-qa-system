import requests

questions=["卧推肩膀疼怎么办？","一天吃多少蛋白质?","减脂期能喝奶茶吗？"]
for q in questions:
    m=[{"role":"user","content":q}]
    r=requests.post(url,headers=headers,json={"model":"deepseek-chat","messages":m},timeout=20)
    print(f"问：{q}")
    print(f"答：{r.json()['choices'][0]['message']['content']}")

