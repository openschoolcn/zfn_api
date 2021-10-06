⭐ 新正方教务管理系统 API

> # ⚠️ 原 Django-WebAPI 项目：[jokerwho/zfnew_wenApi](https://github.com/jokerwho/zfnew_webApi)已停止更新，后续 API 更新将在本项目进行

求 ⭐⭐⭐⭐⭐（跪

- [相关说明](#相关说明)
  - [功能实现](#功能实现)
  - [数据内容说明](#数据内容说明)
  - [Tips](#Tips)

---

## 相关说明

### 功能实现

- [x] 登录（自动识别是否需要验证码）
- [x] **[person]**个人信息
- [x] 成绩查询（带平时分）
- [x] **[grade]**成绩查询（不带平时分）
- [x] **[schedule]**课表查询
- [x] **[schedulepdf]**课程表 PDF
- [x] **[study]**学业情况
- [x] **[gradepdf]**学业成绩总表 PDF
- [x] **[message]**停补换课消息
- [x] **[choosed]**查询已选课程
- [x] 获取选课板块课列表
- [x] 选课
- [x] 退课
- [ ] 空教室查询

### 数据内容说明

- 点击[JSON 说明.MD](https://github.com/jokerwho/zfn_api/blob/master/JSON说明.MD)访问返回的 JSON 数据键值名称以及具体内容说明

### Tips

- 请先在**config.json**中修改教务系统 URL 和上课下课时间
  > 注意，请仔细留意教务系统网址，部分教务系统并非处于根路径下，例如：正常的登录网址为：`https://xxx.com/xtgl/login_slogin.html`，此时你只需填写`https://xxx.com`到 config.json 的 educationBaseUrl 中
- 本项目提供一个简单的测试示例**test.api**，你可以通过以下方式运行测试

  > `python test.py {classfunc} {func} {cookies}`

  > 如 `python test.py info person` 或 `python test.py info schedule cookies`

  > classfunc 为分别为 info（信息查询）和 choose（选课相关）；func 在上述**功能实现**中已为相关功能标出，可自定义；cookies 为可选参数，当该参数内容为"cookies"时，将使用 test.py 中写的 mycookies 变量为 cookies，无需登录

- ⚠️API 中，cookies 在不同学校设置不同，有的学校是 JSESSIONID+route,有的学校只有 JSESSIONID,有的学校为其它字段...因此，在使用本 API 前，请先搞清楚所在学校教务系统的 Cookies 需要哪些字段，若非 JSESSIONID+route（API 默认），请修改**zfn_api.py**的如下几处：
  > 155-156 行，原逻辑为没有检测到系统返回的 route，则使用登录前返回的 route，可删除 155-157 行，只保留 158 行。
