#!/usr/bin/env python3

import pandas as pd
from tabulate import tabulate

from cookStock import batch_process
from tw_exchange import TwExchange

def main(code_list=[], sectorNameStr="TaiwanStock"):
    
    exchange = TwExchange()
    if code_list:
        selected = code_list
    else:
        # get all tickers
        selected = exchange.get_symbol_list()
        
    print(f"Toatal {len(selected)} tickers.")
    y = batch_process(selected, sectorNameStr, writeToFile=False)
    result_dict = y.batch_pipeline_full()

    for k, v in result_dict.items():
        name = exchange.get_company_name(k)
        if name:
            result_dict[k]["公司"] = name
    
    df = pd.DataFrame(result_dict).T
    df = df[["公司", "short name", "current price", "support price", "pressure price"]]
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'symbol'}, inplace=True)
    print(tabulate(df.to_dict(orient="list"), headers='keys', tablefmt='fancy_grid', showindex=False))

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
    
    main(code_list=args.code)
    print("Done.")
