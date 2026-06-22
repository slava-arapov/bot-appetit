import asyncio
import shutil
import sys
import logging
import subprocess
import schedule
import time

from telegram import Bot
from telegram.error import TelegramError

from config import ADMIN_USER_ID, BACKUP_REPO_PATH, DATA_DIR, TELEGRAM_TOKEN

logger = logging.getLogger(__name__)


def _git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=BACKUP_REPO_PATH,
        capture_output=True,
        text=True,
    )


def _notify_admin(text: str):
    try:
        asyncio.run(Bot(token=TELEGRAM_TOKEN).send_message(chat_id=ADMIN_USER_ID, text=text))
    except TelegramError:
        logger.exception("Не удалось отправить админу уведомление об ошибке бэкапа")


def _fail(message: str):
    logger.error(message)
    _notify_admin(f"⚠️ Бэкап bot-appetit не выполнен: {message}")


def backup():
    if not BACKUP_REPO_PATH:
        logger.warning("BACKUP_REPO_PATH не задан, бэкап пропущен")
        return

    try:
        # сначала синхронизируемся с remote — иначе push может быть отклонён,
        # а локальный коммит (если есть с прошлого неудачного запуска) зависнет навсегда
        pull = _git("pull", "--rebase", "--autostash")
        if pull.returncode != 0:
            _git("rebase", "--abort")
            _fail(f"git pull --rebase не выполнен (конфликт?): {pull.stderr.strip()}")
            return

        shutil.copytree(DATA_DIR, BACKUP_REPO_PATH, dirs_exist_ok=True)

        add = _git("add", "-A")
        if add.returncode != 0:
            _fail(f"git add не выполнен: {add.stderr.strip()}")
            return

        diff = _git("diff", "--cached", "--quiet")
        if diff.returncode != 0:
            commit = _git("commit", "-m", "auto backup")
            if commit.returncode != 0:
                _fail(f"git commit не выполнен: {commit.stderr.strip()}")
                return
        else:
            logger.info("Бэкап: новых изменений в данных нет")

        ahead = _git("rev-list", "--count", "@{u}..HEAD")
        if ahead.returncode == 0 and ahead.stdout.strip() == "0":
            logger.info("Бэкап: всё синхронизировано, push не требуется")
            return

        push = _git("push")
        if push.returncode != 0:
            _fail(f"git push не выполнен: {push.stderr.strip()}")
            return

        logger.info("Бэкап выполнен")
    except Exception as e:
        _fail(f"непредвиденная ошибка: {e}")


def run_scheduler():
    schedule.every().day.at("03:00").do(backup)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if "--now" in sys.argv:
        backup()
    else:
        run_scheduler()
