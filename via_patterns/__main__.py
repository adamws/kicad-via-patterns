from via_patterns._version import __version__

try:
    import pcbnew

    pcbnew_version = pcbnew.Version()
except Exception:
    print("Could not load `pcbnew`, probably running from virtual environment")
    pcbnew_version = None


def app():
    if pcbnew_version:
        print(f"pcbnew version: {pcbnew_version}")
    print(f"plugin version: {__version__}")


if __name__ == "__main__":
    app()
