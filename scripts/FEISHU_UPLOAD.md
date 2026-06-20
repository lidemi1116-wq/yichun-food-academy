# 一键上传教程到飞书知识库

脚本 `feishu_upload.py` 会把 `duanshipin-tutorial.md` 通过飞书官方「导入任务」接口
自动转成在线文档，并（可选）移进你的知识库。**凭证只从环境变量读，不写进仓库。**

## 一次性准备（约 5 分钟）

### 1. 建一个企业自建应用
飞书管理后台 → [开发者后台](https://open.feishu.cn/app) → 创建「企业自建应用」。
记下 **App ID**（`cli_` 开头）和 **App Secret**。

### 2. 开权限（应用 → 权限管理，搜索并开通）
- `drive:drive`（云空间读写）— 上传素材 + 导入任务
- `docx:document`（新版文档读写）
- `wiki:wiki`（知识库读写）— 仅当要移进知识库时需要

开通后 **创建版本并发布**，让管理员审核通过（自建应用通常秒过）。

### 3. 把应用加进目标位置
- **云空间文件夹**：打开飞书云文档，建/选一个文件夹，把这个应用「添加为协作者（可编辑）」。
  文件夹链接形如 `.../drive/folder/fldcnXXXXXX` —— `fldcnXXXXXX` 就是 **FOLDER_TOKEN**。
- **知识库**（可选）：进入目标知识库 → 设置 → 成员/管理，把应用加为可管理。
  知识库链接形如 `.../wiki/space/700000000000` —— 末尾数字是 **WIKI_SPACE_ID**。
  若想放在某个父节点下，复制该节点链接里的 `wikcnYYYY` 作为 **WIKI_PARENT_NODE**。

## 运行

```bash
export FEISHU_APP_ID=cli_xxxxxxxx
export FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
export FEISHU_FOLDER_TOKEN=fldcnXXXXXX        # 必填
export FEISHU_WIKI_SPACE_ID=700000000000      # 选填：配了就移进知识库
export FEISHU_WIKI_PARENT_NODE=wikcnYYYY      # 选填：放在某父节点下

python3 scripts/feishu_upload.py
# 或指定文件与标题：
python3 scripts/feishu_upload.py duanshipin-tutorial.md 短视频内容创作方法论
```

成功后会打印生成的飞书文档链接；若配了知识库，会再打印 `wiki_token`。

## 说明
- 国际版 Lark：额外 `export FEISHU_BASE=https://open.larksuite.com`
- 纯标准库，无需 `pip install`。
- App Secret 建议用临时值或随后轮换；不要提交到 git。
- 报 `91402 / NOTEXIST` 多半是 FOLDER_TOKEN 错或应用没被加为该文件夹协作者；
  报权限类错误多半是 scope 没开或版本没发布。
