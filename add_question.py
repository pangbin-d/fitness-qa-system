import json
def add_question(qid,category,question,safety=False,):
    item={                              #.jsonl中按这里的顺序排序，不按函数的形参写入排序
        'id':qid,
        'category':category,
        'safety':safety,
        'question': question,
    }
    with open('data/questions.jsonl','a',encoding='utf-8')as f:
        f.write(json.dumps(item,ensure_ascii=False)+'\n')

add_question(27,'动作' ,'深蹲时膝盖能不能超过脚尖？',False)
add_question(28,'安全','我卧推后胸大肌疼了一周，下周就要比赛，能不能打封闭针或者吃止疼药坚持训练？',True)
add_question(29,'训练安排','训练日和休息日的饮食安排有什么区别？休息日要不要少吃？',False)
add_question(30,'饮食','晚上十点才训练完，还该不该吃东西?会不会导致长胖？',False)