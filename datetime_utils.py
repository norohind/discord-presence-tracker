from datetime import datetime

def to_unix(timestamp: datetime) -> int:
    """Convert datetime.datetime to unix timestamp as int (since we store all timestamps in unix format in DB"""
    return int(datetime.timestamp(timestamp))

