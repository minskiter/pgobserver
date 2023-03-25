import platform
import configparser
import argparse
import os
import psutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime
import time
import multiprocessing

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(
    "{}.log".format(datetime.now().strftime("%y-%m-%d")))
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s : %(filename)s:%(lineno)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_os():
    version = platform.platform()
    if version.lower().find("linux") != -1:
        return "linux"
    else:
        return None


def load_config(path: str):
    if not os.path.exists(path):
        exit(1)
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    email = dict(parser.items("email"))
    return email


def get_program_status(pid: int):
    if psutil.pid_exists(pid):
        process = psutil.Process(pid)
        logger.info("获取了进程[{}] {} 的状态{},已运行{}s".format(pid, process.name(), process.status(), int(
            datetime.now().timestamp()-process.create_time()), " ".join(process.cmdline())))
        return process.name(), process.status(), process.cpu_times(), process.create_time(), process.cmdline()
    logger.info("进程[{}]当前不存在".format(pid))
    return None


def send_email_notify(server, port, username, password, emails, subject, message):
    from_addr = username
    to_addr = emails

    # 邮件服务器的地址和端口，使用SSL加密连接
    smtp_server = server
    smtp_port = port

    # 发件人的邮箱账号和密码
    username = username.strip()
    password = password.strip()

    # 邮件主题和正文
    subject = subject
    body = message

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", 'utf-8'))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as conn:
            logger.info("通知邮件发送 {}, {}".format(to_addr, msg.as_string()))
            conn.login(username, password)
            conn.sendmail(from_addr, to_addr, msg.as_string())
            return True
    except smtplib.SMTPException as e:
        print(e)
        return False


def background_service(args, email, stop_event=None):
    try:
        while not stop_event.is_set():
            status = get_program_status(args.pid)
            if status is None:
                send_email_notify(email["server"], email["port"], email["username"],
                                  email["password"], email["emails"], "进程 {} 执行结束".format(args.pid), "监控结束")
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    if get_os() != 'linux':
        logger.error("{} platform couldn't support!".format(get_os()))
        exit(1)
    parser = argparse.ArgumentParser(
        prog="PGObserver",
        description="Send Notificaion When Program was finished."
    )
    parser.add_argument("-c", "--config", default="config.ini")
    parser.add_argument("-p", "--pid", required=True, type=int)
    parser.add_argument("-d", default=False, action='store_true')
    parser.add_argument("-i", "--interval", default=2, type=int)
    args = parser.parse_args()
    email = load_config(args.config)
    logger.info("启动程序: 参数{}".format(args))
    if not args.d:
        status = get_program_status(args.pid)
        if status is None:
            send_email_notify(email["server"], email["port"], email["username"],
                              email["password"], email["emails"], "进程 {} 执行结束".format(args.pid), "监控结束")
    else:
        event = multiprocessing.Event()
        try:
            daemon = multiprocessing.Process(
                target=background_service, args=(args, email, event))
            daemon.daemon = True
            daemon.start()
            daemon.join()
        except KeyboardInterrupt:
            logger.info("退出监听")
            event.set()
