from mws import mws
from scrape_attempt.creds import zon_creds
from scrape_attempt.database_con import SQLConnection as db
from requests.packages.urllib3.connectionpool import xrange
import csv
import re
import datetime
from time import sleep

db_to_load = 'azure'


#########################################################################

def get_sellers():
    sellers = []
    for seller in zon_creds().accounts_dict.items():
        sellers.append(seller)

    return sellers


#########################################################################

def request_report_return_report_id(info_dict):
    id = info_dict
    retriever_class = id["report_retriever"]
    report_type = id["report_type"]
    startdatetime = id["startdatetime"]
    enddatetime = id["enddatetime"]

    resp = retriever_class.request_report(report_type, startdatetime, enddatetime)

    return resp


#########################################################################


def insert_placeholder_row(tablename, seller_id, date):
    with db(db_to_load) as db_con:
        insert_sql = """
        INSERT INTO {table_name} (sellerid, [startdate], [enddate])
                 VALUES ('{seller_id}', cast(dateadd(day, -1,'{date}') as datetime2), cast('{date}' as datetime2) );

         """.format(table_name=tablename, seller_id=seller_id, date=date)

        print('Inserting placeholder row')
        db_con.execute(insert_sql)

    print("Row Inserted")


#########################################################################

def get_dates_needed(seller_id, report_type):
    dates_needed = []
    with db(db_to_load) as db_con:
        db_con.execute('EXEC find_dates_needing_data {report_type},{seller_id},{window}'.format(report_type=report_type,
                                                                                                seller_id=seller_id,
                                                                                                window=280))  # was 280
        for date in db_con:
            dates_needed.append(date[0].strftime('%Y-%m-%d'))

    return dates_needed


#########################################################################

def run_report_return_data(report_retriever, report_type, date):
    seller_id = report_retriever.account_id

    resp = report_retriever.request_report(report_type, date).parsed
    report_request_id = resp.get("ReportRequestInfo").get("ReportRequestId").get("value")

    print ("Requested report id: {}".format(report_request_id))

    ########################################################################
    # Loop until report ready or cancelled
    ########################################################################
    report_ready = False
    report_stat = {"ReportProcessingStatus": {"value": "_DEFAULT_"}}
    while not report_ready:
        try:
            report_stat = report_retriever.get_report_request_list([report_request_id]).parsed.get("ReportRequestInfo")

        except mws.MWSError as error:
            if '503 Server Error' in error.message:
                print ("Encountered throttle notice. Sleeping 1 minute.")
                sleep(60)
                report_ready = False

        report_status = [report_stat.get("ReportProcessingStatus").get("value")]

        if report_status == ["_DONE_"]:
            print ("Report ready. Retrieving generated report ID")

            for i in xrange(0, 11):
                try:
                    generated_report_id = report_retriever. \
                        get_report_request_list([report_request_id]).parsed. \
                        get("ReportRequestInfo").get("GeneratedReportId").get("value")
                    report_ready = True
                    break
                except mws.mws.MWSError as error:
                    if '503 Server Error' in error.message:
                        print (
                            "Received throttling notice when Trying to get GeneratedReportId. Sleeping 1 minute before next attempt")
                        sleep(60)  # sleep for a minute and then try again


        elif "_CANCELLED_" in report_status:
            print ("Could not get report for date: {}. Report was cancelled by API!".format(date))
            insert_placeholder_row(report_type, seller_id, date)
            report_data = 'You did not have any data for this date'
            # raise Exception("Report was cancelled!")
            break
        else:
            sleep_time = 30  # seconds
            print ("Report status was: {}".format(report_status))
            print ("Report not ready, sleeping {} seconds.".format(sleep_time))
            sleep(sleep_time)
    # END LOOP #############################################################

    if report_ready:
        print("Retrieving report for report id: {}".format(generated_report_id))

        for i in xrange(0, 11):

            try:
                report_data = report_retriever.get_report(generated_report_id).parsed
                break  # Report done
            except mws.mws.MWSError as error:
                if '503 Server Error' in error.message:
                    print("Received throttling notice when calling getReport. Sleeping 1 minute before next attempt")
                    sleep(60)  # sleep for a minute and then try again
                else:
                    raise error

            if i == 10:
                print (
                    "Unable to retrieve report after 10 tries. Aborting. Attempt will be made the next time this report runs.")
                report_data = []

    return report_data


#########################################################################


