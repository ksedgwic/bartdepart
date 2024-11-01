import argparse
import asyncio
import httpx
import math
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
BART_PHASE = 10  # seconds past the minute target

ETD_DATA = deque(maxlen=BART_NGHOST)
GHOST_WEIGHT = [1.0, 0.3, 0.1, 0.1]

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

# Given a ghost index, current index, and a train tuple return the index of a match or None
def find_tndx(gndx, cndx, train):
        etd, color = train
        if gndx >= len(ETD_DATA) or gndx < -len(ETD_DATA):
            # print(gndx, train, "OUT-OF-RANGE")
            return None
        ghost = ETD_DATA[gndx]
        for tndx, (getd, gcolor) in enumerate(ETD_DATA[gndx]['etds']):
            if gcolor == color and abs(getd - etd) < 120:
                # print(gndx, train, tndx)
                return tndx
        # print(gndx, train, "NOT-FOUND")
        return None

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
    ETD_DATA.append({ 'tstamp': tstamp, 'etds': etds })

    # First time through only
    if len(ETD_DATA) == 1:
        present_sorted = sorted(present, key=lambda x: x[0])
        showing_sorted = sorted(showing, key=lambda x: x[0])
        print(f"present {present_sorted}")
        print(f"showing {showing_sorted}")

    formatted_now = time.strftime("%H:%M:%S", time.localtime(now))
    print(f"{formatted_now}: lag {lag:>2}:", end="")
    prev_time = now
    for i, (etd, color) in enumerate(etds):
        # What was our etd in the previous ghost (maybe don't have one)
        prev_etd = None
        prev_tndx = find_tndx(-2, -1, (etd, color))
        if prev_tndx is not None:
            prev_etd = ETD_DATA[-2]['etds'][prev_tndx][0]

        # Are we speeding up or slowing down?
        faster = False
        slower = False
        tolerance = 30
        if prev_etd and etd > prev_etd + tolerance:
            slower = True
        if prev_etd and etd < prev_etd - tolerance:
            faster = True

        delta = int((etd - prev_time) / 60)
        etd_formatted = time.strftime("%H:%M:%S", time.localtime(etd))
        if slower:
            print(f" +{delta} ({pale_red(etd_formatted)}:{color})", end="")
        elif faster:
            print(f" +{delta} ({pale_green(etd_formatted)}:{color})", end="")
        else:
            print(f" +{delta} ({etd_formatted}:{color})", end="")
        prev_time = etd
    print()

def pale_yellow(text):
    # Use RGB values for pale yellow (e.g., RGB(255, 255, 204))
    return f"\033[48;2;255;255;204m{text}\033[0m"

def pale_red(text):
    # Use RGB values for pale red (e.g., RGB(255, 204, 204))
    return f"\033[48;2;255;204;204m{text}\033[0m"

def pale_green(text):
    # Use RGB values for pale green (e.g., RGB(204, 255, 204))
    return f"\033[48;2;204;255;204m{text}\033[0m"

async def track_bart(station, *, direction=None, platform=None, destinations=None):
    while True:
        # Retry until data is successfully fetched
        while True:
            data = await fetch_bart_data(station)
            if data:
                harvest_etd(direction, platform, destinations, data)
                break  # Exit the retry loop once data is fetched
            else:
                await asyncio.sleep(1)  # Retry in 1 second if no data

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
    'ORANGE':	(1.0, 0.4, 0.0),
    'YELLOW':	(1.0, 1.0, 0.0),
    'GREEN':	(0.0, 1.0, 0.0),
    'BLUE':	(0.0, 0.0, 1.0),
    'WHITE':	(1.0, 1.0, 1.0),
}

def scale_rgb(rgb, factor):
    return tuple(component * factor for component in rgb)

import math

def throbbing_brightness(seq, max_brightness=1.0, steps=64):
     # Use sin to create a smooth wave that starts at 0, goes up to max, then back to 0
    # `steps` defines the length of one full brightness cycle
    angle = (seq % steps) * (math.pi / (steps / 2))
    brightness = max_brightness * (math.sin(angle) ** 2)  # Square to smooth out peaks
    return brightness

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
def compensate(rgb, offset=0.15):
    return tuple(offset + c * (1.0 - offset) for c in rgb)

def rgb_to_hex(rgb):
    r, g, b = (int(c * 255) for c in rgb)
    return f"{r:02X}{g:02X}{b:02X}"

def process_rgb(seq, rgb):
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
        seg.append(process_rgb(seq, scale_rgb(rgb, factor)))
        ndx += 1
        factor += 1 / 15
    return seg

def bart_segment(seq):
    global ETD_DATA
    now = time.time()
    rgb_array = [(0.0, 0.0, 0.0) for _ in range(WLED_NLEDS)]
    # iterate from most recent to oldest
    for ndx, ghost in enumerate(reversed(ETD_DATA)):
        # ndx 0 is most recent, ghost_index is reversed
        ghost_index = len(ETD_DATA) - 1 - ndx
        for tndx, etd in enumerate(ghost['etds']):
            delta = int(etd[0] - now)
            if delta < 0:
                continue
            index = delta / 60
            int_index = int(index)
            frac_index = index - int_index
            if 0 <= int_index < WLED_NLEDS:
                r, g, b = scale_rgb(COLOR_MAP[etd[1]], WLED_BRIGHTNESS)

                if ndx == 0:
                    weight = GHOST_WEIGHT[ghost_index]
                else:
                    # Compare this ghost to the most current
                    curr_tndx = find_tndx(-1, ghost_index, etd)
                    if curr_tndx is None:
                        continue

                    # If the etd for ghost is same as current then we are steady contribution
                    if abs(ETD_DATA[-1]['etds'][curr_tndx][0] - \
                           ETD_DATA[ghost_index]['etds'][tndx][0]) < 30:
                        weight = GHOST_WEIGHT[ghost_index]
                    else:
                        weight = GHOST_WEIGHT[ghost_index] * throbbing_brightness(seq)

                # Full value if index is exactly an integer
                if frac_index == 0:
                    rgb_array[int_index] = (
                        rgb_array[int_index][0] + r * weight,
                        rgb_array[int_index][1] + g * weight,
                        rgb_array[int_index][2] + b * weight,
                    )
                else:
                    # Distribute based on fractional part
                    lower_weight = (1.0 - frac_index) * weight
                    upper_weight = frac_index * weight

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
                process_rgb(seq, rgb_array[index])
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

if __name__ == "__main__":
    asyncio.run(main())
