import argparse
import json
from mailer import send_mail
from monitor import run_once, collect_status
import storage

def main():
    parser = argparse.ArgumentParser(description="GCP Watchdog")
    parser.add_argument("--once", action="store_true", help="run one check")
    parser.add_argument("--status", action="store_true", help="print current status without alerts")
    parser.add_argument("--test-mail", action="store_true", help="send test mail")
    args = parser.parse_args()

    storage.init_db()

    if args.test_mail:
        send_mail("GCP Watchdog 测试邮件", "如果你收到这封邮件，说明 QQ SMTP 发信成功。")
        print("mail sent")
        return

    if args.status:
        print(json.dumps(collect_status(), ensure_ascii=False, indent=2))
        return

    if args.once:
        data = run_once()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    parser.print_help()

if __name__ == "__main__":
    main()
