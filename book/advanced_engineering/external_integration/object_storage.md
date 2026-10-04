---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 对象存储

后端之外的四种外部能力都在本章配齐：存文件的对象存储、加速读取的 Redis、搬运慢活的 Kafka，以及生成摘要的大模型。本节先讲第一种，要回答的问题很朴素：东西放在哪里、谁能取、怎么取。

后端处理的数据大多小而规整，一行订单、一条用户记录，数据库把它们管得井井有条。但真实系统里还有另一类东西：用户上传的合同与头像、定时导出的报表、文档查询应用里的原文 PDF。它们体积大、数量多，内容本身是什么不重要，重要的是放得住、取得回。数据库的表格装不下它们的体积，应用服务器的磁盘经不起多机部署的考验，于是有了专门干这件事的一类服务，对象存储（Object Storage）。云上有 S3、OSS 这些产品，本地自建常用 MinIO。

本节先把"文件为什么不进数据库、不落磁盘"这笔账算清楚，再看它如何给文件编地址、私有文件如何限时授权、大文件如何上传，最后收在长期管理上。

## 文件与数据库的分工

先回答第一个问题：文件为什么不能像业务数据一样，直接存进数据库？

数据库的行是为结构化数据设计的，把文件塞进去有三笔账算不过来。体积上，一篇 PDF 几 MB，上千篇就是几 GB，表膨胀之后备份越来越慢。查询上，再简单的 `SELECT` 也要扛着大字段走，索引帮不上忙。职责上，数据库要保事务与一致性，拿它当文件柜用，是让贵的东西干了便宜的活。

落应用服务器的磁盘也不行。单机时代看似方便，一上多机就露馅：用户这次上传到 A 机，下次请求被分发到 B 机，文件就不见了；换机器、扩容、迁移，文件也跟着丢。两条路都不通，对比看一眼：

| 放哪 | 体积大了会怎样 | 多机部署会怎样 | 前端加速怎么做 |
| --- | --- | --- | --- |
| 数据库 | 表膨胀，备份与查询一起慢 | 主从同步拖着大字段跑 | 做不了，只能走应用 |
| 应用服务器磁盘 | 单机磁盘迟早满 | A 机存的 B 机看不到 | 做不了，只能走应用 |
| 对象存储 | 按量计费，加机器是服务商的事 | 任何机器凭 key 都能取 | CDN 直接加速，不走应用 |

文档查询应用里，文档原文 PDF、用户上传的文件都走对象存储，SQLite 里只存 key。数据库保关系，对象存储保文件，各干各的。文件有了去处，下一个问题随之而来：怎么在成千上万个对象里，把它准确找回来？

## bucket 与 key

找文件靠地址。文件系统用目录树编地址，对象存储换了一种更简单的办法：所有对象平铺放在桶里，靠两级名字定位。外层叫 bucket（桶），内层叫 key（对象键）。

bucket 用来按用途分家。比如 `doc-originals` 存原文、`doc-thumbs` 存预览图，一类东西一个桶。key 是桶内每个对象的完整名字，形如 `docs/{doc_id}/original.pdf`。它看起来像路径，但对象存储并不真的创建目录，斜杠只是名字的一部分。用业务 ID 做前缀有两个好处：按前缀批量管理，控制台里一眼看出归属。

上传时后端做两件事，把文件放进桶，把 key 写进库：

```python
# 后端：文件进桶，key 入库（展示代码，boto3 未在本书环境安装）
import boto3

s3 = boto3.client("s3", endpoint_url="http://localhost:9000")
key = f"docs/{doc_id}/original.pdf"
s3.upload_fileobj(file_obj, "doc-originals", key)
db.execute("UPDATE documents SET file_key = ? WHERE id = ?", (key, doc_id))
```

这段代码的顺序有讲究：先传文件，成功后再把 key 写进库。反过来先写库、传文件失败，库里就留下一条指向空气的记录。之后任何机器、任何时候，凭这个 key 都能把文件取回来。

## 预签名 URL

能存能取了，下一个问题是给谁看。对象存储的桶默认是私有的，这是有意为之：文档原文、用户上传里可能有敏感内容，桶一旦公开，任何人都能枚举和下载。

但前端总得让用户看文件。一个办法是让文件流经后端转发，小文件还行，大文件会把带宽和内存都吃一遍。更常用的办法是临时授权：后端签一张限定文件和有效期的票交给前端，前端凭票直接去对象存储取文件。这张票叫预签名 URL（presigned URL）。

