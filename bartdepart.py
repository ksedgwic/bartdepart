import argparse
import asyncio
import httpx
import os
import sys
import time
from datetime import datetime
from collections import deque

import pytz

from wled import WLED, Device

WLED_IP = "192.168.86.49"
WLED_NLEDS = 60
WLED_BRIGHTNESS = 0.75
WLED_FPS = 5

# BART_ORIG = "NBRK"
# BART_DIRECTION = "South"
BART_API_KEY = os.getenv("BART_API_KEY")
BART_SECS = 60
BART_NGHOST = 4
BART_PHASE = 5  # seconds past the top of the minute
BART_SOD = "05:00"  # Start of polling
BART_EOD = "01:00"  # End of polling (next day)
BART_EOD_TIME = datetime.strptime(BART_EOD, "%H:%M").time()
BART_SOD_TIME = datetime.strptime(BART_SOD, "%H:%M").time()

ETD_DATA = deque(maxlen=BART_NGHOST)
GHOST_WEIGHT = [1.0, 0.4, 0.2, 0.1]

async def fetch_bart_data(station):
    bart_api_url = (
        f"https://api.bart.gov/api/etd.aspx?"
        f"cmd=etd&orig={station}&key={BART_API_KEY}&json=y"
    )
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(bart_api_url)
            response.raise_for_status()  # Raise error for bad status codes
            data = response.json()       # Parse response as JSON
            # Sanity check response
            if 'root' not in data or 'time' not in data['root'] or 'station' not in data['root']:
                print("Missing 'root' or necessary data keys in API response")
                return None
            return data
        except httpx.HTTPStatusError as e:
            # print(f"HTTP error occurred: {e}", file=sys.stderr)
            return None
        except httpx.RequestError as e:
            print(f"Request error occurred: {e}", file=sys.stderr)
        except Exception as e:
            print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return None  # Return None if an error occurred

def grok_bart_time(time_str):
    # Define the PDT timezone
    pdt_zone = pytz.timezone("America/Los_Angeles")

    # Get today's date in PDT timezone
    today_date = datetime.now(pdt_zone).strftime("%Y-%m-%d")
    full_time_str = f"{today_date} {time_str}"

    # Define the input format to match our full datetime string
    time_format = "%Y-%m-%d %I:%M:%S %p %Z"

    # Parse the datetime string and localize it to PDT
    dt = datetime.strptime(full_time_str, time_format)
    dt = pdt_zone.localize(dt)

    # Convert to UTC and get Unix timestamp
    unix_seconds = int(dt.astimezone(pytz.UTC).timestamp())
    return unix_seconds

def harvest_etd(direction, platform, destinations, data):
    global ETD_DATA
    now = time.time()
    tstamp = grok_bart_time(data['root']['time'])
    lag = int(now - tstamp)
    etds = []
    present = set()
    showing = set()
    for station in data['root']['station']:
        for dest in station['etd']:
            for estimate in dest['estimate']:
                present.add((
                    estimate['color'],
                    estimate['direction'],
                    estimate['platform'],
                    dest['destination']
                    ))
                # need to filter after we record what we saw
                if len(destinations) and dest['destination'] not in destinations:
                    continue
                if direction and estimate['direction'] != direction:
                    continue
                if platform and estimate['platform'] != platform:
                    continue
                showing.add((
                    estimate['color'],
                    estimate['direction'],
                    estimate['platform'],
                    dest['destination']))
                if estimate['minutes'] == "Leaving":
                    etd = tstamp
                    color = 'WHITE'
                else:
                    etd = tstamp + (int(estimate['minutes']) * 60)
                    color = estimate['color']
                etds.append((etd, color))
    etds.sort(key=lambda x: x[0])
    if len(ETD_DATA) == 0:
        present_sorted = sorted(present, key=lambda x: x[0])
        showing_sorted = sorted(showing, key=lambda x: x[0])
        print(f"present {present_sorted}")
        print(f"showing {showing_sorted}")
    formatted_now = time.strftime("%H:%M:%S", time.localtime(now))
    print(f"{formatted_now}: lag {lag:>2}:", end="")
    prev_time = now
    for etd, color in etds:
        delta = int((etd - prev_time) / 60)
        etd_formatted = time.strftime("%H:%M:%S", time.localtime(etd))
        print(f" +{delta} ({etd_formatted}:{color})", end="")
        prev_time = etd
    print()
    ETD_DATA.append({ 'tstamp': tstamp, 'etds': etds })

