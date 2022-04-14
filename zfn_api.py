import base64
import binascii
import json
import re
import os
import time
import traceback

import requests
import rsa
from pyquery import PyQuery as pq
from requests import exceptions

def loadConfig():
    with open(os.path.abspath("config.json"),"r") as f:
        return json.loads(f.read())
config = loadConfig()
BASE_URL = config["educationBaseUrl"]
TIMESUP = config["timesUp"]
TIMESDOWN = config["timesDown"]
TIMEOUT = config["educationTimeout"]

def urljoin(base, path):
    if base.endswith('/'):
        base = base[:-1]
    return base + path

class Login(object):
    """登录类"""

    def __init__(self):
        self.key_url = urljoin(BASE_URL, "/xtgl/login_getPublicKey.html")
        self.login_url = urljoin(BASE_URL, "/xtgl/login_slogin.html")
        self.kaptcha_url = urljoin(BASE_URL, "/kaptcha")
        self.headers = requests.utils.default_headers()
        self.headers["Referer"] = self.login_url
        self.headers[
            "User-Agent"
        ] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36"
        self.headers[
            "Accept"
        ] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3"
        self.sess = requests.Session()
        self.sess.keep_alive = False
        self.req = ""
        self.cookies = {}

    def login(self, sid, password):
        """登录教务系统"""
        try:
            # 登录页
            req_csrf = self.sess.get(
                self.login_url, headers=self.headers, timeout=TIMEOUT
            )
            # 获取csrf_token
            doc = pq(req_csrf.text)
            csrf_token = doc("#csrftoken").attr("value")
            pre_cookies = self.sess.cookies.get_dict()
            # 获取publicKey并加密密码
            req_pubkey = self.sess.get(
                self.key_url, headers=self.headers, timeout=TIMEOUT
            ).json()
            modulus = req_pubkey["modulus"]
            exponent = req_pubkey["exponent"]
            if str(doc("input#yzm")) != "":
                try:
                    req_kaptcha = self.sess.get(
                        self.kaptcha_url, headers=self.headers, timeout=TIMEOUT
                    )
                    kaptcha_pic = base64.b64encode(req_kaptcha.content).decode()
                    return {
                        "code": 1001,
                        "msg": "获取验证码成功",
                        "data": {
                            "sid": sid,
                            "csrf_token": csrf_token,
                            "cookies": pre_cookies,
                            "password": password,
                            "modulus": modulus,
                            "exponent": exponent,
                            "kaptcha_pic": kaptcha_pic,
                            "timestamp":time.time()
                        },
                    }
                except exceptions.Timeout:
                    return {"code": 1003, "msg": "获取验证码超时"}
                except exceptions.RequestException:
                    traceback.print_exc()
                    return {"code": 2333, "msg": "请重试或教务系统维护中"}
                except Exception as e:
                    traceback.print_exc()
                    return {"code": 999, "msg": "获取验证码时未记录的错误：" + str(e)}
            else:
                encrypt_password = self.encryptPassword(
                    password, modulus, exponent
                )
                # 登录数据
                login_data = {
                    "csrftoken": csrf_token,
                    "yhm": sid,
                    "mm": encrypt_password,
                }
                # 请求登录
                self.req = self.sess.post(
                    self.login_url,
                    headers=self.headers,
                    data=login_data,
                    timeout=TIMEOUT,
                )
                doc = pq(self.req.text)
                tips = doc("p#tips")
                if str(tips) != "":
                    if "用户名或密码" in tips.text():
                        return {"code": 1002, "msg": "用户名或密码不正确"}
                    else:
                        return {"code": 998, "msg": tips.text()}
                self.cookies = self.sess.cookies.get_dict()
                return {"code": 1000, "msg": "登录成功", "data": {"cookies": self.cookies}}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "登录超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "登录时未记录的错误：" + str(e)}

    def loginWithKaptcha(
        self, sid, csrf_token, cookies, password, modulus, exponent, kaptcha
    ):
        """需要验证码的登陆"""
        try:
            encrypt_password = self.encryptPassword(password, modulus, exponent)
            login_data = {
                "csrftoken": csrf_token,
                "yhm": sid,
                "mm": encrypt_password,
                "yzm": kaptcha,
            }
            self.req = self.sess.post(
                self.login_url,
                headers=self.headers,
                cookies=cookies,
                data=login_data,
                timeout=TIMEOUT,
            )
            # 请求登录
            doc = pq(self.req.text)
            tips = doc("p#tips")
            if str(tips) != "":
                if "验证码" in tips.text():
                    return {"code": 1004, "msg": "验证码输入错误"}
                elif "用户名或密码" in tips.text():
                    return {"code": 1002, "msg": "用户名或密码不正确"}
                else:
                    return {"code": 998, "msg": tips.text()}
            self.cookies = self.sess.cookies.get_dict()
            if not self.cookies.get("route"):
                return {"code": 1000, "msg": "登录成功", "data": {"cookies": {"JSESSIONID":self.cookies["JSESSIONID"],"route":cookies["route"]}}}
            else:
                return {"code": 1000, "msg": "登录成功", "data": {"cookies": self.cookies}}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "登录超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "验证码登录时未记录的错误：" + str(e)}

    @classmethod
    def encryptPassword(cls, pwd, n, e):
        """对密码base64编码"""
        message = str(pwd).encode()
        rsa_n = binascii.b2a_hex(binascii.a2b_base64(n))
        rsa_e = binascii.b2a_hex(binascii.a2b_base64(e))
        key = rsa.PublicKey(int(rsa_n, 16), int(rsa_e, 16))
        encropy_pwd = rsa.encrypt(message, key)
        result = binascii.b2a_base64(encropy_pwd)
        return result


