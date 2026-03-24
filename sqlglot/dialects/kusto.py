from __future__ import annotations

import typing as t

from sqlglot import exp, generator, tokens
from sqlglot.dialects.dialect import Dialect, rename_func
from sqlglot.parsers.kusto import KustoParser
from sqlglot.tokens import TokenType

SQL_UNIT_TO_KQL = {
    "DAY": "d",
    "HOUR": "h",
    "MINUTE": "m",
    "SECOND": "s",
    "MILLISECOND": "ms",
    "MICROSECOND": "us",
}

SQL_JOIN_TO_KQL_KIND: t.Dict[t.Tuple[t.Optional[str], t.Optional[str]], str] = {
    (None, None): "inner",
    ("LEFT", None): "leftouter",
    ("RIGHT", None): "rightouter",
    ("", None): "inner",
    ("LEFT", "OUTER"): "leftouter",
    ("RIGHT", "OUTER"): "rightouter",
    ("", "OUTER"): "fullouter",
    ("FULL", None): "fullouter",
}


class Kusto(Dialect):
    DPIPE_IS_STRING_CONCAT = False
    NORMALIZE_FUNCTIONS: bool | str = "lower"

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

    class Generator(generator.Generator):
        TRANSFORMS = {
            **generator.Generator.TRANSFORMS,
            exp.ApproxDistinct: rename_func("dcount"),
            exp.ArrayAgg: rename_func("make_list"),
            exp.ArrayUniqueAgg: rename_func("make_set"),
            exp.ArraySize: rename_func("array_length"),
            exp.Ceil: rename_func("ceiling"),
            exp.Concat: rename_func("strcat"),
            exp.ConcatWs: rename_func("strcat_delim"),
            exp.CountIf: rename_func("countif"),
            exp.Exp: rename_func("exp"),
            exp.Lag: rename_func("prev"),
            exp.Lead: rename_func("next"),
            exp.Length: rename_func("strlen"),
            exp.Ln: rename_func("log"),
            exp.Lower: rename_func("tolower"),
            exp.MD5: rename_func("hash"),
            exp.Rank: lambda self, e: "row_rank()",
            exp.RegexpLike: rename_func("matches regex"),
            exp.RowNumber: lambda self, e: "row_number()",
            exp.Split: rename_func("split"),
            exp.Sqrt: rename_func("sqrt"),
            exp.StrPosition: rename_func("indexof"),
            exp.Trim: lambda self, e: self._kql_trim_sql(e),
            exp.Upper: rename_func("toupper"),
        }

        def _kql_trim_sql(self, expression: exp.Trim) -> str:
            this = self.sql(expression, "this")
            pos = expression.args.get("position")
            if pos == "LEADING":
                return f"trim_start({this})"
            elif pos == "TRAILING":
                return f"trim_end({this})"
            return f"trim({this})"

        def select_sql(self, expression: exp.Select) -> str:
            from_ = expression.args.get("from_")
            table = self.sql(from_.this) if from_ else ""

            sep = "\n| " if self.pretty else " | "

            # SELECT expressions / GROUP BY / DISTINCT
            group = expression.args.get("group")
            distinct = expression.args.get("distinct")
            exprs = expression.expressions
            where = expression.args.get("where")
            order = expression.args.get("order")
            limit = expression.args.get("limit")
            joins = expression.args.get("joins")

            is_star = len(exprs) == 1 and isinstance(exprs[0], exp.Star)
            has_kql_ops = where or group or order or limit or joins or distinct or not is_star

            # Fall back to base SQL generation for plain SELECT * FROM t
            if not has_kql_ops:
                return super().select_sql(expression)

            parts = [table]

            # JOIN
            for join in joins or []:
                parts.append(self._kql_join(join))

            # WHERE
            if where:
                parts.append(f"where {self.sql(where, 'this')}")

            has_agg = any(
                isinstance(e.this if isinstance(e, exp.Alias) else e, exp.AggFunc) for e in exprs
            )

            if group:
                parts.append(self._kql_summarize(exprs, group))
            elif has_agg and not is_star:
                # summarize without by (e.g. summarize count())
                aggs = ", ".join(self.sql(e) for e in exprs)
                parts.append(f"summarize {aggs}")
            elif distinct:
                cols = ", ".join(self.sql(e) for e in exprs)
                parts.append(f"distinct {cols}")
            elif not is_star:
                cols = ", ".join(self.sql(e) for e in exprs)
                parts.append(f"project {cols}")

            # ORDER BY
            if order:
                order_exprs = ", ".join(self.sql(e) for e in order.expressions)
                parts.append(f"sort by {order_exprs}")

            # LIMIT
            if limit:
                limit_val = self.sql(limit.expression)
                parts.append(f"take {limit_val}")

            return sep.join(parts)

        def _kql_summarize(self, exprs: t.List[exp.Expression], group: exp.Group) -> str:
            group_col_sqls = {self.sql(g) for g in group.expressions}

            aggs = []
            for e in exprs:
                sql = self.sql(e)
                col_sql = self.sql(e.args.get("alias")) if isinstance(e, exp.Alias) else sql
                if col_sql not in group_col_sqls:
                    aggs.append(sql)

            by_cols = ", ".join(self.sql(g) for g in group.expressions)
            agg_str = ", ".join(aggs)

            if agg_str and by_cols:
                return f"summarize {agg_str} by {by_cols}"
            elif agg_str:
                return f"summarize {agg_str}"
            else:
                return f"summarize by {by_cols}"

        def _kql_join(self, join: exp.Join) -> str:
            side = join.side
            kind = join.kind
            kql_kind = SQL_JOIN_TO_KQL_KIND.get((side, kind), "inner")
            table = self.sql(join.this)
            on = join.args.get("on")
            on_sql = f" on {self.sql(on)}" if on else ""
            return f"join kind={kql_kind} {table}{on_sql}"

        def alias_sql(self, expression: exp.Alias) -> str:
            alias = self.sql(expression, "alias")
            this = self.sql(expression, "this")
            return f"{alias} = {this}"

        def ordered_sql(self, expression: exp.Ordered) -> str:
            this = self.sql(expression, "this")
            desc = expression.args.get("desc")
            if desc is True:
                return f"{this} desc"
            elif desc is False:
                return f"{this} asc"
            return this

        def is_sql(self, expression: exp.Is) -> str:
            this = self.sql(expression, "this")
            expr = expression.expression
            if isinstance(expr, exp.Null):
                return f"isnull({this})"
            if isinstance(expr, exp.Not) and isinstance(expr.this, exp.Null):
                return f"isnotnull({this})"
            return f"{this} == {self.sql(expr)}"

        def not_sql(self, expression: exp.Not) -> str:
            inner = expression.this
            if isinstance(inner, exp.Is):
                inner_expr = inner.expression
                col = self.sql(inner, "this")
                if isinstance(inner_expr, exp.Null):
                    return f"isnotnull({col})"
            return f"not({self.sql(inner)})"

        def if_sql(self, expression: exp.If) -> str:
            this = self.sql(expression, "this")
            true = self.sql(expression, "true")
            false = self.sql(expression, "false")
            return f"iff({this}, {true}, {false})"

        def currenttimestamp_sql(self, expression: exp.CurrentTimestamp) -> str:
            return "now()"

        def cast_sql(self, expression: exp.Cast, safe_prefix: t.Optional[str] = None) -> str:
            this = self.sql(expression, "this")
            to = expression.to
            type_name = to.this.value if hasattr(to.this, "value") else str(to.this)

            type_map = {
                "TEXT": "tostring",
                "VARCHAR": "tostring",
                "INT": "toint",
                "BIGINT": "tolong",
                "DOUBLE": "toreal",
                "FLOAT": "toreal",
                "DECIMAL": "todecimal",
                "BOOLEAN": "tobool",
                "TIMESTAMPTZ": "todatetime",
                "TIMESTAMP": "todatetime",
                "INTERVAL": "totimespan",
            }
            func_name = type_map.get(type_name.upper(), f"to{type_name.lower()}")
            return f"{func_name}({this})"

        def datetrunc_sql(self, expression: exp.DateTrunc) -> str:
            unit = expression.args.get("unit")
            this = self.sql(expression, "this")
            unit_text = unit.name if unit and hasattr(unit, "name") else str(unit or "DAY")
            unit_upper = unit_text.strip("'").upper()

            startof_map = {
                "DAY": "startofday",
                "MONTH": "startofmonth",
                "YEAR": "startofyear",
                "WEEK": "startofweek",
            }
            if func := startof_map.get(unit_upper):
                return f"{func}({this})"

            kql_unit = SQL_UNIT_TO_KQL.get(unit_upper, unit_upper.lower()[0])
            return f"bin({this}, 1{kql_unit})"

        def sub_sql(self, expression: exp.Sub) -> str:
            if isinstance(expression.this, exp.CurrentTimestamp) and isinstance(
                expression.expression, exp.Interval
            ):
                interval = expression.expression
                num = self.sql(interval, "this")
                unit = interval.args.get("unit")
                unit_name = unit.name if unit else "DAY"
                kql_unit = SQL_UNIT_TO_KQL.get(unit_name.upper(), "d")
                return f"ago({num}{kql_unit})"
            return super().sub_sql(expression)

        def datetimeadd_sql(self, expression: exp.DatetimeAdd) -> str:
            unit = self.sql(expression, "unit")
            expr = self.sql(expression, "expression")
            this = self.sql(expression, "this")
            return f"datetime_add({unit}, {expr}, {this})"

        def datetimediff_sql(self, expression: exp.DatetimeDiff) -> str:
            unit = self.sql(expression, "unit")
            this = self.sql(expression, "this")
            expr = self.sql(expression, "expression")
            return f"datetime_diff({unit}, {this}, {expr})"

        def extract_sql(self, expression: exp.Extract) -> str:
            this = self.sql(expression, "this")
            expr = self.sql(expression, "expression")
            return f"datetime_part({this}, {expr})"

        def timetostr_sql(self, expression: exp.TimeToStr) -> str:
            this = self.sql(expression, "this")
            fmt = self.sql(expression, "format")
            return f"format_datetime({this}, {fmt})"

        def unixtotime_sql(self, expression: exp.UnixToTime) -> str:
            this = self.sql(expression, "this")
            scale = expression.args.get("scale")
            if scale == exp.UnixToTime.MILLIS:
                return f"unixtime_milliseconds_todatetime({this})"
            return f"unixtime_seconds_todatetime({this})"

        def count_sql(self, expression: exp.Count) -> str:
            this = expression.this
            if isinstance(this, exp.Star) or this is None:
                return "count()"
            return f"count({self.sql(this)})"

        def regexpextract_sql(self, expression: exp.RegexpExtract) -> str:
            this = self.sql(expression, "this")
            expr = self.sql(expression, "expression")
            group = self.sql(expression, "group")
            return f"extract({expr}, {group}, {this})"

        def log_sql(self, expression: exp.Log) -> str:
            this = expression.this
            expr = self.sql(expression, "expression")
            if isinstance(this, exp.Literal):
                base = this.to_py()
                if base == 10:
                    return f"log10({expr})"
                if base == 2:
                    return f"log2({expr})"
            return f"log({expr})"

        def pow_sql(self, expression: exp.Pow) -> str:
            this = expression.this
            expr = self.sql(expression, "expression")
            if isinstance(this, exp.Literal) and this.to_py() == 10:
                return f"exp10({expr})"
            return f"pow({self.sql(this)}, {expr})"

        def sha2_sql(self, expression: exp.SHA2) -> str:
            return f"hash_sha256({self.sql(expression, 'this')})"

        def abs_sql(self, expression: exp.Abs) -> str:
            return f"abs({self.sql(expression, 'this')})"

        def round_sql(self, expression: exp.Round) -> str:
            this = self.sql(expression, "this")
            decimals = expression.args.get("decimals")
            if decimals:
                return f"round({this}, {self.sql(decimals)})"
            return f"round({this})"

        def coalesce_sql(self, expression: exp.Coalesce) -> str:
            this = self.sql(expression, "this")
            rest = ", ".join(self.sql(e) for e in expression.expressions)
            if rest:
                return f"coalesce({this}, {rest})"
            return f"coalesce({this})"

        def percentilecont_sql(self, expression: exp.PercentileCont) -> str:
            this = self.sql(expression, "this")
            expr = self.sql(expression, "expression")
            return f"percentile({this}, {expr})"

        def eq_sql(self, expression: exp.EQ) -> str:
            return f"{self.sql(expression, 'this')} == {self.sql(expression, 'expression')}"

        def neq_sql(self, expression: exp.NEQ) -> str:
            return f"{self.sql(expression, 'this')} != {self.sql(expression, 'expression')}"
