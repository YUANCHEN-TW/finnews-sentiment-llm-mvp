from datetime import datetime, timedelta

def align_timestamp_to_session(published_at, session_close_hour=13, tz_offset_hours=0):
    # MVP：若在收盤前，視為 T；否則 T+1
    if published_at.hour < session_close_hour:
        return "T"
    return "T+1"
