import os
import sublime
import linecache
import time
import sublime_plugin
from .core.protocol import Request, Range, Point
from .core.registry import client_for_view, LspTextCommand
from .core.views import range_to_region
from .core.url import uri_to_filename
from .core.workspace import get_project_path
from .references import ensure_references_panel

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

    # def input(self, args):
    #     return Query(self.view)

    def _group_references_by_file(self, references, base_dir) -> 'Dict[str, List[Dict]]':
        """ Return a dictionary that groups references by the file it belongs. """
        grouped_references = {}  # type: Dict[str, List[Dict]]
        for reference in references:
            file_path = uri_to_filename(reference['location']['uri'])
            relative_file_path = os.path.relpath(file_path, base_dir)

            point = Point.from_lsp(reference['location']['range']['start'])
            # get line of the reference, to showcase its use
            reference_line = linecache.getline(file_path, point.row + 1).strip()

            if grouped_references.get(relative_file_path) is None:
                grouped_references[relative_file_path] = []
            grouped_references[relative_file_path].append({'point': point, 'text': reference_line})

        # we don't want to cache the line, we always want to get fresh data
        linecache.clearcache()

        return grouped_references

    def _format_references(self, grouped_references) -> str:
        text = ''
        for file in grouped_references:
            text += '◌ {}:\n'.format(file)
            references = grouped_references.get(file)
            for reference in references:
                point = reference.get('point')
                text += '\t{:>8}:{:<4} {}\n'.format(point.row + 1, point.col + 1, reference.get('text'))
            # append a new line after each file name
            text += '\n'
        return text

    def _get_formatted_symbols(self, references: 'List[Dict]', base_dir) -> str:
        grouped_references = self._group_references_by_file(references, base_dir)
        formatted_references = self._format_references(grouped_references)
        return formatted_references

    def _handle_response(self, query_str, response: 'Optional[List[Dict]]'):
        window = self.view.window()
        base_dir = get_project_path(window)

        if response is None:
            response = []

        symbols_count = len(response)
        print("count " + str(symbols_count))

        # return if there are no symbols
        if symbols_count < 1:
            window.run_command("hide_panel", {"panel": "output.symbols"})
            window.status_message("No symbols found")
            return

        formatted_symbols = self._get_formatted_symbols(response, base_dir)

        panel = ensure_references_panel(window, "symbols")
        print("panel ? {}".format(panel))
        if not panel:
            return

        panel.settings().set("result_base_dir", base_dir)

        panel.set_read_only(False)
        # panel.run_command("lsp_clear_panel")
        window.run_command("show_panel", {"panel": "output.symbols"})
        panel.run_command('append', {
            'characters': "{} references for '{}'\n\n{}".format(symbols_count, query_str, formatted_symbols),
            'force': True,
            'scroll_to_end': False
        })

        # highlight all word occurrences
        regions = panel.find_all(r"\b{}\b".format(query_str))
        panel.add_regions('ReferenceHighlight', regions, 'comment', flags=sublime.DRAW_OUTLINED)
        panel.set_read_only(True)

    def run(self, edit):
        # path = uri_to_filename(results['location']['uri'])
        # path_x = "{}:{}:{}".format(path, range['start']['line'], range['start']['character'])

        def on_change(str):
            client = client_for_view(self.view)
            if client and str != "":
                print(str)
                params = {
                    "query": str
                }
                request = Request.workspaceSymbol(params)
                print("request {}".format(request))
                client.send_request(request, lambda response: self._handle_response(str, response))

        new_view = self.view.window().show_input_panel("symbol", "", None, on_change, None)
