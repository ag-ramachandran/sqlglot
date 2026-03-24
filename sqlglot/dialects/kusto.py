from __future__ import annotations

from sqlglot import tokens
from sqlglot.dialects.dialect import Dialect
from sqlglot.parsers.kusto import KustoParser
from sqlglot.tokens import TokenType


class Kusto(Dialect):
    DPIPE_IS_STRING_CONCAT = False

    class Tokenizer(tokens.Tokenizer):
        QUOTES = ["'", '"']
        IDENTIFIERS = ["`"]

        SINGLE_TOKENS = {
            **tokens.Tokenizer.SINGLE_TOKENS,
            "'": TokenType.QUOTE,
            '"': TokenType.QUOTE,
            "`": TokenType.IDENTIFIER,
        }

        KEYWORDS = {
            **tokens.Tokenizer.KEYWORDS,
            "CONTAINS": TokenType.COMMAND,
            "!CONTAINS": TokenType.COMMAND,
            "CONTAINS_CS": TokenType.COMMAND,
            "!CONTAINS_CS": TokenType.COMMAND,
            "HAS": TokenType.COMMAND,
            "!HAS": TokenType.COMMAND,
            "HAS_CS": TokenType.COMMAND,
            "!HAS_CS": TokenType.COMMAND,
            "STARTSWITH": TokenType.COMMAND,
            "!STARTSWITH": TokenType.COMMAND,
            "ENDSWITH": TokenType.COMMAND,
            "!ENDSWITH": TokenType.COMMAND,
            "MATCHES": TokenType.COMMAND,
            "SUMMARIZE": TokenType.COMMAND,
            "EXTEND": TokenType.COMMAND,
            "PROJECT": TokenType.COMMAND,
            "TAKE": TokenType.COMMAND,
            "LET": TokenType.COMMAND,
            "PRINT": TokenType.COMMAND,
            "KIND": TokenType.COMMAND,
            "REAL": TokenType.DOUBLE,
            "BOOL": TokenType.BOOLEAN,
            "LONG": TokenType.BIGINT,
            "DYNAMIC": TokenType.VARIANT,
            "TIMESPAN": TokenType.INTERVAL,
            "DATETIME": TokenType.TIMESTAMPTZ,
        }

    Parser = KustoParser
