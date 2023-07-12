import pymongo

from os import environ
from logging import getLogger

logger = getLogger(__name__)


class MetaData_Factory:
    def db(self, name):
        """
        Factory methode to provide access to the specified database,
        Note: in case the requested database does not exist, a new one is created
        """
        #return MongoDB().db(name)
        return MongoDB_Singleton().db(name)
    
    def client(self):
        return MongoDB_Singleton().client()


class MongoDB_Singleton:
    """
    Singleton wrapper for accessing the mongo database
    """

    _instance = None
    _mongo_client = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating singleton wrapper for MongoDB")
            cls._instance = super(MongoDB_Singleton, cls).__new__(cls)
            # initialisation
            __db_host__ = "localhost"
            if environ.get("MONGODB_HOST") is not None:
                __db_host__ = environ.get("MONGODB_HOST")
                logger.debug("using %s to connecto mongodb" % __db_host__)
            db_url = f"mongodb://{__db_host__}:27017/"

            cls._mongo_client = pymongo.MongoClient(db_url)
            try:
                cls._mongo_client.server_info()
            except pymongo.errors.ServerSelectionTimeoutError:
                raise RuntimeError("Mongo instance not reachable.")

        return cls._instance

    def db(self, name: str):
        db = self._mongo_client[name]
        return db
    
    def client(self):
        return self._mongo_client

class MongoDB:

    def __init__(self) -> None:
        logger.info("Creating wrapper for MongoDB")
        # initialisation
        __db_host__ = "localhost"
        if environ.get("MONGODB_HOST") is not None:
            __db_host__ = environ.get("MONGODB_HOST")
            logger.debug("using %s to connecto mongodb" % __db_host__)
        db_url = f"mongodb://{__db_host__}:27017/"

        self._mongo_client = pymongo.MongoClient(db_url)
        try:
            self._mongo_client.server_info()
        except pymongo.errors.ServerSelectionTimeoutError:
            exit("Mongo instance not reachable.")

    def db(self, name: str):
        db = self._mongo_client[name]
        return db
    
    def client(self):
        return self._mongo_client
