 
from   humanfriendly import format_size
import pandas as pd
from   sqlalchemy import create_engine
import typer


def column_letter(n):
    string = ""

    while n > 0:
        n, remainder = divmod(n - 1, 26)
        string = chr(65 + remainder) + string

    return string


def build_month_distributions(engine, writer):
    sheet_name = 'Time Distributions'

    get_columns_sql = '''
        SELECT
            table_schema,
            table_name,
            column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND   (data_type = 'date'
               OR data_type LIKE 'timestamp%%');'''

    get_dist_sql = '''
        SELECT TO_CHAR("%s", 'YYYY-MM') AS yyyy_mm,
               COUNT(*) AS row_count
        FROM "%s"."%s"
        GROUP BY 1;'''

    results = engine.execute(get_columns_sql)

    out = {}

    for table_schema, table_name, column_name in results:
        result2 = engine.execute(get_dist_sql % (column_name,
                                                 table_schema,
                                                 table_name))

        for yyyy_mm, row_count in result2:
            if yyyy_mm not in out.keys():
                out[yyyy_mm] = {}

            out[yyyy_mm]['%s.%s' % (table_name, column_name)] = row_count

    df = pd.DataFrame(out)
    df = df.transpose().sort_index()

    df.to_excel(writer, sheet_name=sheet_name, index=True)
    num_rows, num_cols = df.shape

    # Format large numbers
    nice_numbers = writer.book.add_format({'num_format': '#,##0'})
    writer.sheets[sheet_name].set_column('B:%s' % column_letter(num_cols + 1),
                                         cell_format=nice_numbers)

    # Add an auto-filter
    bottom_right_ceil = '%s%d' % (column_letter(num_cols + 1), num_rows + 1)
    writer.sheets[sheet_name].autofilter('A1:%s' % bottom_right_ceil)

    # Add heat maps
    for col_num in range(1, num_cols + 2):
        range_ = '%s2:%s%d' % (column_letter(col_num),
                               column_letter(col_num),
                               num_rows + 1)
        writer.sheets[sheet_name]\
              .conditional_format(range_, {'type': '3_color_scale'})

    # Set column widths
    writer.sheets[sheet_name].set_column('A:%s' % column_letter(num_cols + 1),
                                         width=18)

    return writer


def build_metrics(engine, writer):
    sheet_name = 'Metrics'

    get_counts_sql = '''
        SELECT table_schema,
               table_name,
               (XPATH('/row/cnt/text()', xml_num_rows))[1]::text::int
                    AS num_rows,
               num_columns,
               num_bytes
        FROM (
          SELECT a.table_name,
                 a.table_schema,
                 QUERY_TO_XML(FORMAT('SELECT COUNT(*) AS cnt
                                      FROM %%I.%%I',
                                     a.table_schema,
                                     a.table_name),
                              false,
                              true,
                              '') AS xml_num_rows,
                 PG_RELATION_SIZE(quote_ident(a.table_name)) AS num_bytes,
                 (
                    SELECT count(*)
                    FROM   information_schema.columns b
                    WHERE  b.table_schema = a.table_schema
                    AND    b.table_name = a.table_name
                 ) AS num_columns
          FROM  information_schema.tables a
          WHERE table_schema = 'public'
        ) t
        ORDER BY num_bytes DESC;'''

    df = pd.read_sql_query(get_counts_sql, con=engine)

    # Add an extra column with the byte count in human-readable form
    df['size'] = df.apply(lambda row: format_size(row['num_bytes']),
                                axis=1)

    df.to_excel(writer, sheet_name=sheet_name, index=False)

    # Add an auto-filter
    writer.sheets[sheet_name].autofilter(0, 0, df.shape[0], 5)

    # Add heat maps
    for column_letter in ('C', 'D', 'E'):
        range_ = '%s2:%s%d' % (column_letter, column_letter, df.shape[0] + 1)
        writer.sheets[sheet_name]\
              .conditional_format(range_, {'type': '3_color_scale'})

    # Format large numbers
    nice_numbers = writer.book.add_format({'num_format': '#,##0'})
    right_align  = writer.book.add_format({'align': 'right'})

    writer.sheets[sheet_name].set_column('A:F', width=18)
    writer.sheets[sheet_name].set_column('C:E', cell_format=nice_numbers)
    writer.sheets[sheet_name].set_column('F:F', cell_format=right_align)

    return writer



def main(pg_dns = 'postgresql://postgres:juhari123@localhost:5432/postgres', output = 'fluency.xlsx'):
    engine =  create_engine(pg_dns)
    writer= pd.ExcelWriter(output, engine='xlsxwriter')
    writer = build_metrics(engine, writer)
    writer = build_month_distributions(engine, writer)
    writer.save()

if __name__  == "__main__":
    typer.run(main)