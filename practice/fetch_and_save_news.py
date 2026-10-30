#核心：请求接口；解析JSON取data列表；逐条逐行写成JSONL文件；返回条数；出任何岔子返回0不许崩。
# JSONL：管持续记录
# - 你的毕设直接能用：每次评测的问答记录，一条一条往日志文件追加，跑挂了重启，前面的数据还在。整个大 JSON 数组写一半崩了，文件直接损坏
# - 大模型训练数据：训练语料基本都是 JSONL 格式，OpenAI 微调接口要的就是它
# - 日志系统：服务器日志天然就是"每行一条事件"
import json
import requests
from unittest.mock import patch,MagicMock  #unittest.mock原理是把requestes.get临时换成一个返回假数据的东西
def fetch_and_save_news(api_url,output_file):
    try:
        resp=requests.get(api_url)
        if resp.status_code!=200:          #判断网络状态
            return 0
        result=resp.json()
        new_list=result['data']            #resp.json（）解析，result['data']取出列表
        with open(output_file,'w',encoding='utf-8')as f:
            for item in new_list:
                line=json.dumps(item,ensure_ascii=False)#防止中文乱码
                f.write(line+'\n')
        return len(new_list)
    except Exception:
        return 0
if __name__=="__main__":
    #mock:模仿，替身
    #patch：打补丁（这里指临时替换）
    #fake：假的
    #MagicMock：万能假对象
    fake = MagicMock()
    fake.status_code = 200      #状态码伪装成请求成功
    #fake.json是个假方法；.return_value表示被调用时，假装返回什么。意思就是提前准备好这个字典，等函数里执行resp.json时直接放这个信息
    fake.json.return_value = {
        "status": "success",
        "data": [
            {"id": 1, "title": "LLM新突破", "summary": "上下文窗口达到1M"},
            {"id": 2, "title": "Agent框架", "summary": "多智能体协作成为主流"}
        ]
    }
#假的get被调用时，固定返回fake这个替身响应
    with patch("requests.get", return_value=fake):
        count = fetch_and_save_news("http://mock.api/news", "news.jsonl")
        print(count)  # 预期 2，打开 news.jsonl 检查两行中文

