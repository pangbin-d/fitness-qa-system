"""题库入库 + 相似度检索 demo
用 Chroma 把 data/questions.jsonl 存进向量库，再按语义检索 top3
"""
#chroma_db文件夹里的文件代表含义
# 文件	                       装什么	                              类比
# chroma.sqlite3	每条记录的 id、原文、metadatas，以及“名字→目录”的映射	学校教务系统台账：学号、姓名、班级
# header.bin	    索引的元信息：1024 维、30 条、cosine、最大层数	    索引的身份证
# data_level0.bin	第 0 层（最底层）的全部向量本体	                    全校所有学生
# link_lists.bin	邻接表，每个向量连着哪些邻居	                        也就是社交关系图
# length.bin	    每层各有多少个节点	                                各年级人数统计
import os
import json
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.utils.embedding_functions import register_embedding_function
from openai import OpenAI
from dotenv import load_dotenv

DB_DIR = "./chroma_db"          # 向量库存哪个文件夹（自动创建）
COLLECTION_NAME = "fitness_qa"  # 抽屉名
QUESTION_FILE = "data/questions.jsonl"
EMBED_MODEL = "BAAI/bge-m3"     # 1024 维，硅基流动免费
BATCH_SIZE = 10                 # 一次最多送几条给 API，代表步长

load_dotenv()


#  自定义 embedding 函数
@register_embedding_function        #装饰器，给类办身份证
#EmbeddingFunction[Documents]:继承＋泛型，告诉chroma我吃文本
class SiliconFlowEmbedding(EmbeddingFunction[Documents]):
    """把 Chroma 的文本请求转给硅基流动，拿回向量"""

    def __init__(self, model: str = EMBED_MODEL):
        self.model = model
        key = os.environ.get("SILICONFLOW_API_KEY")
        if not key:
            raise ValueError("没读到 SILICONFLOW_API_KEY，检查 .env 文件")
        #self的本质是跨方法共享状态，将client存到self实例上，call函数也可用，单纯写client=...init结束就没了
        self.client = OpenAI(
            api_key=key,
            base_url="https://api.siliconflow.cn/v1",
        )
#__call__核心是让对象能像函数一样调用
    def __call__(self, input: Documents) -> Embeddings: #这里指返回向量列表
        vectors=[]
        #外层for：分批（控制网络请求次数）
        for i in range(0,len(input),BATCH_SIZE):
            #切片
            batch=list(input[i:i+BATCH_SIZE])
            resp=self.client.embeddings.create(model=self.model,input=batch)
            #内层for：批内排序（控制数据顺序）
            for item in sorted(resp.data,key=lambda x:x.index):
                vectors.append(item.embedding)
        return vectors

    @staticmethod                            #@staticmethod不读任何实例数据，返回值是常量
    def name() -> str:                        #返回字符串
        """身份证名，Chroma 靠它在花名册里认人"""
        return "siliconflow-bge-m3"

    def get_config(self) -> dict:             #返回字典
        """存档：只存模型名，绝不存 key"""
        return {"model": self.model}          #依赖实例状态，所以不用@staticmethod

    @classmethod                              #
    #函数作用是拿get_config的字典，重新造一个实例，下次打开数据库时chroma靠它运行embedding
    #"SiliconFlowEmbedding"为什么这个时候加引号，因为类还没定义完，函数在类内部，执行时会报错，加引号变成字符串python会当文字存起来，这是前向引用
    def build_from_config(cls, config: dict) -> "SiliconFlowEmbedding":
        """读档：按配方重建一个实例"""
        return cls(model=config.get("model", EMBED_MODEL))

    def default_space(self) -> str:           #默认行为声明，告诉chroma我这个模型产出的向量最适合用余弦算距离
        return "cosine"


# 读题库
def load_questions(path: str) -> list:        #这里返回列表
    questions = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


# 建库 + 入库
def build_index(questions: list):
    client=chromadb.PersistentClient(path=DB_DIR)
    #把create改成get_or_create是为了重跑不报已存在
    collection=client.get_or_create_collection(
        name=COLLECTION_NAME,
        #加embedding_function是为了用bge-m3，不用内置默认·
        embedding_function=SiliconFlowEmbedding(),
        #加configuration是为了用余弦，1-dist才成立
        configuration={'hnsw':{'space':'cosine'}},
    )

    #add改成upset是为了重跑不报id冲突。一次传三个列表，即chroma的列式接口
    collection.upsert(
        ids=[str(q['id'])for q in questions],         #把一个for循环改成批量，1次请求代替30次
        documents=[q['question'] for q in questions],
        #metadatas能按标签过滤
        metadatas=[
            {
                'category':q['category'],
                'safety':q['safety']
            }for q in questions
        ],
    )
    return collection
# 检索
def search(collection, query_text:str,top_k:int=3) ->list:       #top_k是检索通用术语：关键字参数带默认值
    #query_texts=[query_text]：包装成列表是因为chroma支持一次查多句，所以输入永远是列表
    res=collection.query(query_texts=[query_text],n_results=top_k)
    ids=res['ids'][0]
    docs=res['documents'][0]
    dists=res['distances'][0]
    metas=res['metadatas'][0]
    results=[]
    for i in range(len(ids)):
        results.append(
            {
                #第i条结果，这条结果的category/safety键
                'id':ids[i],
                'question':docs[i],
                'category':metas[i]['category'],
                'safety':metas[i]['safety'],
                'similarity':round(1-dists[i],4),
            }
        )
    return results


# 主流程
def main():
    questions = load_questions(QUESTION_FILE)
    print(f"读取题库：{len(questions)} 条")

    collection = build_index(questions)
    print(f"已入库：{collection.count()} 条")

    queries = [
        "肌肉酸痛好几天了怎么办",
        "想减掉肚子上的肉",
        "膝盖疼还能练腿吗",
        "一天吃几个鸡蛋合适",
    ]

    for q in queries:
        print("\n" + "=" * 55)
        print(f"查询：{q}")
        for r in search(collection, q):
            flag = "[安全]" if r["safety"] else "      "
            print(f"  {r['similarity']:.3f} {flag} [{r['category']}] {r['question']}")


if __name__ == "__main__":
    main()