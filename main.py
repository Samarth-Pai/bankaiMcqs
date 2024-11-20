# Jai
from flask import Flask, request, redirect, render_template, session, url_for
from flask_pymongo import MongoClient, ObjectId
from dotenv import load_dotenv
from datetime import datetime, timedelta, UTC
import os, re, random, asyncio, aiosmtplib
load_dotenv()

app =   Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET_KEY")

client = MongoClient(os.getenv("CONNECTION_STRING"))
db = client["mcqDB"]
users = db["usersLogin"]
subjectsDB = db["subjects"]
extraDB = db["extras"]
questionss = []
class otpModel():
    otpMode: bool = False
    name: str = ""
    emailId: str =  ""
    password: str = ""
    code: str = ""
otpObj = otpModel()

def authorized():
    return bool(session.get("emailId"))

@app.route("/")
def root():
    if authorized():
        return redirect("/subjects")
    return render_template("welcomePage.html")

@app.route("/subjects")
def subjects():
    if not authorized():
        return redirect("/login")
    print(session["emailId"])
    firstYears = subjectsDB.find({"year": 1, "visible": True})
    secondYears = subjectsDB.find({"year": 2, "visible": True})
    thirdYears = subjectsDB.find({"year": 3, "visible": True})
    fourthYears = subjectsDB.find({"year": 4, "visible": True})
    extraDicts = extraDB.find({"visible": True})
    return render_template("subjects.html", name = session["name"], firstYears = firstYears, secondYears = secondYears, thirdYears = thirdYears, fourthYears = fourthYears, extraDicts = extraDicts, pageTitle = "Subjects", preferredTheme = session["preferredTheme"])

