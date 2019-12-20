#!/usr/bin/env python3
"""pdoc's CLI interface and helper functions."""

import importlib
import inspect
import os
import os.path as path
import re
import sys
import warnings
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Sequence
from warnings import warn

import app.pdoc as pdoc

DEFAULT_HOST, DEFAULT_PORT = 'localhost', 8080


class WebDoc(BaseHTTPRequestHandler):
    args = None  # Set before server instantiated
    template_config = None

    def do_HEAD(self):
        status = 200
        if self.path != "/":
            status = self.check_modified()

        self.send_response(status)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def check_modified(self):
        try:
            module = pdoc.import_module(self.import_path_from_req_url)
            new_etag = str(os.stat(module.__file__).st_mtime)
        except ImportError:
            return 404

        old_etag = self.headers.get('If-None-Match', new_etag)
        if old_etag == new_etag:
            # Don't log repeating checks
            self.log_request = lambda *args, **kwargs: None
            return 304

        return 205

    def do_GET(self):
        # Deny favicon shortcut early.
        if self.path == "/favicon.ico":
            return None

        importlib.invalidate_caches()
        code = 200
        if self.path == "/":
            modules = [pdoc.import_module(module, reload=True)
                       for module in self.args.modules]
            modules = sorted((module.__name__, inspect.getdoc(module))
                             for module in modules)
            out = pdoc._render_template('/html.mako',
                                        modules=modules,
                                        **self.template_config)
        elif self.path.endswith(".ext"):
            # External links are a bit weird. You should view them as a giant
            # hack. Basically, the idea is to "guess" where something lives
            # when documenting another module and hope that guess can actually
            # track something down in a more global context.
            #
            # The idea here is to start specific by looking for HTML that
            # exists that matches the full external path given. Then trim off
            # one component at the end and try again.
            #
            # If no HTML is found, then we ask `pdoc` to do its thang on the
            # parent module in the external path. If all goes well, that
            # module will then be able to find the external identifier.

            import_path = self.path[:-4].lstrip("/")
            resolved = self.resolve_ext(import_path)
            if resolved is None:  # Try to generate the HTML...
                print("Generating HTML for %s on the fly..." % import_path, file=sys.stderr)
                try:
                    out = pdoc.html(import_path.split(".")[0], **self.template_config)
                except Exception as e:
                    print('Error generating docs: {}'.format(e), file=sys.stderr)
                    # All hope is lost.
                    code = 404
                    out = "External identifier <code>%s</code> not found." % import_path
            else:
                return self.redirect(resolved)
        # Redirect '/pdoc' to '/pdoc/' so that relative links work
        # (results in '/pdoc/cli.html' instead of 'cli.html')
        elif not self.path.endswith(('/', '.html')):
            return self.redirect(self.path + '/')
        # Redirect '/pdoc/index.html' to '/pdoc/' so it's more pretty
        elif self.path.endswith(pdoc._URL_PACKAGE_SUFFIX):
            return self.redirect(self.path[:-len(pdoc._URL_PACKAGE_SUFFIX)] + '/')
        else:
            try:
                out = self.html()
            except ImportError:
                code = 404
                out = "Module <code>%s</code> not found." % self.import_path_from_req_url

        self.send_response(code)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.echo(out)

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def echo(self, s):
        self.wfile.write(s.encode("utf-8"))

    def html(self):
        """
        Retrieves and sends the HTML belonging to the path given in
        URL. This method is smart and will look for HTML files already
        generated and account for whether they are stale compared to
        the source code.
        """
        return pdoc.html(self.import_path_from_req_url,
                         reload=True, http_server=True, external_links=True,
                         **self.template_config)

    def resolve_ext(self, import_path):
        def exists(p):
            p = path.join(args.output_dir, p)
            pkg = path.join(p, pdoc._URL_PACKAGE_SUFFIX.lstrip('/'))
            mod = p + pdoc._URL_MODULE_SUFFIX

            if path.isfile(pkg):
                return pkg[len(args.output_dir):]
            elif path.isfile(mod):
                return mod[len(args.output_dir):]
            return None

        parts = import_path.split(".")
        for i in range(len(parts), 0, -1):
            p = path.join(*parts[0:i])
            realp = exists(p)
            if realp is not None:
                return "/%s#%s" % (realp.lstrip("/"), import_path)
        return None

    @property
    def import_path_from_req_url(self):
        pth = self.path.split('#')[0].lstrip('/')
        for suffix in ('/',
                       pdoc._URL_PACKAGE_SUFFIX,
                       pdoc._URL_INDEX_MODULE_SUFFIX,
                       pdoc._URL_MODULE_SUFFIX):
            if pth.endswith(suffix):
                pth = pth[:-len(suffix)]
                break
        return pth.replace('/', '.')


def module_path(m: pdoc.Module, ext: str):
    return path.join(args.output_dir, *re.sub(r'\.html$', ext, m.url()).split('/'))


