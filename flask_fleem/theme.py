import os
import yaml
from flask import current_app, _app_ctx_stack
from jinja2.loaders import FileSystemLoader, BaseLoader, TemplateNotFound
from werkzeug import cached_property, LocalProxy
from flask_assets import Bundle
from .compat import implements_to_string

_fleem = LocalProxy(lambda: current_app.extensions['fleem_manager'])

class Theme(object):
    """
    Contains a theme's metadata.

    :param path: The path to the theme directory.
    """
    def __init__(self, path):
        self.path = os.path.abspath(path)

        with open(os.path.join(self.path, 'info.yaml')) as fd:
            self.info = i = yaml.load(fd)

        if not all(k in i for k in ('name', 'identifier', 'application')):
            raise AttributeError("""
                                 Theme configuration MUST contain:\n
                                 - theme name\n
                                 - theme identifier\n
                                 - application identifier\n
                                 theme configuration contained:{i}
                                 """).format(i)

        # The theme's human readable name, as given in info.yaml.
        self.name = i.pop('name')

        # The theme's identifier. In most situations should match the name of
        # the directory the theme is in.
        self.identifier = i.pop('identifier')

        # The application name to associate them with application.
        self.application = i.pop('application')

        for k,v in iter(i.items()):
            setattr(self, k, v)

    def join_or_no(self, base_path, *join_paths):
        if join_paths:
            return os.path.join(base_path, *join_paths)
        else:
            return base_path

    def has_path(self, base_path, *join_paths):
        return os.path.exists(self.join_or_no(base_path, *join_paths))

    def ext_fname(self, fname, ext):
        return os.path.splitext(fname)[-1] == ext

    def list_dirs(self, base_path, *join_paths):
        return os.listdir(self.join_or_no(base_path, *join_paths))

    def extension_absolute(self, ext):
        return ext[1:]

    def theme_files_of(self, extension):
        lf = []
        ext_abs = self.extension_absolute(extension)
        if self.has_path(self.static_path):
            lf.extend([self.join_or_no(self.static_path, fname) for fname \
                       in self.list_dirs(self.static_path) \
                       if self.ext_fname(fname, extension)])
        if self.has_path(self.static_path, ext_abs):
            lf.extend([self.join_or_no(self.static_path, ext_abs, fname) for fname \
                       in self.list_dirs(self.static_path, ext_abs) \
                       if self.ext_fname(fname, extension)])
        return lf

    def return_bundle(self, extension, resource_filter):
        resource_tag = "{}/theme-{}-packed{}".format(extension[1:], self.identifier, extension)
        resources = self.theme_files_of(extension)
        if resources:
            manifest = "{} for theme {} == {}".format(extension, self.name, [r for r in resources])
            bundle = Bundle(*resources, output=resource_tag, filters=resource_filter)
        else:
            manifest = "No {} resources for {}".format(extension, self.name)
            bundle = None
        return manifest, bundle

    @cached_property
    def static_path(self):
        """The absolute path to the theme's static files directory."""
        return os.path.join(self.path, 'static')

    @cached_property
    def templates_path(self):
        """The absolute path to the theme's templates directory."""
        return os.path.join(self.path, 'templates')

    @cached_property
    def jinja_loader(self):
        """This is a Jinja2 template loader that loads templates from the theme's
        ``templates`` directory.
        """
        return FileSystemLoader(self.templates_path)

    def bundle_name(self, asset_type):
        return "{}_{}".format(self.identifier, asset_type)

    def __repr__(self):
        return "<Theme: {} | app_id: {} | id: {} >".format(self.name, self.application, self.identifier)


class ThemeTemplateLoader(BaseLoader):
    """Loads templates from the current app's loaded themes."""
    def __init__(self):
        BaseLoader.__init__(self)

    def get_source(self, environment, template):
        template = template[8:]
        try:
            themename, templatename = template.split('/', 1)
            theme = _fleem.themes[themename]
        except (ValueError, KeyError):
            raise TemplateNotFound(template)
        try:
            return theme.jinja_loader.get_source(environment, templatename)
        except TemplateNotFound:
            raise TemplateNotFound(template)

    def list_templates(self):
        res = []
        for ident, theme in iter(_fleem.themes.items()):
            res.extend(implements_to_string('_themes/{}/{}'.format(ident, t))
                       for t in theme.jinja_loader.list_templates())
        return res