def create_table_if_not_exists(report_retriever, tablename):
    with db(db_to_load) as db_con:
        print ('Checking if table "{}" exists'.format(tablename))
        res = db_con.execute("""
        select count(*) from INFORMATION_SCHEMA.tables as t
            where t.table_name = '{}';
        """.format(tablename))

        res = res.fetchall()[0][0]

    if res == 0:
        print ("Table did not exist, attempting to create.")
        headers_received = False
        dt_to_pull = datetime.datetime.today()

        for i in xrange(0, 11):
            dt_pull_fmt = dt_to_pull.strftime('%Y-%m-%d')
            headers = re.split(r'\t+', run_report_return_data(report_retriever, tablename, dt_pull_fmt).splitlines()[0])

            if headers:
                # print headers
                print ('Headers received for create table statement.Formatting.')
                headers = [re.sub('[^A-Za-z0-9]', '', column.lower()) for column in headers]
                print ('Headers formatted.')
                break
            # try again if necessary
            dt_to_pull += datetime.timedelta(days=-i)

        sql_part = '[sellerid] varchar(1000),'

        if 'startdate' not in headers:
            sql_part += '[startdate] varchar(1000),'
            sql_part += '[enddateate] varchar(1000),'

        for column in headers:
            column = re.sub('[^A-Za-z0-9]', '', column.lower())
            sql_part += '[{column}] varchar(4000),\n'.format(column=column)

        sql = \
            'create table [{tbl}] ({columns});'.format(tbl=tablename, columns=sql_part.rstrip(','))
        # print sql
        with db('azure') as db_con:

            print("Creating table")
            db_con.execute(sql)

        print("Table Created")

    else:
        print("Table Existed")


#########################################################################

def insert_data(table_name, seller_id, date, data):
    data_for_load = list(data)  # csv reader to list
    length = len(data_for_load)
    headers = data_for_load[0:1]
    # lowercase headers and remove non alphanumeric
    #headers = [re.sub('[^A-Za-z0-9]', '', column.lower()) for column in headers]

    '''for row in data_for_load[1:]:
        for num, item in enumerate(row):
            if item.endswith(' PST'):
                new_val = item.replace(' PST', '')
                del row[num]
                row.insert(num, new_val)'''

    #fields = ','.join('?' * len(headers))
    report_name = table_name + date
    print(length)

    with open('%s.csv' % report_name, 'wb') as f:
        writer = csv.writer(f)
        writer.writerows(data_for_load)
        '''for i in range(length):
            writer.writerows(data_for_load[i])
            i += 1
            if i < length:
                continue
            else:
                break'''

    print("Data Inserted")



    '''if 'startdate' in headers:
            insert_sql = """
            INSERT INTO {table_name}
                     VALUES ('{seller_id}',{binds});
             """.format(table_name=tablename, seller_id=seller_id, binds=fields)

        else:
            print ("Report does not have start and end date fields, interpolating.")
            insert_sql = """
            INSERT INTO {table_name}
                     VALUES ('{seller_id}',cast(dateadd(day, -1,'{date}') as datetime2), cast('{date}' as datetime2),{binds});
             """.format(table_name=tablename, seller_id=seller_id, date=date, binds=fields)
        # print insert_sql
        print("Actually inserting")
        db_con.executemany(insert_sql, data_for_load[1:])'''


#########################################################################

def get_and_insert_report_data(report_retriever, seller_record, report_type, dates_list):
    seller_id = report_retriever.account_id

    for date in dates_list:
        # date = '2015-12-17'
        print ("Getting data for report: {report_type}. Date: {date}".format(report_type=report_type,
                                                                             date=date))

        report_data = run_report_return_data(report_retriever, report_type, date)

        if "You did not have any" not in report_data and report_data != []:
            # Identify tab delimited files
            if '\t' in report_data.splitlines()[0]:
                print ("Found tab in first row. Inserting as CSV")
                csv_data = csv.reader(report_data.splitlines(), delimiter='\t')
            else:
                print ("Did not find tab in first row.")
                csv_data = csv.reader(report_data.splitlines())  # assuming csv

            insert_data(report_type, seller_id, date, csv_data)
            # with open('info.csv', 'w') as f:
            # writer = csv.writer(f)
            # writer.writerow([seller_id, report_type, date, csv_data])
        else:
            print ("No report data found for this day, inserting placeholder row")


#########################################################################


def fetch_reports_and_insert_data(seller_record):
    seller_id = seller_record[0]
    seller_data = seller_record[1]
    report_retriever = mws.Reports(access_key=seller_data["aws_acc_key"],
                                       secret_key=seller_data["aws_sec_key"],
                                       account_id=seller_id)

    requested_report_types = seller_data["requested_report_types"]

    requested_report_ids = []

    for report_type in requested_report_types:
        print ("Getting data for report type: {}".format(report_type))
        # create_table_if_not_exists(report_retriever, report_type)
        # dates_list = get_dates_needed(seller_id, report_type)
        # print ("The following days reports will be requested: {}".format(dates_list))
        dates_list = ['2019-06-18']
        print ("The following days reports will be requested: {}".format(dates_list))

        get_and_insert_report_data(report_retriever, seller_record, report_type, dates_list)


#########################################################################
def main():
    sellers = [seller for seller in get_sellers() if seller[0] == ""]

    for seller_record in sellers:
        fetch_reports_and_insert_data(seller_record)


main()

# create_table_if_not_exists('Fake_table',['col1','col2'])