def _quit_if_exists(m: pdoc.Module, ext: str):
    if args.force:
        return

    paths = [module_path(m, ext)]
    if m.is_package:  # If package, make sure the dir doesn't exist either
        paths.append(path.dirname(paths[0]))

    for pth in paths:
        if path.lexists(pth):
            print("File '%s' already exists. Delete it, or run with --force" % pth,
                  file=sys.stderr)
            sys.exit(1)


def write_files(m: pdoc.Module, ext: str, **kwargs):
    assert ext in ('.html', '.md')
    f = module_path(m, ext=ext)

    dirpath = path.dirname(f)
    if not os.access(dirpath, os.R_OK):
        os.makedirs(dirpath)

    try:
        with open(f, 'w+', encoding='utf-8') as w:
            if ext == '.html':
                w.write(m.html(**kwargs))
            elif ext == '.md':
                w.write(m.text(**kwargs))
    except Exception:
        try:
            os.unlink(f)
        except Exception:
            pass
        raise

    for submodule in m.submodules():
        write_files(submodule, ext=ext, **kwargs)


def _flatten_submodules(modules: Sequence[pdoc.Module]):
    for module in modules:
        yield module
        for submodule in module.submodules():
            yield from _flatten_submodules((submodule,))


def print_pdf(modules, **kwargs):
    modules = list(_flatten_submodules(modules))
    print(pdoc._render_template('/pdf.mako', modules=modules, **kwargs))


def _warn_deprecated(option, alternative='', use_config_mako=False):
    msg = 'Program option `{}` is deprecated.'.format(option)
    if alternative:
        msg += ' Use `' + alternative + '`'
        if use_config_mako:
            msg += ' or override config.mako template'
        msg += '.'
    warn(msg, DeprecationWarning, stacklevel=2)


def main(_args=None):
    """ Command-line entry point """
    global args
    args = _args

    warnings.simplefilter("once", DeprecationWarning)

    if (args.html or args.http) and not args.output_dir:
        args.output_dir = 'html'

    template_config = {}

    # Support loading modules specified as python paths relative to cwd
    sys.path.append(os.getcwd())

    # Virtual environment handling for pdoc script run from system site
    try:
        venv_dir = os.environ['VIRTUAL_ENV']
    except KeyError:
        pass  # pdoc was not invoked while in a virtual environment
    else:
        from distutils.sysconfig import get_python_lib
        sys.path.append(get_python_lib(prefix=venv_dir))

    if args.http:
        template_config['link_prefix'] = "/"

        # Run the HTTP server.
        WebDoc.args = args  # Pass params to HTTPServer xP
        WebDoc.template_config = template_config

        host, _, port = args.http.partition(':')
        host = host or DEFAULT_HOST
        port = int(port or DEFAULT_PORT)

        print('Starting pdoc server on {}:{}'.format(host, port), file=sys.stderr)
        httpd = HTTPServer((host, port), WebDoc)
        print("pdoc server ready at http://%s:%d" % (host, port), file=sys.stderr)

        # Allow tests to perform `pdoc.cli._httpd.shutdown()`
        global _httpd
        _httpd = httpd

        try:
            httpd.serve_forever()
        finally:
            httpd.server_close()
            sys.exit(0)

    docfilter = None

    modules = [pdoc.Module(module, docfilter=docfilter)
               for module in args.modules]
    pdoc.link_inheritance()

    if args.pdf:
        print_pdf(modules, **template_config)
        print("""
PDF-ready markdown written to standard output.
                              ^^^^^^^^^^^^^^^
Convert this file to PDF using e.g. Pandoc:

    pandoc --metadata=title:"MyProject Documentation"             \\
           --toc --toc-depth=4 --from=markdown+abbreviations      \\
           --pdf-engine=xelatex --variable=mainfont:"DejaVu Sans" \\
           --output=pdf.pdf pdf.md

or using Python-Markdown and Chrome/Chromium/WkHtmlToPDF:

    markdown_py --extension=meta         \\
                --extension=abbr         \\
                --extension=attr_list    \\
                --extension=def_list     \\
                --extension=fenced_code  \\
                --extension=footnotes    \\
                --extension=tables       \\
                --extension=admonition   \\
                --extension=smarty       \\
                --extension=toc          \\
                pdf.md > pdf.html

    chromium --headless --disable-gpu --print-to-pdf=pdf.pdf pdf.html

    wkhtmltopdf -s A4 --print-media-type pdf.html pdf.pdf

or similar, at your own discretion.""",
              file=sys.stderr)
        sys.exit(0)

    for module in modules:
        if args.html:
            _quit_if_exists(module, ext='.html')
            write_files(module, ext='.html', **template_config)
        elif args.output_dir:  # Generate text files
            _quit_if_exists(module, ext='.md')
            write_files(module, ext='.md', **template_config)
        else:
            sys.stdout.write(module.text(**template_config))
            # Two blank lines between two modules' texts
            sys.stdout.write(os.linesep * (1 + 2 * int(module != modules[-1])))
