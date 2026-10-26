import json
import sys
DIMENSIONS=('accuracy','completeness','safety','relevance')
TOP_N=5
def load_results(path):
    result={}
    with open(path,'r',encoding='utf-8')as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            record=json.loads(line)
            #先定义qid，相当于门牌号，方便后续复用
            qid=record['question_id']
            #通过qid取出每个门牌号后边的整个record：货物
            result[qid]=record
    print(f"已加载{path}:{len(result)}题")
    return result

def pair_ids(v1_map,v2_map):
    v1_ids=set(v1_map.keys())
    v2_ids=set(v2_map.keys())
    common=sorted(v1_ids&v2_ids)             #&表示交集，两版都有的题，sorted是让输出有序，因为set本身无序
    print(f"v1共{len(v1_ids)}题，v2共{len(v2_ids)}题，配对成功{len(common)}题")
    missing=v1_ids^v2_ids                    #^表示对称差，即只出现在一边的题，防止缺题，30对30应该为空集
    if missing:
        print('警告，以下题目只出现在一个版本中：',sorted(missing))
    return common
def calc_deltas(v1_map,v2_map,common_ids):
    rows=[]
    for qid in common_ids:
        r1=v1_map[qid]
        r2=v2_map[qid]
        row={
            'qid':qid,
            'question':r1['question'],         #两版题目相同，从旧版取一次即可
            'safety_flag':r1.get('safety',False),#False是备胎，键不存在才默认False，防止程序崩溃
        }
        #引入这个for循环里的dim变量是为了以后再加维度的话只改这一处即可
        for dim in DIMENSIONS:
            row[dim]=r2['scores'][dim]-r1['scores'][dim]
            row['overall']=r2['overall']-r1['overall']
            row['judge_reason']=r2.get('judge_reason',"")
        rows.append(row)                        #这个也不要缩到for循环里不然每个题会打印四次
    return rows                                 #注意缩进，不要缩进到循环里边，不然只会打印q001一道题
#引入这个函数也是为了方便复用求均值直接avg即可
def avg(values):
    if not values:
        return 0.0
    return sum(values)/len(values)
def print_report(common_ids,v1_map,v2_map,rows):
    print('\n'+'='*50)
    print('一、宏观：五维度均分对比')
    print('='*50)
    metrics=DIMENSIONS+('overall',)                  #单元素元组必须带逗号；不然括号只被当成先算括号，拿到的是字符串不是元组
    print(f'{'维度':<15}{'v1':>8}{'v2':>8} {'delta'}:>8')#<表示左对齐；>表示右对齐
    for m in metrics:
        if m=='overall':
        #     v1_vals = []
        #     for q in common_ids:
        #         record = v1_map[q]  # 这题的整条记录
        #         score = record["overall"]  # 从一楼取总分
        #         v1_vals.append(score)  # 装进列表
        #上述拆解代码与下方v_vals等价
            v1_vals=[v1_map[q]['overall']for q in common_ids]
            v2_vals=[v2_map[q]['overall']for q in common_ids]
        else:
            v1_vals = [v1_map[q]['scores'][m] for q in common_ids]
            v2_vals = [v2_map[q]['scores'][m] for q in common_ids]
            #8是右对齐，.2f是结果保留两位小数
        print(f"{m:<15}{avg(v1_vals):>8.2f}{avg(v2_vals):>8.2f}{avg(v2_vals)-avg(v1_vals):>8.2f}")
    print('\n'+'='*50)
    print('二、中观：安全题专项')
    print('='*50)
    #列表推导式带了个 if 尾巴，读法：从 rows 里逐条取 r，只保留 safety_flag 为 True 的。
    # 展开：
    # safe_rows = []
    # for r in rows:
    #     if r["safety_flag"]:
    #         safe_rows.append(r)
    safe_rows=[r for r in rows if r['safety_flag']]
    print(f"安全题共{len(safe_rows)}道")
    if safe_rows:
        for m in ('safety','overall'):
            print(f"{m:<15}平均退化：{avg([r[m]for r in safe_rows]):.2f}")
    print('\n'+'='*50)
    print(f'三、微观：退步最多TOP{TOP_N}')
    print('='*50)
    #lambda r: r["overall"]：匿名函数，"给我一条 r，我还你它的 overall 字段"。相当于临时排序钥匙
    #sorted(rows, key=...)：按 overall 这个值从小到大排——delta 越小越烂，最烂的自然在最前面。delta即v2-v1得到的值
    #[:TOP_N]意思是切片取前五个
    worst=sorted(rows,key=lambda r:r['overall'])[:TOP_N]
    for r in worst:
        print(f"\n{r['qid']}(overall{r['overall']:+.2f}):{r['question']}")
        if r['judge_reason']:
            print(f"考官评语：{r['judge_reason']}")


if __name__=='__main__':
# sys.argv 是终端命令行参数的列表，纯文字对应：
#argv里装的是路径字符串，不是内存地址
# argv[0] = 脚本名 compare_results.py
# argv[1] = v1 基线文件路径
# argv[2] = v2 教练版文件路径
# len(sys.argv) != 3 意思是少敲路径直接打印用法、exit(1) 拒跑。路径敲反则正负号全反。
    if len(sys.argv)!=3:
        print('用法：python compare_results.py<v1结果><v2结果>')
        exit(1)
    v1_map=load_results(sys.argv[1])
    v2_map=load_results(sys.argv[2])
    common_ids=pair_ids(v1_map,v2_map)
    rows=calc_deltas(v1_map,v2_map,common_ids)
    print_report(common_ids,v1_map,v2_map,rows)    #这里没有=因为print_report不吐数据没有return只管打印