# utils/find_chat_file.py
"""
Module: find_chat_file
Author: Willian Prado
Description:
    Asynchronous and synchronous chat file detector following SOLID and Clean Code principles.
    Supports WhatsApp-style message pattern recognition in text files.

Key Features:
    - Pattern Strategy (OCP: easy to extend for new chat formats)
    - Asynchronous file scanning using aiofiles for non-blocking I/O
    - Concurrent pattern detection with asyncio for performance
    - Clean Architecture separation: Strategy → Filter → Scanner → Finder → Builder
"""

from __future__ import annotations
import asyncio
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Optional, Pattern

import aiofiles  # asynchronous file operations

logger = logging.getLogger(__name__)


# ============================================================
# Strategy Pattern: Pattern Definition Layer
# ============================================================

class ChatPatternStrategy(ABC):
    """Abstract base class defining the pattern detection contract."""

    @abstractmethod
    def get_patterns(self) -> List[Pattern]:
        """Return regex patterns used to identify chat-style messages."""
        raise NotImplementedError


class WhatsAppPatternStrategy(ChatPatternStrategy):
    """Concrete strategy for detecting WhatsApp chat export patterns."""

    def get_patterns(self) -> List[Pattern]:
        """
        Return compiled regex patterns for WhatsApp-like chat exports.
        Implemented as a plain method to match the ChatPatternStrategy contract.
        """
        return [
            re.compile(r"\[\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2}\] ~[A-Za-z0-9]+:"),
            re.compile(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2} - [A-Za-z0-9]+:"),
            re.compile(r"\d{2}/\d{2}/\d{2}, \d{2}:\d{2} - \+[\d\s]+:")
        ]



# ============================================================
# File Validation Layer
# ============================================================

class TextFileFilter:
    """Validates and filters text files before scanning."""

    def __init__(self, allowed_extensions: Iterable[str] = ('.txt',)):
        self.allowed_extensions = tuple(ext.lower() for ext in allowed_extensions)

    def _is_valid_file(self, file: Path) -> bool:
        """Synchronous file validation."""
        if not isinstance(file, Path):
            logger.warning(f"Invalid file type: {type(file)}")
            return False
        if not file.exists():
            logger.warning(f"File not found: {file}")
            return False
        if file.suffix.lower() not in self.allowed_extensions:
            return False
        return True

    def filter_valid_files(self, files: Iterable[Path]) -> List[Path]:
        """Synchronous filtering (used for backward compatibility)."""
        return [f for f in files if self._is_valid_file(f)]

    async def filter_valid_files_async(self, files: Iterable[Path]) -> List[Path]:
        """Asynchronous version of file validation using threads."""
        loop = asyncio.get_running_loop()
        tasks = [loop.run_in_executor(None, self._is_valid_file, f) for f in files]
        results = await asyncio.gather(*tasks)
        return [f for f, ok in zip(files, results) if ok]


# ============================================================
# Asynchronous File Scanning Utility
# ============================================================

async def async_file_scanner_is_chat_file(file: Path, patterns: List[Pattern]) -> bool:
    """
    Scans a file asynchronously to detect chat patterns.
    Uses aiofiles for non-blocking I/O.
    """
    try:
        async with aiofiles.open(file, 'r', encoding='utf-8', errors='ignore') as f:
            async for line in f:
                for pattern in patterns:
                    if pattern.search(line):
                        return True
    except Exception as e:
        logger.warning(f"Async scan failed for {file}: {e}")
    return False


# ============================================================
# File Scanning Layer
# ============================================================

