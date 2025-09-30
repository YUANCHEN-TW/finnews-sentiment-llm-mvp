import logging

def get_logger(name: str = "app", level: int = logging.INFO):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        ch = logging.StreamHandler()
        ch.setLevel(level)
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s")
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger
