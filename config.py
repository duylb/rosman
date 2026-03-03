import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    APP_VERSION = "v26.02"
    APP_AUTHOR = "DuyLB"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
