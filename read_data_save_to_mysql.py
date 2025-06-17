# -*- coding: utf-8 -*-
import pandas as pd
import pymysql
import numpy as np

config =  {'user': 'root',
          'password': 'YOUR_MYSQL_PASSWORD',
          'port':3306,
          'host': '127.0.0.1',
          'db': 'Book',
          'charset':'utf8'}


class BookSqlTools:
    #链接MYSQL数据库
    #读取出来转化成pandas的dataframe格式

    def LinkMysql(self, sql):
        connection = None
        cur = None
        Main = pd.DataFrame() # 默认返回空的DataFrame
        try:
            connection = pymysql.connect(user=config['user'],
                                          password=config['password'],
                                          port=config['port'],
                                          host=config['host'],
                                          db=config['db'],
                                          charset=config['charset'])
            cur = connection.cursor()
            cur.execute(sql)
            result1 = cur.fetchall()
            if cur.description: # 确保 cur.description 不是 None
                title1 = [i[0] for i in cur.description]
                if result1:
                    Main = pd.DataFrame(list(result1), columns=title1)
                else:
                    Main = pd.DataFrame(columns=title1) # 返回带列名的空DataFrame
            # else: cur.description is None, e.g. for non-query SQL, Main remains empty.
            
        except Exception as e:
            print(f"LinkMysql error: {e}") # 更详细的错误信息
        finally:
            if cur:
                cur.close()
            if connection:
                connection.close()
        return Main
    

    # 修改后的 UpdateMysqlTable 方法
    def UpdateMysqlTable(self, df_data, sql_create_table, sql_insert_template, current_table_name):
        connection = None
        cursor = None
        
        # 定义特定列的最大长度 (可以根据需要为其他表和列添加规则)
        # 表名: {DataFrame中的列名: 数据库定义的最大长度}
        # 注意：这里的键是 DataFrame 中的列名
        column_max_lengths = {
            "User": {"Location": 100} 
            # 如果Books表的BookTitle也可能超长，且数据库定义VARCHAR(255)，可以添加：
            # "Books": {"Book-Title": 255} # 假设DataFrame中的列名是 'Book-Title'
        }

        try:
            connection = pymysql.connect(user=config['user'],
                                         password=config['password'],
                                         port=config['port'],
                                         host=config['host'],
                                         db=config['db'],
                                         charset=config['charset'])
            cursor = connection.cursor()
            
            try:
                cursor.execute(sql_create_table)
                connection.commit() 
            except Exception as e_create:
                # 检查是否是 "Table already exists" 错误 (MySQL error code 1050)
                if isinstance(e_create, pymysql.err.OperationalError) and e_create.args[0] == 1050:
                    print(f"Table for {current_table_name} already exists, skipping creation.")
                else:
                    print(f"Table creation/check error for {current_table_name} ({sql_create_table}): {e_create}")
                    connection.rollback() 
                    raise # 重新抛出错误，因为这可能是个严重问题

            records = df_data.to_dict(orient='records')
            
            # 获取DataFrame中的列名列表，确保我们按此顺序处理值
            # 这对于使用 .format({}) 来填充整个VALUES元组的SQL模板很重要
            df_column_order = list(df_data.columns)

            for record_dict in records:
                sql_ready_values = []
                
                for col_name_in_df in df_column_order: # 按DataFrame列的顺序获取值
                    value_from_df = record_dict[col_name_in_df]

                    if pd.isna(value_from_df):
                        sql_ready_values.append("NULL")
                    else:
                        current_value_str = str(value_from_df)
                        
                        # 应用截断规则
                        if current_table_name in column_max_lengths and \
                           col_name_in_df in column_max_lengths[current_table_name]:
                            max_len = column_max_lengths[current_table_name][col_name_in_df]
                            if len(current_value_str) > max_len:
                                current_value_str = current_value_str[:max_len] # 截断
                        
                        # 转义 SQL 特殊字符
                        escaped_value = current_value_str.replace("\\", "\\\\").replace("'", "''")
                        sql_ready_values.append(f"'{escaped_value}'")
                
                values_tuple_as_string_literal = f"({','.join(sql_ready_values)})"
                sql_command_text = sql_insert_template.format(values_tuple_as_string_literal)
                sql_bytes = sql_command_text.encode('utf-8')
                
                # print(sql_bytes.decode('utf-8', errors='replace')) # 用于调试

                try:
                    cursor.execute(sql_bytes)
                except Exception as e_insert:
                    # 打印包含原始数据和生成的SQL的更详细错误信息
                    print(f"MySQL insert fail for row {record_dict} with SQL {sql_command_text}: {e_insert}")
                    # 决定是否在这里回滚或继续；当前设计是尝试所有行然后批量提交
            
            connection.commit() # 提交所有成功的插入
            print(f"Data insertion attempted for table '{current_table_name}'. Check logs for any errors.")

        except Exception as e:
            if connection:
                connection.rollback()
            print(f"UpdateMysqlTable overall error for table '{current_table_name}': {e}")
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()




