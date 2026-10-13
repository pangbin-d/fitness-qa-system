def calculate_metrics(y_true,y_pred):      #y_true是实际答案，每条样本是0还是1；y_pred是模型交上来的答案，预测成0还是1

    if len(y_true)!=len(y_pred):           #两个列表是按位置一一配对的同一张成绩单，所以长度必须相等
        raise ValueError("两个列表长度不一致")
    if len(y_true)==0:
        raise ValueError("列表不能为空")
# t（真相）	p（预测）	结局
# 1	        1	TP：真标准，说标准 ✅
# 1	        0	FN：真标准，说不标准，漏了
# 0	        1	FP：不标准，说标准，放水
# 0	        0	TN：不标准，说不标准 ✅
    tp=fp=tn=fn=0
    for t,p in zip(y_true,y_pred):          #zip相当于拉链，把俩列表的数据一一配对起来
        if t not in(0,1)or p not in (0,1):  #1,0就是动作标准不标准
            raise ValueError("标签只能是0或1")
        if t==1 and p==1:
            tp+=1
        elif t==0 and p==0:
            tn+=1
        elif t==1 and p==0:
            fn+=1
        else:
            fp+=1
    n=len(y_true)
    accuracy=(tp+tn)/n
    if tp+fp==0:
        precision=0.0
    else:
        precision=tp/(tp+fp)
    if tp+fn==0:
        recall=0.0
    else:
        recall=tp/(tp+fn)
    if precision+recall==0:
        f1=0.0
    else:
        f1=2*precision*recall/(precision+recall)
    return {
        'accuracy':round(accuracy,4),       #（round，4）保留到四位小数
        'precision':round(precision,4),
        'recall':round(recall,4),
        'f1':round(f1,4),
    }
# 1. 官方示例 → 0.6667 / 0.75 / 0.75 / 0.75
print(calculate_metrics([1,0,1,1,0,1], [1,0,0,1,1,1]))

# 2. 预测全0：precision、recall、f1 全 0.0，不许炸
print(calculate_metrics([1,1,0], [0,0,0]))

# 3. 真实全0全被误报：recall=0.0，不许炸
print(calculate_metrics([0,0], [1,1]))

# 4. 长度不等 → ValueError
calculate_metrics([1,0], [1])

# 5. 含非0/1 → ValueError
calculate_metrics([1,2], [1,0])