class Info(object):
    """获取信息类"""

    def __init__(self, cookies):
        self.headers = requests.utils.default_headers()
        self.headers["Referer"] = BASE_URL
        self.headers[
            "User-Agent"
        ] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36"
        self.sess = requests.Session()
        self.sess.keep_alive = False
        self.cookies = cookies

    def getPersonInfo(self):
        """获取个人信息"""
        url = urljoin(BASE_URL, "/xsxxxggl/xsxxwh_cxCkDgxsxx.html?gnmkdm=N100801")
        try:
            req_info = self.sess.get(
                url, headers=self.headers, cookies=self.cookies, timeout=TIMEOUT,
            )
            doc = pq(req_info.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            info = req_info.json()
            result = {
                "name": "无" if info.get("xm") is None else info["xm"],
                "studentId": "无" if info.get("xh") is None else info["xh"],
                "birthDay": "无" if info.get("csrq") is None else info["csrq"],
                "idNumber": "无" if info.get("zjhm") is None else info["zjhm"],
                "candidateNumber": "无" if info.get("ksh") is None else info["ksh"],
                "status": "无" if info.get("xjztdm") is None else info["xjztdm"],
                "collegeName": info.get("jg_id")
                if info.get("zsjg_id") is None
                else info["zsjg_id"],
                "majorName": info.get("zyh_id")
                if info.get("zszyh_id") is None
                else info["zszyh_id"],
                "className": info.get("xjztdm")
                if info.get("bh_id") is None
                else info["bh_id"],
                "entryDate": "无" if info.get("rxrq") is None else info["rxrq"],
                "graduationSchool": "无" if info.get("byzx") is None else info["byzx"],
                "domicile": "无" if info.get("jg") is None else info["jg"],
                "phoneNumber": "无" if info.get("sjhm") is None else info["sjhm"],
                "parentsNumber": "无" if info.get("gddh") is None else info["gddh"],
                "email": "无" if info.get("dzyx") is None else info["dzyx"],
                "politicalStatus": "无" if info.get("zzmmm") is None else info["zzmmm"],
                "national": "无" if info.get("mzm") is None else info["mzm"],
                "education": "无" if info.get("pyccdm") is None else info["pyccdm"],
                "postalCode": "无" if info.get("yzbm") is None else info["yzbm"],
                "grade": int(info["xh"][0:2]),
            }
            return {"code": 1000, "msg": "获取个人信息成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取个人信息超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            if str(e) == "'NoneType' object has no attribute 'get'":
                return {"code": 2333, "msg": "请重试或教务系统维护中"}
            traceback.print_exc()
            return {"code": 999, "msg": "获取个人信息时未记录的错误：" + str(e)}

    def getGrade(self, year, term):
        """获取成绩"""
        url = urljoin(BASE_URL, "/cjcx/cjcx_cxDgXscj.html?doType=query&gnmkdm=N305005")
        dict = {"1": "3", "2": "12", "0": ""}  # 修改检测学期
        if dict.get(term) is not None:
            term = dict.get(term)
        else:
            return {"code": 1006, "msg": "错误的学期编号：" + str(term)}
        data = {
            "xnm": year,  # 学年数
            "xqm": term,  # 学期数，第一学期为3，第二学期为12, 整个学年为空''
            "_search": "false",
            "nd": int(time.time() * 1000),
            "queryModel.showCount": "100",  # 每页最多条数
            "queryModel.currentPage": "1",
            "queryModel.sortName": "",
            "queryModel.sortOrder": "asc",
            "time": "0",  # 查询次数
        }
        try:
            req_grade = self.sess.post(
                url,
                headers=self.headers,
                data=data,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_grade.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            grade = req_grade.json()
            if grade.get("items"):  # 防止数据出错items为空
                result = {
                    "name": grade["items"][0]["xm"],
                    "gpa": self.getGPA(),
                    "studentId": grade["items"][0]["xh"],
                    "schoolYear": grade["items"][0]["xnm"],
                    "schoolTerm": grade["items"][0]["xqmmc"],
                    "err": "ok",
                    "course": [
                        {
                            "courseTitle": i.get("kcmc"),
                            "teacher": i.get("jsxm"),
                            "courseId": i.get("kch_id"),
                            "className": "无" if i.get("jxbmc") is None else i["jxbmc"],
                            "courseNature": "无"
                            if i.get("kcxzmc") is None
                            else i["kcxzmc"],
                            "credit": "无"
                            if i.get("xf") is None
                            else format(float(i["xf"]), ".1f"),
                            "grade": " " if i.get("cj") is None else i["cj"],
                            "gradePoint": " "
                            if i.get("jd") is None
                            else format(float(i["jd"]), ".1f"),
                            "gradeNature": i.get("ksxz"),
                            "startCollege": "无"
                            if i.get("kkbmmc") is None
                            else i["kkbmmc"],
                            "courseMark": i.get("kcbj"),
                            "courseCategory": "无"
                            if i.get("kclbmc") is None
                            else i["kclbmc"],
                            "courseAttribution": "无"
                            if i.get("kcgsmc") is None
                            else i["kcgsmc"],
                        }
                        for i in grade.get("items")
                    ],
                }
                return {"code": 1000, "msg": "获取成绩成功", "data": result}
            else:
                return {"code": 1005, "msg": "获取内容为空"}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取成绩超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取成绩时未记录的错误：" + str(e)}

    def getSchedule(self, year, term):
        """获取课程表信息"""
        url = urljoin(BASE_URL, "/kbcx/xskbcx_cxXsKb.html?gnmkdm=N2151")
        dict = {"1": "3", "2": "12"}
        if dict.get(term) is not None:
            term = dict.get(term)
        else:
            return {"code": 1006, "msg": "错误的学期编号：" + str(term)}
        data = {"xnm": year, "xqm": term}
        try:
            req_schedule = self.sess.post(
                url,
                headers=self.headers,
                data=data,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_schedule.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            schedule = req_schedule.json()
            result = {
                "name": schedule["xsxx"]["XM"],
                "studentId": schedule["xsxx"]["XH"],
                "schoolYear": schedule["xsxx"]["XNM"],
                "schoolTerm": schedule["xsxx"]["XQMMC"],
                "normalCourse": [
                    {
                        "courseTitle": i.get("kcmc"),
                        "teacher": "无" if i.get("xm") is None else i["xm"],
                        "courseId": i.get("kch_id"),
                        "courseWeekday": i.get("xqj"),
                        "courseSection": i.get("jc"),
                        "includeSection": self.listTime(re.findall(r"(\d+)", i["jc"])),
                        "upTime": self.upTime(re.findall(r"(\d+)", i["jc"])),
                        "courseTime": self.calTime(re.findall(r"(\d+)", i["jc"])),
                        "courseWeek": i.get("zcd"),
                        "includeWeeks": self.calWeeks(re.findall(r"[^,]+", i["zcd"])),
                        "exam": i.get("khfsmc"),
                        "campus": i.get("xqmc"),
                        "courseRoom": i.get("cdmc"),
                        "className": i.get("jxbmc"),
                        "hoursComposition": i.get("kcxszc"),
                        "weeklyHours": i.get("zhxs"),
                        "totalHours": i.get("zxs"),
                        "credit": "0.0"
                        if i.get("xf") == "无"
                        else format(float(i.get("xf")), ".1f"),
                    }
                    for i in schedule["kbList"]
                ],
                "otherCourse": [i.get("qtkcgs") for i in schedule.get("sjkList")],
            }
            """
                处理同周同天同课程不同时段合并显示的问题
            """
            repetIndex = []
            count = 0
            for items in result["normalCourse"]:
                for index in range(len(result["normalCourse"])):
                    if (result["normalCourse"]).index(items) == count:  # 如果对比到自己就忽略
                        pass
                    elif (
                        items["courseTitle"]
                        == result["normalCourse"][index]["courseTitle"]  # 同周同天同课程
                        and items["courseWeekday"]
                        == result["normalCourse"][index]["courseWeekday"]
                        and items["courseWeek"]
                        == result["normalCourse"][index]["courseWeek"]
                    ):
                        repetIndex.append(index)  # 满足条件记录索引
                    else:
                        pass
                count = count + 1  # 记录当前对比课程的索引
            if len(repetIndex) % 2 != 0:  # 暂时考虑一天两个时段上同一门课，不满足条件不进行修改
                return {"code": 1000, "msg": "获取课表成功", "data": result}
            for r in range(0, len(repetIndex), 2):  # 索引数组两两成对，故步进2循环
                fir = repetIndex[r]
                sec = repetIndex[r + 1]
                if (
                    len(
                        re.findall(
                            r"(\d+)", result["normalCourse"][fir]["courseSection"]
                        )
                    )
                    == 4
                ):
                    result["normalCourse"][fir]["courseSection"] = (
                        re.findall(
                            r"(\d+)", result["normalCourse"][fir]["courseSection"]
                        )[0]
                        + "-"
                        + re.findall(
                            r"(\d+)", result["normalCourse"][fir]["courseSection"]
                        )[1]
                        + "节"
                    )
                    result["normalCourse"][fir]["includeSection"] = self.listTime(
                        re.findall(
                            r"(\d+)", result["normalCourse"][fir]["courseSection"]
                        )
                    )
                    result["normalCourse"][fir]["upTime"] = self.upTime(
                        re.findall(
                            r"(\d+)", result["normalCourse"][fir]["courseSection"]
                        )
                    )
                    result["normalCourse"][fir]["courseTime"] = self.calTime(
                        re.findall(
                            r"(\d+)", result["normalCourse"][fir]["courseSection"]
                        )
                    )

                    result["normalCourse"][sec]["courseSection"] = (
                        re.findall(
                            r"(\d+)", result["normalCourse"][sec]["courseSection"]
                        )[2]
                        + "-"
                        + re.findall(
                            r"(\d+)", result["normalCourse"][sec]["courseSection"]
                        )[3]
                        + "节"
                    )
                    result["normalCourse"][sec]["includeSection"] = self.listTime(
                        re.findall(
                            r"(\d+)", result["normalCourse"][sec]["courseSection"]
                        )
                    )
                    result["normalCourse"][sec]["upTime"] = self.upTime(
                        re.findall(
                            r"(\d+)", result["normalCourse"][sec]["courseSection"]
                        )
                    )
                    result["normalCourse"][sec]["courseTime"] = self.calTime(
                        re.findall(
                            r"(\d+)", result["normalCourse"][sec]["courseSection"]
                        )
                    )
                else:
                    pass
            return {"code": 1000, "msg": "获取课表成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取课表超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取课表时未记录的错误：" + str(e)}


    def getSchedulePDF(self, name, year, term):
        """获取课表pdf"""
        url_policy = urljoin(BASE_URL,"/kbdy/bjkbdy_cxXnxqsfkz.html")
        url_file = urljoin(BASE_URL, "/kbcx/xskbcx_cxXsShcPdf.html")
        origin_term = term
        dict = {"1": "3", "2": "12", "0": ""}  # 修改检测学期
        if dict.get(term) is not None:
            term = dict.get(term)
        else:
            return {"code": 1006, "msg": "错误的学期编号：" + str(term)}
        data = {
            "xnm": year,
            "xqm": term,
            "xnmc": year+"-"+str(int(year)+1),
            "xqmmc": origin_term,
            "jgmc":"undefined",
            "xm": name,
            "xxdm": "",
            "xszd.sj": "true",
            "xszd.cd": "true",
            "xszd.js": "true",
            "xszd.jszc": "false",
            "xszd.jxb": "true",
            "xszd.xkbz": "true",
            "xszd.kcxszc": "true",
            "xszd.zhxs": "true",
            "xszd.zxs": "true",
            "xszd.khfs": "true",
            "xszd.xf": "true",
            "xszd.skfsmc": "false",
            "kzlx": "dy"
        }

        try:
            # 许可接口
            pilicy_params = {
                "gnmkdm":"N2151"
            }
            req_policy = self.sess.post(
                url_policy,
                headers=self.headers,
                data=data,
                params=pilicy_params,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_policy.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            # 获取PDF文件URL
            file_params = {"doType":"table"}
            req_file = self.sess.post(
                url_file,
                headers=self.headers,
                data=data,
                params=file_params,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_file.text)
            if doc("title").text() == "错误提示":
                error = doc("p.error_title").text()
                return {"code": 999, "msg": "错误：" + error}
            result = req_file.content  # 二进制内容
            return {"code": 1000, "msg": "获取课程表pdf成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取课程表pdf超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取课程表pdf时未记录的错误：" + str(e)}


    def getStudy(self, sid):
        """获取学业情况"""
        url_main = urljoin(
            BASE_URL, "/xsxy/xsxyqk_cxXsxyqkIndex.html?gnmkdm=N105515&layout=default",
        )
        url_info = urljoin(
            BASE_URL, "/xsxy/xsxyqk_cxJxzxjhxfyqKcxx.html?gnmkdm=N105515"
        )
        try:
            req_main = self.sess.get(
                url_main,
                headers=self.headers,
                cookies=self.cookies,
                timeout=TIMEOUT,
                stream=True,
            )
            doc_main = pq(req_main.text)
            if doc_main("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            allc_str = [allc.text() for allc in doc_main("font[size='2px']").items()]
            gpa = float(allc_str[2])
            allc_num = re.findall(r"\d+", allc_str[3])
            allc_num2 = re.findall(r"\d+", allc_str[5])
            allc_num.append(allc_num2[0])
            ipa = int(allc_num[0])
            ipp = int(allc_num[1])
            ipf = int(allc_num[2])
            ipn = int(allc_num[3])
            ipi = int(allc_num[4])
            allc_num3 = re.findall(r"\d+", allc_str[6])
            allc_num4 = re.findall(r"\d+", allc_str[7])
            opp = int(allc_num3[0])
            opf = int(allc_num4[0])

            id_find = re.findall(r"xfyqjd_id='(.*)' jdkcsx='1' leaf=''", req_main.text)
            id_find2 = re.findall(r"xfyqjd_id='(.*)' jdkcsx='2' leaf=''", req_main.text)
            idList = list({}.fromkeys(id_find).keys())
            idList2 = list({}.fromkeys(id_find2).keys())
            tsid = "None"
            tzid = "None"
            zyid = "None"
            qtid = "None"
            # 本校特色，不同年级获取四项id的方法不同
            if int(sid[0:2]) < 19:
                for i in idList:
                    if re.findall(r"tsjy", i):
                        tsid = i[0:14]
                    elif re.findall(r"tzjy", i):
                        tzid = i[0:14]
                    elif re.findall(r"zyjy", i):
                        zyid = i[0:14]
                    elif re.findall(r"qtkcxfyq", i):
                        qtid = i
            elif int(sid[0:2]) == 19:
                tsid = idList[0]
                tzid = idList[2]
                zyid = idList[1]
                qtid = idList2[0]
            elif int(sid[0:2]) >= 20:
                tsid = idList[0]
                tzid = idList[2]
                zyid = idList[1]
                qtid = idList[3]
            else:
                tsid = idList[0]
                tzid = idList[2]
                zyid = idList[1]
                qtid = idList2[0]

            req_ts = self.sess.post(
                url_info,
                headers=self.headers,
                data={"xfyqjd_id": tsid},
                cookies=self.cookies,
                timeout=TIMEOUT,
                stream=True,
            )
            req_tz = self.sess.post(
                url_info,
                headers=self.headers,
                data={"xfyqjd_id": tzid},
                cookies=self.cookies,
                timeout=TIMEOUT,
                stream=True,
            )
            req_zy = self.sess.post(
                url_info,
                headers=self.headers,
                data={"xfyqjd_id": zyid},
                cookies=self.cookies,
                timeout=TIMEOUT,
                stream=True,
            )
            req_qt = self.sess.post(
                url_info,
                headers=self.headers,
                data={"xfyqjd_id": qtid},
                cookies=self.cookies,
                timeout=TIMEOUT,
                stream=True,
            )
            ts_point_find = re.findall(
                # r"通识(.*)&nbsp;要求学分:(\d+\.\d+)&nbsp;获得学分:(\d+\.\d+)&nbsp;&nbsp;未获得学分:(\d+\.\d+)&nbsp",
                r"通识(.*)\* 要求学分 \*/\+\":([0-9]{1,}[.][0-9]*)(.*)\* 获得学分 \*/\+\":([0-9]{1,}[.][0-9]*)(.*)\* 未获得学分 \*/\+\":([0-9]{1,}[.][0-9]*)",
                req_main.text,
            )
            ts_point_list = list(
                list({}.fromkeys(ts_point_find).keys())[0]
            )  # 先得到元组再拆开转换成列表
            ts_point = {
                "tsr": ts_point_list[1],
                "tsg": ts_point_list[2],
                "tsn": ts_point_list[3],
            }
            tz_point_find = re.findall(
                # r"拓展(.*)&nbsp;要求学分:(\d+\.\d+)&nbsp;获得学分:(\d+\.\d+)&nbsp;&nbsp;未获得学分:(\d+\.\d+)&nbsp",
                r"拓展(.*)\* 要求学分 \*/\+\":([0-9]{1,}[.][0-9]*)(.*)\* 获得学分 \*/\+\":([0-9]{1,}[.][0-9]*)(.*)\* 未获得学分 \*/\+\":([0-9]{1,}[.][0-9]*)",
                req_main.text,
            )
            tz_point_list = list(list({}.fromkeys(tz_point_find).keys())[0])
            tz_point = {
                "tzr": tz_point_list[1],
                "tzg": tz_point_list[2],
                "tzn": tz_point_list[3],
            }
            zy_point_find = re.findall(
                # r"专业(.*)&nbsp;要求学分:(\d+\.\d+)&nbsp;获得学分:(\d+\.\d+)&nbsp;&nbsp;未获得学分:(\d+\.\d+)&nbsp",
                r"专业(.*)\* 要求学分 \*/\+\":([0-9]{1,}[.][0-9]*)(.*)\* 获得学分 \*/\+\":([0-9]{1,}[.][0-9]*)(.*)\* 未获得学分 \*/\+\":([0-9]{1,}[.][0-9]*)",
                req_main.text,
            )
            zy_point_list = list(list({}.fromkeys(zy_point_find).keys())[0])
            zy_point = {
                "zyr": zy_point_list[1],
                "zyg": zy_point_list[2],
                "zyn": zy_point_list[3],
            }
            result = {
                "gpa": str(gpa)
                if gpa != "" and gpa is not None
                else "init",  # 平均学分绩点GPA
                "ipa": ipa,  # 计划内总课程数
                "ipp": ipp,  # 计划内已过课程数
                "ipf": ipf,  # 计划内未过课程数
                "ipn": ipn,  # 计划内未修课程数
                "ipi": ipi,  # 计划内在读课程数
                "opp": opp,  # 计划外已过课程数
                "opf": opf,  # 计划外未过课程数
                "tsData": {
                    "tsPoint": ts_point,  # 通识教育学分情况
                    "tsItems": [
                        {
                            "courseTitle": j.get("KCMC"),
                            "courseId": j.get("KCH"),
                            "courseSituation": j.get("XDZT"),
                            "courseTerm": self.formatTermCN(
                                sid, j.get("JYXDXNM"), j.get("JYXDXQMC")
                            ),
                            "courseCategory": "无"
                            if j.get("KCLBMC") is None
                            else j["KCLBMC"],
                            "courseAttribution": "无"
                            if j.get("KCXZMC") is None
                            else j["KCXZMC"],
                            "maxGrade": " " if j.get("MAXCJ") is None else j["MAXCJ"],
                            "credit": " "
                            if j.get("XF") is None
                            else format(float(j["XF"]), ".1f"),
                            "gradePoint": " "
                            if j.get("JD") is None
                            else format(float(j["JD"]), ".1f"),
                        }
                        for j in req_ts.json()
                    ],  # 通识教育修读情况
                },
                "tzData": {
                    "tzPoint": tz_point,  # 拓展教育学分情况
                    "tzItems": [
                        {
                            "courseTitle": k.get("KCMC"),
                            "courseId": k.get("KCH"),
                            "courseSituation": k.get("XDZT"),
                            "courseTerm": self.formatTermCN(
                                sid, k.get("JYXDXNM"), k.get("JYXDXQMC")
                            ),
                            "courseCategory": "无"
                            if k.get("KCLBMC") is None
                            else k["KCLBMC"],
                            "courseAttribution": "无"
                            if k.get("KCXZMC") is None
                            else k["KCXZMC"],
                            "maxGrade": " " if k.get("MAXCJ") is None else k["MAXCJ"],
                            "credit": " "
                            if k.get("XF") is None
                            else format(float(k["XF"]), ".1f"),
                            "gradePoint": " "
                            if k.get("JD") is None
                            else format(float(k["JD"]), ".1f"),
                        }
                        for k in req_tz.json()
                    ],  # 拓展教育修读情况
                },
                "zyData": {
                    "zyPoint": zy_point,  # 专业教育学分情况
                    "zyItems": [
                        {
                            "courseTitle": l.get("KCMC"),
                            "courseId": l.get("KCH"),
                            "courseSituation": l.get("XDZT"),
                            "courseTerm": self.formatTermCN(
                                sid, l.get("JYXDXNM"), l.get("JYXDXQMC")
                            ),
                            "courseCategory": "无"
                            if l.get("KCLBMC") is None
                            else l["KCLBMC"],
                            "courseAttribution": "无"
                            if l.get("KCXZMC") is None
                            else l["KCXZMC"],
                            "maxGrade": " " if l.get("MAXCJ") is None else l["MAXCJ"],
                            "credit": " "
                            if l.get("XF") is None
                            else format(float(l["XF"]), ".1f"),
                            "gradePoint": " "
                            if l.get("JD") is None
                            else format(float(l["JD"]), ".1f"),
                        }
                        for l in req_zy.json()
                    ],  # 专业教育修读情况
                },
                "qtData": {
                    "qtPoint": "{}",  # 其它课程学分情况
                    "qtItems": [
                        {
                            "courseTitle": m.get("KCMC"),
                            "courseId": m.get("KCH"),
                            "courseSituation": m.get("XDZT"),
                            "courseTerm": self.formatTermCN(sid, m["XNM"], m["XQMMC"]),
                            "courseCategory": self.catByCourseId(m.get("KCH")),
                            "courseAttribution": " "
                            if m.get("KCXZMC") is None
                            else m["KCXZMC"],
                            "maxGrade": " " if m.get("MAXCJ") is None else m["MAXCJ"],
                            "credit": " "
                            if m.get("XF") is None
                            else format(float(m["XF"]), ".1f"),
                            "gradePoint": " "
                            if m.get("JD") is None
                            else format(float(m["JD"]), ".1f"),
                        }
                        for m in req_qt.json()
                    ],  # 其它课程修读情况
                },
            }
            return {"code": 1000, "msg": "获取学业情况成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取学业情况超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取学业情况时未记录的错误：" + str(e)}

    def getGradePDF(self, sid):
        """获取学生成绩总表pdf"""
        url_view = urljoin(BASE_URL, "/bysxxcx/xscjzbdy_dyXscjzbView.html")
        url_window = urljoin(BASE_URL,"/bysxxcx/xscjzbdy_dyCjdyszxView.html")
        url_policy = urljoin(BASE_URL,"/xtgl/bysxxcx/xscjzbdy_cxXsCount.html")
        url_filetype = urljoin(BASE_URL, "/bysxxcx/xscjzbdy_cxGswjlx.html")
        url_common = urljoin(BASE_URL, "/common/common_cxJwxtxx.html")
        url_file = urljoin(BASE_URL, "/bysxxcx/xscjzbdy_dyList.html")
        url_progress = urljoin(BASE_URL,"/xtgl/progress_cxProgressStatus.html")
        data = {
            "gsdygx": "10628-zw-mrgs",
            "ids": "",
            "bdykcxzDms": "",
            "cytjkcxzDms": "",
            "cytjkclbDms": "",
            "cytjkcgsDms": "",
            "bjgbdykcxzDms": "",
            "bjgbdyxxkcxzDms": "",
            "djksxmDms": "",
            "cjbzmcDms": "",
            "cjdySzxs": "",
            "wjlx": "pdf",
        }

        try:
            data_view = {
                "time": str(round(time.time() * 1000)),
                "gnmkdm": "N558020",
                "su": str(sid),
            }
            data_params = data_view
            del data_params["time"]
            # View接口
            req_view = self.sess.post(
                url_view,
                headers=self.headers,
                data=data_view,
                params=data_view,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_view.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            # Window接口
            data_window = {"xh": ""}
            self.sess.post(
                url_window,
                headers=self.headers,
                data=data_window,
                params=data_params,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            # 许可接口
            data_policy = data
            del data_policy["wjlx"]
            self.sess.post(
                url_policy,
                headers=self.headers,
                data=data_policy,
                params=data_params,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            # 文件类型接口
            data_filetype = data_policy
            self.sess.post(
                url_filetype,
                headers=self.headers,
                data=data_filetype,
                params=data_params,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            # Common接口
            self.sess.post(
                url_common,
                headers=self.headers,
                data=data_params,
                params=data_params,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            # 获取PDF文件URL
            req_file = self.sess.post(
                url_file,
                headers=self.headers,
                data=data,
                params=data_params,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_file.text)
            if doc("title").text() == "错误提示":
                error = doc("p.error_title").text()
                return {"code": 999, "msg": "错误：" + error}
            # 进度接口
            data_progress = {
                "key": "score_print_processed",
                "gnmkdm": "N558020",
                "su": str(sid),
            }
            self.sess.post(
                url_progress,
                headers=self.headers,
                data=data_progress,
                params=data_progress,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            # 生成PDF文件URL
            pdf = (
                req_file.text.replace("#成功", "")
                .replace('"', "")
                .replace("/", "\\")
                .replace("\\\\", "/")
            )
            # 下载PDF文件
            req_pdf = self.sess.get(
                urljoin(BASE_URL, pdf),
                headers=self.headers,
                cookies=self.cookies,
                timeout=TIMEOUT + 2,
            )
            result = req_pdf.content  # 二进制内容
            return {"code": 1000, "msg": "获取学生成绩总表pdf成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取成绩总表pdf超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取成绩总表pdf时未记录的错误：" + str(e)}

    def getMessage(self):
        """获取消息"""
        def makeLineFeed(str):
            if str is not None:
                return str[:str.find(":")] + ":\\n"+str[str.find(":")+1:]
            else:
                return None
        url = urljoin(BASE_URL, "/xtgl/index_cxDbsy.html?doType=query")
        data = {
            "sfyy": "0",  # 是否已阅，未阅未1，已阅为2
            "flag": "1",
            "_search": "false",
            "nd": int(time.time() * 1000),
            "queryModel.showCount": "1000",  # 最多条数
            "queryModel.currentPage": "1",  # 当前页数
            "queryModel.sortName": "cjsj",
            "queryModel.sortOrder": "desc",  # 时间倒序, asc正序
            "time": "0",
        }
        try:
            req_msg = self.sess.post(
                url,
                headers=self.headers,
                data=data,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_msg.text)
            if doc("h5").text() == "用户登录" or doc("title").text() == "错误提示":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            msg = req_msg.json()
            result = [
                {"message": makeLineFeed(i.get("xxnr")), "ctime": i.get("cjsj")}
                for i in msg.get("items")
            ]
            return {"code": 1000, "msg": "获取消息成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取消息超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取消息时未记录的错误：" + str(e)}

    def getNowClass(self):
        """获取当前班级"""
        url = urljoin(BASE_URL, "/xsxxxggl/xsxxwh_cxCkDgxsxx.html?gnmkdm=N100801")
        try:
            req_class = self.sess.get(
                url, headers=self.headers, cookies=self.cookies, timeout=TIMEOUT,
            )
            doc = pq(req_class.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            info = req_class.json()
            result = info.get("xjztdm") if info.get("bh_id") is None else info["bh_id"]
            return {"code": 1000, "msg": "获取当前班级成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取当前班级超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取当前班级时未记录的错误：" + str(e)}

    def getGPA(self):
        """获取GPA"""
        url = urljoin(
            BASE_URL, "/xsxy/xsxyqk_cxXsxyqkIndex.html?gnmkdm=N105515&layout=default",
        )
        req_gpa = self.sess.get(
            url, headers=self.headers, cookies=self.cookies, timeout=TIMEOUT,
        )
        doc = pq(req_gpa.text)
        if doc("h5").text() == "用户登录":
            return {"code": 1013, "msg": "登录过期，请重新登录"}
        allc_str = [allc.text() for allc in doc("font[size='2px']").items()]
        try:
            gpa = float(allc_str[2])
            if gpa != "" and gpa is not None:
                return gpa
            else:
                return "init"
        except Exception as e:
            # if "list index" in str(e):
            #     return "init"
            return "init"

    def catByCourseId(self, course_id):
        """根据课程号获取类别"""
        url = urljoin(BASE_URL, "/jxjhgl/common_cxKcJbxx.html?id=" + course_id)
        req_category = self.sess.get(
            url, headers=self.headers, cookies=self.cookies, timeout=TIMEOUT,
        )
        doc = pq(req_category.text)
        th_list = doc("th")
        try:
            data_list = [
                (content.text).strip()
                for content in th_list
                if (content.text).strip() != ""
            ]
            return data_list[5]
        except:
            return "未知类别"

    def getGradeDetail(self, year, term):
        """
            获取成绩接口：可查看平时成绩和期末成绩及总评成绩；
            部分学校系统中平时成绩查看为“没权限”，故本接口并非都适用
        """
        url = urljoin(BASE_URL, "/cjcx/cjcx_cxXsKccjList.html?gnmkdm=N305007")
        dict = {"1": "3", "2": "12", "0": ""}  # 修改检测学期
        if dict.get(term) is not None:
            term = dict.get(term)
        else:
            return {"code": 1006, "msg": "错误的学期编号：" + str(term)}
        data = {
            "xnm": year,  # 学年数
            "xqm": term,  # 学期数，第一学期为3，第二学期为12, 整个学年为空''
            "_search": "false",
            "nd": int(time.time() * 1000),
            "queryModel.showCount": "100",  # 每页最多条数
            "queryModel.currentPage": "1",
            "queryModel.sortName": "",
            "queryModel.sortOrder": "asc",
            "time": "0",  # 查询次数
        }
        try:
            req_grade = self.sess.post(
                url,
                headers=self.headers,
                data=data,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_grade.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            grade = req_grade.json()
            if grade.get("items"):  # 防止数据出错items为空
                result = {
                    "name": "DteailAPI",
                    "gpa": self.getGPA(),
                    "studentId": grade["items"][0]["xh_id"],
                    "schoolYear": grade["items"][0]["xnm"],
                    "schoolTerm": grade["items"][0]["xqmmc"],
                    "err": "ok",
                    "course": [
                        {
                            "courseTitle": i.get("kcmc"),
                            "teacher": "无",
                            "courseId": i.get("kch_id"),
                            "className": "无" if i.get("jxbmc") is None else i["jxbmc"],
                            "courseNature": "N",
                            "credit": "无"
                            if i.get("xf") is None
                            else format(float(i.get("xf")), ".1f"),
                            "grade": " " if i.get("xmcj") is None else i["xmcj"],
                            "gradePoint": self.calPoint(i.get("xmcj")),
                            "gradeNature": "N",
                            "gradeDetail": i.get("xmblmc"),
                            "startCollege": "无"
                            if i.get("kkbmmc") is None
                            else i["kkbmmc"],
                            "courseMark": "无",
                            "courseCategory": "无",
                            "courseAttribution": "无",
                        }
                        for i in grade.get("items")
                    ],
                }
                """
                    处理总评成绩、期末成绩和平时成绩
                """
                new_dict = []
                alreadyId = []
                for items in result["course"]:
                    if items["courseId"] in alreadyId:
                        continue
                    newc = {
                        "courseTitle": items["courseTitle"],
                        "courseId": items["courseId"],
                        "courseNature": items["courseNature"],
                        "credit": items["credit"],
                        "grade": items["grade"],
                        "gradePoint": items["gradePoint"],
                        "gradeNature": items["gradeNature"],
                        "courseMark": "N",
                        "courseCategory": "N",
                        "courseAttribution": "N",
                        "nor": "N",
                        "exam": "N",
                    }
                    for index in range(0, len(result["course"])):
                        if items["courseId"] == result["course"][index]["courseId"]:
                            # print(res_dict["course"][index]["courseTitle"])
                            if "总评" in result["course"][index]["gradeDetail"]:
                                newc["grade"] = result["course"][index]["grade"]
                                if newc["grade"] is None:
                                    pass
                                if newc["grade"].isdigit():
                                    newc["gradePoint"] = format(
                                        float((int(newc["grade"]) - 60) // 5 * 0.5 + 1),
                                        ".1f",
                                    )
                                    if float(newc["gradePoint"]) < 0:
                                        newc["gradePoint"] = "0.0"
                                else:
                                    newc["gradePoint"] = "null"
                            elif "平时" in result["course"][index]["gradeDetail"]:
                                newc["nor"] = (
                                    result["course"][index]["gradeDetail"]
                                    + ":"
                                    + result["course"][index]["grade"]
                                )
                            elif "期末" in result["course"][index]["gradeDetail"]:
                                newc["exam"] = (
                                    result["course"][index]["gradeDetail"]
                                    + ":"
                                    + result["course"][index]["grade"]
                                )
                        else:
                            pass
                    alreadyId.append(items["courseId"])
                    new_dict.append(newc)
                result["course"] = new_dict
                return {"code": 1000, "msg": "获取成绩详细成功", "data": result}
            else:
                return {"code": 1005, "msg": "获取内容为空"}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取成绩详细超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取成绩详细时未记录的错误：" + str(e)}

    @staticmethod
    def calPoint(grade):
        """计算绩点"""
        if grade is None:
            return "null"
        else:
            if grade.isdigit() is False:
                return "null"
            else:
                return format(float((int(grade) - 60) // 5 * 0.5 + 1), ".1f")

    @staticmethod
    def calTime(args):
        """返回上下课时间"""
        up_time = TIMESUP[str(args[0])]
        down_time = TIMESDOWN[str(args[1])]
        return up_time + "~" + down_time

    @staticmethod
    def upTime(args):
        """计算上课时间"""
        return TIMESUP[str(args[0])]

    @staticmethod
    def listTime(args):
        """返回该课程为第几节到第几节"""
        return [n for n in range(int(args[0]), int(args[1]) + 1)]

    @staticmethod
    def formatTermCN(sid, year, term):
        """计算培养方案具体学期转化成中文"""
        grade = int(sid[0:2])
        year = int(year[2:4])
        term = int(term)
        dict = {
            grade: "大一上" if term == 1 else "大一下",
            grade + 1: "大二上" if term == 1 else "大二下",
            grade + 2: "大三上" if term == 1 else "大三下",
            grade + 3: "大四上" if term == 1 else "大四下",
        }
        return dict.get(year) if dict.get(year) is not None else "未知"

    @staticmethod
    def calWeeks(args):
        """返回课程所含周列表"""
        week_list = []
        for item in args:
            if "-" in item:
                weeks_pair = re.findall(r"(\d+)", item)
                if len(weeks_pair) != 2:
                    continue
                if "单" in item:
                    for i in range(int(weeks_pair[0]), int(weeks_pair[1])+1):
                        if i % 2 == 1:
                            week_list.append(i)
                elif "双" in item:
                    for i in range(int(weeks_pair[0]), int(weeks_pair[1])+1):
                        if i % 2 == 0:
                            week_list.append(i)
                else:
                    for i in range(int(weeks_pair[0]), int(weeks_pair[1])+1):
                        week_list.append(i)
            else:
                week_num = re.findall(r"(\d+)",item)
                if len(week_num) == 1:
                    week_list.append(int(week_num[0]))
        return week_list


class Choose(object):
    """选课类"""

    def __init__(self, cookies):
        self.headers = {
            "Referer": BASE_URL,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36",
        }
        self.sess = requests.Session()
        self.sess.keep_alive = False
        self.cookies = cookies

    def getChoosed(self, year, term):
        """获取已选课程信息"""
        try:
            url = urljoin(
                BASE_URL, "/xsxk/zzxkyzb_cxZzxkYzbChoosedDisplay.html?gnmkdm=N253512"
            )
            term_dict = {"1": "3", "2": "12", "0": ""}  # 修改检测学期
            if term_dict.get(term) is not None:
                term = term_dict.get(term)
            else:
                return {"code": 1006, "msg": "错误的学期编号：" + str(term)}
            data = {"xkxnm": year, "xkxqm": term}
            req_choosed = self.sess.post(
                url,
                data=data,
                headers=self.headers,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_choosed.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            choosed = req_choosed.json()
            result = {
                "courseNumber": len(choosed),  # 已选课程数
                "items": [
                    {
                        "courseTitle": i.get("kcmc"),
                        "courseCategory": i.get("kklxmc"),
                        "teacher": (re.findall(r"/(.*?)/", i.get("jsxx")))[0],
                        "teacher_id": (re.findall(r"(.*?\d+)/", i.get("jsxx")))[0],
                        "classId": i.get("jxb_id"),
                        "classVolume": int(i.get("jxbrs")),
                        "classPeople": int(i.get("yxzrs")),
                        "courseRoom": (i.get("jxdd").split("<br/>"))[0]
                        if "<br/>" in i.get("jxdd")
                        else i.get("jxdd"),
                        "courseId": i.get("kch"),
                        "doId": i.get("do_jxb_id"),
                        "courseTime": (i.get("sksj").split("<br/>"))[0]
                        + "、"
                        + (i.get("sksj").split("<br/>"))[1]
                        if "<br/>" in i.get("sksj")
                        else i.get("sksj"),
                        "credit": float(i.get("xf")),
                        "chooseSelf": int(i.get("zixf")),
                        "waiting": i.get("sxbj"),
                    }
                    for i in choosed
                ],
            }
            return {"code": 1000, "msg": "获取已选课程成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取已选课程超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取已选课程时未记录的错误：" + str(e)}

    def getBkkList(self, bkk, year, term):
        """获取板块课选课列表"""
        try:
            """获取head_data"""
            url_data1 = urljoin(
                BASE_URL,
                "/xsxk/zzxkyzb_cxZzxkYzbIndex.html?gnmkdm=N253512&layout=default",
            )
            data1 = self.sess.get(
                url_data1, headers=self.headers, cookies=self.cookies, timeout=TIMEOUT
            )
            doc = pq(data1.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1013, "msg": "登录过期，请重新登录"}
            got_credit_list = [i for i in doc("font[color='red']").items()]
            got_credit = got_credit_list[2].string

            kklxdm_list = []
            xkkz_id_list = []
            for tab_content in doc("a[role='tab']").items():
                onclick_content = tab_content.attr("onclick")
                r = re.findall(r"'(.*?)'", str(onclick_content))
                kklxdm_list.append(r[0].strip())
                xkkz_id_list.append(r[1].strip())
            tab_list = [
                ("bkk1_kklxdm", kklxdm_list[0]),
                ("bkk2_kklxdm", kklxdm_list[1]),
                ("bkk3_kklxdm", kklxdm_list[2]),
                ("bkk1_xkkz_id", xkkz_id_list[0]),
                ("bkk2_xkkz_id", xkkz_id_list[1]),
                ("bkk3_xkkz_id", xkkz_id_list[2]),
            ]
            tab_dict = dict(tab_list)

            data1_list = []
            for data1_content in doc("input[type='hidden']"):
                name = data1_content.attr("name")
                value = data1_content.attr("value")
                data1_list.append((str(name), str(value)))
            data1_dict = dict(data1_list)
            data1_dict.update(gotCredit=got_credit)
            data1_dict.update(tab_dict)

            url_data2 = urljoin(
                BASE_URL, "/xsxk/zzxkyzb_cxZzxkYzbDisplay.html?gnmkdm=N253512"
            )
            data2_data = {
                "xkkz_id": data1_dict["bkk" + bkk + "_xkkz_id"],
                "xszxzt": "1",
                "kspage": "0",
            }
            data2 = self.sess.post(
                url_data2,
                headers=self.headers,
                data=data2_data,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc2 = pq(data2.text)
            data2_list = []
            for data2_content in doc2("input[type='hidden']").items():
                name = data2_content.get("name")
                value = data2_content.get("value")
                data2_list.append((str(name), str(value)))
            data2_dict = dict(data2_list)
            data1_dict.update(data2_dict)
            # print(data2_dict)
            head_data = data1_dict

            """获取课程列表"""
            url_kch = urljoin(
                BASE_URL, "/xsxk/zzxkyzb_cxZzxkYzbPartDisplay.html?gnmkdm=N253512"
            )
            url_bkk = urljoin(
                BASE_URL, "/xsxk/zzxkyzb_cxJxbWithKchZzxkYzb.html?gnmkdm=N253512"
            )
            term_dict = {"1": "3", "2": "12", "0": ""}  # 修改检测学期
            if term_dict.get(term) is not None:
                term = term_dict.get(term)
            else:
                return {"code": 1006, "msg": "错误的学期编号：" + str(term)}
            kch_data = {
                "bklx_id": head_data["bklx_id"],
                "xqh_id": head_data["xqh_id"],
                "zyfx_id": head_data["zyfx_id"],
                "njdm_id": head_data["njdm_id"],
                "bh_id": head_data["bh_id"],
                "xbm": head_data["xbm"],
                "xslbdm": head_data["xslbdm"],
                "ccdm": head_data["ccdm"],
                "xsbj": head_data["xsbj"],
                "xkxnm": year,
                "xkxqm": term,
                "kklxdm": head_data["bkk" + bkk + "_kklxdm"],
                "kkbk": head_data["kkbk"],
                "rwlx": head_data["rwlx"],
                "kspage": "1",
                "jspage": "10",
            }
            kch_res = self.sess.post(
                url_kch,
                headers=self.headers,
                data=kch_data,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            jkch_res = kch_res.json()
            bkk_data = {
                "bklx_id": head_data["bklx_id"],
                "xkxnm": year,
                "xkxqm": term,
                "xkkz_id": head_data["bkk" + bkk + "_xkkz_id"],
                "xqh_id": head_data["xqh_id"],
                "zyfx_id": head_data["zyfx_id"],
                "njdm_id": head_data["njdm_id"],
                "bh_id": head_data["bh_id"],
                "xbm": head_data["xbm"],
                "xslbdm": head_data["xslbdm"],
                "ccdm": head_data["ccdm"],
                "xsbj": head_data["xsbj"],
                "kklxdm": head_data["bkk" + bkk + "_kklxdm"],
                "kch_id": jkch_res["tmpList"][0]["kch_id"],
                "kkbk": head_data["kkbk"],
                "rwlx": head_data["rwlx"],
                "zyh_id": head_data["zyh_id"],
            }
            bkk_res = self.sess.post(
                url_bkk,
                headers=self.headers,
                data=bkk_data,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            jbkk_res = bkk_res.json()
            if bkk != "3" and (len(jkch_res["tmpList"]) != len(jbkk_res)):
                return {"code": 1007, "msg": "板块课编号及长度错误"}
            list1 = jkch_res["tmpList"]
            list2 = jbkk_res
            for i in range(0, len(list1)):
                list1[i].update(list2[i])

            result = {
                "courseNumber": len(list1),
                "items": [
                    {
                        "courseTitle": j.get("kcmc"),
                        "teacher": (re.findall(r"/(.*?)/", j.get("jsxx")))[0],
                        "teacher_id": (re.findall(r"(.*?\d+)/", j.get("jsxx")))[0],
                        "classId": j.get("jxb_id"),
                        "doId": j.get("do_jxb_id"),
                        "kklxdm": head_data["bkk" + bkk + "_kklxdm"],
                        "classVolume": int(j.get("jxbrl")),
                        "classPeople": int(j.get("yxzrs")),
                        "courseRoom": (j.get("jxdd").split("<br/>"))[0]
                        if "<br/>" in j.get("jxdd")
                        else j.get("jxdd"),
                        "courseId": j["kch_id"],
                        "courseTime": (j.get("sksj").split("<br/>"))[0]
                        + "、"
                        + (j.get("sksj").split("<br/>"))[1]
                        if "<br/>" in j.get("sksj")
                        else j.get("sksj"),
                        "credit": float(j.get("xf")),
                    }
                    for j in list1
                ],
            }
            return {"code": 1000, "msg": "获取板块课信息成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取板块课信息超时"}
        except exceptions.RequestException:
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试或教务系统维护中"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取板块课信息时未记录的错误：" + str(e)}

    def choose(self, doId, kcId, gradeId, majorId, kklxdm, year, term):
        url_choose = urljoin(
            BASE_URL, "/xsxk/zzxkyzb_xkBcZyZzxkYzb.html?gnmkdm=N253512"
        )
        term_dict = {"1": "3", "2": "12", "0": ""}  # 修改检测学期
        if term_dict.get(term) is not None:
            term = term_dict.get(term)
        else:
            return {"code": 1006, "msg": "错误的学期编号：" + str(term)}
        choose_data = {
            "jxb_ids": str(doId),
            "kch_id": str(kcId),
            # 'rwlx': '3',
            # 'rlkz': '0',
            # 'rlzlkz': '1',
            # 'sxbj': '1',
            # 'xxkbj': '0',
            # 'cxbj': '0',
            "qz": "0",
            # 'xkkz_id': '9B247F4EFD6291B9E055000000000001',
            "xkxnm": year,
            "xkxqm": term,
            "njdm_id": str(gradeId),
            "zyh_id": str(majorId),
            "kklxdm": str(kklxdm),
            # 'xklc': '1',
        }
        isOk = self.sess.post(
            url_choose,
            headers=self.headers,
            data=choose_data,
            cookies=self.cookies,
            timeout=TIMEOUT,
        )
        doc = pq(isOk.text)
        if doc("h5").text() == "用户登录":
            return {"code": 1013, "msg": "登录过期，请重新登录"}
        result = isOk.json()
        return {"code": 1000, "msg": "选课成功", "data": result}

    def cancel(self, doId, kcId, year, term):
        url_cancel = urljoin(
            BASE_URL, "/xsxk/zzxkyzb_tuikBcZzxkYzb.html?gnmkdm=N253512"
        )
        term_dict = {"1": "3", "2": "12", "0": ""}  # 修改检测学期
        if term_dict.get(term) is not None:
            term = term_dict.get(term)
        else:
            return {"code": 1006, "msg": "错误的学期编号：" + str(term)}
        cancel_data = {
            "jxb_ids": str(doId),
            "kch_id": str(kcId),
            "xkxnm": year,
            "xkxqm": term,
        }
        isOk = self.sess.post(
            url_cancel,
            headers=self.headers,
            data=cancel_data,
            cookies=self.cookies,
            timeout=TIMEOUT,
        )
        doc = pq(isOk.text)
        if doc("h5").text() == "用户登录":
            return {"code": 1013, "msg": "登录过期，请重新登录"}
        result = re.findall(r"(\d+)", isOk.text)[0]
        return {"code": 1000, "msg": "退课成功", "data": result}