connection = pymysql.connect(user=config['user'],
                          password=config['password'],
                          port=config['port'],
                          host=config['host'],
                          charset=config['charset'])

cur = connection.cursor()
cur.execute('DROP DATABASE if exists Book')
cur.execute('CREATE DATABASE if not exists Book')
connection.commit()
cur.close()
# 创建购物车表

connection = pymysql.connect(user=config['user'],
                          password=config['password'],
                          port=config['port'],
                          host=config['host'],
                          db=config['db'],
                          charset=config['charset'])

cur = connection.cursor()
createCartSql = '''CREATE TABLE Cart         
               (UserID                 VARCHAR(100)   ,
                BookID                VARCHAR(100) )'''
cur.execute(createCartSql)
connection.commit()
cur.close()
connection.close()


BookInfoInsert = BookSqlTools()
#--------------------------------------------------------------------------
#读取本地的BX-Users.csv文件  在数据库中建一个User表   将User.csv内容插入到数据库中
#--------------------------------------------------------------------------
path_users = './data/BX-Users.csv'
try:
    # 确保使用了正确的 sep 和 encoding
    User_df = pd.read_csv(path_users, sep=';', encoding='latin1', on_bad_lines='skip', quotechar='"', low_memory=False)

    # 重命名DataFrame的列以匹配SQL表中的列名 (如果需要)
    # 确保DataFrame中的列名与你在column_max_lengths中定义的键一致
    User_df.rename(columns={'User-ID': 'UserID', 'Location': 'Location', 'Age': 'Age'}, inplace=True)
    
    # 选择要插入的列，并确保顺序与SQL语句中(col1, col2, col3)的顺序一致
    User_for_insert = User_df[['UserID', 'Location', 'Age']]


    createUserSql = '''CREATE TABLE IF NOT EXISTS User 
                     (UserID VARCHAR(100),
                      Location VARCHAR(100), 
                      Age VARCHAR(100) );''' # 使用 IF NOT EXISTS 更安全

    UserSql_insert='insert into User (UserID,Location,Age) values {}' # 模板保持不变

    # 调用 UpdateMysqlTable 时传入表名 "User"
    BookInfoInsert.UpdateMysqlTable(User_for_insert, createUserSql, UserSql_insert, current_table_name="User")

except FileNotFoundError:
    print(f"File not found: {path_users}")
except Exception as e:
    print(f"Error processing {path_users}: {e}")
finally:
    if 'User_df' in locals(): # 清理
        del User_df
    if 'User_for_insert' in locals():
        del User_for_insert
#--------------------------------------------------------------------------
#读取本地的BX-Books.csv文件  在数据库中建一个Books表   将book.csv内容插入到数据库中
#--------------------------------------------------------------------------
path_books = './data/BX-Books.csv' # 确保 path_books 已正确定义
try:
    Book_df = pd.read_csv(path_books, sep=';', encoding='latin1', on_bad_lines='skip', quotechar='"', escapechar='\\', low_memory=False)

    # 列重命名
    rename_map_books = {
        "ISBN": "BookID",
        "Book-Title": "BookTitle",
        "Book-Author": "BookAuthor",
        "Year-Of-Publication": "PublicationYear", # 确保拼写正确
        "Publisher": "Publisher",
        "Image-URL-S": "ImageS",
        "Image-URL-M": "ImageM",
        "Image-URL-L": "ImageL"
    }
    Book_df.rename(columns=rename_map_books, inplace=True)

    # 清洗 BookID 并删除重复项
    if 'BookID' in Book_df.columns:
        Book_df['BookID'] = Book_df['BookID'].str.strip()
        # Book_df['BookID'] = Book_df['BookID'].str.lower() # 可选的大小写统一
        Book_df.drop_duplicates(subset=['BookID'], keep='first', inplace=True)
    else:
        # 如果 BookID 列在重命名后不存在，这是个严重错误
        print("CRITICAL ERROR: 'BookID' column not found in Book_df after renaming (Books table).")
        raise KeyError("BookID column missing after rename for Books table.")

    # --- 确保在这里定义 SQL 语句 ---
    createBooksSql =''' CREATE TABLE IF NOT EXISTS Books 
                     (BookID VARCHAR(255) PRIMARY KEY, 
                      BookTitle VARCHAR(999),
                      BookAuthor VARCHAR(999),
                      PublicationYear VARCHAR(20),   -- 确保拼写正确
                      Publisher VARCHAR(999),
                      ImageS VARCHAR(999),
                      ImageM VARCHAR(999),
                      ImageL VARCHAR(999));'''

    BooksSql_insert='insert ignore into Books (BookID,BookTitle,BookAuthor,PublicationYear,Publisher,ImageS,ImageM,ImageL) values {}' # 使用 INSERT IGNORE

    # --- 确保在这里准备好要插入的 DataFrame ---
    books_columns_for_sql = ['BookID','BookTitle','BookAuthor','PublicationYear','Publisher','ImageS','ImageM','ImageL']
    
    # 检查 Book_df 是否包含所有需要的列
    missing_cols = [col for col in books_columns_for_sql if col not in Book_df.columns]
    if missing_cols:
        raise KeyError(f"Following columns are missing in Book_df for SQL selection (Books table): {missing_cols}")
    
    Books_for_insert = Book_df[books_columns_for_sql]
    
    # --- 然后才调用 UpdateMysqlTable ---
    BookInfoInsert.UpdateMysqlTable(Books_for_insert, createBooksSql, BooksSql_insert, current_table_name="Books")

