# IDSep 格式规范

## 概述
IDSep（IDentifier Separator 的缩写）是一种用于编码键值对（Key-Value Pair）的文本格式。它通过一个特定的分隔符 `$ID` 将键（Key）和值（Value）连接起来，形成一串连续的字符序列。

## 格式定义
IDSep 采用 `$ID` Key `$ID` Value 的循环结构进行编码。

### 语法规则
假设有一组键值对：`k1: v1, k2: v2, ..., kn: vn`。

其对应的 IDSep 编码结果为：
```
$ID k1 $ID v1 $ID k2 $ID v2 $ID ... $ID kn $ID vn $ID
```

**核心特征：**
1.  **首尾包裹**：整个字符串以分隔符 `$ID` 开始，并以分隔符 `$ID` 结束。
2.  **交替排列**：严格遵循 `Key -> Value -> Key -> Value` 的交替顺序。

## 当前实现
在当前版本中，分隔符 `$ID` 被定义为固定字符串：`{sepid}`。

## 示例
以下是一个具体的 KVs 转换为 IDSep 格式的示例。

**输入数据：**
```
"mother": "she"
"father": "he"
"me": "boy"
"gf": "girl"
```

**IDSep 编码结果：**
```text
{sepid}mother{sepid}she{sepid}father{sepid}he{sepid}me{sepid}boy{sepid}gf{sepid}girl{sepid}
```

*(注：请注意示例中开头的 `{sepid}` 和结尾的 `{sepid}`，它们确保了结构的完整性。)*
