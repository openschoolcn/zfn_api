⭐ 新正方教务管理系统 API

> ⚠️ 原 Django-WebAPI 项目：[jokerwho/zfnew_wenApi](https://github.com/jokerwho/zfnew_webApi) 已停止更新，后续 API 更新将在本项目进行

求 ⭐⭐⭐⭐⭐（跪

---

## 相关说明

### 功能实现

- [x] 登录（自动识别是否需要验证码）
- [x] 个人信息
- [x] 成绩查询（两种接口）
- [x] 课表查询
- [x] 课程表 PDF
- [x] 学业生涯数据（**较小兼容问题**）
- [x] 学业生涯（学业成绩总表） PDF （**较大兼容问题**）
- [x] 停补换课消息
- [x] 查询已选课程
- [x] 获取选课板块课列表
- [x] 选课
- [x] 退课
- [ ] 空教室查询

### 状态码

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

### Tips⚠️

- 请先在**config.json**中修改教务系统 base_url 和上下课时间
  > 请仔细留意教务系统网址，部分教务系统并非处于根路径下，如正常的登录网址为：`https://xxx.com/xtgl/login_slogin.html`，只需填写`https://xxx.com`到 config.json 的 base_url 中，`/xtgl` 部分在 API 内代码增删改
- 教务系统的 cookies 在不同学校系统设置不同（因为统一认证系统不尽相同）。因此在使用前，请先搞明白该教务系统的 cookies 包含字段，若与 API 默认有出入，请修改**zfn_api.py**中 `156行` 后内容
- 各校培养方案分类命名不同，故学业生涯数据的获取，也就是 `get_academia_type_statistics()` 函数，打印出 `id_list` 后，请根据学校的分类和命名去编写 `map`
- 兼容导致 学业生涯数据 PDF 表的导出也会出现问题
- 提供一个简单的测试示例 **example.py**

  ```python
    import base64
    import os
    import sys
    from pprint import pprint

    from zfn_api import Client

    cookies = {}

    stu = Client(cookies=cookies)

    if cookies == {}:
        lgn = stu.login("sid", "password")
        if lgn["code"] == 1001:
            verify_data = lgn["data"]
            with open(os.path.abspath("kaptcha.png"), "wb") as pic:
                pic.write(base64.b64decode(verify_data["kaptcha_pic"]))
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
    # result = stu.get_grade(2021, 2)  # 获取成绩信息，若接口错误请添加 use_personal_info=True
    # result = stu.get_schedule(2022, 1)  # 获取课程表信息
    # result = stu.get_academia()  # 获取学业生涯数据
    # result = stu.get_notifications()  # 获取通知消息
    # result = stu.get_selected_courses(2022, 1)  # 获取已选课程信息
    # result = stu.get_block_courses(2021, 1, 1)  # 获取选课板块课列表
    pprint(result, sort_dicts=False)

    # file_result = stu.get_academia_pdf()["data"]  # 获取学业生涯（学生成绩总表）PDF文件
    file_result = stu.get_schedule_pdf(2022, 1)["data"]  # 获取课程表PDF文件
    with open("preview.pdf", "wb") as f:
        f.write(file_result)

  ```
