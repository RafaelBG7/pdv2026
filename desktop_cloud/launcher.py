from __future__ import annotations

import traceback

from . import APP_VERSION
from .config import ConfigError, DesktopConfig, load_desktop_config, validate_desktop_config
from .connectivity import check_server_available
from .local_logging import configure_launcher_logger
from .single_instance import SingleInstanceLock
from .window import open_window


def main() -> int:
    logger = configure_launcher_logger()
    logger.info("launcher_start version=%s", APP_VERSION)

    lock = SingleInstanceLock()
    if not lock.acquire():
        logger.warning("duplicate_instance_blocked")
        return 0

    try:
        try:
            config = validate_desktop_config(load_desktop_config())
            logger.info("config_loaded environment=%s", config.environment)
        except ConfigError as exc:
            logger.error("config_error %s", exc)
            open_window(DesktopConfig(), logger, "A configuração local do Girofy Desktop é inválida. Verifique o domínio configurado.")
            return 1

        result = check_server_available(config)
        logger.info("connectivity_check ok=%s status=%s", result.ok, result.status_code)
        if result.ok:
            open_window(config, logger)
        else:
            open_window(config, logger, "Verifique sua conexão com a internet e tente novamente.")
        return 0
    except Exception:
        logger.error("launcher_unexpected_error\n%s", traceback.format_exc())
        raise
    finally:
        lock.release()
        logger.info("launcher_stop")


if __name__ == "__main__":
    raise SystemExit(main())
