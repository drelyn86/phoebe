import json
from os import path
from null import Null

class LocalStorage(dict):
    def __init__(self, storage_path, logger=Null()):
        self.logger = logger
        self.log = self.logger.getLogger('phoebe.local_storage.LocalStorage')
        self.log.debug('LocalStorage object initialized: %s' % storage_path)
        self.storage_path = storage_path
        if path.isfile(storage_path):
            self.log.info('Loading existing file: %s' % storage_path)
            self.load()
        else:
            self.log.info('Saving new file: %s' % storage_path)
            self.storage = {}
            self.save()

    def load(self):
        self.log.info('Loading file: %s' % self.storage_path)
        storage_file = open(self.storage_path, 'r')
        self.storage = json.load(storage_file)
        storage_file.close()

    def save(self):
        self.log.info('Saving file: %s' % self.storage_path)
        storage_file = open(self.storage_path, 'w')
        json.dump(self.storage, storage_file)
        storage_file.close()

    def __getitem__(self, key):
        self.load()
        return self.storage[key]

    def __setitem__(self, key, value):
        self.storage[key] = value
        self.save()

    def __delitem__(self, key):
        del self.storage[key]
        self.save()

    def __repr__(self):
        self.load()
        return self.storage.__repr__()

    def keys(self):
        self.load()
        return self.storage.keys()

    def values(self):
        self.load()
        return self.storage.values()

    def items(self):
        self.load()
        return self.storage.items()

    def get(self, key):
        return self.storage.get(key)
