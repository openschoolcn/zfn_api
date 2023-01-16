import base64
import json
from datetime import datetime
from zfn_api import Client


def execute(variables, payload):
    # 获取&组装参数
    base_url = variables["BASE_URL"]
    timeout = variables.get("TIMEOUT", 5)

    req_ignore_type = variables.get("IGNORE_TYPE", None)
    req_detail_category_type = variables.get("DETAIL_CATEGORY_TYPE", None)
    ignore_type = req_ignore_type.split(",") if req_ignore_type else []
    detail_category_type = (
        req_detail_category_type.split(",") if req_detail_category_type else []
    )

    try:
        payload = json.loads(payload)
    except json.decoder.JSONDecodeError:
        return {"code": 999, "msg": "传入参数格式错误"}

    cookies = payload.get("cookies", {})
    client = Client(
        cookies,
        base_url=base_url,
        timeout=timeout,
        ignore_type=ignore_type,
        detail_category_type=detail_category_type,
    )

    # 登录模式 payload require: username, password
    if cookies == {} and payload.get("username") and payload.get("password"):
        lgn = client.login(payload["username"], payload["password"])
        return lgn
    # 验证码登录模式
    elif cookies and payload.get("kaptcha"):
        lgn = client.login_with_kaptcha(**payload)
        return lgn

    year = int(payload.get("query", {}).get("year", datetime.now().year - 1))
    term = int(payload.get("query", {}).get("term", 1))
    block = int(payload.get("query", {}).get("block", 1))
    use_personal_info = payload.get("query", {}).get("use_personal_info", False)

    func = payload.pop("func", None)
    executor = globals().get(f"client.get_{func}")
    if not (func and executor):
        return {"code": 999, "msg": "未指定或未找到调用函数"}

    if func in ["info", "academia", "notifications"]:
        ret = executor()
    elif func in ["schedule", "selected_courses"]:
        ret = executor(year, term)
    elif func == "grade":
        ret = executor(year, term, use_personal_info)
    elif func == "block_courses":
        ret = executor(year, term, block)

    return ret


def main(req, res):
    """Appwrite Cloud Function 入口函数

    Args:
        req: 请求内容，包含 variables headers payload
        res: 响应内容，包含 send() 和 json() 方法

    Returns:
        json: JSON格式数据
    """
    ret = execute(req.variables, req.payload)
    return res.json(ret)
