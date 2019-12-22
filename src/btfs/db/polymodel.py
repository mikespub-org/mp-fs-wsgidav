import logging

from .. import db

_CLASS_KEY_PROPERTY = "class"


class PolyModel(db.Model):
    def _init_entity(self, **kwargs):
        if _CLASS_KEY_PROPERTY not in kwargs:
            # kwargs[_CLASS_KEY_PROPERTY] = [type(self).__name__]
            parents = []
            for parent in type(self).__mro__:
                if parent.__name__ == "PolyModel":
                    break
                parents.append(parent.__name__)
            kwargs[_CLASS_KEY_PROPERTY] = list(reversed(parents))
        super(PolyModel, self)._init_entity(**kwargs)

    @classmethod
    def from_entity(cls, entity):
        # keep it simple and stick to the last piece of the class key here
        if _CLASS_KEY_PROPERTY in entity:
            class_name = entity[_CLASS_KEY_PROPERTY][-1]
            if class_name in db._class_map:
                return db._class_map[class_name](_from_entity=entity)
            logging.error("Invalid class_name %s" % class_name)
        return cls(_from_entity=entity)

    @classmethod
    def query(cls, **kwargs):
        query = super(PolyModel, cls).query(**kwargs)
        if cls._kind != cls.class_name():
            # logging.debug('Extra filter for class = %s' % cls.class_name())
            query.add_filter(_CLASS_KEY_PROPERTY, "=", cls.class_name())
        return query
