🏫 【青龙面板】正方教务系统成绩发布提醒

## 使用方法
### 1. 青龙面板添加订阅
类型：公开仓库
地址：https://github.com/Xuuyuan/zfn_scorecheck.git
添加订阅后点击运行以下载脚本。

### 2. 设置环境变量
在青龙面板中设置以下环境变量
ZF_URL: 教务系统地址，FJNU为"https://jwglxt.fjnu.edu.cn/jwglxt/"
ZF_ACCOUNT: 教务系统账号
ZF_PASSWORD: 教务系统密码
ZF_YEAR: 启用学年，如2024-2025学年则填写"2024"

### 3. 修改定时任务时间
在青龙面板中找到zfn_main.py，修改定时规则
建议使用：0 */20 * * * ? #每隔20分钟执行一次

### 4. Enjoy it