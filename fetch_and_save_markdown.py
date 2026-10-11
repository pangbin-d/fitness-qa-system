import os
import requests
from unittest.mock import patch,MagicMock
def fetch_and_save_markdown(api_url,save_path):
    response=requests.get(api_url)
    #判断状态码
    if response.status_code!=200:
        raise ValueError(f"API请求失败，状态码：{response.status_code}")
    #解析json
    data=response.json()
    #校检title/sections在不在
    if 'title'not in data or 'sections' not in data:
        raise ValueError('JSON缺少title或sections字段')
    #列表推导式过滤空值
    valid_sections=[
        s for s in data['sections']
        if isinstance(s,str)and s.strip()
                    ]
    # 拼Markdown:'\n\n.join()'作为元素之间的胶水
    content=f"#{data['title']}\n\n"+'\n\n'.join(valid_sections)
    #先问父目录在不在；os.path.dirname作用是从路径里切目录，save_path没带目录时dirname返回空串。
    parent_dir=os.path.dirname(save_path)
    if parent_dir:     #直接os.markdirs，如果是空的话会直接报错，所以要先if parent_dir存在
        os.makedirs(parent_dir,exist_ok=True)
        #落盘
    with open(save_path,'w',encoding='utf-8')as f:
        f.write(content)

#验收
# 场景1：正常数据（含None）——应生成文件、null被过滤
mock_ok = MagicMock()
mock_ok.status_code = 200
mock_ok.json.return_value = {
    "title": "AI日报",
    "sections": ["## 简介\n这是简介", "## 详情\n这是详情", None, "## 总结\n这是总结"]
}
with patch("requests.get", return_value=mock_ok):
    fetch_and_save_markdown("http://mock.api/doc", "./out/report.md")
# 打开 ./out/report.md 检查：首行 # AI日报，三个section之间空一行，null消失

# 场景2：状态码500——应抛 ValueError，且 ./out2 目录根本不该被创建
mock_500 = MagicMock()
mock_500.status_code = 500
with patch("requests.get", return_value=mock_500):
    try:
        fetch_and_save_markdown("http://mock.api/doc", "./out2/report.md")
        print("场景2 FAIL：没抛异常")
    except ValueError:
        print("场景2 PASS")

# 场景3：缺 sections 字段——应抛 ValueError
mock_bad = MagicMock()
mock_bad.status_code = 200
mock_bad.json.return_value = {"title": "光杆标题"}
with patch("requests.get", return_value=mock_bad):
    try:
        fetch_and_save_markdown("http://mock.api/doc", "./out3/report.md")
        print("场景3 FAIL：没抛异常")
    except ValueError:
        print("场景3 PASS")
