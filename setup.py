
from setuptools import setup, find_packages  # Импортируем функции из setuptools

setup(
    name="ecommerce_etl",  # Название пакета
    version="0.1.0",  # Версия
    packages=find_packages(where="src"),  # Автоматически найти все пакеты в папке src
    package_dir={"": "src"},  # Указать, что исходники лежат в папке src
    python_requires=">=3.9",  # Требование к версии Python
)