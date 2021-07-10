from sqlalchemy import create_engine

con=  create_engine('postgresql://postgres:juhari123@localhost:5432/postgres')

sql_order = con.execute("""
select * from airbnb_contact""").fetchall()
sql_order