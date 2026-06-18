from .plugin_action import PluginAction


def app():
    # KiCad's IPC plugin runtime launches `entrypoint.py`, which in turn
    # execs `python -m via_patterns` (see entrypoint.py) - so this is the
    # real entrypoint used when the plugin is run from within KiCad, not
    # just a diagnostic stub.
    PluginAction().run()


if __name__ == "__main__":
    app()
