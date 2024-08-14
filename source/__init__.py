import inspect


def __is_in_call_stack(function_name: str, module_name: str) -> bool:
    current_stack = inspect.stack()

    for frame_info in current_stack:
        frame = frame_info.frame
        if frame.f_globals.get("__name__") == module_name:
            if function_name in frame.f_locals or function_name in frame.f_globals:
                return True

    return False


if __is_in_call_stack("LoadPluginModule", "pcbnew"):
    from .plugin_action import PluginAction

    PluginAction().register()
