import os
import sys
import json
import hashlib
from zfn_api import zfn_api
from zfn_api import notify


def str_to_md5(string):
    if isinstance(string, str):
        string = string.encode("utf-8")
    m = hashlib.md5()
    m.update(string)
    return m.hexdigest()


# 检查环境变量
for item in ["ZF_ACCOUNT", "ZF_PASSWORD", "ZF_URL", "ZF_YEAR"]:
    if item not in os.environ:
        print(f"环境变量 {item} 未设置。")
        sys.exit()
try:
    year = int(os.environ.get("ZF_YEAR"))
except ValueError:
    print("环境变量 ZF_YEAR 不是有效值。")
    sys.exit()

# 读取或创建本地存储的Cookie列表
cookie_file_name = 'ZF_COOKIE.json'
course_file_name = 'ZF_COURSE.json'
if os.path.exists(cookie_file_name):
    with open(cookie_file_name, 'r') as json_file:
        cookies = json.load(json_file)
else:
    with open(cookie_file_name, 'w') as json_file:
        json.dump({}, json_file)
    cookies = {}

# 读取或创建本地存储的课程列表
if os.path.exists(course_file_name):
    with open(course_file_name, 'r') as json_file:
        courses = json.load(json_file)
else:
    with open(course_file_name, 'w') as json_file:
        json.dump({}, json_file)
    courses = {}

print(f"读取到本地存储的Cookie: {cookies}")

# 创建Client
if cookies is None:
    cookies = {}
stu = zfn_api.Client(cookies=cookies, base_url=os.getenv("ZF_URL"), raspisanie=[],
             ignore_type=[], detail_category_type=[], timeout=8, retry_times=3)

if cookies == {}:
    lgn = stu.login(os.getenv("ZF_ACCOUNT"), os.getenv("ZF_PASSWORD"))
    if lgn["code"] != 1000:
        print(lgn['msg'])
        sys.exit()
    else:
        with open(cookie_file_name, 'w') as json_file:
            json.dump(lgn["data"]["cookies"], json_file)

result = stu.get_grade(year)
msg = []
msg_short = []
if result['code'] == 1006:  # 登录状态过期，下次运行自动重新登录
    with open(cookie_file_name, 'w') as json_file:
        json.dump({}, json_file)
    print('Cookie过期，已清除本地存储的Cookie')
else:
    for i in result['data']['courses']:
        key_name = str_to_md5(f"{i['title']}_{i['course_id']}_{i['class_name']}_{i['teacher']}")
        line_msg = f"【{i['nature']}】{i['title']}({i['teacher']}) | 课程得分: {i['grade']}分, 课程学分: {i['credit']}分, 绩点: {i['grade_point']}"
        if key_name not in courses or courses[key_name] != str_to_md5(line_msg):
            print(line_msg)
            msg_short.append(i['title'])
            msg.append(line_msg)
            courses[key_name] = str_to_md5(line_msg)
            with open(course_file_name, 'w') as json_file:
                json.dump(courses, json_file)
if len(msg) != 0:
    notify.send(f"【正方推送】考试成绩变动提醒:" + "|".join(msg_short), "\n".join(msg))
