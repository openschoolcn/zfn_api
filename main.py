# example.py
import base64
import os
import sys
import ast
# 调试

os.environ["ZF_URL"] = "https://jwglxt.fjnu.edu.cn/jwglxt/"

from zfn_api import Client

cookies = os.getenv("ZF_COOKIE")
print(f"读取到Cookie: {cookies}")
raspisanie = []
ignore_type = []
detail_category_type = []

stu = Client(cookies=ast.literal_eval(cookies), base_url=os.getenv("ZF_URL"), raspisanie=raspisanie, ignore_type=ignore_type, detail_category_type=detail_category_type, timeout=10)

if cookies is None:
    lgn = stu.login(os.getenv("ZF_ACCOUNT"), os.getenv("ZF_PASSWORD"))
    if lgn["code"] == 1001:
        verify_data = lgn["data"]
        with open(os.path.abspath("kaptcha.png"), "wb") as pic:
            pic.write(base64.b64decode(verify_data.pop("kaptcha_pic")))
        verify_data["kaptcha"] = input("输入验证码：")
        ret = stu.login_with_kaptcha(**verify_data)
        if ret["code"] != 1000:
            print(ret)
            sys.exit()
        print(ret)
    elif lgn["code"] != 1000:
        print(lgn)
        sys.exit()
    else:
        os.environ["ZF_COOKIE"] = str(lgn["data"]["cookies"])
        print(lgn)
# result = stu.get_info()  # 获取个人信息
result = stu.get_grade(2023)  # 获取成绩信息，若接口错误请添加 use_personal_info=True，只填年份获取全年
# result = stu.get_schedule(2024, 1)  # 获取课程表信息
# result = stu.get_academia()  # 获取学业生涯数据
# result = stu.get_notifications()  # 获取通知消息
# result = stu.get_selected_courses(2024, 1)  # 获取已选课程信息
# result = stu.get_block_courses(2021, 1, 1)  # 获取选课板块课列表
print(result)