```python
# 后端：签一张 300 秒有效的票，前端拿票直接读文件
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": "doc-originals", "Key": key},
    ExpiresIn=300,
)
```

票上写着取哪个对象、几分钟后作废，由后端用密钥签名生成，不需要给前端分发账号。前端拿票直读，不经过后端；后端只在"签不签"这一步做鉴权。票过期重签即可，文件本身一直在桶里没动过。

## 直传与断点续传

读的授权讲完了，写的方向还有同样的矛盾：文件越大，走后端中转越亏。带宽要花两遍，内容还要在内存里过一手，并发一高后端先被拖垮。所以生产做法是前端直传：后端只签发一张上传用的凭证，前端把文件直接推给对象存储，传完把 key 回告后端入库。

```{mermaid}
flowchart LR
    A["前端请求上传凭证"] --> B["后端鉴权<br/>签发直传票"]
    B --> C["前端拿票<br/>PUT 直达对象存储"]
    C --> D["前端回告后端<br/>key 已就绪"]
    D --> E["后端把 key 入库"]
```

直传解决了带宽，网络稳定性还有一关。一个 200 MB 的文件传到九成断线，从头再来用户会崩溃。办法是分片：把文件切成固定大小的块，每块单独编号上传，全部收齐后拼成完整对象。断网后只补传缺失的块，这就是断点续传。块的大小与并发数是经验值，内网调大、弱网调小。

## 生命周期

文件存进来容易，系统跑上几年，桶会越来越大，账单越来越厚。对象存储给的管理手段是生命周期规则，按年龄自动搬家：

| 数据 | 规则 | 理由 |
| --- | --- | --- |
| 访问日志 | 30 天后删 | 只用于排查，过期无用 |
| 缩略图 | 90 天后转冷存储 | 偶尔看，便宜优先 |
| 文档原文 | 长期保留，开版本控制 | 误删可找回，版本是后悔药 |

误覆盖是另一类常见故障：同名 key 上传失败一半，或者盖掉了不该盖的版本。开启版本控制后，旧版本保留，删错能找回。最后别忘了用量告警：桶是后付费的，半夜被刷量时，先收到通知总比先收到账单好。

## python 代码示例

概念讲完，落到代码只是一个客户端的事。真实环境里，连接对象存储需要四样信息：服务地址、区域、访问密钥、桶名。云厂商与自建服务的差别只在地址：

```python
import os

import boto3

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT", "http://localhost:9000"),
    aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
    aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
)
```

本地想连真的对象存储，用 MinIO 起一个即可（9000 是接口端口，9001 是控制台）：

```bash
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  quay.io/minio/minio server /data --console-address ":9001"
```

书中的构建环境没有真实对象存储，下面的例子用 moto 在进程内模拟 S3，boto3 的调用不用改一处；换成上面的真实配置，就是生产代码。

```{code-cell} ipython3
import boto3
from moto import mock_aws

BUCKET = "doc-originals"
KEY = "docs/doc-001/original.txt"
CONTENT = "pydantic 是一套数据校验工具。"

with mock_aws():
    s3 = boto3.client("s3", region_name="us-east-1")

    s3.create_bucket(Bucket=BUCKET)
    s3.put_object(Bucket=BUCKET, Key=KEY, Body=CONTENT.encode("utf-8"))

    objects = s3.list_objects_v2(Bucket=BUCKET)["Contents"]
    print(f"桶内对象数: {len(objects)}，key: {objects[0]['Key']}")

    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET, "Key": KEY}, ExpiresIn=300
    )
    print(f"预签名 URL 前 60 字符: {url[:60]}")

    body = s3.get_object(Bucket=BUCKET, Key=KEY)["Body"].read().decode("utf-8")
    print(f"读回内容: {body}")
    assert body == CONTENT
```

观测小结：建桶、上传、列出、签名、读回五步全部走通。退出 with 块，模拟出的桶随内存一起消失，随时可以重跑；预签名 URL 在真实环境由浏览器直接 GET，模拟环境不提供这个入口，替换连接参数后其余代码不变。

## 本节小结

- 数据库保关系，对象存储保文件，大文件进表会拖慢备份与查询，多机下磁盘文件会找不到。
- bucket 按用途分家，key 带业务 ID 做前缀，库里只存 key；先传文件、后写库，顺序不能反。
- 桶默认私有，前端看文件靠后端签预签名 URL，限时限额，文件本身不动。
- 大文件走前端直传，后端只发凭证；断点续传靠分片编号，断了只补缺失的块。
- 桶要长期经营：冷热分层、版本控制、用量告警，一个都不能少。
