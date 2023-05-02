from datetime import datetime
from zoneinfo import ZoneInfo

def humanize_price(price: dict) -> dict:
    data={}
    data["currency_symbol"] = price["currencySymbol"]

    orig_timezone = ZoneInfo("America/New_York")
    local_timezone = ZoneInfo("Europe/Berlin")

    # regular market-state
    # show regular market time
    regularMarketPrice = price["regularMarketPrice"]["raw"]
    regularMarketChange = price["regularMarketChange"]["raw"]
    regularMarketChangePercent = price["regularMarketChangePercent"]["raw"] * 100

    regularMarketTime = price["regularMarketTime"]
    orig_dt_object = datetime.fromtimestamp(regularMarketTime, orig_timezone)

    local_dt_object = orig_dt_object.astimezone(local_timezone)

    data["local_timestamp"] = local_dt_object
    data["price"] = regularMarketPrice
    data["change"] = regularMarketChange
    data["change_percent"] = regularMarketChangePercent
    

    marketState = price["marketState"]
    data["marketState"] = marketState

    if marketState == "POST":
        # show pre market time
        if "postMarketTime" in price.keys():
            postMarketTime = price["postMarketTime"]
            orig_dt_object = datetime.fromtimestamp(postMarketTime, orig_timezone)
            local_dt_object = orig_dt_object.astimezone(local_timezone)
            additional_data = {}
            additional_data["state"] = "post"
            additional_data["local_timestamp"] = local_dt_object
            additional_data["price"] = price["postMarketPrice"]["raw"]
            additional_data["change"] = price["postMarketChange"]["raw"]
            additional_data["change_percent"] = price["postMarketChangePercent"]["raw"] * 100
            data["additional_data"] = additional_data
        
    elif marketState == "PRE":

        # show pre market time
        if "preMarketTime" in price.keys():
            preMarketTime = price["preMarketTime"]
            orig_dt_object = datetime.fromtimestamp(preMarketTime, orig_timezone)
            local_dt_object = orig_dt_object.astimezone(local_timezone)
            additional_data = {}
            additional_data["state"] = "pre"
            additional_data["local_timestamp"] = local_dt_object
            additional_data["price"] = price["preMarketPrice"]["raw"]
            additional_data["change"] = price["preMarketChange"]["raw"]
            additional_data["change_percent"] = price["preMarketChangePercent"]["raw"] * 100
            data["additional_data"] = additional_data
    
    return data
