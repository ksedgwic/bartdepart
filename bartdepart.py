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
WLED_BRIGHTNESS = 1.0

# BART_ORIG = "NBRK"
# BART_DIRECTION = "South"
BART_API_KEY = os.getenv("BART_API_KEY")
BART_SECS = 60
BART_NGHOST = 4

ETD_DATA = deque(maxlen=BART_NGHOST)
GHOST_WEIGHT = [1.0, 0.6, 0.4, 0.3]

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

def harvest_etd(direction, destinations, data):
    global ETD_DATA
    now = time.time()
    tstamp = grok_bart_time(data['root']['time'])
    lag = int(now - tstamp)
    etds = []
    saw = set()
    for station in data['root']['station']:
        for dest in station['etd']:
            for estimate in dest['estimate']:
                saw.add((estimate['direction'], dest['destination']))
                # need to filter after we record what we saw
                if len(destinations) and dest['destination'] not in destinations:
                    continue
                if direction and estimate['direction'] != direction:
                    continue
                if estimate['minutes'] == "Leaving":
                    etd = tstamp
                    color = 'WHITE'
                else:
                    etd = tstamp + (int(estimate['minutes']) * 60)
                    color = estimate['color']
                etds.append((etd, color))
    etds.sort(key=lambda x: x[0])
    if len(ETD_DATA) == 0:
        saw_sorted = sorted(saw, key=lambda x: x[0])
        print(f"saw {saw_sorted}")
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

async def track_bart(station, direction, destinations):
    while True:
        # Retry until data is successfully fetched
        while True:
            data = await fetch_bart_data(station)
            if data:
                harvest_etd(direction, destinations, data)
                break  # Exit the retry loop once data is fetched
            else:
                await asyncio.sleep(1)  # Retry in 1 second if no data

        # Calculate time until the top of the next minute
        now = time.time()
        seconds_until_next_sample = BART_SECS - (now % BART_SECS)
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
    'ORANGE':	(1.0, 0.7, 0.4),
    'YELLOW':	(1.0, 1.0, 0.0),
    'GREEN':	(0.0, 1.0, 0.0),
    'BLUE':	(0.0, 0.0, 1.0),
    'WHITE':	(1.0, 1.0, 1.0),
}

def normalize_rgb(rgb):
    # Find the maximum component in the tuple
    max_value = max(rgb)
    # If the maximum component is greater than 1.0, scale each component
    if max_value > 1.0:
        return tuple(component / max_value for component in rgb)
    else:
        return rgb  # If max_value is 1.0 or less, return as is

def scale_rgb(rgb, factor):
    return tuple(component * factor for component in rgb)

def rgb_to_hex(rgb, gamma_r=2.4, gamma_g=2.0, gamma_b=1.6):
    r, g, b = (max(0.0, min(1.0, component)) for component in rgb)
    # Apply gamma correction to each component
    r_corrected = int((r ** gamma_r) * 255)
    g_corrected = int((g ** gamma_g) * 255)
    b_corrected = int((b ** gamma_b) * 255)
    return f"{r_corrected:02X}{g_corrected:02X}{b_corrected:02X}"

def pattern_segment(seq):
    ndx = int(seq/20)
    colors = list(COLOR_MAP.keys())
    color = colors[ndx % len(colors)]
    rgb = COLOR_MAP[color]
    ndx = 0
    factor = 0.0
    seg = []
    while factor <= 1.0:
        seg.append(ndx)
        seg.append(rgb_to_hex(normalize_rgb(scale_rgb(rgb, factor))))
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
            rgb_to_hex(normalize_rgb(rgb_array[index]))
        )
    ]
    return seg

async def update_display(wled, pattern):
    seq = 0
    while True:
        if pattern:
            seg_array = pattern_segment(seq)
        else:
            seg_array = bart_segment(seq)
        await wled.segment(0, individual=seg_array)
        await asyncio.sleep(0.01)
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

async def main() -> None:
    """Show example on controlling your WLED device."""
    parser = argparse.ArgumentParser(description="Process BART station and destinations.")
    add_args(parser)
    args = parser.parse_args()

    # Access the arguments
    station = args.station
    direction = args.direction
    destinations = args.destination if args.destination else []  # Default to an empty list if None

    if args.no_wled:
        tracker = asyncio.create_task(
            print_exception(track_bart(station, direction, destinations)))
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

            if args.pattern:
                tracker = None
            else:
            	# Start the BART tracker
                tracker = asyncio.create_task(
                    print_exception(track_bart(station, direction, destinations)))

            # Start the display updates
            display = asyncio.create_task(print_exception(update_display(wled, args.pattern)))

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
        "-p", "--pattern",
        action="store_true",
        help="Display a test pattern"
    )

if __name__ == "__main__":
    asyncio.run(main())
