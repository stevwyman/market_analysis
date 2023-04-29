from datetime import datetime
from zoneinfo import ZoneInfo

def humanize_price(price: dict) -> dict:
    data={}
    data["currency_symbol"] = price["currencySymbol"]

    
    orig_timezone = ZoneInfo("America/New_York")
    local_timezone = ZoneInfo("Europe/Berlin")

    

    marketState = price["marketState"]
    if marketState == "REGULAR":
        # show regular market time
        regularMarketPrice = price["regularMarketPrice"]["raw"]
        regularMarketChange = price["regularMarketChange"]["raw"]
        regularMarketChangePercent = price["regularMarketChangePercent"]["raw"] * 100

        regularMarketTime = price["regularMarketTime"]
        orig_dt_object = datetime.fromtimestamp(regularMarketTime, orig_timezone)
        
        local_dt_object = orig_dt_object.astimezone(local_timezone)
        print(f"{orig_dt_object} --> {local_dt_object}")

        data["local_timestamp"] = local_dt_object
        data["price"] = regularMarketPrice
        data["change"] = regularMarketChange
        data["change_percent"] = regularMarketChangePercent
    elif marketState == "POST":
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
    elif marketState == "CLOSED":
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


    # preMarketTime = price["preMarketTime"]
    
    return data
