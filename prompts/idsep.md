# IDSep 格式规范

## 概述
IDSep（IDentifier Separator 的缩写）是一种用于编码键值对（Key-Value Pair）的文本格式。它通过三个特定的分隔符 `$IDK`, `$IDV` 和 `$IDE` 将键（Key）和值（Value）连接起来，形成一串连续的字符序列。

## 格式定义
IDSep 采用 `$IDK` Key `$IDV` Value 的循环结构进行编码，并在循环结束后添加 `$IDE`。

### 语法规则
假设有一组键值对：`k1: v1, k2: v2, ..., kn: vn`。

其对应的 IDSep 编码结果为：
```
$IDK k1 $IDV v1 $IDK k2 $IDV v2 $IDK ... $IDK kn $IDV vn $IDE
```

**核心特征：**
1.  **首尾包裹**：整个字符串以分隔符 `$IDK` 开始，并以分隔符 `$IDE` 结束。
2.  **交替排列**：严格遵循 `Key -> Value -> Key -> Value` 的交替顺序。

## 当前实现
在当前版本中，分隔符 `$IDK` 被定义为固定字符串：`@{MYAGENT:sepidk}`，分隔符 `$IDV` 被定义为固定字符串：`@{MYAGENT:sepidv}`，分隔符 `$IDE` 被定义为固定字符串：`@{MYAGENT:sepide}`。

## 示例
以下是一个具体的 Key-Value 集合转换为 IDSep 格式的示例。

**输入数据：**
```json
{
    "mother": "she",
    "father": "he",
    "me": "boy",
    "gf": "girl"
}
```

**IDSep 编码结果：**
```text
@{MYAGENT:sepidk}mother@{MYAGENT:sepidv}she@{MYAGENT:sepidk}father@{MYAGENT:sepidv}he@{MYAGENT:sepidk}me@{MYAGENT:sepidv}boy@{MYAGENT:sepidk}gf@{MYAGENT:sepidv}girl@{MYAGENT:sepide}
```

*(注：请注意示例中开头的 `@{MYAGENT:sepidk}` 和结尾的 `@{MYAGENT:sepide}`，它们确保了结构的完整性。)*
