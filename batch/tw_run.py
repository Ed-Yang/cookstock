#!/usr/bin/env python3

import math
import datetime as dt
import requests
from pydantic import BaseModel
from typing import Optional

from cookStock import batch_process

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

class TSE:
    def __init__(self) -> None:
        self._ohlcvs = {
            "TSE": [],
            "OTC": [],
            "OES": [],
        }

    def _get_day_ohlcvs_tse(self, date):
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
        return data

    def _get_code_list(self, ohlcvs:list, suffix: str = ".TW"):
        code_list = []
        for ohlcv in ohlcvs:
            code = ohlcv.code
            code_list.append(code + suffix)
        return code_list
    
    def get_ticker_list(self, exchange:str="") -> list:
        date = dt.date.today()
        while date.weekday() > 4:
            date = date - dt.timedelta(days=1)
        code_list = []
        if exchange == "":
            tse_ohlcvs = self._get_day_ohlcvs_tse(date)
            tse_list = self._get_code_list(tse_ohlcvs, suffix=".TW")
            code_list.extend(tse_list)
        elif exchange == "TSE":
            tse_ohlcvs = self._get_day_ohlcvs_tse(date)
            tse_list = self._get_code_list(tse_ohlcvs, suffix=".TW")
            code_list.extend(tse_list)
        elif exchange == "OTC":
            pass
        elif exchange == "OES":
            pass
        else:
            raise ValueError(f"invalid exchange {exchange}")
        
        return code_list
        

def main(selected, sectorNameStr):
    y = batch_process(selected, sectorNameStr)
    y.batch_pipeline_full()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()

    # device
    parser.add_argument(
        "--code",
        type=str,
        action="append",
        default=[],
        help="the name of symbol in yahoo format, e.g. 2330.TW",
    )

    args = parser.parse_args()
    
    if args.code:
        code_list = args.code
    else:
        code_list = TSE().get_ticker_list()
    
    sectorNameStr = "台灣證券交易所"
    main(code_list, sectorNameStr)
    print("Done.")
