class sql_server:

    def __init__(self, server, username):

        self.driver = "ODBC Driver 17 for SQL Server"
        self.username = username
        self.db_str = ''
        if username == 'mydb':
            self.username = username
            self.pwd = ''
            self.db_str = 'DATABASE=mysql;'
        if server == 'local':
            self.server = ''
            self.pwd = ''
        if server == 'azure':
            self.server = ''
        else:
            self.server = server
        self.con_str = 'DRIVER={driver};SERVER={server};UID={uid};{db_str}PWD={passwd}'.format(
            driver=self.driver,
            server=self.server,
            uid=self.username,
            db_str=self.db_str,
            passwd=self.pwd)


class zon_creds:

    def __init__(self, seller_id=None):
        # House multiple accounts either here (In the DB later).
        self.accounts_dict = {

            "": {
                "marketplace_ids": {
                    "Azon Payments Sandbox": "",
                    "Azon Payments Live": "",
                    "IBA": "",
                    "Amazon.ca": "",
                    "Amazon.com": "",
                    "Amazon.com.mx": ""},
                "developer_account_number": "",
                "aws_acc_key": "",
                "aws_sec_key": "",
                "requested_report_types": [
                    '_GET_AMAZON_FULFILLED_SHIPMENTS_DATA_',
                    '_GET_FLAT_FILE_ACTIONABLE_ORDER_DATA_', '_GET_FLAT_FILE_ORDER_REPORT_DATA_',
                    '_GET_FLAT_FILE_ORDERS_DATA_', '_GET_CONVERGED_FLAT_FILE_ORDER_REPORT_DATA_',
                    '_GET_PAYMENT_SETTLEMENT_DATA_',
                    '_GET_MERCHANT_LISTINGS_DATA_', '_GET_MERCHANT_LISTINGS_DATA_LITE_',
                    '_GET_MERCHANT_LISTINGS_DATA_LITER_', '_GET_MERCHANT_CANCELLED_LISTINGS_DATA_',
                    '_GET_AFN_INVENTORY_DATA_', '_GET_MERCHANT_LISTINGS_INACTIVE_DATA_',
                    '_GET_MERCHANT_LISTINGS_DATA_BACK_COMPAT_'
                ]
            }
        }

        if seller_id is not None:
            self.accounts_dict = self.accounts_dict[seller_id]