async def track_bart(station, *, direction=None, platform=None, destinations=None):
    max_delay = 64  # Maximum backoff delay in seconds
    delay = 1       # Initial delay for retry

    while True:
        now = int(datetime.now().timestamp())

        # These need to be recalculated because the day updates at midnight
        # BART_EOD is always earlier
        today = datetime.now().date()
        bart_eod = int(datetime.combine(today, BART_EOD_TIME).timestamp())
        bart_sod = int(datetime.combine(today, BART_SOD_TIME).timestamp())

        if now > bart_eod and now < bart_sod:
            sleep_until = bart_sod - now
            print(f"sleeping for {sleep_until} seconds until {BART_SOD}")
            await asyncio.sleep(sleep_until)
            continue

        # Retry until data is successfully fetched
        while True:
            data = await fetch_bart_data(station)
            if data:
                harvest_etd(direction, platform, destinations, data)
                delay = 1  # Reset delay after successful fetch
                break  # Exit the retry loop once data is fetched
            else:
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)  # Exponential backoff

        # Calculate time until the top of the next minute
        now = time.time()
        seconds_until_next_sample = BART_SECS - ((now - BART_PHASE) % BART_SECS)
        await asyncio.sleep(seconds_until_next_sample)

def get_color(index):
    if index % 10 == 0:
        return "420000"
    elif index % 5 == 0:
        return "004200"
    else:
        return "000042"

COLOR_MAP = {
    'RED': 	(1.0, 0.0, 0.0),
    'ORANGE':	(1.0, 0.6, 0.2),
    'YELLOW':	(1.0, 1.0, 0.0),
    'GREEN':	(0.0, 1.0, 0.0),
    'BLUE':	(0.0, 0.0, 1.0),
    'WHITE':	(1.0, 1.0, 1.0),
}

def scale_rgb(rgb, factor):
    return tuple(component * factor for component in rgb)

def fit_rgb(rgb):
    # Find the maximum component in the tuple
    max_value = max(rgb)
    # If the maximum component is greater than 1.0, scale each component
    if max_value > 1.0:
        return tuple(component / max_value for component in rgb)
    else:
        return rgb  # If max_value is 1.0 or less, return as is

def apply_gamma(rgb, gamma_r=1.6, gamma_g=1.6, gamma_b=1.4):
    r, g, b = rgb
    return (r ** gamma_r, g ** gamma_g, b ** gamma_b)

# the low end of the leds requires remapping
def compensate(rgb, off_r=0.11, off_g=0.10, off_b=0.12):
    return (
        off_r + rgb[0] * (1.0 - off_r),
        off_g + rgb[1] * (1.0 - off_g),
        off_b + rgb[2] * (1.0 - off_b)
    )

def rgb_to_hex(rgb):
    r, g, b = (int(c * 255) for c in rgb)
    return f"{r:02X}{g:02X}{b:02X}"

def process_rgb(rgb):
    try:
        val = rgb_to_hex(compensate(apply_gamma(fit_rgb(rgb))))
        # print(val)
        return val
    except Exception as e:
        print("Exception in process_rgb:", e)
        print("Original input RGB:", rgb)
        sys.exit(1)

def test_pattern_segment(seq):
    ndx = int(seq/20)
    colors = list(COLOR_MAP.keys())
    color = colors[ndx % len(colors)]
    rgb = COLOR_MAP[color]
    ndx = 0
    factor = 0.0
    seg = []
    while factor <= 1.0:
        seg.append(ndx)
        seg.append(process_rgb(scale_rgb(rgb, factor)))
        ndx += 1
        factor += 0.1
    return seg

