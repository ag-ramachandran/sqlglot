from __future__ import annotations

import typing as t

from sqlglot import exp, parser
from sqlglot.helper import seq_get
from sqlglot.tokens import TokenType
from collections.abc import Collection


KQL_JOIN_KINDS = {
    "INNER": "",
    "LEFTOUTER": "LEFT",
    "RIGHTOUTER": "RIGHT",
    "FULLOUTER": "FULL",
    "LEFTSEMI": "LEFT",
    "LEFTANTI": "LEFT",
}

KQL_TIMESPAN_UNITS = {
    "D": "DAY",
    "H": "HOUR",
    "M": "MINUTE",
    "S": "SECOND",
    "MS": "MILLISECOND",
    "US": "MICROSECOND",
}


class KustoParser(parser.Parser):
    # In KQL, | is the pipe operator, not bitwise OR
    BITWISE = {
        TokenType.AMP: exp.BitwiseAnd,
        TokenType.CARET: exp.BitwiseXor,
    }

    # KQL uses extract(regex, group, text), not SQL EXTRACT(part FROM expr)
    # AGO takes KQL timespan literals like ago(1d), ago(6h)
    FUNCTION_PARSERS = {
        **{
            k: v
            for k, v in parser.Parser.FUNCTION_PARSERS.items()
            if k not in ("EXTRACT", "TRIM", "SUBSTRING")
        },
        "AGO": lambda self: self._parse_kql_ago(),
        "BIN": lambda self: self._parse_kql_bin(),
    }

    CONJUNCTION = {
        **parser.Parser.CONJUNCTION,
        TokenType.AND: exp.And,
    }

    DISJUNCTION = {
        **parser.Parser.DISJUNCTION,
        TokenType.OR: exp.Or,
    }

    TRANSFORM_PARSERS = {
        "WHERE": lambda self, query: query.where(self._parse_kql_condition(), copy=False),
        "PROJECT": lambda self, query: self._parse_project(query),
        "EXTEND": lambda self, query: self._parse_extend(query),
        "SUMMARIZE": lambda self, query: self._parse_summarize(query),
        "SORT BY": lambda self, query: self._parse_sort_by(query),
        "ORDER BY": lambda self, query: self._parse_sort_by(query),
        "SORT": lambda self, query: self._parse_sort_by(query),
        "ORDER": lambda self, query: self._parse_sort_by(query),
        "TAKE": lambda self, query: query.limit(self._parse_number(), copy=False),
        "LIMIT": lambda self, query: query.limit(self._parse_number(), copy=False),
        "JOIN": lambda self, query: self._parse_kql_join(query),
        "DISTINCT": lambda self, query: self._parse_kql_distinct(query),
        "TOP": lambda self, query: self._parse_kql_top(query),
        "COUNT": lambda self, query: self._parse_kql_count(query),
    }

    FUNCTIONS = {
        **parser.Parser.FUNCTIONS,
        # Aggregation
        "COUNT": lambda args: exp.Count(this=seq_get(args, 0) or exp.Star()),
        "DCOUNT": lambda args: exp.ApproxDistinct(this=seq_get(args, 0)),
        "COUNTIF": lambda args: exp.CountIf(this=seq_get(args, 0)),
        "SUMIF": lambda args: exp.func(
            "SUM", exp.If(this=seq_get(args, 1), true=seq_get(args, 0), false=exp.Null())
        ),
        "PERCENTILE": lambda args: exp.PercentileCont(
            this=seq_get(args, 0), expression=seq_get(args, 1)
        ),
        "MAKE_LIST": lambda args: exp.ArrayAgg(this=seq_get(args, 0)),
        "MAKE_SET": lambda args: exp.ArrayUniqueAgg(this=seq_get(args, 0)),
        # String
        "STRLEN": lambda args: exp.Length(this=seq_get(args, 0)),
        "TOLOWER": lambda args: exp.Lower(this=seq_get(args, 0)),
        "TOUPPER": lambda args: exp.Upper(this=seq_get(args, 0)),
        "STRCAT": lambda args: exp.Concat(expressions=args),
        "STRCAT_DELIM": lambda args: exp.ConcatWs(expressions=args),
        "SUBSTRING": lambda args: exp.Substring(
            this=seq_get(args, 0), start=seq_get(args, 1), length=seq_get(args, 2)
        ),
        "INDEXOF": lambda args: exp.StrPosition(this=seq_get(args, 0), substr=seq_get(args, 1)),
        "REPLACE": lambda args: exp.func(
            "REPLACE", seq_get(args, 0), seq_get(args, 1), seq_get(args, 2)
        ),
        "TRIM": lambda args: exp.Trim(this=seq_get(args, 0)),
        "TRIM_START": lambda args: exp.Trim(this=seq_get(args, 0), position="LEADING"),
        "TRIM_END": lambda args: exp.Trim(this=seq_get(args, 0), position="TRAILING"),
        "SPLIT": lambda args: exp.Split(this=seq_get(args, 0), expression=seq_get(args, 1)),
        "EXTRACT": lambda args: exp.RegexpExtract(
            this=seq_get(args, 2), expression=seq_get(args, 0), group=seq_get(args, 1)
        ),
        "REVERSE": lambda args: exp.func("REVERSE", seq_get(args, 0)),
        "COUNTOF": lambda args: exp.func("REGEXP_COUNT", seq_get(args, 0), seq_get(args, 1)),
        # Type conversions
        "TOSTRING": lambda args: exp.Cast(this=seq_get(args, 0), to=exp.DataType.build("TEXT")),
        "TOINT": lambda args: exp.Cast(this=seq_get(args, 0), to=exp.DataType.build("INT")),
        "TOLONG": lambda args: exp.Cast(this=seq_get(args, 0), to=exp.DataType.build("BIGINT")),
        "TOREAL": lambda args: exp.Cast(this=seq_get(args, 0), to=exp.DataType.build("DOUBLE")),
        "TODECIMAL": lambda args: exp.Cast(this=seq_get(args, 0), to=exp.DataType.build("DECIMAL")),
        "TOBOOL": lambda args: exp.Cast(this=seq_get(args, 0), to=exp.DataType.build("BOOLEAN")),
        "TODATETIME": lambda args: exp.Cast(
            this=seq_get(args, 0), to=exp.DataType.build("TIMESTAMPTZ")
        ),
        "TOTIMESPAN": lambda args: exp.Cast(
            this=seq_get(args, 0), to=exp.DataType.build("INTERVAL")
        ),
        # Datetime
        "NOW": lambda args: exp.CurrentTimestamp(),
        "DATETIME_DIFF": lambda args: exp.DatetimeDiff(
            unit=seq_get(args, 0), this=seq_get(args, 1), expression=seq_get(args, 2)
        ),
        "DATETIME_ADD": lambda args: exp.DatetimeAdd(
            unit=seq_get(args, 0), expression=seq_get(args, 1), this=seq_get(args, 2)
        ),
        "DATETIME_PART": lambda args: exp.Extract(
            this=seq_get(args, 0), expression=seq_get(args, 1)
        ),
        "FORMAT_DATETIME": lambda args: exp.TimeToStr(
            this=seq_get(args, 0), format=seq_get(args, 1)
        ),
        "STARTOFDAY": lambda args: exp.DateTrunc(
            unit=exp.Literal.string("DAY"), this=seq_get(args, 0)
        ),
        "STARTOFMONTH": lambda args: exp.DateTrunc(
            unit=exp.Literal.string("MONTH"), this=seq_get(args, 0)
        ),
        "STARTOFYEAR": lambda args: exp.DateTrunc(
            unit=exp.Literal.string("YEAR"), this=seq_get(args, 0)
        ),
        "STARTOFWEEK": lambda args: exp.DateTrunc(
            unit=exp.Literal.string("WEEK"), this=seq_get(args, 0)
        ),
        "UNIXTIME_SECONDS_TODATETIME": lambda args: exp.UnixToTime(
            this=seq_get(args, 0), scale=exp.UnixToTime.SECONDS
        ),
        "UNIXTIME_MILLISECONDS_TODATETIME": lambda args: exp.UnixToTime(
            this=seq_get(args, 0), scale=exp.UnixToTime.MILLIS
        ),
        # Conditional
        "IFF": lambda args: exp.If(
            this=seq_get(args, 0), true=seq_get(args, 1), false=seq_get(args, 2)
        ),
        "COALESCE": lambda args: exp.Coalesce(
            this=seq_get(args, 0), expressions=args[1:] if args else []
        ),
        # Null / empty checks
        "ISNULL": lambda args: exp.Is(this=seq_get(args, 0), expression=exp.Null()),
        "ISNOTNULL": lambda args: exp.Is(
            this=seq_get(args, 0), expression=exp.Not(this=exp.Null())
        ),
        "ISNOTEMPTY": lambda args: exp.NEQ(
            this=seq_get(args, 0), expression=exp.Literal.string("")
        ),
        "ISEMPTY": lambda args: exp.EQ(this=seq_get(args, 0), expression=exp.Literal.string("")),
        # Math
        "ABS": lambda args: exp.Abs(this=seq_get(args, 0)),
        "CEILING": lambda args: exp.Ceil(this=seq_get(args, 0)),
        "FLOOR": lambda args: exp.Floor(this=seq_get(args, 0)),
        "ROUND": lambda args: exp.Round(this=seq_get(args, 0), decimals=seq_get(args, 1)),
        "LOG": lambda args: exp.Ln(this=seq_get(args, 0)),
        "LOG10": lambda args: exp.Log(this=exp.Literal.number(10), expression=seq_get(args, 0)),
        "LOG2": lambda args: exp.Log(this=exp.Literal.number(2), expression=seq_get(args, 0)),
        "POW": lambda args: exp.Pow(this=seq_get(args, 0), expression=seq_get(args, 1)),
        "SQRT": lambda args: exp.Sqrt(this=seq_get(args, 0)),
        "EXP": lambda args: exp.Exp(this=seq_get(args, 0)),
        "EXP10": lambda args: exp.Pow(this=exp.Literal.number(10), expression=seq_get(args, 0)),
        "SIGN": lambda args: exp.func("SIGN", seq_get(args, 0)),
        # Array
        "ARRAY_LENGTH": lambda args: exp.ArraySize(this=seq_get(args, 0)),
        "ARRAY_SORT_ASC": lambda args: exp.ArraySort(this=seq_get(args, 0)),
        # Hash
        "HASH": lambda args: exp.MD5(this=seq_get(args, 0)),
        "HASH_SHA256": lambda args: exp.SHA2(this=seq_get(args, 0), length=exp.Literal.number(256)),
        # Window
        "ROW_NUMBER": lambda args: exp.RowNumber(),
        "PREV": lambda args: exp.Lag(this=seq_get(args, 0)),
        "NEXT": lambda args: exp.Lead(this=seq_get(args, 0)),
        "ROW_RANK": lambda args: exp.Rank(),
    }

    def _parse_equality(self) -> t.Optional[exp.Expr]:
        eq = self._parse_comparison()

        while self._match_set(self.EQUALITY):
            comments = self._prev_comments
            eq = self.expression(
                self.EQUALITY[self._prev.token_type](this=eq, expression=self._parse_comparison()),
                comments=comments,
            )

        if not isinstance(eq, (exp.EQ, exp.NEQ)):
            return eq

        # Handle null comparison like PRQL
        if isinstance(eq.expression, exp.Null):
            is_exp = exp.Is(this=eq.this, expression=eq.expression)
            return is_exp if isinstance(eq, exp.EQ) else exp.Not(this=is_exp)
        if isinstance(eq.this, exp.Null):
            is_exp = exp.Is(this=eq.expression, expression=eq.this)
            return is_exp if isinstance(eq, exp.EQ) else exp.Not(this=is_exp)
        return eq

    def _parse_kql_timespan(self) -> exp.Interval:
        """Parse KQL timespan literal like 1d, 6h, 30m, 10s, 100ms."""
        num = self._parse_number()
        if not num:
            self.raise_error("Expected number in timespan literal")
            return exp.Interval(this=exp.Literal.number(0), unit=exp.Var(this="DAY"))

        unit_text = ""
        if self._curr and self._curr.token_type == TokenType.VAR:
            unit_text = self._curr.text.upper()
            self._advance()

        sql_unit = KQL_TIMESPAN_UNITS.get(unit_text, "DAY")
        return exp.Interval(this=num, unit=exp.Var(this=sql_unit))

    def _parse_kql_ago(self) -> exp.Sub:
        """Parse ago(timespan) → CURRENT_TIMESTAMP - INTERVAL N UNIT."""
        self._match(TokenType.L_PAREN)
        interval = self._parse_kql_timespan()
        self._match(TokenType.R_PAREN)
        return exp.Sub(this=exp.CurrentTimestamp(), expression=interval)

    def _parse_kql_bin(self) -> exp.DateTrunc:
        """Parse bin(column, timespan) → DATE_TRUNC(unit, column)."""
        self._match(TokenType.L_PAREN)
        column = self._parse_disjunction()
        self._match(TokenType.COMMA)
        interval = self._parse_kql_timespan()
        self._match(TokenType.R_PAREN)
        unit = interval.args.get("unit")
        return exp.DateTrunc(unit=exp.Literal.string(unit.name if unit else "DAY"), this=column)

    def _parse_statement(self) -> t.Optional[exp.Expr]:
        return self._parse_query() or self._parse_expression()

    def _parse_query(self) -> t.Optional[exp.Query]:
        table = self._parse_table_parts()
        if not table:
            return None

        query: exp.Query = exp.select("*").from_(table, copy=False)

        while self._match(TokenType.PIPE):
            if not self._match_texts(self.TRANSFORM_PARSERS):
                self.raise_error("Expected KQL operator after |")
                break
            query = self.TRANSFORM_PARSERS[self._prev.text.upper()](self, query)

        return query

    def _parse_kql_condition(self) -> t.Optional[exp.Expr]:
        """Parse a KQL condition, handling KQL string operators."""
        left = self._parse_disjunction()
        return self._parse_kql_string_op(left) if left else left

    def _parse_kql_string_op(self, left: exp.Expr) -> exp.Expr:
        """Parse KQL infix string operators like contains, has, startswith, endswith."""
        text = self._curr.text.upper() if self._curr else ""

        if text in ("CONTAINS", "CONTAINS_CS"):
            self._advance()
            right = self._parse_primary()
            return exp.func("CONTAINS", left, right)
        elif text == "!CONTAINS" or text == "!CONTAINS_CS":
            self._advance()
            right = self._parse_primary()
            return exp.Not(this=exp.func("CONTAINS", left, right))
        elif text in ("HAS", "HAS_CS"):
            self._advance()
            right = self._parse_primary()
            return exp.func("CONTAINS", left, right)
        elif text == "!HAS" or text == "!HAS_CS":
            self._advance()
            right = self._parse_primary()
            return exp.Not(this=exp.func("CONTAINS", left, right))
        elif text in ("STARTSWITH", "STARTSWITH_CS"):
            self._advance()
            right = self._parse_primary()
            return exp.func("STARTS_WITH", left, right)
        elif text == "!STARTSWITH":
            self._advance()
            right = self._parse_primary()
            return exp.Not(this=exp.func("STARTS_WITH", left, right))
        elif text in ("ENDSWITH", "ENDSWITH_CS"):
            self._advance()
            right = self._parse_primary()
            return exp.func("ENDS_WITH", left, right)
        elif text == "!ENDSWITH":
            self._advance()
            right = self._parse_primary()
            return exp.Not(this=exp.func("ENDS_WITH", left, right))
        elif text == "MATCHES":
            self._advance()
            # expect "regex" keyword after "matches"
            if self._curr and self._curr.text.upper() == "REGEX":
                self._advance()
            right = self._parse_primary()
            return exp.RegexpLike(this=left, expression=right)
        elif text == "!MATCHES":
            self._advance()
            if self._curr and self._curr.text.upper() == "REGEX":
                self._advance()
            right = self._parse_primary()
            return exp.Not(this=exp.RegexpLike(this=left, expression=right))
        elif text == "BETWEEN":
            self._advance()
            # KQL between uses ( start .. end )
            self._match(TokenType.L_PAREN)
            low = self._parse_primary()
            self._match_text_seq("..")
            high = self._parse_primary()
            self._match(TokenType.R_PAREN)
            return exp.Between(this=left, low=low, high=high)
        elif text == "IN":
            self._advance()
            self._match(TokenType.L_PAREN)
            values = self._parse_csv(self._parse_primary)
            self._match(TokenType.R_PAREN)
            return exp.In(this=left, expressions=values)
        elif text == "!IN":
            self._advance()
            self._match(TokenType.L_PAREN)
            values = self._parse_csv(self._parse_primary)
            self._match(TokenType.R_PAREN)
            return exp.Not(this=exp.In(this=left, expressions=values))

        return left

    def _parse_kql_alias_expr(self) -> t.Optional[exp.Expr]:
        """Parse a KQL expression that may have an alias via =."""
        if self._next and self._next.token_type == TokenType.EQ:
            alias = self._parse_id_var(any_token=True)
            self._match(TokenType.EQ)
            return self.expression(exp.Alias(this=self._parse_disjunction(), alias=alias))
        return self._parse_disjunction()

    def _parse_project(self, query: exp.Query) -> exp.Query:
        """Parse: project col1, col2, alias = expr, ..."""
        selects = self._parse_csv(self._parse_kql_alias_expr)
        return query.select(*selects, append=False, copy=False)

    def _parse_extend(self, query: exp.Query) -> exp.Query:
        """Parse: extend alias = expr, ..."""
        selects = self._parse_csv(self._parse_kql_alias_expr)
        return query.select(*selects, append=True, copy=False)

    def _parse_summarize(self, query: exp.Query) -> exp.Query:
        """Parse: summarize agg1, agg2 by col1, col2"""
        agg_exprs = []
        while self._curr and not (
            self._curr.text.upper() == "BY"
            or self._curr.token_type == TokenType.PIPE
            or self._curr.token_type == TokenType.SEMICOLON
        ):
            expr = self._parse_kql_alias_expr()
            if expr:
                # Auto-alias unaliased aggregations with the function name
                if not isinstance(expr, exp.Alias) and isinstance(expr, exp.Func):
                    alias_name = expr.sql_name().lower()
                    expr = exp.Alias(this=expr, alias=exp.to_identifier(alias_name))
                agg_exprs.append(expr)
            if not self._match(TokenType.COMMA):
                break

        by_exprs: t.List[exp.Expr] = []
        if self._match_text_seq("BY"):
            by_exprs = self._parse_csv(self._parse_kql_alias_expr)

        all_selects = [*agg_exprs, *by_exprs]
        result: exp.Select = query.select(*all_selects, append=False, copy=False)  # type: ignore
        if by_exprs:
            group_cols: t.List[t.Union[str, exp.Expr]] = []
            for by_expr in by_exprs:
                if isinstance(by_expr, exp.Alias):
                    group_cols.append(by_expr.alias)
                else:
                    group_cols.append(by_expr)
            result = result.group_by(*group_cols, copy=False)
        return result

    def _parse_sort_by(self, query: exp.Query) -> exp.Query:
        """Parse: sort by col1 asc, col2 desc"""
        self._match_text_seq("BY")

        expressions = self._parse_csv(self._parse_kql_ordered)
        return query.order_by(self.expression(exp.Order(expressions=expressions)), copy=False)

    def _parse_kql_ordered(
        self, parse_method: t.Optional[t.Callable] = None
    ) -> t.Optional[exp.Ordered]:
        expr = self._parse_disjunction()
        if not expr:
            return None

        desc = None
        nulls_first = True

        if self._curr and self._curr.text.upper() == "DESC":
            self._advance()
            desc = True
            nulls_first = False
        elif self._curr and self._curr.text.upper() == "ASC":
            self._advance()
            desc = False
            nulls_first = True

        if self._match_text_seq("NULLS"):
            if self._match_text_seq("FIRST"):
                nulls_first = True
            elif self._match_text_seq("LAST"):
                nulls_first = False

        return self.expression(exp.Ordered(this=expr, desc=desc, nulls_first=nulls_first))

    def _parse_kql_join(self, query: exp.Query) -> exp.Query:
        """Parse: join kind=inner Table on Col"""
        join_type = ""
        if self._match_text_seq("KIND", "="):
            kind_text = self._curr.text.upper() if self._curr else "INNER"
            join_type = KQL_JOIN_KINDS.get(kind_text, "")
            self._advance()

        table = self._parse_table_parts()
        if not table:
            self.raise_error("Expected table name after join")
            return query

        on_condition: t.Optional[exp.Expr] = None
        if self._match(TokenType.ON):
            on_condition = self._parse_disjunction()

        return query.join(table, on=on_condition, join_type=join_type, copy=False)  # type: ignore

    def _parse_kql_distinct(self, query: exp.Query) -> exp.Query:
        """Parse: distinct col1, col2"""
        selects = self._parse_csv(self._parse_kql_alias_expr)
        result = query.select(*selects, append=False, copy=False)
        result.args["distinct"] = exp.Distinct()
        return result

    def _parse_kql_top(self, query: exp.Query) -> exp.Query:
        """Parse: top N by col [asc|desc]"""
        num = self._parse_number()
        self._match_text_seq("BY")
        order_exprs = self._parse_csv(self._parse_kql_ordered)
        result = query.limit(num or 0, copy=False)
        return result.order_by(self.expression(exp.Order(expressions=order_exprs)), copy=False)

    def _parse_kql_count(self, query: exp.Query) -> exp.Query:
        """Parse standalone count operator."""
        return query.select(
            exp.Alias(this=exp.Count(this=exp.Star()), alias=exp.to_identifier("Count")),
            append=False,
            copy=False,
        )

    def _parse_table(
        self,
        schema: bool = False,
        joins: bool = False,
        alias_tokens: t.Optional[Collection[TokenType]] = None,
        parse_bracket: bool = False,
        is_db_reference: bool = False,
        parse_partition: bool = False,
        consume_pipe: bool = False,
    ) -> t.Optional[exp.Expr]:
        return self._parse_table_parts()

    def _parse_from(
        self,
        joins: bool = False,
        skip_from_token: bool = False,
        consume_pipe: bool = False,
    ) -> t.Optional[exp.From]:
        if not skip_from_token and not self._match(TokenType.FROM):
            return None

        comments = self._prev_comments
        return self.expression(
            exp.From(this=self._parse_table(joins=joins)),
            comments=comments,
        )
