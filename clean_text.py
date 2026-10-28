# 场景设定：你开一家"问答数据清洗厂"。脏问题上流水线，洗成统一规格用于判重；前台负责拦重复访客。
_WHITESPACE_AND_PUNCT = (
    " \t\n\r\x0b\x0c"
    "，。！？、；：（）【】“”‘’《》…—"
    ",.!?;:'\"()[]{}<>~`-_/\\|@#$%^&*+="
)
# 0x3000: None：全角空格的码位 → None（None = 见到就删）
# {i: i - 0xFEE0 for i in range(...)}：字典推导式，i 从 0xFF01 走到 0xFF5E（range 左闭右开），每个全角码位配一个"减 0xFEE0 后的半角码位"。一行生成 94 条"全角→半角"规则。
# 前面的 ： 字典解包 ，把整本小字典"哗啦"一下倒进大字典，省得手写 94 行。像把一整盒名片直接倒进名片簿。
# {ord(c): None for c in _WHITESPACE_AND_PUNCT}：遍历垃圾桶清单，ord(c) 取每个标点的码位，全部配 None = 删除。
_TABLE = str.maketrans({
    0x3000: None,
     **{i: i - 0xFEE0 for i in range(0xFF01, 0xFF5F)},
    **{ord(c): None for c in _WHITESPACE_AND_PUNCT},
})
def clean_text(s):
    if not isinstance(s,str):
        raise
    TypeError("clean_text只接受字符串，收到：%r" % type(s))
    #s.translate(_TABLE)：文本上安检传送带，
    # 每个字符查一次墙上表——全角字母换成半角、标点空白直接删、表上没登记的（中文汉字！）原样放行。
    # 汉字不在映射表里，所以"怎么练胸"四个字安全过关。
    return s.translate(_TABLE).lower()
def dedupe_qa(pairs):
    if not isinstance(pairs,list):
        raise TypeError('pairs必须是list')
    #seen：访客登记本（集合），只回答一个问题——"这身份证号登记过吗？"，哈希柜号直查 O(1)
    seen=set()
    #result：放行名单（列表），负责记住放行的先后顺序。集合不保序，所以顺序得靠列表
    result=[]
    for pair in pairs:
        key=clean_text(pair[0])
        if key not in seen:
            seen.add(key)
            result.append(pair)#放进去的是本人pair不是key门禁卡
    return result