def bart_segment(seq):
    global ETD_DATA
    now = time.time()
    rgb_array = [(0.0, 0.0, 0.0) for _ in range(WLED_NLEDS)]
    # iterate from most recent to oldest
    for ghost_index, ghost in enumerate(reversed(ETD_DATA)):
        for etd in ghost['etds']:
            delta = int(etd[0] - now)
            if delta < 0:
                continue
            index = delta / 60
            int_index = int(index)
            frac_index = index - int_index
            if 0 <= int_index < WLED_NLEDS:
                r, g, b = scale_rgb(COLOR_MAP[etd[1]], WLED_BRIGHTNESS)

                # Full value if index is exactly an integer
                if frac_index == 0:
                    rgb_array[int_index] = (
                        rgb_array[int_index][0] + r * GHOST_WEIGHT[ghost_index],
                        rgb_array[int_index][1] + g * GHOST_WEIGHT[ghost_index],
                        rgb_array[int_index][2] + b * GHOST_WEIGHT[ghost_index],
                    )
                else:
                    # Distribute based on fractional part
                    lower_weight = (1.0 - frac_index) * GHOST_WEIGHT[ghost_index]
                    upper_weight = frac_index * GHOST_WEIGHT[ghost_index]

                    # Accumulate the lower part
                    if 0 <= int_index < WLED_NLEDS:
                        rgb_array[int_index] = (
                            rgb_array[int_index][0] + r * lower_weight,
                            rgb_array[int_index][1] + g * lower_weight,
                            rgb_array[int_index][2] + b * lower_weight,
                        )

                    # Accumulate the upper part
                    if 0 <= int_index + 1 < WLED_NLEDS:
                        rgb_array[int_index + 1] = (
                            rgb_array[int_index + 1][0] + r * upper_weight,
                            rgb_array[int_index + 1][1] + g * upper_weight,
                            rgb_array[int_index + 1][2] + b * upper_weight,
                        )
    seg = [
        item
        for index in range(WLED_NLEDS)
        for item in (
                index,
                process_rgb(rgb_array[index])
        )
    ]
    return seg

async def update_display(wled, test_pattern):
    seq = 0
    while True:
        if test_pattern:
            seg_array = test_pattern_segment(seq)
        else:
            seg_array = bart_segment(seq)
        await wled.segment(0, individual=seg_array)
        await asyncio.sleep(1.0/WLED_FPS)
        seq += 1

def wled_updated(device: Device) -> None:
    """Call when WLED reports a state change."""
    # print("Received an update from WLED")
    # print(device.state)
    # print(device.info)

async def print_exception(coro):
    """Wrapper to catch and re-raise exceptions in tasks."""
    try:
        await coro
    except Exception as e:
        print(f"Exception in task: {e}")
        raise  # Re-raise to propagate to gather

async def start() -> None:
    """Show example on controlling your WLED device."""
    parser = argparse.ArgumentParser(description="Process BART station and destinations.")
    add_args(parser)
    args = parser.parse_args()

    station = args.station
    direction = args.direction
    platform = args.platform
    destinations = args.destination if args.destination else []  # Default to an empty list if None

    if args.no_wled:
        tracker = asyncio.create_task(
            print_exception(track_bart(station,
                                       direction=direction,
                                       platform=platform,
                                       destinations=destinations)))
        try:
            await asyncio.gather(tracker)
        except Exception as e:
            print(f"One of the tasks failed with an exception: {e}")
        finally:
            # Ensure all tasks are canceled if any task fails
            tracker.cancel()
            await asyncio.gather(tracker, return_exceptions=True)
    else:
        async with WLED(WLED_IP) as wled:
            await wled.connect()
            if wled.connected:
                print("connected!")

            # Listen for WLED updates (do we need this?)
            listener = asyncio.create_task(print_exception(wled.listen(callback=wled_updated)))

            if args.test_pattern:
                tracker = None
            else:
            	# Start the BART tracker
                tracker = asyncio.create_task(
                    print_exception(track_bart(station,
                                               direction=direction,
                                               platform=platform,
                                               destinations=destinations)))

            # Start the display updates
            display = asyncio.create_task(print_exception(update_display(wled, args.test_pattern)))

            try:
                if tracker:
                    await asyncio.gather(listener, tracker, display)
                else:
                    await asyncio.gather(listener, display)
            except Exception as e:
                print(f"One of the tasks failed with an exception: {e}")
            finally:
                # Ensure all tasks are canceled if any task fails
                listener.cancel()
                if tracker:
                    tracker.cancel()
                display.cancel()
                await asyncio.gather(listener, tracker, display, return_exceptions=True)

def add_args(parser):
    parser.add_argument(
        "-s", "--station",
        type=str,
        required=True,
        help="Four-character code for the station"
    )
    parser.add_argument(
        "-p", "--platform",
        type=str,
        help="Specify the platform"
    )
    parser.add_argument(
        "-d", "--direction",
        type=str,
        choices=["North", "South"],
        help="Specify the direction"
    )
    parser.add_argument(
        "-t", "--destination",
        action="append",
        help="Destination code (can be provided multiple times)"
    )
    parser.add_argument(
        "-n", "--no-wled",
        action="store_true",
        help="Run w/o using the WLED interface (text only)"
    )
    parser.add_argument(
        "-x", "--test-pattern",
        action="store_true",
        help="Display a test pattern"
    )

def main():
    asyncio.run(start())

if __name__ == "__main__":
    main()
