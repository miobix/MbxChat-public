import logging

from mbxchat import config
from mbxchat.health import make_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mbxchat")


def main() -> None:
    server = make_server("0.0.0.0", config.HEALTH_PORT)
    log.info("health endpoint on :%s", config.HEALTH_PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
