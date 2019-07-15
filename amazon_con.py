from requests.packages.urllib3.connectionpool import xrange
import mechanize
import http.cookiejar
import codecs
import re
import datetime
from .amazon_sql import run_report_return_data, request_report_return_report_id, get_dates_needed
from .database_con import SQLConnection as db, SQLConnection

db_to_load = 'this'

#########################################################################
base_url = 'https://sellercentral.amazon.com'
sign_in_url = 'https://sellercentral.amazon.com/gp/homepage.html'
reports_url = base_url + '/sspa/tresah/ref=xx_perftime_dnav_xx#/hsa/?s=0353232fa65408&v=1'


#########################################################################

def format_column_names(col_list):
    col_list = [re.sub('[^A-Za-z0-9 _]', '', column.lower()).replace(' ', '_') for column in col_list]
    return col_list


#########################################################################

def days_past(start_date_YYYYMMDD):
    start_date = datetime.datetime.strptime(start_date_YYYYMMDD, '%Y%m%d')
    days_past = datetime.datetime.today() - start_date
    return days_past.days


#########################################################################

def create_table_if_not_exists(report_retriever, tablename):
    global headers
    with db(db_to_load) as db_con:

        print("Checking if table {} exists".format(tablename))
        res = db_con.execute("""
        select count(*) from INFORMATION_SCHEMA.tables as t
            where t.table_name = '{tblname}';
        """.format(tblname=tablename))

        res = res.fetchall()[0][0]

    if res == 0:
        print('Table did not exist, attempting to create.')
        headers_received = False
        dt_to_pull = datetime.datetime.today()

        for i in xrange(0, 11):
            dt_pull_fmt = dt_to_pull.strftime('%Y-%m-%d')
            headers = re.split(r'\t+', run_report_return_data(report_retriever, tablename, dt_pull_fmt).splitlines()[0])

            if headers:
                # print headers
                print('Headers received for create table statement.Formatting.')
                headers = format_column_names(headers)
                print('Headers formatted.')
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
        print("Table existed.")


#########################################################################

def get_data(account_info, requested_report, start_date, end_date):

    # Browser
    br = mechanize.Browser()

    # Cookie Jar
    cj = http.cookiejar.LWPCookieJar()
    br.set_cookiejar(cj)

    # Browser options
    br.set_handle_equiv(True)
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    br.set_handle_robots(False)

    # Follows refresh 0 but not hangs on refresh > 0
    br.set_handle_refresh(mechanize.HTTPRefreshProcessor(), max_time=1)

    # User-Agent
    br.addheaders = [('User-agent',
                      'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]

    r = br.open(sign_in_url)

    br.select_form(name='signinWidget')

    # Let's login

    ##################################
    br.form['username'] = ''
    br.form['password'] = ''
    ##################################
    br.submit()

    print("Logged in.")
    report_params = {"cols": "/c0/c1/c2/c3/c4/c5/c6/c7/c8/c9/c10/c11/c12",
                     #  "sortColumn":"13",
                     "fromDate": start_date,
                     "toDate": end_date,
                     "reportID": requested_report,
                     # "sortIsAscending":"0",
                     # "currentPage":"0",
                     "dateUnit": "1"
                     }

    req = br.click_link(text='Business Reports')
    print("Attempting to open form.")
    br.open(req)
    print("Link clicked")

    br.select_form(predicate=lambda f: f.attrs.get('id', None) == 'dwnldFormCSV')
    br.form.set_all_readonly(False)
    for k, v in report_params.items():
        br.form[k] = v
    print("Attempting to get data...")
    r = br.submit()
    import csv
    csv = csv.reader(r.read().splitlines())

    for row in csv:
        if row[0].startswith(codecs.BOM_UTF8):
            row[0] = row[0][3:]
        print(row)

    return list(csv)


#########################################################################
# get all customers from DB
def get_customers():
    with SQLConnection('azure') as db_con:
        customers = db_con.execute('EXEC get_customers').fetchall()
    return customers


#########################################################################

def get_requested_reports(account_id):
    with SQLConnection('azure') as db_con:
        reports = db_con.execute('EXEC get_requested_reports {acct_id}'.format(acct_id=account_id)).fetchall()
    return reports


#########################################################################

def process_customer(account_id):
    print("Getting report data for customer: {}".format(account_id))
    for row in request_report_return_report_id(account_id):
        # for each requested_report row in this account:
        # Find dates needed
        if not row.request_report_return_report_id:
            dates_needed = get_dates_needed(account_id, row)
            print("Getting data for the following dates: {}".format(dates_needed))
        # for each date needed:
        for date in dates_needed:
            get_data(account_id, dates_needed, date, date)
        # for each report, determine days needed

        # for each date:


#########################################################################

def get_dates_needed(account_id, report_info):
    with SQLConnection('azure') as db_con:
        tablename = report_info[8]
        datefield_name = report_info[9]
        past_n_days = days_past(report_info[4].strftime('%Y%m%d'))
        try:
            and_statements = report_info[10]
        except IndexError as e:
            and_statements = ''
        if past_n_days is None:
            past_n_days = '90'

        if and_statements is None:
            and_statements = ''

        proc_text = 'EXEC FIND_DATES_NEEDING_DATA_ASC_UNIVERSAL {tablename}, {datefield_name}, {past_n_days}, \'{and_statements}\''.format(
            tablename=tablename,
            datefield_name=datefield_name,
            past_n_days=past_n_days,
            and_statements=and_statements)

        dates_needed = db_con.execute(proc_text)
        print(proc_text)



#########################################################################



for row in get_customers():
    account_id = row[0]
    customer = row[1]
    process_customer(account_id)

