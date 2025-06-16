import wx

from .plugin_action import PluginAction


if __name__ == "__main__":
    app = wx.App()
    plugin = PluginAction()
    plugin.initialize()
    plugin.run()
