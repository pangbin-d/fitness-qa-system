import json
with open('data/questions.jsonl',encoding="utf-8")as f:
    for i,line in enumerate(f,start=1):
        line=line.strip()
        if line:
            item=json.loads(line)
            print(item['id'],item['category'],item['safety'],item['question'][:10])#[:10]意思是取questions前10个字