except FileNotFoundError:
    print(f"File not found: {path_books}")
except Exception as e: # 其他所有异常，包括上面可能raise的KeyError
    print(f"Error processing {path_books}: {e}") # 这里的 e 会包含具体的错误信息
finally:
    if 'Book_df' in locals():
        del Book_df
    if 'Books_for_insert' in locals():
        del Books_for_insert

#--------------------------------------------------------------------------
#读取本地的BX-Book-Ratings文件  在数据库中建一个Bookrating表   将bookrating.csv内容插入到数据库中
#--------------------------------------------------------------------------

path_ratings = './data/BX-Book-Ratings.csv'
try:
    Rating_df = pd.read_csv(path_ratings, sep=';', encoding='latin1', on_bad_lines='skip', quotechar='"', low_memory=False)
    Rating_df.rename(columns={'User-ID': 'UserID', 'ISBN': 'BookID', 'Book-Rating': 'Rating'}, inplace=True)
    Rating_for_insert = Rating_df[['UserID','BookID','Rating']]

    createBookratingSql = '''CREATE TABLE IF NOT EXISTS Bookrating 
                         (UserID VARCHAR(100) ,       # 之前这里是999，根据User表的UserID调整为100
                          BookID VARCHAR(255) ,       # 之前这里是999，根据Books表的BookID调整为255
                          Rating VARCHAR(10));'''     # VARCHAR(999)对于评分来说太大了

    BookratingSql_insert='insert into Bookrating (UserID,BookID,Rating) values {}'

    BookInfoInsert.UpdateMysqlTable(Rating_for_insert, createBookratingSql, BookratingSql_insert, current_table_name="Bookrating")
except FileNotFoundError:
    print(f"File not found: {path_ratings}")
except Exception as e:
    print(f"Error processing {path_ratings}: {e}")
finally:
    if 'Rating_df' in locals():
        del Rating_df
    if 'Rating_for_insert' in locals():
        del Rating_for_insert
#--------------------------------------------------------------------------
#读取本地的Booktuijian.csv文件  在数据库中建一个Booktuijian表   将Booktuijian.csv内容插入到数据库中
#--------------------------------------------------------------------------

path_recom = 'data/booktuijian.csv'
try:
    Booktuijian_df = pd.read_csv(path_recom, sep=',', encoding='utf-8', on_bad_lines='skip') 
    
    # 数据处理部分
    Booktuijian_df['score'] = Booktuijian_df['score'].apply(lambda x: round(x,2) if pd.notna(x) else None) 
    if not Booktuijian_df['score'].empty and Booktuijian_df['score'].notna().any() and max(Booktuijian_df['score'].dropna()) != 0 :
        Booktuijian_df['score'] = 10*(Booktuijian_df['score'])/(max(Booktuijian_df['score'].dropna()))
    else:
        BooktuJjian_df['score'] = 0 

    Booktuijian_for_insert = Booktuijian_df[['BookID','UserID','score']]

    createBookrecomql = '''CREATE TABLE IF NOT EXISTS Booktuijian 
                         (BookID VARCHAR(255) ,  
                          UserID VARCHAR(100) ,
                          score FLOAT(5,3)  );''' 

    BooktuijianSql_insert='insert into Booktuijian (BookID,UserID,score) values {}'
    
    BookInfoInsert.UpdateMysqlTable(Booktuijian_for_insert,createBookrecomql ,BooktuijianSql_insert, current_table_name="Booktuijian")
    # 暂时注释掉 Booktuijian 的插入，除非 UpdateMysqlTable 做了更细致的类型处理
    # print("Skipping Booktuijian insertion for now due to mixed data types requiring more complex SQL formatting logic or parameterization.") # <--- 注释掉或删除此行

except FileNotFoundError:
    print(f"File not found: {path_recom}")
except Exception as e:
    print(f"Error processing {path_recom}: {e}")
finally:
    if 'Booktuijian_df' in locals():
        del Booktuijian_df
    # if 'Booktuijian_for_insert' in locals():
    # del Booktuijian_for_insert # 如果上面注释掉了，这里也注释


