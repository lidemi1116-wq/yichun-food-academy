#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Markdown 教程上传到飞书 —— 走官方「导入任务」接口：
  1) 用 app_id/app_secret 换 tenant_access_token
  2) 上传 .md 素材 (ccm_import_open) 拿 file_token
  3) 创建导入任务 (md -> docx)，飞书自动转成在线文档
  4) 轮询任务结果，拿到 docx token 与 url
  5) 若配置了知识库 space_id，则把文档移进知识库

所有凭证只从环境变量读取，不落盘、不进仓库。

用法:
  export FEISHU_APP_ID=cli_xxx
  export FEISHU_APP_SECRET=xxxxxxxx
  export FEISHU_FOLDER_TOKEN=fldcnXXXX        # 必填: 先导入到这个云空间文件夹
  export FEISHU_WIKI_SPACE_ID=700000000000    # 选填: 配了就移进该知识库
  export FEISHU_WIKI_PARENT_NODE=wikcnYYYY     # 选填: 知识库里的父节点(放在它下面)
  python3 scripts/feishu_upload.py [markdown文件] [文档标题]

默认文件 = duanshipin-tutorial.md，默认标题 = 短视频内容创作方法论
国际版(Lark)请: export FEISHU_BASE=https://open.larksuite.com
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = os.environ.get("FEISHU_BASE", "https://open.feishu.cn").rstrip("/")


def _req(method, path, token=None, body=None, raw=None, content_type=None):
    url = BASE + path
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    elif raw is not None:
        data = raw
        if content_type:
            headers["Content-Type"] = content_type
    else:
        data = None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")
        raise SystemExit("✗ HTTP %s on %s\n  %s" % (e.code, path, detail))
    except urllib.error.URLError as e:
        raise SystemExit("✗ 网络不可达 %s\n  %s\n  (检查环境网络策略是否放行 %s)"
                         % (path, e.reason, BASE))


def _check(resp, what):
    if resp.get("code", 0) != 0:
        raise SystemExit("✗ %s 失败: code=%s msg=%s" % (what, resp.get("code"), resp.get("msg")))
    return resp["data"]


def get_token(app_id, app_secret):
    resp = _req("POST", "/open-apis/auth/v3/tenant_access_token/internal",
                body={"app_id": app_id, "app_secret": app_secret})
    if resp.get("code", 0) != 0:
        raise SystemExit("✗ 取 token 失败: %s (检查 app_id/app_secret)" % resp.get("msg"))
    return resp["tenant_access_token"]


def upload_media(token, folder_token, file_path):
    name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        content = f.read()
    boundary = "----feishuUpload%d" % int(time.time())
    fields = {
        "file_name": name,
        "parent_type": "ccm_import_open",
        "parent_node": folder_token,
        "size": str(len(content)),
        "extra": json.dumps({"obj_type": "docx", "file_extension": "md"}),
    }
    parts = []
    for k, v in fields.items():
        parts.append("--" + boundary)
        parts.append('Content-Disposition: form-data; name="%s"' % k)
        parts.append("")
        parts.append(v)
    head = ("\r\n".join(parts) + "\r\n").encode("utf-8")
    filehdr = ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
               "Content-Type: text/markdown\r\n\r\n" % (boundary, name)).encode("utf-8")
    tail = ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    raw = head + filehdr + content + tail
    resp = _req("POST", "/open-apis/drive/v1/medias/upload_all", token=token,
                raw=raw, content_type="multipart/form-data; boundary=" + boundary)
    return _check(resp, "上传素材")["file_token"]


def create_import(token, file_token, folder_token, title):
    body = {
        "file_extension": "md",
        "file_token": file_token,
        "type": "docx",
        "file_name": title,
        "point": {"mount_type": 1, "mount_key": folder_token},
    }
    resp = _req("POST", "/open-apis/drive/v1/import_tasks", token=token, body=body)
    return _check(resp, "创建导入任务")["ticket"]


def poll_import(token, ticket):
    for _ in range(30):
        resp = _req("GET", "/open-apis/drive/v1/import_tasks/" + ticket, token=token)
        result = _check(resp, "查询导入任务")["result"]
        status = result.get("job_status")
        if status == 0:
            return result.get("token"), result.get("url")
        if status not in (1, 2):  # 1/2 = 处理中
            raise SystemExit("✗ 导入失败: job_status=%s msg=%s" % (status, result.get("job_error_msg")))
        time.sleep(2)
    raise SystemExit("✗ 导入超时，请稍后去飞书查看是否已生成")


def move_to_wiki(token, space_id, obj_token, parent_node):
    body = {"space_id": space_id, "obj_type": "docx", "obj_token": obj_token, "apply": True}
    if parent_node:
        body["parent_wiki_token"] = parent_node
    resp = _req("POST", "/open-apis/wiki/v2/space-node/move_docs_to_wiki", token=token, body=body)
    data = _check(resp, "移入知识库")
    return data.get("wiki_token"), data.get("task_id")


def main():
    md = sys.argv[1] if len(sys.argv) > 1 else "duanshipin-tutorial.md"
    title = sys.argv[2] if len(sys.argv) > 2 else "短视频内容创作方法论"
    if not os.path.isfile(md):
        raise SystemExit("✗ 找不到文件: %s" % md)

    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    folder = os.environ.get("FEISHU_FOLDER_TOKEN")
    space_id = os.environ.get("FEISHU_WIKI_SPACE_ID")
    parent_node = os.environ.get("FEISHU_WIKI_PARENT_NODE")

    missing = [k for k, v in {
        "FEISHU_APP_ID": app_id, "FEISHU_APP_SECRET": app_secret,
        "FEISHU_FOLDER_TOKEN": folder}.items() if not v]
    if missing:
        raise SystemExit("✗ 缺少环境变量: %s\n  (见 scripts/FEISHU_UPLOAD.md)" % ", ".join(missing))

    print("· 取 tenant_access_token ...")
    token = get_token(app_id, app_secret)
    print("· 上传 Markdown 素材 ...")
    file_token = upload_media(token, folder, md)
    print("· 创建导入任务 (md → 飞书文档) ...")
    ticket = create_import(token, file_token, folder, title)
    print("· 等待转换 ...")
    doc_token, url = poll_import(token, ticket)
    print("✓ 已生成飞书文档: %s" % (url or doc_token))

    if space_id:
        print("· 移入知识库 space=%s ..." % space_id)
        wiki_token, task_id = move_to_wiki(token, space_id, doc_token, parent_node)
        if wiki_token:
            print("✓ 已移入知识库, wiki_token=%s" % wiki_token)
        else:
            print("· 移动任务已提交 (task_id=%s)，稍后在知识库查看" % task_id)
    else:
        print("· 未配置 FEISHU_WIKI_SPACE_ID，文档留在云空间文件夹；"
              "如需进知识库，配置后重跑，或在飞书里手动「移动到知识库」")
    print("完成。")


if __name__ == "__main__":
    main()