@app.route("/login", methods = ["GET", "POST"])
def login():
    if request.method=="POST":
        emailId = request.form.get("emailId")
        password = request.form.get("password")
        print(emailId, password, "one sec")
        res = users.find_one({"emailId": emailId, "password": password})
        print("Res is ", res)
        if res:
            print("requesting")
            session["emailId"] = emailId
            session["name"] = res["name"]
            session["preferredTheme"] = res["preferredTheme"]
            return redirect("/subjects")
        return render_template("loginInvalid.html")
    
    return render_template("loginPg.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

async def mailer(to,subject,msg):
    sender = os.getenv("EMAIL_SENDER")
    mailserver = os.getenv("EMAIL_SERVER")
    s = aiosmtplib.SMTP(hostname=mailserver, port=587)
    print("Connecting...")
    await s.connect()
    print("Logging in...")
    await s.login(sender, os.getenv("SMTP_PASSW"))
    print("Login successfull.")
    print("Sending email..")
    await s.sendmail(sender,to,f"Subject: {subject}\nTo: {to}\nFrom: {sender}\n\n{msg}")
    print("Mail sent successfully")
    
async def mailDriver(to, subject, msg):
    await mailer(to, subject, msg)

@app.route("/signup", methods = ["GET", "POST"])
def signup():
    if request.method=="POST":
        name = request.form.get("name")
        emailId = request.form.get("emailId")
        password = request.form.get("password")
        confirmPassword = request.form.get("confirmPassword")
        if not all([name, emailId, password, confirmPassword]):
            return render_template("signupNoBlank.html", name=name, emailId = emailId, password = password, confirmPassword = confirmPassword)
        elif users.find_one({"emailId": emailId}):
            return render_template("signupUserExists.html", name=name, emailId = emailId, password = password, confirmPassword = confirmPassword)
        elif not re.fullmatch(r"(?=.*\w)(?=.*\d)(?=.*\W).{8,}", password) :
            return render_template("signupPasswordWeak.html", name=name, emailId = emailId, password = password, confirmPassword = confirmPassword)
        elif password!=confirmPassword:
            return render_template("signupPasswordNotSame.html", name=name, emailId = emailId, password = password, confirmPassword = confirmPassword)
        
        print("Async await mode..")
        otpObj.otpMode = True
        otpObj.name = name
        otpObj.emailId = emailId
        otpObj.password = password
        otpObj.code = str(random.randrange(100000, 1000000))
        asyncio.run(mailDriver(otpObj.emailId, "Bankai MCQs Email Verification", f"Your OTP for Bankai MCQs web application is {otpObj.code}"))
        
        return redirect("/otp")
    return render_template("signupPg.html")

@app.route("/otp", methods = ["GET", "POST"])
def otp():
    if not otpObj.otpMode:
        return redirect("/login")
    
    if request.method == "POST":
        if request.form.get("otpPin").strip()!=otpObj.code:
            print(otpObj.code, request.form.get("otpPin"))
            return render_template("otpInvalid.html", **session, pageTitle = "Senkaimon 2FA", otpEmailId = otpObj.emailId)
        
        otpObj.mode = False
        dt = datetime.now(UTC) + timedelta(hours= 5, minutes = 30)
        
        users.insert_one({
            "name": otpObj.name,
            "emailId": otpObj.emailId,
            "password": otpObj.password,
            "accountCreated": dt,
            "preferredTheme": "default",
            "history": []
        })
        
        session["name"] = otpObj.name
        session["emailId"] = otpObj.emailId
        session["preferredTheme"] = "default"
        
        return redirect("/subjects")
        
    return render_template("otp.html", **session, pageTitle = "Senkaimon 2FA", otpEmailId = otpObj.emailId)
    

def randomizeOptions(questionDict: dict):
    optionA, optionB, optionC, optionD = questionDict["optionA"], questionDict["optionB"], questionDict["optionC"], questionDict["optionD"]
    randomOptions = random.sample([optionA, optionB, optionC, optionD], 4)
    correctOption = [optionA, optionB, optionC, optionD]["ABCD".index(questionDict["answer"])]
    answer = "ABCD"[randomOptions.index(correctOption)]
    questionDict["optionA"], questionDict["optionB"], questionDict["optionC"], questionDict["optionD"] = randomOptions
    questionDict["answer"] = answer
    return questionDict
    
def addLists(*l):
    res = []
    for listt in l:
        res.extend(listt)
    return res

def randomizeQuestions(courseCode, mode):
    questions = []
    if mode=="SEE":
        mse1q, mse2q, seeq = list(db[f"{courseCode}/MSE1"].find({})), list(db[f"{courseCode}/MSE2"].find({})), list(db[f"{courseCode}/SEE"].find({}))
        # questions = list(mse1q[:10]) + list(mse2q[:10]) + list(seeq[:10])
        questions = list(map(randomizeOptions, random.sample(random.sample(list(mse1q), 10) + random.sample(list(mse2q), 10) + random.sample(list(seeq), 10), 30)))
        
    else:
        questions = db[f"{courseCode}/{mode}"].find({})
        questions = list(map(randomizeOptions, random.sample(list(questions), 20)))
    return questions

@app.route("/quiz/<courseCode>/<mode>", methods = ["GET", "POST"])
def quiz(courseCode: str, mode: str):
    if not authorized():
        return redirect("/login")
    global questionss
    if request.method=="POST":
        if ((mode.startswith("MSE") or mode=="QUESTIONS") and len(request.form)<20) or (mode=="SEE" and len(request.form)<30):
            print(request.form, len(request.form))
            return render_template("quizNotCompleted.html", **session, pageTitle = "Quiz", courseCode = courseCode, mode = mode, questions = enumerate(questionss, 1), attemptedQuestions = {ObjectId(k):v for k, v in request.form.items()})
        points = 0
        history: list = users.find_one({"emailId": session["emailId"]})["history"]
        dt = datetime.now(UTC) + timedelta(hours= 5, minutes= 30)
        sessionDetails = {
            "courseTitle":  extraDB.find_one({"courseCode": courseCode})["courseTitle"] if mode=="QUESTIONS" else subjectsDB.find_one({"courseCode": courseCode})["courseTitle"],
            "courseCode": courseCode,
            "mode": mode,
            "maxi": 20 if mode.startswith("MSE") or mode=="QUESTIONS" else 30,
            "dateAttempted": dt,
        }
        
        requestedForm = {ObjectId(k):v for k, v in request.form.items()}
        for question in questionss:
            question["attemptedAnswer"] = requestedForm[question["_id"]]
            points+=question["answer"]==question["attemptedAnswer"]
        sessionDetails["sessionQuestions"] = questionss
        sessionDetails["points"] = points
        history.append(sessionDetails)
        users.find_one_and_update({"emailId": session["emailId"]}, {"$set": {"history": history}})
        return redirect("/progress/last")
    
    questions = randomizeQuestions(courseCode, mode)
    questionss = questions.copy()
    return render_template("quiz.html", **session, pageTitle = "Quiz", courseCode = courseCode, mode = mode, questions = enumerate(questions, 1), attemptedQuestions = {})

@app.route("/progress/<index>")
def progress(index: str):
    if not authorized():
        return redirect("/login")
    sessionDetails = users.find_one({"emailId": session["emailId"]})["history"][-1 if index=="last" else int(index)]
    return render_template("progress.html", **session, pageTitle = "Progress report", **sessionDetails, questions = enumerate(sessionDetails["sessionQuestions"], 1))

@app.route("/attempts")
def attempts():
    if not authorized():
        return redirect("/login")
    history = users.find_one({"emailId": session["emailId"]})["history"]
    return render_template("attempts.html", **session, pageTitle = "Attempt history", history = list(enumerate(history))[::-1])

@app.route("/themes")
def themes():
    if not authorized():
        return redirect("/login")
    print("Current theme: ", session["preferredTheme"])
    return render_template("themes.html", **session)

@app.route("/settheme/<themeName>")
def settheme(themeName: str):
    if not authorized():
        return redirect("/login")
    session["preferredTheme"] = themeName
    users.find_one_and_update({"emailId": session["emailId"]}, {"$set": {"preferredTheme": themeName}})
    return redirect("/themes")

@app.route("/account", methods = ["POST", "GET"])
def account():
    if not authorized():
        return redirect("/login")
    if request.method=="POST":
        name = request.form.get("name").strip()
        currentPassword = request.form.get("currentPassword")
        newPassword = request.form.get("newPassword")
        if not all([name, currentPassword, newPassword]):
            return render_template("dontLeaveBlank.html", **session, pageTitle = f"{session["name"]}'s account")
        elif currentPassword!=users.find_one({"emailId": session["emailId"]})["password"]:
            return render_template("cantApply.html", **session, pageTitle = f"{session["name"]}'s account")
        elif not re.fullmatch(r"(?=.*\w)(?=.*\d)(?=.*\W).{8,}", newPassword):
            return render_template("passwordCriteria.html", **session, pageTitle = f"{session["name"]}'s account")
        else:
            session["name"] = name
            users.find_one_and_update({"emailId": session["emailId"]}, {"$set": {"name": name, "password": newPassword}})
            return render_template("successfullyApplied.html", **session, pageTitle = f"{name}'s account")
    else:
        return render_template("account.html", **session, pageTitle = f"{session["name"]}'s account")


if __name__=="__main__":
    app.run(debug=True)