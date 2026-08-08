from __future__ import annotations

import sys

from loguru import logger as _logger

__all__ = ["setup_logger", "logger"]

# 移除 loguru 默认 handler
_logger.remove()


def setup_logger(
    level: str = "DEBUG",
    log_file: str | None = None,
    rotation: str = "10 MB",
    serialize: bool = False,
) -> None:
    """配置 mobile-use 日志

    Args:
        level: 日志级别 (DEBUG / INFO / WARNING / ERROR)
        log_file: 日志文件路径，None 则只输出到控制台
        rotation: 日志文件轮转策略
        serialize: 是否输出 JSON 格式
    """
    _logger.remove()

    # 控制台输出
    _logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 文件输出（可选）
    if log_file:
        _logger.add(
            log_file,
            level=level,
            rotation=rotation,
            encoding="utf-8",
            serialize=serialize,
        )


# 默认配置：只输出到控制台
setup_logger(level="DEBUG")

logger = _logger
