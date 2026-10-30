import requests
from unittest.mock import patch,MagicMock
def fetch_and_save_quota(api_key,date_str):
    #请求三件套：地址，请求头，文件
    url='https://api.mock-ai.com/v1/quota'
    headers={"Authorization":f"Bearer {api_key}"}
    params={"date":date_str}
    response=requests.get(url,headers=headers,params=params)
    #查状态码
    if response.status_code!=200:
        raise ValueError(f"请求失败，状态码：{response.status_code}")
    #解析json
    data=response.json()
    #字段安检，缺一个都不写
    if'model'not in data or 'remaining_tokens'not in data:
        raise KeyError("返回数据缺必要字段：model或remaining_tokens")
    line=f"{data['model']}:{data['remaining_tokens']}"

    with open("quota_log.txt",'a',encoding="utf-8")as f:  #'a'=append,光标蹲到文件末尾往后加，文件不存在还会自动建
        f.write(line+'\n')

#mock验收
#情况一：成功+查请求参数有没有带对
with patch('requests.get')as mock_get:
    fake=MagicMock()
    fake.status_code=200
    fake.json.return_value={"model":"gpt-4o","remaining_tokens":15000}
    mock_get.return_value=fake
    fetch_and_save_quota("sk-123",'2026-10-09')
    # 断言：requests.get 必须带着这些参数被调用过，差一个字符都报错
    mock_get.assert_called_once_with(
        "https://api.mock-ai.com/v1/quota",
        headers={"Authorization": "Bearer sk-123"},
        params={"date": "2026-10-09"}
    )
    print("场景1通过 ✅")

#场景二：状态码500，必须拦截
with patch("requests.get") as mock_get:
    fake = MagicMock()
    fake.status_code = 500
    mock_get.return_value = fake

    try:
        fetch_and_save_quota("sk-123", "2026-10-09")
        print("场景2挂了 ❌ 该抛不抛")
    except ValueError:
        print("场景2通过 ✅ 500被拦下")

#场景三：JSON缺字段，不许写文件
with patch("requests.get") as mock_get:
    fake = MagicMock()
    fake.status_code = 200
    fake.json.return_value = {"model": "gpt-4o"}  # 故意缺 remaining_tokens
    mock_get.return_value = fake

    try:
        fetch_and_save_quota("sk-123", "2026-10-09")
        print("场景3挂了 ❌ 缺字段也敢写")
    except KeyError:
        print("场景3通过 ✅ 缺字段被拦下")