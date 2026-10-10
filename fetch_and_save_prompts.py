import requests
from unittest.mock import patch, MagicMock
def fetch_and_save_prompts(api_url):
    resp=requests.get(api_url)
    if resp.status_code!=200:
        print("请求失败，状态码：",resp.status_code)
        return
    result=resp.json()
    data_list=result['data']
    grouped={}
    for item in data_list:
        #item.get防止KeyError，存在就取值，不存在返回None，比单纯item（）要保险
        category=item.get('category')
        content=item.get('content')
        if  category is None or content is None:
            print("警告，数据缺少字段，已跳过->",item)
            continue
        #setdefault把检查＋开门写成一步。这段代码意思是字典里有这个类别就取出其列表，没有就先塞空列表进去再取出来，等价于下面三行代码
            # if category not in grouped:  # 新类别？
            #     grouped[category] = []  # 先给它开门
            # grouped[category].append(content)
        grouped.setdefault(category,[]).append(content)
        for category,contents in grouped.items():
            with open(f'{category}.txt','w',encoding="utf-8")as f:
                for content in contents:
                    f.write(content+"\n")

#验收
fake = MagicMock()
fake.status_code = 200
fake.json.return_value = {
    "data": [
        {"id": 1, "category": "coding", "content": "Write a python script"},
        {"id": 2, "category": "writing", "content": "Write a poem"},
        {"id": 3, "category": "coding", "content": "Fix the bug"},
        {"id": 4, "content": "无类别数据"},          # 缺 category
        {"id": 5, "category": "coding"}               # 缺 content
    ]
}

with patch("requests.get", return_value=fake):
    fetch_and_save_prompts("http://mock/api/prompts")