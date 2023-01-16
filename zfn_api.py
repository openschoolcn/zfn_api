import base64
import binascii
import json
import re
import time
import traceback
import unicodedata
from datetime import datetime
from urllib.parse import urljoin

import requests
import rsa
from pyquery import PyQuery as pq
from requests import exceptions

RASPIANIE = [
    ["8:00", "8:40"],
    ["8:45", "9:25"],
    ["9:30", "10:10"],
    ["10:30", "11:10"],
    ["11:15", "11:55"],
    ["14:30", "15:10"],
    ["15:15", "15:55"],
    ["16:05", "16:45"],
    ["16:50", "17:30"],
    ["18:40", "19:20"],
    ["19:25", "20:05"],
    ["20:10", "20:50"],
    ["20:55", "21:35"],
]


def execute(variables, payload):
    # 获取&组装参数
    base_url = variables["BASE_URL"]
    timeout = int(variables.get("TIMEOUT", 5))

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
    print("variables: ", req.variables)
    print("payload: ", req.payload)
    ret = execute(req.variables, req.payload)
    return res.json(ret)


class Client:
    raspisanie = []
    ignore_type = []

    def __init__(self, cookies={}, **kwargs):
        # 基础配置
        self.base_url = kwargs.get("base_url")
        self.raspisanie = kwargs.get("raspisanie", RASPIANIE)
        self.ignore_type = kwargs.get("ignore_type", [])
        self.detail_category_type = kwargs.get("detail_category_type", [])
        self.timeout = kwargs.get("timeout", 3)
        Client.raspisanie = self.raspisanie
        Client.ignore_type = self.ignore_type

        self.key_url = urljoin(self.base_url, "/xtgl/login_getPublicKey.html")
        self.login_url = urljoin(self.base_url, "/xtgl/login_slogin.html")
        self.kaptcha_url = urljoin(self.base_url, "/kaptcha")
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
        self.cookies = cookies

    def login(self, sid, password):
        """登录教务系统"""
        need_verify = False
        try:
            # 登录页
            req_csrf = self.sess.get(
                self.login_url, headers=self.headers, timeout=self.timeout
            )
            if req_csrf.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            # 获取csrf_token
            doc = pq(req_csrf.text)
            csrf_token = doc("#csrftoken").attr("value")
            pre_cookies = self.sess.cookies.get_dict()
            # 获取publicKey并加密密码
            req_pubkey = self.sess.get(
                self.key_url, headers=self.headers, timeout=self.timeout
            ).json()
            modulus = req_pubkey["modulus"]
            exponent = req_pubkey["exponent"]
            if str(doc("input#yzm")) == "":
                # 不需要验证码
                encrypt_password = self.encrypt_password(password, modulus, exponent)
                # 登录数据
                login_data = {
                    "csrftoken": csrf_token,
                    "yhm": sid,
                    "mm": encrypt_password,
                }
                # 请求登录
                req_login = self.sess.post(
                    self.login_url,
                    headers=self.headers,
                    data=login_data,
                    timeout=self.timeout,
                )
                doc = pq(req_login.text)
                tips = doc("p#tips")
                if str(tips) != "":
                    if "用户名或密码" in tips.text():
                        return {"code": 1002, "msg": "用户名或密码不正确"}
                    return {"code": 998, "msg": tips.text()}
                self.cookies = self.sess.cookies.get_dict()
                return {"code": 1000, "msg": "登录成功", "data": {"cookies": self.cookies}}
            # 需要验证码，返回相关页面验证信息给用户，TODO: 增加更多验证方式
            need_verify = True
            req_kaptcha = self.sess.get(
                self.kaptcha_url, headers=self.headers, timeout=self.timeout
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
                    "timestamp": time.time(),
                },
            }
        except exceptions.Timeout:
            msg = "获取验证码超时" if need_verify else "登录超时"
            return {"code": 1003, "msg": msg}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            msg = "获取验证码时未记录的错误" if need_verify else "登录时未记录的错误"
            return {"code": 999, "msg": f"{msg}：{str(e)}"}

    def login_with_kaptcha(
        self, sid, csrf_token, cookies, password, modulus, exponent, kaptcha, **kwargs
    ):
        """需要验证码的登陆"""
        try:
            encrypt_password = self.encrypt_password(password, modulus, exponent)
            login_data = {
                "csrftoken": csrf_token,
                "yhm": sid,
                "mm": encrypt_password,
                "yzm": kaptcha,
            }
            req_login = self.sess.post(
                self.login_url,
                headers=self.headers,
                cookies=cookies,
                data=login_data,
                timeout=self.timeout,
            )
            if req_login.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            # 请求登录
            doc = pq(req_login.text)
            tips = doc("p#tips")
            if str(tips) != "":
                if "验证码" in tips.text():
                    return {"code": 1004, "msg": "验证码输入错误"}
                if "用户名或密码" in tips.text():
                    return {"code": 1002, "msg": "用户名或密码不正确"}
                return {"code": 998, "msg": tips.text()}
            self.cookies = self.sess.cookies.get_dict()
            # 不同学校系统兼容差异
            if not self.cookies.get("route"):
                route_cookies = {
                    "JSESSIONID": self.cookies["JSESSIONID"],
                    "route": cookies["route"],
                }
                self.cookies = route_cookies
            else:
                return {"code": 1000, "msg": "登录成功", "data": {"cookies": self.cookies}}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "登录超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "验证码登录时未记录的错误：" + str(e)}

    def get_info(self):
        """获取个人信息"""
        url = urljoin(self.base_url, "/xsxxxggl/xsxxwh_cxCkDgxsxx.html?gnmkdm=N100801")
        try:
            req_info = self.sess.get(
                url,
                headers=self.headers,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_info.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_info.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            info = req_info.json()
            result = {
                "sid": info.get("xh"),
                "name": info.get("xm"),
                "college_name": info.get("zsjg_id", info.get("jg_id")),
                "major_name": info.get("zszyh_id", info.get("zyh_id")),
                "class_name": info.get("bh_id", info.get("xjztdm")),
                "status": info.get("xjztdm"),
                "enrollment_date": info.get("rxrq"),
                "candidate_number": info.get("ksh"),
                "graduation_school": info.get("byzx"),
                "domicile": info.get("jg"),
                "postal_code": info.get("yzbm"),
                "politics_status": info.get("zzmmm"),
                "nationality": info.get("mzm"),
                "education": info.get("pyccdm"),
                "phone_number": info.get("sjhm"),
                "parents_number": info.get("gddh"),
                "email": info.get("dzyx"),
                "birthday": info.get("csrq"),
                "id_number": info.get("zjhm"),
            }
            return {"code": 1000, "msg": "获取个人信息成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取个人信息超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取个人信息时未记录的错误：" + str(e)}

    def get_grade(self, year: int, term: int = 0, use_personal_info: bool = False):
        """
        获取成绩
        use_personal_info: 是否使用获取个人信息接口获取成绩
        """
        url = urljoin(
            self.base_url,
            "/cjcx/cjcx_cxDgXscj.html?doType=query&gnmkdm=N305005"
            if use_personal_info
            else "/cjcx/cjcx_cxXsgrcj.html?doType=query&gnmkdm=N305005",
        )
        temp_term = term
        term = term**2 * 3
        term = "" if term == 0 else term
        data = {
            "xnm": str(year),  # 学年数
            "xqm": str(term),  # 学期数，第一学期为3，第二学期为12, 整个学年为空''
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
                timeout=self.timeout,
            )
            if req_grade.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_grade.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            grade = req_grade.json()
            grade_items = grade.get("items")
            if not grade_items:
                return {"code": 1005, "msg": "获取内容为空"}
            result = {
                "sid": grade_items[0]["xh"],
                "name": grade_items[0]["xm"],
                "year": year,
                "term": temp_term,
                "count": len(grade_items),
                "courses": [
                    {
                        "course_id": i.get("kch_id"),
                        "title": i.get("kcmc"),
                        "teacher": i.get("jsxm"),
                        "class_name": i.get("jxbmc"),
                        "credit": self.align_floats(i.get("xf")),
                        "category": i.get("kclbmc"),
                        "nature": i.get("kcxzmc"),
                        "grade": self.parse_int(i.get("cj")),
                        "grade_point": self.align_floats(i.get("jd")),
                        "grade_nature": i.get("ksxz"),
                        "start_college": i.get("kkbmmc"),
                        "mark": i.get("kcbj"),
                    }
                    for i in grade_items
                ],
            }
            return {"code": 1000, "msg": "获取成绩成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取成绩超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取成绩时未记录的错误：" + str(e)}

    def get_schedule(self, year: int, term: int):
        """获取课程表信息"""
        url = urljoin(self.base_url, "/kbcx/xskbcx_cxXsKb.html?gnmkdm=N2151")
        temp_term = term
        term = term**2 * 3
        data = {"xnm": str(year), "xqm": str(term)}
        try:
            req_schedule = self.sess.post(
                url,
                headers=self.headers,
                data=data,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_schedule.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_schedule.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            schedule = req_schedule.json()
            if not schedule.get("kbList"):
                return {"code": 1005, "msg": "获取内容为空"}
            result = {
                "sid": schedule["xsxx"].get("XH"),
                "name": schedule["xsxx"].get("XM"),
                "year": year,
                "term": temp_term,
                "count": len(schedule["kbList"]),
                "courses": [
                    {
                        "course_id": i.get("kch_id"),
                        "title": i.get("kcmc"),
                        "teacher": i.get("xm"),
                        "class_name": i.get("jxbmc"),
                        "credit": self.align_floats(i.get("xf")),
                        "weekday": self.parse_int(i.get("xqj")),
                        "time": self.display_course_time(i.get("jc")),
                        "sessions": i.get("jc"),
                        "list_sessions": self.list_sessions(i.get("jc")),
                        "weeks": i.get("zcd"),
                        "list_weeks": self.list_weeks(i.get("zcd")),
                        "evaluation_mode": i.get("khfsmc"),
                        "campus": i.get("xqmc"),
                        "place": i.get("cdmc"),
                        "hours_composition": i.get("kcxszc"),
                        "weekly_hours": self.parse_int(i.get("zhxs")),
                        "total_hours": self.parse_int(i.get("zxs")),
                    }
                    for i in schedule["kbList"]
                ],
                "extra_courses": [i.get("qtkcgs") for i in schedule.get("sjkList")],
            }
            result = self.split_merge_display(result)
            return {"code": 1000, "msg": "获取课表成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取课表超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取课表时未记录的错误：" + str(e)}

    def get_academia(self):
        """获取学业生涯情况"""
        url_main = urljoin(
            self.base_url,
            "/xsxy/xsxyqk_cxXsxyqkIndex.html?gnmkdm=N105515&layout=default",
        )
        url_info = urljoin(
            self.base_url, "/xsxy/xsxyqk_cxJxzxjhxfyqKcxx.html?gnmkdm=N105515"
        )
        try:
            req_main = self.sess.get(
                url_main,
                headers=self.headers,
                cookies=self.cookies,
                timeout=self.timeout,
                stream=True,
            )
            if req_main.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc_main = pq(req_main.text)
            if doc_main("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            if str(doc_main("div.alert-danger")) != "":
                return {"code": 998, "msg": doc_main("div.alert-danger").text()}
            sid = doc_main("form#form input#xh_id").attr("value")
            display_statistics = (
                doc_main("div#alertBox").text().replace(" ", "").replace("\n", "")
            )
            sid = doc_main("input#xh_id").attr("value")
            statistics = self.get_academia_statistics(display_statistics)
            type_statistics = self.get_academia_type_statistics(req_main.text)
            details = {}
            for type in type_statistics.keys():
                details[type] = self.sess.post(
                    url_info,
                    headers=self.headers,
                    data={"xfyqjd_id": type_statistics[type]["id"]},
                    cookies=self.cookies,
                    timeout=self.timeout,
                    stream=True,
                ).json()
            result = {
                "sid": sid,
                "statistics": statistics,
                "details": [
                    {
                        "type": type,
                        "credits": type_statistics[type]["credits"],
                        "courses": [
                            {
                                "course_id": i.get("KCH"),
                                "title": i.get("KCMC"),
                                "situation": self.parse_int(i.get("XDZT")),
                                "display_term": self.get_display_term(
                                    sid, i.get("JYXDXNM"), i.get("JYXDXQMC")
                                ),
                                "credit": self.align_floats(i.get("XF")),
                                "category": self.get_course_category(type, i),
                                "nature": i.get("KCXZMC"),
                                "max_grade": self.parse_int(i.get("MAXCJ")),
                                "grade_point": self.align_floats(i.get("JD")),
                            }
                            for i in details[type]
                        ],
                    }
                    for type in type_statistics.keys()
                    if len(details[type]) > 0
                ],
            }
            return {"code": 1000, "msg": "获取学业情况成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取学业情况超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取学业情况时未记录的错误：" + str(e)}

    def get_academia_pdf(self):
        """获取学业生涯（学生成绩总表）pdf"""
        url_view = urljoin(self.base_url, "/bysxxcx/xscjzbdy_dyXscjzbView.html")
        url_window = urljoin(self.base_url, "/bysxxcx/xscjzbdy_dyCjdyszxView.html")
        url_policy = urljoin(self.base_url, "/xtgl/bysxxcx/xscjzbdy_cxXsCount.html")
        url_filetype = urljoin(self.base_url, "/bysxxcx/xscjzbdy_cxGswjlx.html")
        url_common = urljoin(self.base_url, "/common/common_cxJwxtxx.html")
        url_file = urljoin(self.base_url, "/bysxxcx/xscjzbdy_dyList.html")
        url_progress = urljoin(self.base_url, "/xtgl/progress_cxProgressStatus.html")
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
            data_view = {"time": str(round(time.time() * 1000)), "gnmkdm": "N558020"}
            data_params = data_view
            del data_params["time"]
            # View接口
            req_view = self.sess.post(
                url_view,
                headers=self.headers,
                data=data_view,
                params=data_view,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_view.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_view.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            # Window接口
            data_window = {"xh": ""}
            self.sess.post(
                url_window,
                headers=self.headers,
                data=data_window,
                params=data_params,
                cookies=self.cookies,
                timeout=self.timeout,
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
                timeout=self.timeout,
            )
            # 文件类型接口
            data_filetype = data_policy
            self.sess.post(
                url_filetype,
                headers=self.headers,
                data=data_filetype,
                params=data_params,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            # Common接口
            self.sess.post(
                url_common,
                headers=self.headers,
                data=data_params,
                params=data_params,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            # 获取PDF文件URL
            req_file = self.sess.post(
                url_file,
                headers=self.headers,
                data=data,
                params=data_params,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            doc = pq(req_file.text)
            if "错误" in doc("title").text():
                error = doc("p.error_title").text()
                return {"code": 998, "msg": error}
            # 进度接口
            data_progress = {
                "key": "score_print_processed",
                "gnmkdm": "N558020",
            }
            self.sess.post(
                url_progress,
                headers=self.headers,
                data=data_progress,
                params=data_progress,
                cookies=self.cookies,
                timeout=self.timeout,
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
                urljoin(self.base_url, pdf),
                headers=self.headers,
                cookies=self.cookies,
                timeout=self.timeout + 2,
            )
            result = req_pdf.content  # 二进制内容
            return {"code": 1000, "msg": "获取学生成绩总表pdf成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取成绩总表pdf超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取成绩总表pdf时未记录的错误：" + str(e)}

    def get_schedule_pdf(self, year: int, term: int, name: str = "导出"):
        """获取课表pdf"""
        url_policy = urljoin(self.base_url, "/kbdy/bjkbdy_cxXnxqsfkz.html")
        url_file = urljoin(self.base_url, "/kbcx/xskbcx_cxXsShcPdf.html")
        origin_term = term
        term = term**2 * 3
        data = {
            "xm": name,
            "xnm": str(year),
            "xqm": str(term),
            "xnmc": f"{year}-{year+1}",
            "xqmmc": str(origin_term),
            "jgmc": "undefined",
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
            "kzlx": "dy",
        }

        try:
            # 许可接口
            pilicy_params = {"gnmkdm": "N2151"}
            req_policy = self.sess.post(
                url_policy,
                headers=self.headers,
                data=data,
                params=pilicy_params,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_policy.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_policy.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            # 获取PDF文件URL
            file_params = {"doType": "table"}
            req_file = self.sess.post(
                url_file,
                headers=self.headers,
                data=data,
                params=file_params,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            doc = pq(req_file.text)
            if "错误" in doc("title").text():
                error = doc("p.error_title").text()
                return {"code": 998, "msg": error}
            result = req_file.content  # 二进制内容
            return {"code": 1000, "msg": "获取课程表pdf成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取课程表pdf超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取课程表pdf时未记录的错误：" + str(e)}

    def get_notifications(self):
        """获取通知消息"""
        url = urljoin(self.base_url, "/xtgl/index_cxDbsy.html?doType=query")
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
            req_notification = self.sess.post(
                url,
                headers=self.headers,
                data=data,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_notification.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_notification.text)
            if doc("h5").text() == "用户登录" or "错误" in doc("title").text():
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            notifications = req_notification.json()
            result = [
                {**self.split_notifications(i), "create_time": i.get("cjsj")}
                for i in notifications.get("items")
            ]
            return {"code": 1000, "msg": "获取消息成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取消息超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取消息时未记录的错误：" + str(e)}

    def get_selected_courses(self, year: int, term: int):
        """获取已选课程信息"""
        try:
            url = urljoin(
                self.base_url,
                "/xsxk/zzxkyzb_cxZzxkYzbChoosedDisplay.html?gnmkdm=N253512",
            )
            temp_term = term
            term = term**2 * 3
            data = {"xkxnm": str(year), "xkxqm": str(term)}
            req_selected = self.sess.post(
                url,
                data=data,
                headers=self.headers,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_selected.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_selected.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            selected = req_selected.json()
            result = {
                "year": year,
                "term": temp_term,
                "count": len(selected),
                "courses": [
                    {
                        "course_id": i.get("kch"),
                        "class_id": i.get("jxb_id"),
                        "do_id": i.get("do_jxb_id"),
                        "title": i.get("kcmc"),
                        "teacher_id": (re.findall(r"(.*?\d+)/", i.get("jsxx")))[0],
                        "teacher": (re.findall(r"/(.*?)/", i.get("jsxx")))[0],
                        "credit": float(i.get("xf", 0)),
                        "category": i.get("kklxmc"),
                        "capacity": int(i.get("jxbrs", 0)),
                        "selected_number": int(i.get("yxzrs", 0)),
                        "place": self.get_place(i.get("jxdd")),
                        "time": self.get_course_time(i.get("sksj")),
                        "optional": int(i.get("zixf", 0)),
                        "waiting": i.get("sxbj"),
                    }
                    for i in selected
                ],
            }
            return {"code": 1000, "msg": "获取已选课程成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取已选课程超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"获取已选课程时未记录的错误：{str(e)}"}

    def get_block_courses(self, year: int, term: int, block: int):
        """获取板块课选课列表"""
        # TODO: 优化代码
        try:
            # 获取head_data
            url_head = urljoin(
                self.base_url,
                "/xsxk/zzxkyzb_cxZzxkYzbIndex.html?gnmkdm=N253512&layout=default",
            )
            req_head_data = self.sess.get(
                url_head,
                headers=self.headers,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_head_data.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_head_data.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            if str(doc("div.nodata")) != "":
                return {"code": 998, "msg": doc("div.nodata").text()}
            got_credit_list = [i for i in doc("font[color='red']").items()]
            if len(got_credit_list) == 0:
                return {"code": 1005, "msg": "板块课内容为空"}
            head_data = {"got_credit": got_credit_list[2].string}

            kklxdm_list = []
            xkkz_id_list = []
            for tab_content in doc("a[role='tab']").items():
                onclick_content = tab_content.attr("onclick")
                r = re.findall(r"'(.*?)'", str(onclick_content))
                kklxdm_list.append(r[0].strip())
                xkkz_id_list.append(r[1].strip())
            head_data["bkk1_kklxdm"] = kklxdm_list[0]
            head_data["bkk2_kklxdm"] = kklxdm_list[1]
            head_data["bkk3_kklxdm"] = kklxdm_list[2]
            head_data["bkk1_xkkz_id"] = xkkz_id_list[0]
            head_data["bkk2_xkkz_id"] = xkkz_id_list[1]
            head_data["bkk3_xkkz_id"] = xkkz_id_list[2]

            for head_data_content in doc("input[type='hidden']"):
                name = head_data_content.attr("name")
                value = head_data_content.attr("value")
                head_data[str(name)] = str(value)

            url_display = urljoin(
                self.base_url, "/xsxk/zzxkyzb_cxZzxkYzbDisplay.html?gnmkdm=N253512"
            )
            display_req_data = {
                "xkkz_id": head_data[f"bkk{block}_xkkz_id"],
                "xszxzt": "1",
                "kspage": "0",
            }
            req_display_data = self.sess.post(
                url_display,
                headers=self.headers,
                data=display_req_data,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            doc_display = pq(req_display_data.text)
            display_data = {}
            for display_data_content in doc_display("input[type='hidden']").items():
                name = display_data_content.get("name")
                value = display_data_content.get("value")
                display_data[str(name)] = str(value)
            head_data.update(display_data)

            # 获取课程列表
            url_kch = urljoin(
                self.base_url, "/xsxk/zzxkyzb_cxZzxkYzbPartDisplay.html?gnmkdm=N253512"
            )
            url_bkk = urljoin(
                self.base_url, "/xsxk/zzxkyzb_cxJxbWithKchZzxkYzb.html?gnmkdm=N253512"
            )
            term = term**2 * 3
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
                "xkxnm": str(year),
                "xkxqm": str(term),
                "kklxdm": head_data[f"bkk{block}_kklxdm"],
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
                timeout=self.timeout,
            )
            jkch_res = kch_res.json()
            bkk_data = {
                "bklx_id": head_data["bklx_id"],
                "xkxnm": str(year),
                "xkxqm": str(term),
                "xkkz_id": head_data[f"bkk{block}_xkkz_id"],
                "xqh_id": head_data["xqh_id"],
                "zyfx_id": head_data["zyfx_id"],
                "njdm_id": head_data["njdm_id"],
                "bh_id": head_data["bh_id"],
                "xbm": head_data["xbm"],
                "xslbdm": head_data["xslbdm"],
                "ccdm": head_data["ccdm"],
                "xsbj": head_data["xsbj"],
                "kklxdm": head_data[f"bkk{block}_kklxdm"],
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
                timeout=self.timeout,
            )
            jbkk_res = bkk_res.json()
            if block != 3 and (len(jkch_res["tmpList"]) != len(jbkk_res)):
                return {"code": 999, "msg": "板块课编号及长度错误"}
            temp_list = jkch_res["tmpList"]
            block_list = jbkk_res
            for i in range(len(temp_list)):
                temp_list[i].update(block_list[i])

            result = {
                "count": len(temp_list),
                "courses": [
                    {
                        "course_id": j["kch_id"],
                        "class_id": j.get("jxb_id"),
                        "do_id": j.get("do_jxb_id"),
                        "title": j.get("kcmc"),
                        "teacher_id": (re.findall(r"(.*?\d+)/", j.get("jsxx")))[0],
                        "teacher": (re.findall(r"/(.*?)/", j.get("jsxx")))[0],
                        "credit": float(j.get("xf"), 0),
                        "kklxdm": head_data[f"bkk{block}_kklxdm"],
                        "capacity": int(i.get("jxbrl", 0)),
                        "selected_number": int(i.get("yxzrs", 0)),
                        "place": self.get_place(i.get("jxdd")),
                        "time": self.get_course_time(i.get("sksj")),
                    }
                    for j in temp_list
                ],
            }
            return {"code": 1000, "msg": "获取板块课信息成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取板块课信息超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"获取板块课信息时未记录的错误：{str(e)}"}

    def select_course(
        self,
        sid: str,
        course_id: str,
        do_id: str,
        kklxdm: str,
        year: int,
        term: int,
    ):
        """选课"""
        try:
            url_select = urljoin(
                self.base_url, "/xsxk/zzxkyzb_xkBcZyZzxkYzb.html?gnmkdm=N253512"
            )
            term = term**2 * 3
            select_data = {
                "jxb_ids": do_id,
                "kch_id": course_id,
                # 'rwlx': '3',
                # 'rlkz': '0',
                # 'rlzlkz': '1',
                # 'sxbj': '1',
                # 'xxkbj': '0',
                # 'cxbj': '0',
                "qz": "0",
                # 'xkkz_id': '9B247F4EFD6291B9E055000000000001',
                "xkxnm": str(year),
                "xkxqm": str(term),
                "njdm_id": str(sid[0:2]),
                "zyh_id": str(sid[2:6]),
                "kklxdm": str(kklxdm),
                # 'xklc': '1',
            }
            req_select = self.sess.post(
                url_select,
                headers=self.headers,
                data=select_data,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_select.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_select.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            result = req_select.json()
            return {"code": 1000, "msg": "选课成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "选课超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"选课时未记录的错误：{str(e)}"}

    def cancel_course(self, do_id: str, course_id: str, year: int, term: int):
        """取消选课"""
        try:
            url_cancel = urljoin(
                self.base_url, "/xsxk/zzxkyzb_tuikBcZzxkYzb.html?gnmkdm=N253512"
            )
            term = term**2 * 3
            cancel_data = {
                "jxb_ids": do_id,
                "kch_id": course_id,
                "xkxnm": str(year),
                "xkxqm": str(term),
            }
            req_cancel = self.sess.post(
                url_cancel,
                headers=self.headers,
                data=cancel_data,
                cookies=self.cookies,
                timeout=self.timeout,
            )
            if req_cancel.status_code != 200:
                return {"code": 2333, "msg": "教务系统挂了"}
            doc = pq(req_cancel.text)
            if doc("h5").text() == "用户登录":
                return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
            result = {"status": re.findall(r"(\d+)", req_cancel.text)[0]}
            return {"code": 1000, "msg": "退课成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "选课超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "请重试，若多次失败可能是系统错误维护或需更新接口"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"选课时未记录的错误：{str(e)}"}

    # ============= utils =================

    def get_gpa(self):
        """获取GPA"""
        url = urljoin(
            self.base_url,
            "/xsxy/xsxyqk_cxXsxyqkIndex.html?gnmkdm=N105515&layout=default",
        )
        req_gpa = self.sess.get(
            url,
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.timeout,
        )
        doc = pq(req_gpa.text)
        if doc("h5").text() == "用户登录":
            return {"code": 1006, "msg": "未登录或已过期，请重新登录"}
        allc_str = [allc.text() for allc in doc("font[size='2px']").items()]
        try:
            gpa = float(allc_str[2])
            return gpa
        except Exception:
            return "init"

    def get_course_category(self, type, item):
        """根据课程号获取类别"""
        if type not in self.detail_category_type:
            return item.get("KCLBMC")
        if not item.get("KCH"):
            return None
        url = urljoin(self.base_url, f"/jxjhgl/common_cxKcJbxx.html?id={item['KCH']}")
        req_category = self.sess.get(
            url,
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.timeout,
        )
        doc = pq(req_category.text)
        ths = doc("th")
        try:
            data_list = [(th.text).strip() for th in ths]
            return data_list[6]
        except:
            return None

    @classmethod
    def encrypt_password(cls, pwd, n, e):
        """对密码base64编码"""
        message = str(pwd).encode()
        rsa_n = binascii.b2a_hex(binascii.a2b_base64(n))
        rsa_e = binascii.b2a_hex(binascii.a2b_base64(e))
        key = rsa.PublicKey(int(rsa_n, 16), int(rsa_e, 16))
        encropy_pwd = rsa.encrypt(message, key)
        result = binascii.b2a_base64(encropy_pwd)
        return result

    @classmethod
    def parse_int(cls, digits):
        if not digits:
            return None
        if not digits.isdigit():
            return digits
        return int(digits)

    @classmethod
    def align_floats(cls, floats):
        if not floats:
            return None
        if floats == "无":
            return "0.0"
        return format(float(floats), ".1f")

    @classmethod
    def display_course_time(cls, sessions):
        if not sessions:
            return None
        args = re.findall(r"(\d+)", sessions)
        start_time = cls.raspisanie[int(args[0]) + 1][0]
        end_time = cls.raspisanie[int(args[0]) + 1][1]
        return f"{start_time}~{end_time}"

    @classmethod
    def list_sessions(cls, sessions):
        if not sessions:
            return None
        args = re.findall(r"(\d+)", sessions)
        return [n for n in range(int(args[0]), int(args[1]) + 1)]

    @classmethod
    def list_weeks(cls, weeks):
        """返回课程所含周列表"""
        if not weeks:
            return None
        args = re.findall(r"[^,]+", weeks)
        week_list = []
        for item in args:
            if "-" in item:
                weeks_pair = re.findall(r"(\d+)", item)
                if len(weeks_pair) != 2:
                    continue
                if "单" in item:
                    for i in range(int(weeks_pair[0]), int(weeks_pair[1]) + 1):
                        if i % 2 == 1:
                            week_list.append(i)
                elif "双" in item:
                    for i in range(int(weeks_pair[0]), int(weeks_pair[1]) + 1):
                        if i % 2 == 0:
                            week_list.append(i)
                else:
                    for i in range(int(weeks_pair[0]), int(weeks_pair[1]) + 1):
                        week_list.append(i)
            else:
                week_num = re.findall(r"(\d+)", item)
                if len(week_num) == 1:
                    week_list.append(int(week_num[0]))
        return week_list

    @classmethod
    def get_academia_statistics(cls, display_statistics):
        display_statistics = "".join(display_statistics.split())
        gpa_list = re.findall(r"([0-9]{1,}[.][0-9]*)", display_statistics)
        if len(gpa_list) == 0 or not cls.is_number(gpa_list[0]):
            gpa = None
        else:
            gpa = float(gpa_list[0])
        plan_list = re.findall(
            r"计划总课程(\d+)门通过(\d+)门?.*未通过(\d+)门?.*未修(\d+)?.*在读(\d+)门?.*计划外?.*通过(\d+)门?.*未通过(\d+)门",
            display_statistics,
        )
        if len(plan_list) == 0 or len(plan_list[0]) < 7:
            return {"gpa": gpa}
        plan_list = plan_list[0]
        return {
            "gpa": gpa,  # 平均学分绩点GPA
            "planed_courses": {
                "total": int(plan_list[0]),  # 计划内总课程数
                "passed": int(plan_list[1]),  # 计划内已过课程数
                "failed": int(plan_list[2]),  # 计划内未过课程数
                "missed": int(plan_list[3]),  # 计划内未修课程数
                "in": int(plan_list[4]),  # 计划内在读课程数
            },
            "unplaned_courses": {
                "passed": int(plan_list[5]),  # 计划外已过课程数
                "failed": int(plan_list[6]),  # 计划外未过课程数
            },
        }

    @classmethod
    def get_academia_type_statistics(cls, content: str):
        finder = re.findall(
            r"\"(.*)&nbsp.*要求学分.*:([0-9]{1,}[.][0-9]*|0|&nbsp;).*获得学分.*:([0-9]{1,}[.][0-9]*|0|&nbsp;).*未获得学分.*:([0-9]{1,}[.][0-9]*|0|&nbsp;)[\s\S]*?<span id='showKc(.*)'></span>",
            content,
        )
        finder_list = list({}.fromkeys(finder).keys())
        academia_list = [
            list(i)
            for i in finder_list
            if i[0] != ""  # 类型名称不为空
            and len(i[0]) <= 20  # 避免正则到首部过长类型名称
            and "span" not in i[-1]  # 避免正则到尾部过长类型名称
            and i[0] not in cls.ignore_type  # 忽略的类型名称
        ]
        result = {
            i[0]: {
                "id": i[-1],
                "credits": {
                    "required": i[1] if cls.is_number(i[1]) and i[1] != "0" else None,
                    "earned": i[2] if cls.is_number(i[2]) and i[2] != "0" else None,
                    "missed": i[3] if cls.is_number(i[3]) and i[3] != "0" else None,
                },
            }
            for i in academia_list
        }
        return result

    @classmethod
    def get_display_term(cls, sid, year, term):
        """
        计算培养方案具体学期转化成中文
        note: 留级和当兵等情况会不准确
        """
        if (sid and year and term) is None:
            return None
        grade = int(sid[0:2])
        year = int(year[2:4])
        term = int(term)
        dict = {
            grade: "大一上" if term == 1 else "大一下",
            grade + 1: "大二上" if term == 1 else "大二下",
            grade + 2: "大三上" if term == 1 else "大三下",
            grade + 3: "大四上" if term == 1 else "大四下",
        }
        return dict.get(year)

    @classmethod
    def split_merge_display(cls, schedule):
        """
        拆分同周同天同课程不同时段数据合并的问题
        """
        repetIndex = []
        count = 0
        for items in schedule["courses"]:
            for index in range(len(schedule["courses"])):
                if (schedule["courses"]).index(items) == count:  # 如果对比到自己就忽略
                    continue
                elif (
                    items["course_id"]
                    == schedule["courses"][index]["course_id"]  # 同周同天同课程
                    and items["weekday"] == schedule["courses"][index]["weekday"]
                    and items["weeks"] == schedule["courses"][index]["weeks"]
                ):
                    repetIndex.append(index)  # 满足条件记录索引
            count += 1  # 记录当前对比课程的索引
        if len(repetIndex) % 2 != 0:  # 暂时考虑一天两个时段上同一门课，不满足条件不进行修改
            return schedule
        for r in range(0, len(repetIndex), 2):  # 索引数组两两成对，故步进2循环
            fir = repetIndex[r]
            sec = repetIndex[r + 1]
            if len(re.findall(r"(\d+)", schedule["courses"][fir]["sessions"])) == 4:
                schedule["courses"][fir]["sessions"] = (
                    re.findall(r"(\d+)", schedule["courses"][fir]["sessions"])[0]
                    + "-"
                    + re.findall(r"(\d+)", schedule["courses"][fir]["sessions"])[1]
                    + "节"
                )
                schedule["courses"][fir]["list_sessions"] = cls.list_sessions(
                    schedule["courses"][fir]["sessions"]
                )
                schedule["courses"][fir]["time"] = cls.display_course_time(
                    schedule["courses"][fir]["sessions"]
                )

                schedule["courses"][sec]["sessions"] = (
                    re.findall(r"(\d+)", schedule["courses"][sec]["sessions"])[2]
                    + "-"
                    + re.findall(r"(\d+)", schedule["courses"][sec]["sessions"])[3]
                    + "节"
                )
                schedule["courses"][sec]["list_sessions"] = cls.list_sessions(
                    schedule["courses"][sec]["sessions"]
                )
                schedule["courses"][sec]["time"] = cls.display_course_time(
                    schedule["courses"][sec]["sessions"]
                )
        return schedule

    @classmethod
    def split_notifications(cls, item):
        if not item.get("xxnr"):
            return {"type": None, "content": None}
        content_list = re.findall(r"(.*):(.*)", item["xxnr"])
        if len(content_list) == 0:
            return {"type": None, "content": item["xxnr"]}
        return {"type": content_list[0][0], "content": content_list[0][1]}

    @classmethod
    def get_place(cls, place):
        return place.split("<br/>")[0] if "<br/>" in place else place

    @classmethod
    def get_course_time(cls, time):
        return "、".join(time.split("<br/>")) if "<br/>" in time else time

    @classmethod
    def is_number(cls, s):
        if s == "":
            return False
        try:
            float(s)
            return True
        except ValueError:
            pass
        try:
            for i in s:
                unicodedata.numeric(i)
            return True
        except (TypeError, ValueError):
            pass
        return False
