import boto3
import os
from botocore import UNSIGNED
from botocore.client import Config

BUCKET_NAME = "argoverse-datasets"
S3_KEY = "av2/tars/motion-forecasting/val.tar.zst"
LOCAL_PATH = "data/raw/val.tar.zst"


def download_av2_data():
    print(f"Начинаю загрузку {S3_KEY} (~4.5 ГБ)...")

    s3_client = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    os.makedirs(os.path.dirname(LOCAL_PATH), exist_ok=True)

    print("Загрузка может занять 5-15 минут. Не закрывай терминал.")
    s3_client.download_file(BUCKET_NAME, S3_KEY, LOCAL_PATH)
    print(f"✅ Успешно сохранено в: {os.path.abspath(LOCAL_PATH)}")


if __name__ == "__main__":
    download_av2_data()