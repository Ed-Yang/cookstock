import math
import datetime as dt
import requests
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from io import StringIO
import csv

def str_to_float(float_str: str, default_value: Optional[float] = 0.0):
    try:
        v = float(float_str.replace(",", ""))
        if math.isnan(v):
            rv = default_value
        else:
            rv = v
    except Exception:
        rv = default_value
    return rv


def str_to_int(int_str: str, default_value=0):
    try:
        v = int(int_str.replace(",", ""))
        if math.isnan(v):
            v = default_value
    except Exception:
        v = default_value
    return v

class OHLCV(BaseModel):

    code:str
    date: dt.date
    name:str
    volume:int
    transaction:int
    amount:int
    open:Optional[float] = None
    high:Optional[float] = None
    low:Optional[float] = None
    close:Optional[float] = None

class TwExchange:
    def __init__(self) -> None:
        self.symbol_dict = {}

    def _get_day_ohlcvs_tse(self, date, vol_threshold=100000):
        """
        每日收盤行情
        curl -X GET 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20230317&type=ALLBUT0999&response=json'
                          https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date=20211130&type=ALLBUT0999
        ['證券代號(0)', '證券名稱(1)', '成交股數(2)', '成交筆數(3)', '成交金額(4)', '開盤價(5)', '最高價(6)', '最低價(7)', '收盤價(8)', '漲跌(+/-)(9)', '漲跌價差(10)', '最後揭示買價(11)', '最後揭示買量(12)', '最後揭示賣價(13)', ...]
        """  # noqa: E501

        # print(f"download TSE {date.strftime('%Y-%m-%d')} ...")
        datestr = date.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX"
        url += f"?response=json&date={datestr}&type=ALLBUT0999"
        try:
            r = requests.post(url)

            if r.status_code != 200:
                return []

            if r.json().get("tables") and r.json().get("tables")[8].get("data"):
                jdata = r.json()["tables"][8]["data"]
            elif r.json().get("data9"):
                # 2021-11-30, data is in data9
                print(f"warning: {datestr} old format !!!")
                jdata = r.json().get("data9")
            else:
                return []
        except Exception as e:
            print(f"exception: {e}")
            raise ValueError(f"download failed") from e

        data = []
        for x in jdata:
            if len(x) < 12:
                msg = f"invalid data only {len(x)} fields !!!"
                print(msg)
                raise ValueError

            code = x[0]
            if not code.isdigit() or len(code) != 4:
                continue
            name = x[1].rstrip()
            volume = str_to_int(x[2])
            trans = str_to_int(x[3])
            amount = str_to_int(x[4])
            open = str_to_float(x[5])
            high = str_to_float(x[6])
            low = str_to_float(x[7])
            close = str_to_float(x[8])

            no_zero = open and high and low and close
            if not no_zero:
                open = high = low = close = str_to_float(x[11])

            if not code.isdigit() or len(code) != 4:
                continue
            
            if volume and volume < vol_threshold:
                continue
            
            ohlcv = OHLCV(
                code=code,
                date=date,
                name=name,
                open=open,
                high=high,
                low=low,
                close=close,
                volume=volume,
                transaction=trans,
                amount=amount,
            )
            data.append(ohlcv)
            symbol = code + ".TW"
            self.symbol_dict[symbol] = name
        return data

    def _get_day_ohlcvs_otc(self, date: dt.date, vol_threshold=100000):
        """
        if r.text is Big5, decode the content with r.content.decode('Big5')
        """
        datestr = date.strftime("%Y-%m-%d")
        url = f"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?"
        url += f"date={datestr}&id=&response=csv"

        try:
            r = requests.post(url)
        except Exception as e:
            print(f"exception: {e}")
            raise ValueError(f"download failed") from e

        if not r or not r.ok or "元大富櫃50" not in r.text or len(r.text) == 0:
            return []

        lines = r.text.replace("\r", "").split("\n")
        org_df = pd.read_csv(StringIO("\n".join(lines[3:])), header=None)
        org_df.columns = pd.Index(
            map(lambda x: x.replace(" ", "").replace('"', ""), lines[2].split(","))
        )

        num_df = org_df[
            (org_df["代號"].str.isnumeric()) & (org_df["代號"].str.len() <= 4)
        ]
        num_df = num_df[
            (num_df["代號"].astype(int) > 1000) & (num_df["代號"].astype(int) < 10000)
        ]

        deb_df = org_df[org_df["名稱"].str.contains("債", na=False)]
        deb_df = deb_df[~deb_df["名稱"].str.contains("購0")]
        deb_df = deb_df[~deb_df["名稱"].str.contains("售0")]

        df = pd.concat([num_df, deb_df])
        df = df.apply(lambda s: s.astype(str).str.replace("\n", ""))

        new_df = pd.DataFrame()
        new_df["code"] = df["代號"]
        new_df["date"] = date
        new_df["name"] = df["名稱"]
        new_df["open"] = df["開盤"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["close"] = df["收盤"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["high"] = df["最高"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["low"] = df["最低"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["volume"] = df["成交股數"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["transaction"] = df["成交筆數"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["amount"] = df["成交金額(元)"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["shares"] = df["發行股數"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["last_bid"] = df["最後買價"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )
        new_df["last_ask"] = df["最後賣價"].apply(
            lambda s: pd.to_numeric(s.replace(",", ""), errors="coerce")
        )

        # new_df['PE'] = 0.0

        new_df.set_index(["code", "date"], inplace=True)

        data = []
        code: str = ""
        for index, row in new_df.iterrows():
            code, date = index  # type: ignore

            if (
                math.isnan(row["open"])
                or math.isnan(row["high"])
                or math.isnan(row["low"])
                or math.isnan(row["close"])
            ):
                row["open"] = row["high"] = row["low"] = row["close"] = row["last_bid"]

            code = str(code)
            name = row["name"].rstrip()
            
            if not code.isdigit() or len(code) != 4:
                continue
            
            if row["volume"] and row["volume"] < vol_threshold:
                continue
                        
            ohlcv = OHLCV(
                code=code,
                date=date,
                name=name,
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                transaction=row["transaction"],
                amount=row["amount"],
            )
            data.append(ohlcv)
            symbol = code + ".TWO"
            self.symbol_dict[symbol] = name

        return data
    
    def _get_day_ohlcvs_oes(self, date: dt.date, vol_threshold=100000):
        """
        日行情表(電腦議價點選成交)

        'HEADER(0),證券代號(1),證券名稱(2),最後最佳報買價(3),最後最佳報賣價(4),日均價(5),前日均價(6),漲跌(7),漲跌幅(8),最高(9),最低(10),最後(11),成交量(12),成交金額(13),筆數(14),發行股數(15),上市櫃進度日期(16),上市櫃進度(17)'

        興櫃一般板股票是否有開盤價及收盤價?

        否，興櫃一般板股票屬議價交易市場，係由推薦證券商之報價主導其交易進行，
        推薦證券商每日視個股狀況依其專業判斷申報價格，
        且成交價為推薦證券商之報價，因此，無「開盤價」或「收盤價」，故興櫃一般板股票收市時係揭露當日
        「加權平均成交價」供大眾參考。
        """
        datestr = dt.date.strftime(date, "%Y%m%d")
        # url = f"https://www.tpex.org.tw/web/emergingstock/historical/daily/"
        # url += f"EMDaily_dl.php?l=zh-tw&f=EMdes010.{datestr}-C.csv"

        url = f"https://www.tpex.org.tw/www/zh-tw/emerging/dailyDl?"
        url += f"name=EMdes010.{datestr}-C.csv"
        try:
            resp = requests.get(url)
            # resp.encoding = "big5" # enable this '7706' will got 宏�硈邿F
        except Exception as e:
            print(f"exception: {e}")
            raise ValueError(f"download failed") from e

        ohlchs = []
        count = 0
        HEADER_LINES = 4
        reader = csv.reader(StringIO(resp.text))
        for row in reader:
            count += 1
            if count <= HEADER_LINES:
                continue

            r = [x.replace(",", "").rstrip() for x in row]

            if r[0] == "GLOSS" or r[1] == "合計":
                continue

            code = r[1]
            name = r[2].rstrip()
            close = float(r[6]) if r[11] == "-" else float(r[11])  # 最後 or 前日均價
            diff = 0 if r[7] == "-" else float(r[7])
            open = round(close - diff, 2)  # close - 漲跌(7)
            high = open if r[9] == "-" else float(r[9])
            low = open if r[10] == "-" else float(r[10])

            volume = 0 if r[12] == "-" else float(r[12])
            transaction = 0 if r[14] == "-" else float(r[14])
            amount = 0 if r[13] == "-" else float(r[13])

            if not code.isdigit() or len(code) != 4:
                continue
            
            if volume and volume < vol_threshold:
                continue
            
            ohlcv = OHLCV(
                code=code,
                date=date,
                name=name,
                open=open,  # type: ignore[arg-type]
                high=high,  # type: ignore[arg-type]
                low=low,  # type: ignore[arg-type]
                close=close,  # type: ignore[arg-type]
                volume=volume,  # type: ignore[arg-type]
                transaction=transaction,  # type: ignore[arg-type]
                amount=amount,  # type: ignore[arg-type]
            )
            ohlchs.append(ohlcv)
            symbol = code + ".TW"
            self.symbol_dict[symbol] = name
            
        return ohlchs

    def _get_code_list(self, ohlcvs:list, suffix: str = ".TW"):
        symbol_list = []
        for ohlcv in ohlcvs:
            code = ohlcv.code
            symbol_list.append(code + suffix)
        return symbol_list
    
    def get_symbol_list(self, exchange:str="", vol_threshold=100000) -> list:
        date = dt.date.today()
        while date.weekday() > 4:
            date = date - dt.timedelta(days=1)
        symbol_list = []
        if exchange == "":
            tse_ohlcvs = self._get_day_ohlcvs_tse(date, vol_threshold)
            tse_list = self._get_code_list(tse_ohlcvs, suffix=".TW")
            symbol_list.extend(tse_list)
            
            otc_ohlcvs = self._get_day_ohlcvs_otc(date, vol_threshold)
            otc_list = self._get_code_list(otc_ohlcvs, suffix=".TWO")
            symbol_list.extend(otc_list)
            
            oes_ohlcvs = self._get_day_ohlcvs_oes(date, vol_threshold)
            oes_list = self._get_code_list(oes_ohlcvs, suffix=".TWO")
            symbol_list.extend(oes_list)
        elif exchange == "TSE":
            tse_ohlcvs = self._get_day_ohlcvs_tse(date, vol_threshold)
            tse_list = self._get_code_list(tse_ohlcvs, suffix=".TW")
            symbol_list.extend(tse_list)
        elif exchange == "OTC":
            otc_ohlcvs = self._get_day_ohlcvs_otc(date, vol_threshold)
            otc_list = self._get_code_list(otc_ohlcvs, suffix=".TWO")
            symbol_list.extend(otc_list)
        elif exchange == "OES":
            oes_ohlcvs = self._get_day_ohlcvs_otc(date, vol_threshold)
            oes_list = self._get_code_list(oes_ohlcvs, suffix=".TWO")
            symbol_list.extend(oes_list)
        else:
            raise ValueError(f"invalid exchange {exchange}")
        
        return symbol_list
            
    def get_company_name(self, symbol) -> str:
        if not self.symbol_dict:
            self.get_symbol_list()
        if symbol in self.symbol_dict:
            return self.symbol_dict[symbol]
        else:
            return ""
        
if __name__ == "__main__":
    exchange = TwExchange()
    symbol_list = exchange.get_symbol_list()
    print(f"Total {len(symbol_list)} tickers.")