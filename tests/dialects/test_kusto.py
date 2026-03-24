from tests.dialects.test_dialect import Validator


class TestKusto(Validator):
    dialect = "kusto"

    def test_basic_query(self):
        self.validate_all(
            "Logs",
            write={
                "": "SELECT * FROM Logs",
            },
        )

    def test_project(self):
        self.validate_all(
            "Logs | project Name, Age",
            write={
                "": "SELECT Name, Age FROM Logs",
            },
        )
        self.validate_all(
            "Logs | project FullName = Name, Age",
            write={
                "": "SELECT Name AS FullName, Age FROM Logs",
            },
        )

    def test_where(self):
        self.validate_all(
            "Logs | where Level == 'Error'",
            write={
                "": "SELECT * FROM Logs WHERE Level = 'Error'",
            },
        )
        self.validate_all(
            "Logs | where Age > 25",
            write={
                "": "SELECT * FROM Logs WHERE Age > 25",
            },
        )
        self.validate_all(
            "Logs | where Age > 25 and Level == 'Error'",
            write={
                "": "SELECT * FROM Logs WHERE Age > 25 AND Level = 'Error'",
            },
        )
        self.validate_all(
            "Logs | where Age > 25 or Age < 10",
            write={
                "": "SELECT * FROM Logs WHERE Age > 25 OR Age < 10",
            },
        )

    def test_where_and_project(self):
        self.validate_all(
            "Logs | where Level == 'Error' | project Timestamp, Message",
            write={
                "": "SELECT Timestamp, Message FROM Logs WHERE Level = 'Error'",
            },
        )

    def test_take(self):
        self.validate_all(
            "Logs | take 10",
            write={
                "": "SELECT * FROM Logs LIMIT 10",
            },
        )
        self.validate_all(
            "Logs | limit 5",
            write={
                "": "SELECT * FROM Logs LIMIT 5",
            },
        )

    def test_sort_by(self):
        self.validate_all(
            "Logs | sort by Timestamp desc",
            write={
                "": "SELECT * FROM Logs ORDER BY Timestamp DESC",
            },
        )
        self.validate_all(
            "Logs | sort by Timestamp asc",
            write={
                "": "SELECT * FROM Logs ORDER BY Timestamp ASC",
            },
        )
        self.validate_all(
            "Logs | order by Name",
            write={
                "": "SELECT * FROM Logs ORDER BY Name",
            },
        )

    def test_extend(self):
        self.validate_all(
            "Logs | extend MsgLen = strlen(Message)",
            write={
                "": "SELECT *, LENGTH(Message) AS MsgLen FROM Logs",
            },
        )

    def test_summarize(self):
        self.validate_all(
            "Logs | summarize count() by UserId",
            write={
                "": "SELECT COUNT(*) AS count, UserId FROM Logs GROUP BY UserId",
            },
        )
        self.validate_all(
            "Logs | summarize Total = count() by Region",
            write={
                "": "SELECT COUNT(*) AS Total, Region FROM Logs GROUP BY Region",
            },
        )
        self.validate_all(
            "Logs | summarize AvgAge = avg(Age), Total = count() by Department",
            write={
                "": "SELECT AVG(Age) AS AvgAge, COUNT(*) AS Total, Department FROM Logs GROUP BY Department",
            },
        )

    def test_join(self):
        self.validate_all(
            "Errors | join kind=inner Users on UserId",
            write={
                "": "SELECT * FROM Errors JOIN Users ON UserId",
            },
        )
        self.validate_all(
            "Errors | join kind=leftouter Users on UserId",
            write={
                "": "SELECT * FROM Errors LEFT JOIN Users ON UserId",
            },
        )

    def test_distinct(self):
        self.validate_all(
            "Logs | distinct Level",
            write={
                "": "SELECT DISTINCT Level FROM Logs",
            },
        )

    def test_top(self):
        self.validate_all(
            "Logs | top 5 by Timestamp desc",
            write={
                "": "SELECT * FROM Logs ORDER BY Timestamp DESC LIMIT 5",
            },
        )

    def test_count_operator(self):
        self.validate_all(
            "Logs | count",
            write={
                "": "SELECT COUNT(*) AS Count FROM Logs",
            },
        )

    def test_kql_functions(self):
        self.validate_all(
            "Logs | project Lower = tolower(Name)",
            write={
                "": "SELECT LOWER(Name) AS Lower FROM Logs",
            },
        )
        self.validate_all(
            "Logs | project Upper = toupper(Name)",
            write={
                "": "SELECT UPPER(Name) AS Upper FROM Logs",
            },
        )
        self.validate_all(
            "Logs | project Len = strlen(Message)",
            write={
                "": "SELECT LENGTH(Message) AS Len FROM Logs",
            },
        )
        self.validate_all(
            "Logs | project dcount(UserId)",
            write={
                "": "SELECT APPROX_DISTINCT(UserId) FROM Logs",
            },
        )

    def test_type_conversion_functions(self):
        self.validate_all(
            "T | project tostring(x)",
            write={
                "": "SELECT CAST(x AS TEXT) FROM T",
            },
        )
        self.validate_all(
            "T | project toint(x)",
            write={
                "": "SELECT CAST(x AS INT) FROM T",
            },
        )
        self.validate_all(
            "T | project tolong(x)",
            write={
                "": "SELECT CAST(x AS BIGINT) FROM T",
            },
        )
        self.validate_all(
            "T | project toreal(x)",
            write={
                "": "SELECT CAST(x AS DOUBLE) FROM T",
            },
        )
        self.validate_all(
            "T | project tobool(x)",
            write={
                "": "SELECT CAST(x AS BOOLEAN) FROM T",
            },
        )
        self.validate_all(
            "T | project todatetime(x)",
            write={
                "": "SELECT CAST(x AS TIMESTAMPTZ) FROM T",
            },
        )

    def test_string_functions(self):
        self.validate_all(
            "T | project strcat(a, b, c)",
            write={
                "": "SELECT CONCAT(a, b, c) FROM T",
            },
        )
        self.validate_all(
            "T | project substring(s, 1, 3)",
            write={
                "": "SELECT SUBSTRING(s, 1, 3) FROM T",
            },
        )
        self.validate_all(
            "T | project indexof(s, 'abc')",
            write={
                "": "SELECT STR_POSITION(s, 'abc') FROM T",
            },
        )
        self.validate_all(
            "T | project trim(s)",
            write={
                "": "SELECT TRIM(s) FROM T",
            },
        )
        self.validate_all(
            "T | project replace(s, 'a', 'b')",
            write={
                "": "SELECT REPLACE(s, 'a', 'b') FROM T",
            },
        )

    def test_aggregation_functions(self):
        self.validate_all(
            "T | summarize dcount(UserId)",
            write={
                "": "SELECT APPROX_DISTINCT(UserId) AS approx_distinct FROM T",
            },
        )
        self.validate_all(
            "T | summarize countif(Level == 'Error')",
            write={
                "": "SELECT COUNT_IF(Level = 'Error') AS count_if FROM T",
            },
        )
        self.validate_all(
            "T | summarize count(x)",
            write={
                "": "SELECT COUNT(x) AS count FROM T",
            },
        )
        self.validate_all(
            "T | summarize avg(Age) by Department",
            write={
                "": "SELECT AVG(Age) AS avg, Department FROM T GROUP BY Department",
            },
        )
        self.validate_all(
            "T | summarize min(Age), max(Age)",
            write={
                "": "SELECT MIN(Age) AS min, MAX(Age) AS max FROM T",
            },
        )
        self.validate_all(
            "T | summarize sum(Amount) by Region",
            write={
                "": "SELECT SUM(Amount) AS sum, Region FROM T GROUP BY Region",
            },
        )

    def test_null_and_empty_checks(self):
        self.validate_all(
            "T | where isnull(x)",
            write={
                "": "SELECT * FROM T WHERE x IS NULL",
            },
        )
        self.validate_all(
            "T | where isempty(x)",
            write={
                "": "SELECT * FROM T WHERE x = ''",
            },
        )
        self.validate_all(
            "T | where isnotempty(x)",
            write={
                "": "SELECT * FROM T WHERE x <> ''",
            },
        )

    def test_datetime_functions(self):
        self.validate_all(
            "T | project now()",
            write={
                "": "SELECT CURRENT_TIMESTAMP() FROM T",
            },
        )
        self.validate_all(
            "T | where ts > ago(1d)",
            write={
                "": "SELECT * FROM T WHERE ts > CURRENT_TIMESTAMP() - INTERVAL 1 DAY",
            },
        )
        self.validate_all(
            "T | where ts > ago(6h)",
            write={
                "": "SELECT * FROM T WHERE ts > CURRENT_TIMESTAMP() - INTERVAL 6 HOUR",
            },
        )
        self.validate_all(
            "T | where ts > ago(30m)",
            write={
                "": "SELECT * FROM T WHERE ts > CURRENT_TIMESTAMP() - INTERVAL 30 MINUTE",
            },
        )
        self.validate_all(
            "T | where ts > ago(10s)",
            write={
                "": "SELECT * FROM T WHERE ts > CURRENT_TIMESTAMP() - INTERVAL 10 SECOND",
            },
        )
        self.validate_all(
            "T | where ts > ago(100ms)",
            write={
                "": "SELECT * FROM T WHERE ts > CURRENT_TIMESTAMP() - INTERVAL 100 MILLISECOND",
            },
        )
        self.validate_all(
            "T | project datetime_diff('day', dt1, dt2)",
            write={
                "": "SELECT DATETIME_DIFF(dt1, dt2, DAY) FROM T",
            },
        )
        self.validate_all(
            "T | project datetime_add('hour', 3, dt)",
            write={
                "": "SELECT DATETIME_ADD(dt, 3, HOUR) FROM T",
            },
        )
        self.validate_all(
            "T | project datetime_part('month', dt)",
            write={
                "": "SELECT EXTRACT('month' FROM dt) FROM T",
            },
        )
        self.validate_all(
            "T | project format_datetime(dt, 'yyyy-MM-dd')",
            write={
                "": "SELECT TIME_TO_STR(dt, 'yyyy-MM-dd') FROM T",
            },
        )
        self.validate_all(
            "T | project startofday(dt)",
            write={
                "": "SELECT DATE_TRUNC('DAY', dt) FROM T",
            },
        )
        self.validate_all(
            "T | project startofmonth(dt)",
            write={
                "": "SELECT DATE_TRUNC('MONTH', dt) FROM T",
            },
        )
        self.validate_all(
            "T | project startofyear(dt)",
            write={
                "": "SELECT DATE_TRUNC('YEAR', dt) FROM T",
            },
        )
        self.validate_all(
            "T | project startofweek(dt)",
            write={
                "": "SELECT DATE_TRUNC('WEEK', dt) FROM T",
            },
        )
        self.validate_all(
            "T | project unixtime_seconds_todatetime(ts)",
            write={
                "": "SELECT UNIX_TO_TIME(ts, 0) FROM T",
            },
        )
        self.validate_all(
            "T | project unixtime_milliseconds_todatetime(ts)",
            write={
                "": "SELECT UNIX_TO_TIME(ts, 3) FROM T",
            },
        )

    def test_bin_function(self):
        self.validate_all(
            "T | summarize count() by bin(ts, 1h)",
            write={
                "": "SELECT COUNT(*) AS count, DATE_TRUNC('HOUR', ts) FROM T GROUP BY DATE_TRUNC('HOUR', ts)",
            },
        )
        self.validate_all(
            "T | summarize count() by bin(ts, 1d)",
            write={
                "": "SELECT COUNT(*) AS count, DATE_TRUNC('DAY', ts) FROM T GROUP BY DATE_TRUNC('DAY', ts)",
            },
        )
        self.validate_all(
            "T | summarize count() by bin(ts, 1m)",
            write={
                "": "SELECT COUNT(*) AS count, DATE_TRUNC('MINUTE', ts) FROM T GROUP BY DATE_TRUNC('MINUTE', ts)",
            },
        )

    def test_array_functions(self):
        self.validate_all(
            "T | project array_length(arr)",
            write={
                "": "SELECT ARRAY_LENGTH(arr) FROM T",
            },
        )
        self.validate_all(
            "T | project array_sort_asc(arr)",
            write={
                "": "SELECT ARRAY_SORT(arr) FROM T",
            },
        )

    def test_conditional_functions(self):
        self.validate_all(
            "T | project iff(x > 0, 'pos', 'neg')",
            write={
                "": "SELECT CASE WHEN x > 0 THEN 'pos' ELSE 'neg' END FROM T",
            },
        )
        self.validate_all(
            "T | project coalesce(a, b, c)",
            write={
                "": "SELECT COALESCE(a, b, c) FROM T",
            },
        )

    def test_math_functions(self):
        self.validate_all(
            "T | project abs(x)",
            write={
                "": "SELECT ABS(x) FROM T",
            },
        )
        self.validate_all(
            "T | project ceiling(x)",
            write={
                "": "SELECT CEIL(x) FROM T",
            },
        )
        self.validate_all(
            "T | project floor(x)",
            write={
                "": "SELECT FLOOR(x) FROM T",
            },
        )
        self.validate_all(
            "T | project round(x, 2)",
            write={
                "": "SELECT ROUND(x, 2) FROM T",
            },
        )
        self.validate_all(
            "T | project log(x)",
            write={
                "": "SELECT LN(x) FROM T",
            },
        )
        self.validate_all(
            "T | project log10(x)",
            write={
                "": "SELECT LOG(10, x) FROM T",
            },
        )
        self.validate_all(
            "T | project log2(x)",
            write={
                "": "SELECT LOG(2, x) FROM T",
            },
        )
        self.validate_all(
            "T | project pow(x, 2)",
            write={
                "": "SELECT POWER(x, 2) FROM T",
            },
        )
        self.validate_all(
            "T | project sqrt(x)",
            write={
                "": "SELECT SQRT(x) FROM T",
            },
        )
        self.validate_all(
            "T | project exp(x)",
            write={
                "": "SELECT EXP(x) FROM T",
            },
        )
        self.validate_all(
            "T | project exp10(x)",
            write={
                "": "SELECT POWER(10, x) FROM T",
            },
        )
        self.validate_all(
            "T | project sign(x)",
            write={
                "": "SELECT SIGN(x) FROM T",
            },
        )

    def test_extended_string_functions(self):
        self.validate_all(
            "T | project strcat_delim('-', a, b, c)",
            write={
                "": "SELECT CONCAT_WS('-', a, b, c) FROM T",
            },
        )
        self.validate_all(
            "T | project split(s, ',')",
            write={
                "": "SELECT SPLIT(s, ',') FROM T",
            },
        )
        self.validate_all(
            "T | project extract('abc', 1, s)",
            write={
                "": "SELECT REGEXP_EXTRACT(s, 'abc', 1) FROM T",
            },
        )
        self.validate_all(
            "T | project trim_start(s)",
            write={
                "": "SELECT LTRIM(s) FROM T",
            },
        )
        self.validate_all(
            "T | project trim_end(s)",
            write={
                "": "SELECT RTRIM(s) FROM T",
            },
        )
        self.validate_all(
            "T | project reverse(s)",
            write={
                "": "SELECT REVERSE(s) FROM T",
            },
        )

    def test_extended_type_conversions(self):
        self.validate_all(
            "T | project todecimal(x)",
            write={
                "": "SELECT CAST(x AS DECIMAL) FROM T",
            },
        )
        self.validate_all(
            "T | project totimespan(x)",
            write={
                "": "SELECT CAST(x AS INTERVAL) FROM T",
            },
        )

    def test_extended_aggregation_functions(self):
        self.validate_all(
            "T | summarize percentile(x, 95)",
            write={
                "": "SELECT PERCENTILE_CONT(x, 95) AS percentile_cont FROM T",
            },
        )
        self.validate_all(
            "T | summarize make_list(x)",
            write={
                "": "SELECT ARRAY_AGG(x) AS array_agg FROM T",
            },
        )
        self.validate_all(
            "T | summarize make_set(x)",
            write={
                "": "SELECT ARRAY_UNIQUE_AGG(x) AS array_unique_agg FROM T",
            },
        )

    def test_hash_functions(self):
        self.validate_all(
            "T | project hash(x)",
            write={
                "": "SELECT MD5(x) FROM T",
            },
        )
        self.validate_all(
            "T | project hash_sha256(x)",
            write={
                "": "SELECT SHA2(x, 256) FROM T",
            },
        )

    def test_string_operators(self):
        self.validate_all(
            "Logs | where Message contains 'error'",
            write={
                "": "SELECT * FROM Logs WHERE CONTAINS(Message, 'error')",
            },
        )
        self.validate_all(
            "Logs | where Message startswith '/api/'",
            write={
                "": "SELECT * FROM Logs WHERE STARTS_WITH(Message, '/api/')",
            },
        )
        self.validate_all(
            "Logs | where Message endswith '.log'",
            write={
                "": "SELECT * FROM Logs WHERE ENDS_WITH(Message, '.log')",
            },
        )

    def test_chained_operators(self):
        self.validate_all(
            "Logs | where Level == 'Error' | project Timestamp, Message | sort by Timestamp desc | take 10",
            write={
                "": "SELECT Timestamp, Message FROM Logs WHERE Level = 'Error' ORDER BY Timestamp DESC LIMIT 10",
            },
        )

    def test_summarize_no_by(self):
        self.validate_all(
            "Logs | summarize Total = count()",
            write={
                "": "SELECT COUNT(*) AS Total FROM Logs",
            },
        )
