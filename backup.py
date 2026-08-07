import asyncio
import gzip
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import date

import schedule
from telegram import Bot
from telegram.error import TelegramError

from config import (
    ADMIN_USER_ID,
    BACKUP_BACKEND,
    BACKUP_REPO_PATH,
    BACKUP_RETENTION_DAYS,
    DB_PATH,
    S3_BUCKET,
    S3_ENDPOINT_URL,
    S3_PREFIX,
    SNAPSHOT_DIR,
    TELEGRAM_TOKEN,
)

logger = logging.getLogger(__name__)


def _notify_admin(text: str):
    try:
        asyncio.run(Bot(token=TELEGRAM_TOKEN).send_message(chat_id=ADMIN_USER_ID, text=text))
    except TelegramError:
        logger.exception("Не удалось отправить админу уведомление об ошибке бэкапа")


def _fail(message: str):
    logger.error(message)
    _notify_admin(f"⚠️ Бэкап bot-appetit не выполнен: {message}")


def _snapshot() -> str:
    """Делает консистентный снапшот БД через VACUUM INTO, сжимает gzip'ом, ротирует старые."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    raw_path = os.path.join(SNAPSHOT_DIR, f"bot-{date.today().isoformat()}.db")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("VACUUM INTO ?", (raw_path,))
    finally:
        conn.close()

    gz_path = raw_path + ".gz"
    with open(raw_path, "rb") as src, gzip.open(gz_path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    os.remove(raw_path)

    snapshots = sorted(
        (f for f in os.listdir(SNAPSHOT_DIR) if f.startswith("bot-") and f.endswith(".db.gz")),
        reverse=True,
    )
    for old in snapshots[BACKUP_RETENTION_DAYS:]:
        os.remove(os.path.join(SNAPSHOT_DIR, old))

    return gz_path


def _backup_s3(snapshot_path: str):
    import boto3
    from botocore.config import Config

    if not S3_BUCKET:
        _fail("S3_BUCKET не задан")
        return

    # S3-совместимые хранилища не-AWS требуют явный endpoint_url и path-style
    # адресацию (virtual-hosted style bucket.endpoint там не работает), а также
    # отключения новых дефолтных контрольных сумм запроса/ответа в boto3 —
    # иначе PutObject падает с XAmzContentSHA256Mismatch (сторонние S3-провайдеры
    # это расширение не поддерживают).
    client_kwargs = {}
    if S3_ENDPOINT_URL:
        client_kwargs["endpoint_url"] = S3_ENDPOINT_URL
        client_kwargs["config"] = Config(
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        )

    s3 = boto3.client("s3", **client_kwargs)
    key = f"{S3_PREFIX}/{os.path.basename(snapshot_path)}"
    s3.upload_file(snapshot_path, S3_BUCKET, key)

    objects = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=f"{S3_PREFIX}/").get("Contents", [])
    objects.sort(key=lambda o: o["LastModified"], reverse=True)
    for obj in objects[BACKUP_RETENTION_DAYS:]:
        s3.delete_object(Bucket=S3_BUCKET, Key=obj["Key"])

    logger.info("Бэкап загружен в s3://%s/%s", S3_BUCKET, key)


def _git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=BACKUP_REPO_PATH,
        capture_output=True,
        text=True,
    )


def _backup_git(snapshot_path: str):
    if not BACKUP_REPO_PATH:
        _fail("BACKUP_REPO_PATH не задан")
        return

    # сначала синхронизируемся с remote — иначе push может быть отклонён,
    # а локальный коммит (если есть с прошлого неудачного запуска) зависнет навсегда
    pull = _git("pull", "--rebase", "--autostash")
    if pull.returncode != 0:
        _git("rebase", "--abort")
        _fail(f"git pull --rebase не выполнен (конфликт?): {pull.stderr.strip()}")
        return

    # один и тот же файл каждый день — не накапливаем историю бинарников в репозитории
    dest = os.path.join(BACKUP_REPO_PATH, "bot.db.gz")
    shutil.copyfile(snapshot_path, dest)

    add = _git("add", "-A")
    if add.returncode != 0:
        _fail(f"git add не выполнен: {add.stderr.strip()}")
        return

    diff = _git("diff", "--cached", "--quiet")
    if diff.returncode != 0:
        commit = _git("commit", "-m", f"auto backup {date.today().isoformat()}")
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

    logger.info("Бэкап запушен в %s", BACKUP_REPO_PATH)


_BACKENDS = {
    "s3": _backup_s3,
    "git": _backup_git,
}


def backup():
    backend = _BACKENDS.get(BACKUP_BACKEND)
    if backend is None:
        logger.warning("Неизвестный BACKUP_BACKEND=%s, бэкап пропущен", BACKUP_BACKEND)
        return

    try:
        snapshot_path = _snapshot()
        backend(snapshot_path)
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
