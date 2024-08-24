import logging
import sys

logger = logging.getLogger(__name__)


def app():
    logger.error("This plugin is not usable when running as python module")
    sys.exit(1)


if __name__ == "__main__":
    app()
