import requests
import time
import json
from unittest.mock import patch,MagicMock
def fetch_and_save_config(api_url,save_path):
    #正常for循环会老老实实转三圈，但是这个成功路径里有return，只要请求成功一次接着结束并跳出，三次全失败就走到最后一行抛出RuntimeError
    for attempt in range(3):
        try:
            resp=requests.get(api_url)#resp现在是个Exception对象，但程序没炸
            if resp.status_code!=200:
                #主动抛出异常，防止拿着错误状态码继续往下.json导致崩盘。想让except接住要真抛出异常，except不识别错误状态码
                raise ValueError(f"状态码异常：{resp.status_code}")
            result=resp.json()
            data=result['data']
            config={
                'model_name':data['model_name'],
                "system_prompt":data["system_prompt"]
            }
            with open(save_path,'w',encoding="utf-8")as f:
                json.dump(config,f,indent=4,ensure_ascii=False)
            return
        except Exception as e:
            print(f"第{attempt+1}次请求失败：{e}")
            #意思是第三次失败不用再sleep了，直接抛RuntimeError
            if attempt<2:
                time.sleep(1)
    raise  RuntimeError("重试三次后仍然失败！")
#验收：
ok=MagicMock()
ok.status_code=200
ok.json.return_value={
    'code':200,
    #data相当于原始数据，具体提取哪个看代码，比如这个代码就要看config里要哪个，里边不要V那就没有V
    'data':{
        'model_name':'gpt-4o',
        'system_prompt':'Help me!',
        'V':'1.0'
    }
}
#情况一,一次成功
#return_value表示每次结果不变固定时用，而且是要返回正确结果，如果是多次异常相同则不能用
with patch("requests.get",return_value=ok):
    fetch_and_save_config('http://mock/config','out.json')
#情况二，前两次失败，第三次成功
#side_effect表示每次结果变化时用
with patch('requests.get',side_effect=[Exception("断网"),Exception('又断'),ok]):
    fetch_and_save_config('http://mock/config','out.json')
#情况三，三次全灭
with patch('requests.get',side_effect=Exception('网络已死')):
    fetch_and_save_config('http://mock/config','out.json')