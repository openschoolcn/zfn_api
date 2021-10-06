## 个人信息（登录）

```json
{
    "name": "学生姓名",
    "studentId": "学生学号",
    "birthDay": "出生日期",
    "idNumber": "身份证号码",
    "candidateNumber": "考生号",
    "status": "在读情况",
    "collegeName": "所在院系",
    "majorName": "所在专业",
    "className": "所在班级",
    "entryDate": "入学时间",
    "graduationSchool": "毕业高中",
    "domicile": "籍贯",
    "phoneNumber": "电话号码",
    "parentsNumber": "家长号码",
    "email": "电子邮箱",
    "politicalStatus": "政治面貌",
    "national": "民族",
    "education": "学历",
    "postalCode": "邮编",
    "grade": "年级"
}
```

## 学业情况

```json
{
    "gpa":"平均学分绩点GPA",
    "ipa":"计划内总课程数",
    "ipp":"计划内已过课程数",
    "ipf":"计划内未过课程数",
    "ipn":"计划内未修课程数",
    "ipi":"计划内在读课程数",
    "opp":"计划外已过课程数",
    "opf":"计划外未过课程数",
    "tsData":{
        "tsPoint":{
            "tsr":"通识教育要求学分",
            "tsg":"通识教育已得学分",
            "tsn":"通识教育未得学分",
        },
        "tsItems":[{
            "courseTitle":"课程名程",
            "courseId":"课程号",
            "courseSituation":"修读状态",
            "courseTerm":"修读学期",
            "courseCategory": "课程类别",
            "courseAttribution": "课程性质",
            "maxGrade":"最高成绩",
            "credit":"课程学分",
            "gradePoint":"课程绩点",
        }],
        },
    "tzData":{
        "tzPoint":{
            "tzr":"拓展教育要求学分",
            "tzg":"拓展教育已得学分",
            "tzn":"拓展教育未得学分",
        },
        "tzItems":[{
            "courseTitle":"课程名程",
            "courseId":"课程号",
            "courseSituation":"修读状态",
            "courseTerm":"修读学期",
            "courseCategory": "课程类别",
            "courseAttribution": "课程性质",
            "maxGrade":"最高成绩",
            "credit":"课程学分",
            "gradePoint":"课程绩点",
        }],
        },
    "zyData":{
        "zyPoint":{
            "zyr":"专业教育要求学分",
            "zyg":"专业教育已得学分",
            "zyn":"专业教育未得学分",
        },
        "zyItems":[{
            "courseTitle":"课程名程",
            "courseId":"课程号",
            "courseSituation":"修读状态",
            "courseTerm":"修读学期",
            "courseCategory": "课程类别",
            "courseAttribution": "课程性质",
            "maxGrade":"最高成绩",
            "credit":"课程学分",
            "gradePoint":"课程绩点",
        }],
        },
    "qtData":{
        "qtPoint":"{其它课程一般无学分要求}",
        "qtItems":[{
            "courseTitle":"课程名程",
            "courseId":"课程号",
            "courseSituation":"修读状态",
            "courseTerm":"修读学期",
            "courseCategory": "课程类别",
            "courseAttribution": "课程性质",
            "maxGrade":"最高成绩",
            "credit":"课程学分",
            "gradePoint":"课程绩点",
        }],
        },
}
```

## 停补课消息

```json
[
    {
        "message": "消息内容", 
        "ctime": "消息创建时间"
    }
]
```

## 成绩信息

```json
{
    "name": "学生姓名",
    "studentId": "学生学号",
    "schoolYear": "查询学年",
    "schoolTerm": "查询学期",
    "course": [{
        "courseTitle": "课程名程",
        "teacher": "课程老师",
        "courseId": "课程号",
        "className": "教学班名称",
        "courseNature": "课程性质",
        "credit": "课程学分",
        "grade": "课程成绩",
        "gradePoint": "课程绩点",
        "gradeNature": "考试性质",
        "startCollege": "授课院系",
        "courseMark": "主/选修",
        "courseCategory": "课程类别",
        "courseAttribution": "课程方向"
    }]
}
```

## 课表信息
```json
{
    "name": "学生姓名",
    "studentId": "学生学号",
    "schoolYear": "查询学年",
    "schoolTerm": "查询学期",
    "normalCourse": [{
        "courseTitle": "课程名程",
        "courseTitleShort":"课程短名称(超过x个字符显示省略号)",
        "teacher": "课程老师",
        "courseId": "课程号",
        "courseWeekday":"星期几",
        "courseSection": "课程节数",
        "includeSection": "该课程所在节数列表",
        "upTime": "课程上课时间",
        "courseTime":"课程时间",
        "courseWeek": "课程周数",
        "includeWeeks":"该课程所在周数列表",
        "exam":"考试性质",
        "campus": "上课校区",
        "courseRoom": "上课地点",
        "className": "教学班名称",
        "hoursComposition": "学时",
        "weeklyHours": "周学时",
        "totalHours": "总学时",
        "credit": "课程学分"
    }],
}
```

## 已选课程

```json
{
    "courseNumber":"已选课程数",
    "items":[{
        "courseTitle":"课程名程",
        "courseCategory":"课程类别",
        "teacher":"课程老师",
        "teacher_id":"老师ID",
        "classId":"教学班ID",
        "classVolume":"教学班容量",
        "classPeople":"教学班已选人数",
        "courseRoom":"上课地点",
        "courseId":"课程号",
        "doId":"执行ID",
        "courseTime":"上课时间",
        "credit":"课程学分",
        "chooseSelf":"是否自选",
        "waiting":"是否待筛选"
        }]
}
```

## 板块课列表

```json
{
    "courseNumber":"教学班数量",
    "items":[{
        "courseTitle":"课程名程",
        "teacher":"课程老师",
        "teacher_id":"老师ID",
        "classId":"教学班ID",
        "doId":"执行ID",
        "kklxdm":"板块课1/2的特有ID",
        "classVolume":"教学班容量",
        "classPeople":"教学班已选人数",
        "courseRoom":"上课地点",
        "courseId":"课程号",
        "courseTime":"上课时间",
        "credit":"课程学分"
        }]
}
```