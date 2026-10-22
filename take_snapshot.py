import sys
import json
from datetime import datetime
from info_extraction import make_client,chat_with_retry
from evaluate import load_questions,ANSWER_SYS,review_answer
QUESTIONS_PATH='data/questions.jsonl'
DIMENSIONS=('accuracy','completeness','safety','relevance')  #四个评分维度的名单
PROMPTS={                                                    #版本表，key是版本号，value是对应的system prompt
    'v1_baseline':ANSWER_SYS
}
MODEL_NAME='deepseek-chat'
def answer_question_v(client,question,sys_prompt):
    messages = [{
        'role': "system",
        'content': sys_prompt             #1
    },
        {
            'role': "user",
            'content': question
        }]
    resp = chat_with_retry(client, messages, temperature=0.7, json_mode=False)
    return resp.choices[0].message.content.strip()
#主流程
def run_snapshot(version):
    sys_prompt=PROMPTS[version]
    questions=load_questions(QUESTIONS_PATH)
    client=make_client()
    run_id=datetime.now().strftime("%Y%m%d-%H%M")      #括号里的字母各自代表年，月，日，时，分
    out_path=f"data/results_{version}.jsonl"           #version不同，一个版本一份jsonl文件
    with open(out_path,'w',encoding='utf-8')as f:
        for q in questions:
            print(f"q{q['id']:03d}考生答题中...",flush=True)
            try:
                answer=answer_question_v(client,q['question'],sys_prompt)
                review=review_answer(client,q['question'],answer)
                overall=round((review['accuracy']+review['completeness']+review['safety']+review['relevance'])/4,2)
                record={
                    'question_id':f"q{q['id']:03d}",    #03d表示数字补0到第三位
                    'prompt_version':version,           #这次记录是哪个prompt考的
                    'run_id':run_id,                    #第一次记录的批次号

                    'category':q.get('category'),
                    'safety':q.get('safety',False),      #必选键硬取；可选键q.get软取，取不到默认返回None/False，不影响程序运行
                    'question':q['question'],
                    'answer':answer,

                    'scores':{                          #四个维度分包存
                        "accuracy": review["accuracy"],
                        "completeness": review["completeness"],
                        "safety": review["safety"],
                        "relevance": review["relevance"],
                    },
                    "overall": overall,                  #四维平均数
                    "judge_reason": review.get("comments", ""),
                    "model": MODEL_NAME,
                    "timestamp": datetime.now().isoformat(),   #这一条的准确出生时间，isoformat是标准格式，精确到秒
                    }
            except Exception as e:
                record={
                    'question_id': f"q{q['id']:03d}",
                    'prompt_version': version,
                    'run_id': run_id,
                    'category': q.get('category'),
                    'safety': q.get('safety', False),
                    'question': q['question'],
                    'answer': None,
                    'scores':None,
                    'overall':None,
                    'judge_reason':f"本题执行失败：{e}",
                    'model':MODEL_NAME,
                    'timestamp':datetime.now().isoformat()
                }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            #操作系统的真相：调 write()，数据不是马上进硬盘，先进内存里一块叫"缓冲区"的中转站，系统攒够一批才统一写盘——为了快，flush是出一条就写一条。
            f.flush()
            print(f"{record['question_id']} 完成 overall={record['overall']}")


if __name__ == "__main__":
    #sys.argv是命令行参数表，argv[0]永远是脚本名，argv[1]才是第一个参数，如果>1就切换v2版本，啥也不写默认v1
    version = sys.argv[1] if len(sys.argv) > 1 else "v1_baseline"
    if version not in PROMPTS:
        #list(PROMPTS.keys())意思是取字典的所有合法版本号然后用list转换成列表形式打印出来，更方便看
        print(f"未知版本：{version}，可选：{list(PROMPTS.keys())}")
        #exit（）里，1是非正式退出的暗号，0为成功
        sys.exit(1)
    run_snapshot(version)