class ChatFileScanner:
    """Scans files for known chat patterns (sync + async versions)."""

    def __init__(self, pattern_strategy: ChatPatternStrategy):
        self.patterns = pattern_strategy.get_patterns()

    def _is_chat_file(self, file: Path) -> bool:
        """Synchronous pattern detection."""
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if any(p.search(line) for p in self.patterns):
                        return True
        except Exception as e:
            logger.warning(f"Synchronous scan failed for {file}: {e}")
        return False

    def find_chat_file(self, files: Iterable[Path]) -> Optional[Path]:
        """Synchronous chat file detection (legacy support)."""
        for file in files:
            try:
                if (
                    file.name == "_chat.txt"
                    or (len(files) == 1 and file.suffix.lower() == ".txt")
                    or self._is_chat_file(file)
                ):
                    logger.info(f"Chat file found: {file.name}")
                    return file
            except Exception as e:
                logger.warning(f"Error scanning {file.name}: {e}")
        return None

    async def find_chat_file_async(self, files: Iterable[Path]) -> Optional[Path]:
        """
        Concurrent asynchronous detection.
        Returns the first file matching a chat pattern.
        """
        # Quick name-based shortcuts before I/O
        for file in files:
            if file.name == "_chat.txt" or (len(files) == 1 and file.suffix.lower() == ".txt"):
                logger.info(f"Chat file identified by name: {file.name}")
                return file

                # Concurrent scanning
        tasks = {asyncio.create_task(async_file_scanner_is_chat_file(f, self.patterns)): f for f in files}

        pending = set()
        try:
            done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)

            for d in done:
                try:
                    if d.result():
                        # Cancel all remaining tasks
                        for p in pending:
                            p.cancel()
                        chat_file = tasks[d]
                        logger.info(f"Chat file identified by pattern: {chat_file.name}")
                        return chat_file
                except Exception as e:
                    logger.warning(f"Error processing async scan: {e}")
        finally:
            for p in pending:
                p.cancel()



# ============================================================
# Coordinator Layer
# ============================================================

class ChatFileFinder:
    """
    High-level orchestrator combining filter + scanner + strategy.
    Provides both sync and async APIs.
    """

    def __init__(
        self,
        pattern_strategy: ChatPatternStrategy = None,
        file_filter: TextFileFilter = None,
        file_scanner: ChatFileScanner = None,
    ):
        self.pattern_strategy = pattern_strategy or WhatsAppPatternStrategy()
        self.file_filter = file_filter or TextFileFilter()
        self.file_scanner = file_scanner or ChatFileScanner(self.pattern_strategy)

    def find_chat_file(self, files: List[Path]) -> Optional[Path]:
        """Synchronous interface (for legacy compatibility)."""
        if not files:
            logger.warning("Empty file list received")
            return None

        valid_files = self.file_filter.filter_valid_files(files)
        if not valid_files:
            logger.warning("No valid text files found")
            return None

        return self.file_scanner.find_chat_file(valid_files)

    async def find_chat_file_async(self, files: List[Path]) -> Optional[Path]:
        """Asynchronous interface for non-blocking detection."""
        if not files:
            logger.warning("Empty file list received")
            return None

        valid_files = await self.file_filter.filter_valid_files_async(files)
        if not valid_files:
            logger.warning("No valid text files found")
            return None

        return await self.file_scanner.find_chat_file_async(valid_files)


# ============================================================
# Builder Pattern for Flexible Construction
# ============================================================

class ChatFileFinderBuilder:
    """Builder providing flexible configuration of ChatFileFinder."""

    def __init__(self):
        self._pattern_strategy = WhatsAppPatternStrategy()
        self._file_filter = TextFileFilter()
        self._file_scanner = None

    def with_pattern_strategy(self, strategy: ChatPatternStrategy) -> ChatFileFinderBuilder:
        self._pattern_strategy = strategy
        return self

    def with_file_filter(self, file_filter: TextFileFilter) -> ChatFileFinderBuilder:
        self._file_filter = file_filter
        return self

    def with_file_scanner(self, scanner: ChatFileScanner) -> ChatFileFinderBuilder:
        self._file_scanner = scanner
        return self

    def build(self) -> ChatFileFinder:
        scanner = self._file_scanner or ChatFileScanner(self._pattern_strategy)
        return ChatFileFinder(
            pattern_strategy=self._pattern_strategy,
            file_filter=self._file_filter,
            file_scanner=scanner,
        )


# ============================================================
# Factory for Simplicity
# ============================================================

def create_chat_finder() -> ChatFileFinder:
    """Factory for default ChatFileFinder creation."""
    return ChatFileFinderBuilder().build()

