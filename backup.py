import os
import logging
import schedule
import time

from config import BACKUP_REPO_PATH, DATA_DIR

logger = logging.getLogger(__name__)


def backup():
    if not BACKUP_REPO_PATH:
        logger.warning("BACKUP_REPO_PATH не задан, бэкап пропущен")
        return

    os.system(f'cp -r "{DATA_DIR}/." "{BACKUP_REPO_PATH}"')
    os.system(
        f'cd "{BACKUP_REPO_PATH}" && git add . && git commit -m "auto backup" && git push'
    )
    logger.info("Бэкап выполнен")


def run_scheduler():
    schedule.every().day.at("03:00").do(backup)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_scheduler()
