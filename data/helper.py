from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO

from django.core.exceptions import ObjectDoesNotExist
from data.history_dao import History_DAO_Factory
from data.models import DataProvider

import base64
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def humanize_price(price: dict) -> dict:
    data = {}
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
            additional_data["change_percent"] = (
                price["postMarketChangePercent"]["raw"] * 100
            )
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
            additional_data["change_percent"] = (
                price["preMarketChangePercent"]["raw"] * 100
            )
            data["additional_data"] = additional_data

    return data


def humanize_fundamentals(
    financial_data: dict, default_key_statistics: dict, summary_detail: dict
) -> dict():
    data = {}

    data["PE <sub>forward</sub>"] = "N/A"
    if "forwardPE" in summary_detail.keys():
        if "raw" in summary_detail["forwardPE"].keys():
            data["PE <sub>forward</sub>"] = summary_detail["forwardPE"]["raw"]

    data["PE <sub>trailing</sub>"] = "N/A"
    if "trailingPE" in summary_detail.keys():
        if "raw" in summary_detail["trailingPE"].keys():
            data["PE <sub>trailing</sub>"] = summary_detail["trailingPE"]["raw"]

    data["Debt to Equity"] = "N/A"
    if "debtToEquity" in financial_data.keys():
        if "raw" in financial_data["debtToEquity"].keys():
            data["Debt to Equity"] = financial_data["debtToEquity"]["raw"]

    if "pegRatio" in default_key_statistics.keys():
        data["PEG ratio"] = default_key_statistics["pegRatio"]["raw"]
    else:
        data["PEG ratio"] = "N/A"

    data["Short <sub>of float</sub>"] = "N/A"
    if "shortRatio" in default_key_statistics.keys():
        if "raw" in default_key_statistics["shortRatio"].keys():
            data["Short <sub>of float</sub>"] = default_key_statistics["shortRatio"]["raw"]

    if "recommendationMean" in financial_data.keys() and "recommendationKey" in financial_data.keys():
        if "raw" in financial_data["recommendationMean"].keys():
            data[f"Rec <sub>{financial_data['recommendationKey']}</sub>"] = financial_data["recommendationMean"]["raw"]

    return data


def generate_intraday_image(notation_id) -> dict:
    """
    <!-- citi dax indication: 14097793 -->
    <!-- vdax 12105789 
    """
    try:
        onvista_dp = DataProvider.objects.get(name="Onvista")
    except ObjectDoesNotExist:
        onvista_dp = DataProvider.objects.create(name="Onvista")

    onvista = History_DAO_Factory().get_online_dao(onvista_dp)
    # result = onvista.lookupIntraday(14097793)
    result = onvista.lookupIntraday(notation_id)

    # convert unix timestamps to datetime
    timestamps = [datetime.fromtimestamp(unix_ts) for unix_ts in result["datetimePrice"]]
    
    # get the current values, hence the first one
    if timestamps:
        ts = timestamps[0]
        value = result["price"][0]
    else:
        ts = datetime.now
        value = "NaN"

    fig, line = plt.subplots(figsize=(4,2))
    fig.tight_layout()  # otherwise the right y-label is slightly clipped

    line.plot(timestamps, result["price"], linewidth=0.5, label="VDAX-NEW")
    line.spines['top'].set_visible(False)
    line.spines['right'].set_visible(False)

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H"))

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=96, bbox_inches='tight')
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8').replace('\n', '')
    
    # memory management
    buf.close()
    plt.close()

    return {"image": image_base64, "value": value, "ts":ts}

from data.open_interest import get_most_recent_distribution


def generate_max_pain_distribution(parameter) -> dict:
    """

    """
    distribution = get_most_recent_distribution(parameter)

    fig, line = plt.subplots(figsize=(8,4))
    fig.tight_layout()  # otherwise the right y-label is slightly clipped

    line.bar(distribution.keys(), distribution.values(), width=25, label="Distribution")
    line.spines['top'].set_visible(False)
    line.spines['right'].set_visible(False)

    plt.title(parameter["product"]["name"])
    plt.xlabel("Strike")
    plt.ylabel("Price [€]")

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=96, bbox_inches='tight')
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8').replace('\n', '')
    
    # memory management
    buf.close()
    plt.close()

    return {"image": image_base64}

