# -*- coding: utf-8 -*-

from collections import OrderedDict
import json
from operator import attrgetter
import uuid
import argparse
from urllib.parse import urlencode

from mitmproxy import ctx

HOST_FILTER_PARAM = "host_filter"
COLLECTION_NAME_PARAM = "collection_name"

def load(l):
    l.add_option(HOST_FILTER_PARAM, str, "example.com", "Host filter option")
    l.add_option(COLLECTION_NAME_PARAM, str, "collection_name", "Collection name option")

def configure(updated):
    if HOST_FILTER_PARAM in updated or COLLECTION_NAME_PARAM in updated :
        ctx.log.info("host filter : " + ctx.options.host_filter)
        ctx.log.info("collection name : " + ctx.options.collection_name)
        global addons
        addons = [Postman(ctx.options.host_filter, ctx.options.collection_name)]

class Postman:
    def __init__(self, host, collection_name='TestCollection'):
        """
        :param host: Host for which we are creating the Postman collection
        :param collection_name: Name of the collection
        """
        self.host = host
        self.collection = Collection(name=collection_name)
        self.folder_dict = {}

    def request(self, flow):
        """
        Called when a client request has been received by mitmproxy.
        The flow object is guaranteed to have a non-None request attribute.
        :param flow: HTTPFlow object (The flow containing the request which has been received)
        :return: None
        """
        if flow.request.host != self.host:
            return
        headers = {}
        for k, v in flow.request.headers.items():
            if k != 'Content-Length':
                headers[k] = v
        content = flow.request.content
        if content:
            content = content.decode('utf-8')
        print('{url} ({method})'.format(**{'url': flow.request.url, 'method': flow.request.method}))
        data = None
        is_json = False
        path = self.get_path(flow.request)
        try:
            content = json.loads(content)
        except Exception:
            pass
        if flow.request.method in ['POST', 'PUT']:
            data = content
            if 'form-urlencoded' in headers.get('Content-Type', ''):
                try:
                    data = {x.split('=')[0]: x.split('=')[1] for x in data.split('&')}
                except Exception:
                    pass
            elif 'json' in headers.get('Content-Type', ''):
                is_json = True
        req = Request(name=path, url=flow.request.url, method=flow.request.method,
                      headers=headers, data=data, is_json=is_json, description=None, parent=None)
        add_to_folder = False
        folder_name = ''
        if path and path != '/':
            if path[0] == '/':
                path = list(path)
                path[0] = ''
                path = ''.join(path)
            sub_path = path.split('/')
            if len(sub_path) > 1:
                add_to_folder = True
                folder_name = sub_path[0]
        if not add_to_folder:
            self.collection.add_request(req)
        else:
            if self.folder_dict.get(folder_name):
                folder = self.folder_dict.get(folder_name)
            else:
                folder = Folder(name=folder_name, collection=self.collection)
                self.collection.add_folder(folder)
                self.folder_dict[folder_name] = folder
            folder.add_request(req)
        self.collection.save_to_file()

    @staticmethod
    def get_path(req):
        """
        Get path of the domain
        :param req: HTTPRequest object
        :return: domain path
        """
        path = req.path
        if '?' in req.path:
            path = req.path[:req.path.find('?')]
        return path


class Collection(object):
    def __init__(self, name, description=None):
        """
        A Collection object represents a single postman collection
        :param name: Collection name
        :param description: Description for the collection
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self._requests = []
        self._folders = []
        self.description = description

    def get_collection_id(self):
        """
        :return: collection id
        """
        return self.id

    def add_request(self, request):
        """
        Add request to the collection
        :param request: Request object
        :return: None
        """
        request._parent = self
        self._requests.append(request)

    def add_folder(self, folder):
        """
        Add folder to the collection
        :param folder: Folder object
        :return: None
        """
        self._folders.append(folder)
        folder._collection = self

    def get_all_requests(self):
        """
        Get all requests including those in the folders
        :return: list of Request objects
        """
        requests = list(self._requests)
        for f in self._folders:
            requests.extend(f._requests)
        return sorted(requests, key=attrgetter('id'))

    def serialize(self):
        """
        Serialize Collection object
        :return: Collection dict
        """
        obj = OrderedDict()
        obj['id'] = self.id
        obj['name'] = self.name
        if self.description is not None:
            obj['description'] = self.description
        obj['order'] = [r.id for r in self._requests]
        obj['folders'] = [f.serialize() for f in sorted(self._folders, key=attrgetter('id'))]
        requests = self.get_all_requests()
        obj['requests'] = [r.serialize() for r in requests]
        return obj

    def save_to_file(self):
        """
        Save Postman collection to file
        :return: None
        """
        obj = self.serialize()
        filename = '{file_name}.json'.format(**{'file_name': self.name})
        with open(filename, 'wt') as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)


class Folder(object):
    def __init__(self, name, collection=None):
        """
        A Folder object represents a single Postman folder
        :param name: Name of the folder
        :param collection: Collection object (collection to which the folder belongs)
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.order = []
        self._requests = []
        self._collection = collection

    def get_collection_id(self):
        """
        Get the id of the collection to which the folder belongs
        :return: collection id
        """
        return self._collection.id

    def add_request(self, request):
        """
        Add Request to the Folder
        :param request: Request object
        :return: None
        """
        request._parent = self
        self._requests.append(request)

    def serialize(self):
        """
        Serialize Folder object
        :return: Folder dict
        """
        obj = OrderedDict()
        obj['id'] = self.id
        obj['name'] = self.name
        obj['order'] = [r.id for r in self._requests]
        return obj


class Request(object):
    def __init__(self, name, url, method=None, headers=None, data=None, is_json=False, description=None, parent=None):
        """
        A Request object represents a single Postman Request
        :param name: Name of the request
        :param url: URL to send the request
        :param method: HTTP method
        :param headers: Headers dict
        :param data: Body of the request
        :param is_json: Whether data is a json
        :param description: Description for the request
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.url = url
        self.method = method
        self.headers = headers
        self.data = data
        self.is_json = is_json
        self.description = description
        self._parent = parent

    def set_parent(self, parent):
        """
        Set a parent for the Request object
        :param parent: Collection or Folder object
        :return: None
        """
        self._parent = parent

    def serialize(self):
        """
        Serialize Request object
        :return: Request dict
        """
        headers = {} if self.headers is None else self.headers
        obj = OrderedDict()
        obj['id'] = self.id
        obj['name'] = self.name
        obj['url'] = self.url
        obj['method'] = self.method
        if self.data is not None and isinstance(self.data, dict) and not self.is_json:
            obj['dataMode'] = 'urlencoded'
            obj['data'] = [dict(key=k, value=v, enabled=True, type='text') for k, v in self.data.items()]
        elif self.data is not None and not self.is_json:
            obj['dataMode'] = 'raw'
            obj['rawModeData'] = str(self.data)
        elif self.data is not None and self.is_json:
            obj['dataMode'] = 'raw'
            obj['rawModeData'] = json.dumps(self.data, indent=4)
        obj['headers'] = ''.join('%s: %s\n' % kv for kv in headers.items())
        if self.description is not None:
            obj['descriptionFormat'] = 'markdown'
            obj['description'] = self.description
        if self._parent is not None:
            obj['collectionId'] = self._parent.get_collection_id()
        if isinstance(self._parent, Folder):
            obj['folder'] = self._parent.id
        return obj
