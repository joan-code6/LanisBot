import re
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    command: CommandType
    args: Dict[str, Any]
    raw_message: str


class CommandParser:
    PATTERNS = {
        CommandType.LOGIN: [
            r"^\/login",
        ],
        CommandType.LOGOUT: [
            r"^logout",
            r"^abmelden",
        ],
        CommandType.HELP: [
            r"^help",
            r"^hilfe",
            r"^\?",
        ],
    }

    def __init__(self):
        self.compiled_patterns: Dict[CommandType, List[re.Pattern]] = {}
        for cmd, patterns in self.PATTERNS.items():
            self.compiled_patterns[cmd] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def parse(self, message: str) -> ParsedCommand:
        message = message.strip()
        command_type = self._detect_command(message)
        args = self._extract_args(message, command_type)
        return ParsedCommand(command=command_type, args=args, raw_message=message)

    def _detect_command(self, message: str) -> CommandType:
        for cmd, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(message):
                    return cmd
        return CommandType.UNKNOWN

    def _extract_args(self, message: str, command: CommandType) -> Dict[str, Any]:
        args: Dict[str, Any] = {}

        if command == CommandType.LOGIN:
            args["credentials"] = self._extract_credentials(message)

        return args

    def _extract_credentials(self, message: str) -> Optional[Dict[str, str]]:
        parts = message.strip().split()
        
        if len(parts) == 4 and parts[0] == "/login":
            return {
                "school_id": parts[1],
                "username": parts[2],
                "password": parts[3],
            }
        
        if len(parts) >= 4 and parts[0].lower() in ["/login", "login", "anmelden"]:
            return {
                "school_id": parts[1],
                "username": parts[2],
                "password": " ".join(parts[3:]),
            }
        
        match = re.search(
            r"(?:school[-_\s]?id[:\s]*)?(\w+).*?(?:user|username)[:\s]*(\w+).*?(?:pass|password)[:\s]*(\S+)",
            message,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return {
                "school_id": match.group(1),
                "username": match.group(2),
                "password": match.group(3),
            }
        return None


command_parser = CommandParser()