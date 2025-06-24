from commons.models import Singleton


class Cache(Singleton):
    __collection = {}

    def push(self, key, value):
        self.__collection[key] = value

    def pull(self, key):
        return self.__collection.get(key, None)

    def remove(self, key):
        if key in self.__collection:
            del self.__collection[key]

    def clear(self):
        self.__collection.clear()

    def __str__(self):
        return str(self.__collection)
