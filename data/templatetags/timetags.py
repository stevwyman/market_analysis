from django import template
import time

register = template.Library()

def print_timestamp(timestamp):
    try:
        #assume, that timestamp is given in seconds with decimal point
        ts = float(timestamp/1000)
    except ValueError:
        return None
    # return datetime.datetime.fromtimestamp(ts)
    # return time.strftime("%Y-%m-%d", time.gmtime(ts))
    return time.strftime("%b %d, %Y", time.gmtime(ts))
    

register.filter(print_timestamp)