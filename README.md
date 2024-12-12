🏫 新正方教务管理系统 API

😁 几乎规避所有学校不同导致的兼容性问题，可放心食用！！

<!-- > ⚠️ 原 Django-WebAPI 项目：[jokerwho/zfnew_wenApi](https://github.com/jokerwho/zfnew_webApi) 已停止更新，后续 API 更新将在本项目进行 -->

求 ⭐⭐⭐⭐⭐（跪

---

## 功能实现

- [x] 登录（自动识别是否需要验证码）
- [x] 个人信息
- [x] 成绩查询（两种接口）
- [x] 考试信息查询
- [x] 课表查询
- [x] 课程表 PDF
- [x] 学业生涯数据
- [x] 学业生涯（学业成绩总表） PDF （**存在兼容问题**）
- [x] 停补换课消息
- [x] 查询已选课程
- [x] 获取选课板块课列表
- [x] 选课
- [x] 退课（**尽量避免使用退课接口，因为判断课程属性等逻辑均由教务系统前端执行，所以直接调用该接口甚至可以退掉必选课**）
- [ ] 空教室查询

## 状态码

为了一些特殊的业务逻辑，如验证码错误后自动刷新页面获取等，使用了自定义状态码，详情如下：

| 状态码 | 内容                 |
| ------ | -------------------- |
| 998    | 网页弹窗未处理内容   |
| 999    | 接口逻辑或未知错误   |
| 1000   | 请求获取成功         |
| 1001   | （登录）需要验证码   |
| 1002   | 用户名或密码不正确   |
| 1003   | 请求超时             |
| 1004   | 验证码错误           |
| 1005   | 内容为空             |
| 1006   | cookies 失效或过期   |
| 1007   | 接口失效请更新       |
| 2333   | 系统维护或服务被 ban |

## Tips⚠️

- 上下课时间 `raspisanie` 若与 `zfn_api.py` 中不一致，请自行按照相关格式编写。
- 学业生涯数据为教务系统 **“学生学业情况查询”** 页面内容，获取数据时请留意 `ignore_type` 和 `detail_category_type`。
  - `ignore_type` 表示需要忽略的最顶部根类型，如 “主修”，“20XX 级 XX 专业” 等无用类型，**可留空数组，对结果无影响**。
  - `detail_category_type` 表示需要详细获取课程分类的类型，如 “其他课程” 需获取该网课属于什么类等，**可留空数组**。
- 教务系统的 cookies 在不同学校统一认证系统不同，**若系统开启了验证码且 cookies 格式内容与默认有出入**，请修改 `zfn_api.py` 中 `login_with_kaptcha()` 中兼容差异注释部分。
- 兼容导致 学业生涯数据 PDF 表的导出会出现问题，待排查。
- 提供了可供 appwrite 等平台调用的云函数 `main.py` ，也有一个简单的测试示例

  ```python
    # example.py
    import base64
    import os
    import sys
    from pprint import pprint

    from zfn_api import Client

    cookies = {}
    base_url = "https://xxx.com"  # 此处填写教务系统URL
    raspisanie = []
    ignore_type = []
    detail_category_type = []
    timeout = 5

    stu = Client(cookies=cookies, base_url=base_url, raspisanie=raspisanie, ignore_type=ignore_type, detail_category_type=detail_category_type, timeout=timeout)

    if cookies == {}:
        lgn = stu.login("sid", "password")  # 此处填写账号及密码
        if lgn["code"] == 1001:
            verify_data = lgn["data"]
            with open(os.path.abspath("kaptcha.png"), "wb") as pic:
                pic.write(base64.b64decode(verify_data.pop("kaptcha_pic")))
            verify_data["kaptcha"] = input("输入验证码：")
            ret = stu.login_with_kaptcha(**verify_data)
            if ret["code"] != 1000:
                pprint(ret)
                sys.exit()
            pprint(ret)
        elif lgn["code"] != 1000:
            pprint(lgn)
            sys.exit()

    result = stu.get_info()  # 获取个人信息
    # result = stu.get_grade(2024, 1)  # 获取成绩信息，若接口错误请添加 use_personal_info=True，只填年份获取全年
    # result = stu.get_exam_schedule(2024, 1)  # 获取考试日程信息，只填年份获取全年
    # result = stu.get_schedule(2024, 1)  # 获取课程表信息
    # result = stu.get_academia()  # 获取学业生涯数据
    # result = stu.get_notifications()  # 获取通知消息
    # result = stu.get_selected_courses(2024, 1)  # 获取已选课程信息
    # result = stu.get_block_courses(2024, 1, 1)  # 获取选课板块课列表
    pprint(result, sort_dicts=False)

    # file_result = stu.get_academia_pdf()["data"]  # 获取学业生涯（学生成绩总表）PDF文件
    file_result = stu.get_schedule_pdf(2024, 1)["data"]  # 获取课程表PDF文件
    with open(os.path.abspath("preview.pdf"), "wb") as f:
        f.write(file_result)

  ```

## 部分数据字段说明

```json
{
  // 成绩
  "course_id": "课程号",
  "title": "课程标题",
  "teacher": "任课教师",
  "class_name": "教学班名称",
  "credit": "学分",
  "category": "课程类别",
  "nature": "课程性质",
  "grade": "成绩",
  "grade_point": "绩点",
  "grade_nature": "成绩性质",
  "start_college": "开课院系",
  "mark": "",
  // 课表
  "weekday": "星期几",
  "time": "上课时间",
  "sessions": "上课节数",
  "list_sessions": "开课节数列表",
  "weeks": "开课周数",
  "list_weeks": "开课周数列表",
  "evaluation_mode": "考核方式",
  "campus": "上课校区",
  "place": "上课场地",
  "hours_composition": "课程学时组成",
  "weekly_hours": "每周学时",
  "total_hours": "总学时",
  // 学业生涯
  "situation": "修读情况",
  "display_term": "修读学期",
  "max_grade": "最佳成绩",
  // 选课
  "class_id": "教学班ID",
  "do_id": "执行ID",
  "teacher_id": "教师ID",
  "kklxdm": "板块课ID",
  "capacity": "教学班容量",
  "selected_number": "已选人数",
  "optional": "是否自选",
  "waiting": "",
  // 考试日程
  "course_id": "课程号",
  "title": "课程名称",
  "time": "考试时间",
  "location": "考试地点",
  "xq": "考试校区",
  "zwh": "考试座号",
  "cxbj": "重修标记",
  "exam_name": "考试名称(如:2023-2024-1学期期末考试)",
  "teacher": "任课教师",
  "class_name": "教学班名称",
  "kkxy": "开课学院",
  "credit": "学分",
  "ksfs": "考试方式(如:笔试,开卷,机考)",
  "sjbh": "试卷编号",
  "bz": "备注",
}
```

## 星图

[![Stargazers over time](https://starchart.cc/openschoolcn/zfn_api.svg)](https://starchart.cc/openschoolcn/zfn_api)
