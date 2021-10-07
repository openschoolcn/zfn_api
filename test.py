from zfn_api import Login, Info, Choose
from pprint import pprint
import json
import base64
import sys
import os

sid = ""  # 学号
password = ""  # 密码
mycookies = {
    # 字典形式的Cookies
}
test_year = "2020"  # 查询学年
test_term = "2"  # 查询学期（1-上|2-下）

func_class = sys.argv[1]
func = sys.argv[2]
try:
    method = sys.argv[3]
except IndexError:
    method = None

if __name__ == "__main__":
    if method != "cookies":
        lgn = Login()
        pre_login = lgn.login(sid, password)
        if pre_login["code"] == 1001:
            pre_dict = pre_login["data"]
            with open(os.path.abspath("temp.json"), mode="w", encoding="utf-8") as f:
                f.write(json.dumps(pre_dict))
            with open(os.path.abspath("kaptcha.png"), "wb") as pic:
                pic.write(base64.b64decode(pre_dict["kaptcha_pic"]))
            kaptcha = input("输入验证码：")
            result = lgn.loginWithKaptcha(
                pre_dict["sid"],
                pre_dict["csrf_token"],
                pre_dict["cookies"],
                pre_dict["password"],
                pre_dict["modulus"],
                pre_dict["exponent"],
                kaptcha,
            )
            if result["code"] != 1000:
                pprint(result)
                sys.exit()
            cookies = lgn.cookies
        elif pre_login["code"] == 1000:
            cookies = lgn.cookies
        else:
            pprint(pre_login)
            sys.exit()
    else:
        cookies = mycookies
    if func_class == "info":
        person = Info(cookies)
        if func == "person":
            result = person.getPersonInfo()
        elif func == "gradepdf":
            result = person.getGradePDF(sid)
            if result["code"] == 1000:
                with open(os.path.abspath("grade.pdf"), "wb") as pdf:
                    pdf.write(result["data"])
                    result = "已保存到本地"
        elif func == "schedulepdf":
            result = person.getSchedulePDF("自定义昵称", test_year, test_term)
            if result["code"] == 1000:
                with open(os.path.abspath("schedule.pdf"), "wb") as pdf:
                    pdf.write(result["data"])
                    result = "已保存到本地"
        elif func == "study":
            result = person.getStudy(sid)
        elif func == "gpa":
            result = person.getGPA()
        elif func == "msg":
            result = person.getMessage()
        elif func == "grade":
            result = person.getGrade(test_year, test_term)
        elif func == "schedule":
            result = person.getSchedule(test_year, test_term)
        elif func == "class":
            result = person.getNowClass()
        pprint(result if result is not None else "缺少具体参数")
    elif func_class == "choose":
        person = Choose(cookies)
        if func == "choosed":
            result = person.getChoosed(test_year, test_term)
        pprint(result if result is not None else "缺少具体参数")
    else:
        pprint("缺少具体参数")
