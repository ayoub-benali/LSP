import sublime_plugin
import sublime
import time
from .core.protocol import Request, Range
from .core.registry import client_for_view, LspTextCommand
from .core.views import range_to_region
from .core.url import uri_to_filename

try:
    from typing import List, Optional, Dict, Any
    assert List and Optional and Dict and Any
except ImportError:
    pass

class Results(sublime_plugin.ListInputHandler):
    def __init__(self, view, files):
        self.view = view
        self.files = files
        self.ziped = list(map(lambda f: (f.get("location").get("uri"), f), self.files))

    def list_items(self):
        return self.ziped

    def preview(self, v):
        return v.get("name")

    def description(self, v, t):
        return "hello {} {}".format(v, t)

class Query(sublime_plugin.TextInputHandler):
    def __init__(self, view):
        self.view = view
        self.files = []
        self.client = client_for_view(self.view)

    def _handle_response(self, response):
        for e in response:
            print(e)
            print()
            self.files.append(e)

    def validate(self, txt):
        params = {
            "query": txt
        }
        request = Request.workspaceSymbol(params)
        if self.client:
            self.client.send_request(request, lambda response: self._handle_response(response))
        time.sleep(1)
        return len(self.files) != 0

    def placeholder(self):
        return "symbol name"

    def next_input(self, args):
        return Results(self.view, self.files)

class LspWorkspaceSymbol(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def input(self, args):
        return Query(self.view)

    def run(self, edit, results, query):
        print(results)
        print(query)
        range = results['location']['range']
        path = uri_to_filename(results['location']['uri'])
        path_x = "{}:{}:{}".format(path, range['start']['line'], range['start']['character'])
        new_view = self.view.window().open_file(path_x, sublime.ENCODED_POSITION)
