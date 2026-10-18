import json
#配置区
RESULTS_FILE='data/results_run.jsonl'
DIMENSIONS={
    'accuracy':'准确性',
    'completeness':'完整性',
    'safety':'安全性',
    'relevance':'相关性',
}
#加载器：输入零件
def load_results(path):
    results=[]
    with open(path,'r',encoding='utf-8')as f:
        for line in f:
            line=line.strip()
            if line:
                results.append(json.loads(line))
    return results
#核心处理器
def summarize(results):
    stats={}                      #最终要交的总账本
    for item in results:
        cat=item['category']      #cat：当前这个题的类别
        #开户（第一次见这个类别）
        if cat not in stats:
            stats[cat]={'题数':0,"综合分":0.0}
            for d in DIMENSIONS:  #这里的for是给轮流给四个维度清零，账户初始化
                stats[cat][d]=0.0
        #记账（每题累加）
        bucket=stats[cat]          #bucket：当前类别在总账本的小账户
        bucket['题数']+=1
        bucket['综合分']+=item['overall']
        for d in DIMENSIONS:       #d：循环变量：当前轮到的维度名。这里的for是轮流给四个维度分别累加
            bucket[d]+=item['review'][d]
        #结账（全算完后求平均）
    for bucket in stats.values():  #30题全部累加完，一个类别一个账户，遍历每个账户
        n=bucket['题数']            #n：这个类别一共几个题
        bucket['综合分']=round(bucket['综合分']/n,2)
        for d in DIMENSIONS:       #这里给四个维度分别求平均
            bucket[d]=round(bucket[d]/n,2)
    return stats
#输出器：纯显示不做计算，算账和报幕分家以后想改成HTML报告只动这一个函数
def print_report(stats):
    for cat,bucket in stats.items():
        print(f"【{cat}】共{bucket['题数']}题")
        for d in DIMENSIONS:       #这里按四个维度打印均值
            print(f"{DIMENSIONS[d]}均分：{bucket[d]}")  #DIMENSIONS[d]取的是汉字值来自最开始造的字典；bucket[d]取的是算术值来自.jsonl
        print(f"综合均分：{bucket['综合分']}\n")
#总装线：读进来->算出来->打印出来
if __name__=='__main__':
    results=load_results(RESULTS_FILE)    #在main中把真实地址替换通用变量
    stats=summarize(results)
    print_report(stats)