#numpy是科学计算工具箱，箱子里装的是矩阵和向量，数学函数
#句子（str）→ API → 1024 个数字（list）→ np.array 升级成向量 → dot 测默契 / norm 量箭长 → 相除得夹角分数 → 打包排序拆包打印
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()
client=OpenAI(
    #environ[]相当于硬开柜门，不存在当场报警；getenv()可选配置时用，没有就返回None，不会报警
    api_key=os.environ['SILICONFLOW_API_KEY'],
    base_url='https://api.siliconflow.cn/v1'
)
sentences=[
 "怎么练胸肌",
    "卧推主要练哪个部位",      # 跟句1语义近，但一个字都不重
    "今天天气怎么样",
    "鸡胸肉怎么做好吃",
    "每天该吃多少蛋白质",
]
#API发回来的箱子，
resp=client.embeddings.create(
    model='BAAI/bge-m3',            #bge-m3默认是1024维
    input=sentences,
)
#np.array是将普通的d.embedding列表升级成会计算两个列表对应位置相乘再求和
vecs=[np.array(d.embedding)for d in resp.data]
print("向量维度：",len(vecs[0]))
def cos(a,b):
    #np.dot：点积，a和b对应位置相乘再相加；np.linalg.norm(a)：norm是算向量长度。return的是单纯的cos夹角
    return np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))
print('两两相似度：')
#pairs是个中转仓库：1.先攒货后排序，攒齐交给sorted，按分数排队
pairs=[]
for i in range(len(sentences)):
    for j in range(i+1,len(sentences)):
        score=cos(vecs[i],vecs[j])
        #score要带着i和j，三个包成一个包裹存，不能只有分数没有名字，没法辨别。
        pairs.append((score,sentences[i],sentences[j]))
#reverse=True：即是高分排前面，本质是排序
#for score,a,b in sorted（）：元组解包，三个东西落三个变量
for score,a,b in sorted(pairs,reverse=True):
    print(f"{score:.3f}  {a}  vs  {b}")