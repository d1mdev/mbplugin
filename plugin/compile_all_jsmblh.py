import os, sys, re, glob, traceback
import settings, store


def recompile(pluginpath = store.abspath_join(os.path.split(sys.argv[0])[0]), verbose=False):
    os.chdir(pluginpath)
    sys.path.insert(0,pluginpath)
    port = store.options('port', section='HttpServer')
    tmpl = open(store.abspath_join(pluginpath, '..', 'jsmblhplugin', '_template_localweb.jsmb'), encoding='cp1251').read()

    for fn in glob.glob(store.abspath_join(pluginpath, '..', 'plugin', '*.py')):
        if ('def' + ' get_balance(') in open(fn, encoding='utf8').read():
            plugin = os.path.splitext(os.path.split(fn)[1])[0]
            try:
                fl = 'p_' + plugin
                module = __import__(plugin, globals(), locals(), [], 0)
                data = tmpl.replace('{{pluginname}}', fl).replace('{{port}}', port)
                if hasattr(module,'icon'):
                    data = re.sub(r'//\s*Icon\s*:\s*\S*', f'// Icon      : {module.icon}', data)
                plugin_filename = store.abspath_join(pluginpath, '..','jsmblhplugin', fl +'_localweb.jsmb')
                open(plugin_filename, 'w').write(data)
                if verbose:
                    print(os.path.abspath(plugin_filename))
            except Exception:
                errmsg = "".join(traceback.format_exception(*sys.exc_info()))
                if 'import tkinter' not in errmsg:
                    print(f'Compile {plugin} fail: {errmsg}')


if __name__ == '__main__':
    print('main')
    recompile()
