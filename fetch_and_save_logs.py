#核心：
# 接口一次只吐一页，通过？page=X翻页，
# 从第一页响应里读total_pages知道要翻到第几页；
# 所有页数据合并后用csv.DictWriter写CSV带表头；
#单页失败打印错误并跳过，不能崩。
# 分页+CSV：管批量导出
# - 爬虫/数据采集：任何数据量大点的接口（订单列表、用户列表、评论）都是分页的
# - 后台导出功能：你以后进公司写管理系统，"导出为 Excel/CSV" 是产品经理必提的需求
# - 数据分析取数：从 API 批量拉数据存 CSV，交给 pandas 分析
import requests
import csv
from unittest.mock import patch,MagicMock
def fetch_and_save_logs(api_url,output_csv_path):
    all_records=[]
    page=1
    total_pages=1
    while page<=total_pages:
        try:
            #params={'page':page}等价于手动拼接api_url+'?pages='+str(page)
            resp=requests.get(api_url,params={'page':page})
            if resp.status_code!=200:
                print(f'第{page}页失败，状态码{resp.status_code}')
            else:
                result=resp.json()
                total_pages=result['total_pages']
                #为什么用extend不用append，因为append会把整页列表当成一个元素塞进去造成列表嵌套，extend是把元素逐个摊平加进去。
                all_records.extend(result['data'])
        except Exception as e:
            print(f'第{page}页异常：{e}')
        page+=1
        #newline是Windows写CSV的标配，不写的话每行会多出一个空行
    with open(output_csv_path,'w',encoding='utf-8',newline='')as f:
        #DictWriter按照fieldnames的顺序从每个字典里取值，自动对齐列；
        writer=csv.DictWriter(f,fieldnames=['id','prompt','response'])
        #writeheader把fieldnames本身写成第一行表头
        writer.writeheader()
        #writerows是批量写多行，必须在with里，因为要用文件对象f写字；必须在while外，得等所有页全部抓完，all_records攒齐了再一次性写
        #写while循环里的话，每翻一页就打开一次文件把上一次的覆盖，最后只剩最后一页数据。
        writer.writerows(all_records)
if __name__ =='__main__':
    def fake_get(url, params=None):
        page = params["page"]
        m = MagicMock()
        if page==2:
           m.status_code = 500
        else:
            m.status_code=200
        m.json.return_value = {
            "page": page,
            "total_pages": 3,
            "data": [{"id": page, "prompt": f"提问{page}", "response": f"回答{page}"}]
        }
        return m
#side_effect意为副作用，这里表示每次调用时执行的动作，每调一次就执行一次fake_get函数，现造一个新响应
    with patch("requests.get", side_effect=fake_get):
        fetch_and_save_logs("http://api.mock/logs", "logs.csv")